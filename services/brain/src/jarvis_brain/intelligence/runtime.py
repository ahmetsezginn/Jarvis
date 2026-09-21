"""Local intent pipeline; it has no direct operating-system action path."""

from __future__ import annotations

from jarvis_brain import config
from jarvis_brain.errors import IntentValidationError
from jarvis_brain.intelligence.contract import (
    BrainResponse,
    IntentContext,
    IntentName,
    IntentResult,
    validate_intent_object,
)
from jarvis_brain.intelligence.fast_router import FastIntentRouter
from jarvis_brain.intelligence.models.base import IntentModel
from jarvis_brain.intelligence.orchestrator import CoreToolClient, IntentOrchestrator
from jarvis_brain.intelligence.session import SelectionSession


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
        self._context = context or IntentContext(
            max_context_tokens=config.MAX_CONTEXT_TOKENS,
            max_generated_tokens=config.MAX_GENERATED_TOKENS,
        )

    def handle_text(self, text: str, *, force_model: bool = False) -> BrainResponse:
        clean_text = _validate_input(text)
        followup = self._session.handle(clean_text, self._orchestrator)
        if followup is not None:
            return followup
        result, route = self.predict_intent(text, force_model=force_model)
        if result.intent in {IntentName.OPEN_APPLICATION, IntentName.SYSTEM_STATUS}:
            if result.confidence < self._minimum_confidence:
                return BrainResponse(
                    intent=IntentName.CLARIFY,
                    confidence=result.confidence,
                    route=route,
                    executed=False,
                    message="İsteği güvenle anlayamadım; lütfen daha açık ifade et.",
                )
        return self._session.observe(self._orchestrator.execute(result, route=route))

    def predict_intent(self, text: str, *, force_model: bool = False) -> tuple[IntentResult, str]:
        clean_text = _validate_input(text)
        if self._fast_router_enabled and not force_model:
            fast_result = self._router.route(clean_text)
            if fast_result is not None:
                return _revalidate(fast_result), "fast"
        self._model.load()
        return _revalidate(self._model.predict(clean_text, self._context)), "model"


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
