"""Local intent pipeline; it has no direct operating-system action path."""

from __future__ import annotations

from dataclasses import replace

from jarvis_brain import config
from jarvis_brain.errors import IntentValidationError, JarvisBrainError
from jarvis_brain.intelligence.catalog_session import CatalogRecovery
from jarvis_brain.intelligence.contract import (
    BrainResponse,
    IntentContext,
    IntentName,
    IntentResult,
    validate_intent_object,
)
from jarvis_brain.intelligence.conversation import ConversationMemory
from jarvis_brain.intelligence.fast_router import FastIntentRouter
from jarvis_brain.intelligence.models.base import IntentModel
from jarvis_brain.intelligence.orchestrator import CoreToolClient, IntentOrchestrator
from jarvis_brain.intelligence.request_routing import (
    RequestKind,
    validate_reply,
    validate_route,
)
from jarvis_brain.intelligence.session import SelectionSession, normalize


class JarvisBrain:
    def __init__(
        self,
        core: CoreToolClient,
        model: IntentModel,
        *,
        router: FastIntentRouter | None = None,
        fast_router_enabled: bool = True,
        minimum_confidence: float = config.MIN_INTENT_CONFIDENCE,
        context: IntentContext | None = None,
        session: SelectionSession | None = None,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self._model = model
        self._router = router or FastIntentRouter()
        self._fast_router_enabled = fast_router_enabled
        self._orchestrator = IntentOrchestrator(core)
        self._minimum_confidence = minimum_confidence
        self._session = session or SelectionSession()
        self._conversation = ConversationMemory()
        self._catalog_recovery = CatalogRecovery()
        self._context = context or IntentContext(
            max_context_tokens=config.MAX_CONTEXT_TOKENS,
            max_generated_tokens=config.MAX_GENERATED_TOKENS,
        )

    def reset_context(self) -> None:
        self._conversation.clear()
        self._session.clear()
        self._catalog_recovery.clear()

    def handle_text(self, text: str, *, force_model: bool = False) -> BrainResponse:
        clean_text = _validate_input(text)
        if clean_text.casefold() == "/reset":
            self.reset_context()
            return BrainResponse(
                IntentName.CLARIFY, 1.0, "session", False, "Konuşma bağlamı temizlendi."
            )
        if clean_text.casefold() in {"iptal", "vazgeç", "vazgec", "boşver", "bosver", "cancel"}:
            self._conversation.clear()
            self._catalog_recovery.clear()
        refresh, retry_query = self._catalog_recovery.consume(clean_text)
        if refresh:
            self._session.clear()
            self._orchestrator.refresh_catalog()
            if retry_query is None:
                response = BrainResponse(
                    IntentName.CLARIFY, 1.0, "catalog_session", True, "Uygulama kataloğu yenilendi."
                )
            else:
                response = self._session.observe(
                    self._orchestrator.execute(
                        _revalidate(
                            IntentResult(IntentName.OPEN_APPLICATION, 1.0, {"query": retry_query})
                        ),
                        route="catalog_session",
                    )
                )
                response = replace(response, message="Katalog yenilendi. " + response.message)
            return self._conversation.observe(clean_text, response)
        pending = self._session.pending_candidates()
        followup = self._session.handle(clean_text, self._orchestrator)
        if followup is not None:
            return self._conversation.observe(clean_text, followup)
        context = replace(self._context, history=self._conversation.snapshot())
        self._model.load()
        decision = validate_route(self._model.classify_request(clean_text, context))
        if decision.kind is RequestKind.TASK and decision.confidence < self._minimum_confidence:
            return self._conversation.observe(
                clean_text,
                BrainResponse(
                    IntentName.CLARIFY,
                    decision.confidence,
                    "request_router",
                    False,
                    "Do you want me to perform an action, or are you asking a question?",
                ),
            )
        if decision.kind is RequestKind.CONVERSATION:
            # Deliberately return before touching task prediction, Fast Router or orchestrator.
            message = validate_reply(self._model.respond(clean_text, context))
            return self._conversation.observe(
                clean_text,
                BrainResponse(
                    IntentName.RESPOND, decision.confidence, "conversation", False, message
                ),
            )
        # The broad legacy router cannot distinguish app targets from folders or discussion.
        # It remains available to read-only predict diagnostics, never to this execution path.
        result, route = self.predict_intent(text, force_model=True)
        if result.intent in {IntentName.OPEN_APPLICATION, IntentName.SYSTEM_STATUS}:
            if result.confidence < self._minimum_confidence:
                return self._conversation.observe(
                    clean_text,
                    BrainResponse(
                        intent=IntentName.CLARIFY,
                        confidence=result.confidence,
                        route=route,
                        executed=False,
                        message="İsteği güvenle anlayamadım; lütfen daha açık ifade et.",
                    ),
                )
        try:
            matching = [
                candidate
                for candidate in pending
                if result.intent is IntentName.OPEN_APPLICATION
                and normalize(candidate.name) == normalize(str(result.arguments["query"]))
            ]
            if len(matching) > 1:
                response = BrainResponse(
                    IntentName.CLARIFY,
                    1,
                    "session",
                    False,
                    "Select a unique displayed candidate by number.",
                )
            elif len(matching) == 1:
                selected = matching[0]
                response = self._session.observe(
                    self._orchestrator.open_selected(selected.name, selected.app_id)
                )
            else:
                response = self._session.observe(self._orchestrator.execute(result, route=route))
        except JarvisBrainError:
            self._conversation.observe(
                clean_text,
                BrainResponse(
                    result.intent,
                    result.confidence,
                    route,
                    False,
                    "Core request failed; execution was not confirmed.",
                ),
            )
            raise
        if (
            result.intent is IntentName.OPEN_APPLICATION
            and response.intent is IntentName.UNSUPPORTED
        ):
            self._catalog_recovery.remember(str(result.arguments["query"]))
        return self._conversation.observe(clean_text, response)

    def predict_intent(self, text: str, *, force_model: bool = False) -> tuple[IntentResult, str]:
        clean_text = _validate_input(text)
        if self._fast_router_enabled and not force_model and not self._conversation.snapshot():
            fast_result = self._router.route(clean_text)
            if fast_result is not None:
                return _revalidate(fast_result), "fast"
        self._model.load()
        return _revalidate(
            self._model.predict(
                clean_text, replace(self._context, history=self._conversation.snapshot())
            )
        ), "model"


def _validate_input(text: str) -> str:
    if not isinstance(text, str):
        raise IntentValidationError("input must be text")
    stripped = text.strip()
    if not stripped:
        raise IntentValidationError("input must not be empty")
    if len(stripped) > config.MAX_INPUT_CHARS:
        raise IntentValidationError(f"input exceeds {config.MAX_INPUT_CHARS} characters")
    if any(ord(character) < 32 and character not in "\t\r\n" for character in stripped):
        raise IntentValidationError("input contains control characters")
    return stripped


def _revalidate(result: IntentResult) -> IntentResult:
    return validate_intent_object(
        {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "arguments": dict(result.arguments),
        },
        model_output=False,
    )
