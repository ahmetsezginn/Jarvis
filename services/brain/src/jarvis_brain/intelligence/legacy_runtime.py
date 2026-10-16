"""Archived intent/TurnPlan pipeline for regression and predict diagnostics only."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from jarvis_brain import config
from jarvis_brain.errors import IntentValidationError, JarvisBrainError
from jarvis_brain.intelligence.assistant_session import AssistantSession
from jarvis_brain.intelligence.catalog_session import CatalogRecovery
from jarvis_brain.intelligence.contract import (
    BrainResponse,
    ConversationTurn,
    IntentContext,
    IntentName,
    IntentResult,
    validate_intent_object,
)
from jarvis_brain.intelligence.conversation import ConversationMemory
from jarvis_brain.intelligence.dialogue import parse_turn
from jarvis_brain.intelligence.fast_router import FastIntentRouter
from jarvis_brain.intelligence.file_reference import numbered_reference
from jarvis_brain.intelligence.file_session import FILE_INTENTS, FileSession, negative_open
from jarvis_brain.intelligence.models.base import IntentModel
from jarvis_brain.intelligence.orchestrator import CoreToolClient, IntentOrchestrator
from jarvis_brain.intelligence.request_routing import (
    RequestKind,
    RequestPurpose,
    validate_reply,
    validate_route,
)
from jarvis_brain.intelligence.session import SelectionSession, normalize


class LegacyBrain:
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
        self._files = FileSession(core)
        self._assistant = AssistantSession(self._files)
        self._catalog_recovery = CatalogRecovery()
        self._context = context or IntentContext(
            max_context_tokens=config.MAX_CONTEXT_TOKENS,
            max_generated_tokens=config.MAX_GENERATED_TOKENS,
        )

    def reset_context(self) -> None:
        self._conversation.clear()
        self._files.clear()
        self._session.clear()
        self._catalog_recovery.clear()
        self._assistant.clear()

    def handle_text(self, text: str, *, force_model: bool = False) -> BrainResponse:
        clean_text = _validate_input(text)
        if negative_open(clean_text):
            if clean_text.casefold() in {"iptal", "vazgeç", "vazgec", "cancel"}:
                self._conversation.clear()
            self._assistant.clear()
            self._files.clear()
            self._session.clear()
            self._catalog_recovery.clear()
            return self._conversation.observe(
                clean_text,
                BrainResponse(
                    IntentName.CLARIFY,
                    1,
                    "files",
                    False,
                    "Açma isteği iptal edildi; herhangi bir hedef açılmadı.",
                ),
            )
        if clean_text.casefold() == "/reset":
            self.reset_context()
            return BrainResponse(
                IntentName.CLARIFY, 1.0, "session", False, "Konuşma bağlamı temizlendi."
            )
        if clean_text.casefold() in {"iptal", "vazgeç", "vazgec", "boşver", "bosver", "cancel"}:
            self._conversation.clear()
            self._catalog_recovery.clear()
            if callable(getattr(self._model, "plan_turn", None)):
                self.reset_context()
                return self._assistant.reply("Bekleyen işlem iptal edildi.")
        if callable(getattr(self._model, "plan_turn", None)):
            try:
                return self._handle_assistant(clean_text)
            except JarvisBrainError:
                self._files.clear()
                self._assistant.finish_task()
                self._session.clear()
                self._catalog_recovery.clear()
                raise
        file_followup = self._files.handle(clean_text, preserve_unmatched=True)
        if file_followup is not None:
            self._session.clear()
            self._catalog_recovery.clear()
            return self._conversation.observe(clean_text, file_followup)
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
        context = self._model_context(clean_text)
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
            self._files.clear()
            # Deliberately return before touching task prediction, Fast Router or orchestrator.
            reply_context = replace(self._context, history=self._conversation.snapshot())
            message = validate_reply(self._model.respond(clean_text, reply_context))
            return self._conversation.observe(
                clean_text,
                BrainResponse(
                    IntentName.RESPOND, decision.confidence, "conversation", False, message
                ),
            )
        # The broad legacy router cannot distinguish app targets from folders or discussion.
        # It remains available to read-only predict diagnostics, never to this execution path.
        planning_context = self._model_context(clean_text)
        if decision.purpose is RequestPurpose.LOCATE_FILE:
            # Existing results are not an instruction to select/open. A current locating goal
            # uses the search planner; private page/scope state remains with FileSession.
            planning_context = replace(planning_context, file_candidates=(), locating_file=True)
        result, route = self.predict_intent(text, force_model=True, context=planning_context)
        if decision.purpose is RequestPurpose.LOCATE_FILE and result.intent not in {
            IntentName.SEARCH_FILES,
            IntentName.CLARIFY,
        }:
            return self._conversation.observe(
                clean_text,
                BrainResponse(
                    IntentName.CLARIFY,
                    result.confidence,
                    "goal_guard",
                    False,
                    "Dosyayı bulmana yardımcı olayım. "
                    "Adı veya konusu hakkında başka bir ipucu var mı?",
                ),
            )
        reference = numbered_reference(clean_text)
        if reference is not None:
            # A displayed address cannot fall through into a new filesystem/application query.
            if (
                not self._files.accepts_number(reference)
                or result.intent is not IntentName.SELECT_FILE
                or result.arguments.get("number") != reference
            ):
                return self._conversation.observe(
                    clean_text,
                    BrainResponse(
                        IntentName.CLARIFY,
                        1,
                        "file_reference",
                        False,
                        "Bu mesajı sonuç listesinde seçim olarak anladım; yeni arama yapmadım. "
                        "Geçerli listedeki numarayı seç veya önce dosyaları yeniden bulalım.",
                    ),
                )
        if result.intent in {IntentName.OPEN_APPLICATION, IntentName.SYSTEM_STATUS} | FILE_INTENTS:
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
        if result.intent in FILE_INTENTS:
            self._session.clear()
            return self._conversation.observe(clean_text, self._files.execute(result, clean_text))
        if result.intent is not IntentName.CLARIFY:
            self._files.clear()
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

    def _handle_assistant(self, text):
        if self._session.pending_candidates() and not self._files.model_candidates():
            response = self._session.handle(text, self._orchestrator)
            if response is not None:
                return self._conversation.observe(text, response)
        reference = numbered_reference(text)
        if reference is not None and not self._files.accepts_number(reference):
            return self._conversation.observe(
                text,
                self._assistant.ask(
                    "Bu numara için geçerli bir sonuç yok; önce dosyaları bulalım."
                ),
            )
        # A bare page number is the explicit selection notation offered by the UI, already
        # supported by FileSession. It has no filename-search fallback and never guesses IDs.
        if re.fullmatch(r"[0-9]{1,2}[.)]?", text):
            number = int(text.rstrip(".)"))
            if not self._files.accepts_number(number):
                return self._conversation.observe(
                    text,
                    self._assistant.ask(
                        "Bu numara için geçerli bir sonuç yok; önce dosyaları bulalım."
                    ),
                )
            response = self._files.select_displayed(
                IntentResult(
                    IntentName.SELECT_FILE,
                    1,
                    {
                        "number": number,
                        "action": "open",
                        "application": "",
                    },
                )
            )
            self._assistant.record_outcome(response, "Seçili öğeyi açma")
            self._assistant.finish_task()
            return self._conversation.observe(text, response)
        if self._files._confirmation and normalize(text) in {"evet", "aynen", "tamam", "yes"}:
            response = self._files.handle(text, preserve_unmatched=True)
            if response is not None:
                self._assistant.record_outcome(response, "Seçili dosyayı açma")
                return self._conversation.observe(text, response)
        # A changed request cannot confirm an earlier opening on a later bare 'yes'.
        if self._files._confirmation:
            self._files._confirmation = None
            self._files._application = None
        refresh, retry = self._catalog_recovery.consume(text)
        if refresh:
            self._orchestrator.refresh_catalog()
            if retry:
                result = IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": retry})
                response = self._session.observe(
                    self._orchestrator.execute(result, route="catalog_session")
                )
            else:
                response = self._assistant.reply("Uygulama kataloğu yenilendi.", True)
            return self._conversation.observe(text, response)
        self._model.load()
        context = self._model_context(text)
        state = self._assistant.view()
        proposed = self._model.plan_turn(text, context, state)
        plan = parse_turn(
            json.dumps(
                {
                    "move": proposed.move,
                    "confidence": proposed.confidence,
                    "arguments": proposed.arguments,
                }
            )
        )
        opening_check = getattr(self._model, "opening_requested", None)
        if callable(opening_check) and (
            (plan.move == "select" and plan.arguments["action"] in {"open", "parent"})
            or (plan.move == "file" and plan.arguments["operation"] == "open")
            or plan.move == "app"
        ):
            if not opening_check(text, context):
                if plan.move == "select":
                    plan.arguments["action"] = "show"
                elif plan.move == "file":
                    plan.arguments["operation"] = "find"
                else:
                    reply = validate_reply(self._model.respond(text, context))
                    return self._conversation.observe(
                        text, BrainResponse(IntentName.RESPOND, 1, "conversation", False, reply)
                    )
        # A result address cannot be turned into a fresh query by a faulty model.
        reference = numbered_reference(text)
        if reference is not None and (
            plan.move != "select" or plan.arguments.get("number") != reference
        ):
            response = self._assistant.ask(
                "Geçerli listedeki numarayı seç veya önce dosyayı bulalım."
            )
        elif plan.move == "cancel":
            self._assistant.clear()
            self._files.clear()
            self._session.clear()
            response = self._assistant.reply("Bekleyen işlem iptal edildi.")
        elif plan.move == "explain":
            response = self._assistant.explain()
        elif plan.move == "unsupported" or (
            plan.move == "file" and plan.arguments["operation"] == "unsupported"
        ):
            self._files.clear()
            self._assistant.finish_task()
            response = self._assistant.reply(
                "Dosya ve klasör arayabilir, listeleyebilir ve açabilirim. "
                "İçerik okuma, değiştirme veya dosya yükleme henüz desteklenmiyor."
            )
        elif plan.move == "talk":
            reply_context = replace(
                context,
                history=self._conversation.snapshot()[-3:],
                pending_file_question=state.get("pending_question", ""),
            )
            reply = validate_reply(self._model.respond(text, reply_context))
            # Discussing the results is part of assistance. A reply neither consumes
            # the current page nor renews its lifetime, and grants no action permission.
            response = BrainResponse(
                IntentName.RESPOND, plan.confidence, "conversation", False, reply
            )
        elif plan.move == "clarify":
            response = self._assistant.ask(plan.arguments["question"])
        elif plan.confidence < self._minimum_confidence:
            response = self._assistant.ask(
                "Dosyayı mı arıyoruz, yoksa önceki sonuç hakkında mı "
                "konuşuyoruz? Nasıl ilerlememi istersin?"
            )
        elif plan.move == "file":
            response = self._assistant.file_turn(plan, text)
        elif plan.move == "select":
            response = self._assistant.select(plan, text)
        elif plan.move == "next":
            response = self._files.handle("sonraki sayfa", preserve_unmatched=True)
            if response is None:
                response = self._assistant.ask("Devam edilecek sonuç sayfası yok; neyi arayalım?")
        elif plan.move in {"inventory", "refresh"}:
            if plan.move == "refresh":
                self._assistant.finish_task()
            name = (
                IntentName.FILE_CATALOG_STATUS
                if plan.move == "inventory"
                else IntentName.REFRESH_FILE_CATALOG
            )
            response = self._files.execute(IntentResult(name, 1, {}), text)
            self._assistant.record_outcome(response, "Dosya kataloğu sorgusu")
        else:
            self._files.clear()
            self._assistant.finish_task()
            intent = IntentName.OPEN_APPLICATION if plan.move == "app" else IntentName.SYSTEM_STATUS
            if plan.move == "app" and not plan.arguments["query"]:
                return self._conversation.observe(
                    text, self._assistant.ask("Hangi uygulamayı açayım?")
                )
            if plan.move == "app" and normalize(plan.arguments["query"]) in {
                "uygulama",
                "uygulamalar",
                "program",
                "programlar",
                "app",
                "apps",
                "application",
                "applications",
            }:
                # A capability category is an incomplete parameter, not a concrete app name.
                return self._conversation.observe(
                    text,
                    BrainResponse(
                        IntentName.RESPOND,
                        plan.confidence,
                        "conversation",
                        False,
                        "Uygulamaları açabilirim. Hangi uygulamayı açmamı istersin?",
                    ),
                )
            result = _revalidate(IntentResult(intent, plan.confidence, plan.arguments))
            if intent is IntentName.OPEN_APPLICATION and self._session.pending_candidates():
                response = self._session.handle(text, self._orchestrator)
            else:
                response = None
            if response is None:
                response = self._session.observe(self._orchestrator.execute(result, route="model"))
            if intent is IntentName.OPEN_APPLICATION and response.intent is IntentName.UNSUPPORTED:
                self._catalog_recovery.remember(str(result.arguments["query"]))
            self._assistant.record_outcome(response, "Uygulama veya sistem işlemi")
        return self._conversation.observe(text, response)

    def _model_context(self, text: str = "") -> IntentContext:
        candidates = self._files.model_candidates()
        history = self._conversation.planning_snapshot()
        if candidates:
            history = history[-2:]
            # Planning uses user references and metadata, never free-form capability claims.
            history = tuple(ConversationTurn(t.user, "") for t in history)
            while sum(len(t.user) + len(t.assistant) for t in history) > 700:
                history = history[1:]
        if self._files.is_relative(text):
            candidates = ()  # Searching inside a folder is not selecting that folder again.
        reference = numbered_reference(text)
        # Keep invalid numeric references bounded; the execution guard checks the original number.
        if reference is not None:
            reference = min(999, max(0, reference))
        return replace(
            self._context,
            history=history,
            file_candidates=candidates,
            requested_file_number=reference,
        )

    def predict_intent(
        self,
        text: str,
        *,
        force_model: bool = False,
        context: IntentContext | None = None,
    ) -> tuple[IntentResult, str]:
        clean_text = _validate_input(text)
        if self._fast_router_enabled and not force_model and not self._conversation.snapshot():
            fast_result = self._router.route(clean_text)
            if fast_result is not None:
                return _revalidate(fast_result), "fast"
        self._model.load()
        return _revalidate(
            self._model.predict(clean_text, context or self._model_context(clean_text))
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
