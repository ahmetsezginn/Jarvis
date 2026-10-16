"""Production Brain: one capability-driven agent runtime, no intent-classifier fallback."""

from __future__ import annotations

from dataclasses import replace

from jarvis_brain import config
from jarvis_brain.errors import IntentValidationError, JarvisBrainError, ModelOutputInvalid
from jarvis_brain.intelligence.agent.registry import CapabilityRegistry
from jarvis_brain.intelligence.agent.runner import AgentRuntime
from jarvis_brain.intelligence.contract import IntentContext
from jarvis_brain.intelligence.models.base import AgentModel
from jarvis_brain.intelligence.orchestrator import CoreToolClient


class JarvisBrain:
    def __init__(
        self,
        core: CoreToolClient,
        model: AgentModel,
        *,
        capabilities: CapabilityRegistry | None = None,
        minimum_confidence: float = config.MIN_INTENT_CONFIDENCE,
        context: IntentContext | None = None,
        fast_router_enabled: bool = False,
    ):
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self._model = model
        self._core = core
        self._context = context or IntentContext()
        self._fast_router_enabled = fast_router_enabled  # Read-only predict diagnostics only.
        self._agent = AgentRuntime(
            core,
            model,
            registry=capabilities,
            minimum_confidence=minimum_confidence,
            context=self._context,
        )
        self._files = self._agent.files
        self._conversation = self._agent.memory

    def reset_context(self):
        self._agent.reset()

    def handle_text(self, text, *, force_model=False):
        clean = validate_input(text)
        if not all(
            callable(getattr(self._model, name, None))
            for name in ("load", "next_step", "authorize_action")
        ):
            raise ModelOutputInvalid(
                "provider must implement AgentModel; legacy fallback is disabled"
            )
        try:
            return self._agent.handle(clean)
        except JarvisBrainError:
            self._agent.reset()
            raise

    def _model_context(self, text=""):
        return replace(
            self._context,
            history=self._conversation.snapshot(),
            file_candidates=self._files.model_candidates(),
        )

    def predict_intent(self, text, *, force_model=False, context=None):
        # Explicit diagnostic API only: never used by handle_text or by recovery.
        from jarvis_brain.intelligence.legacy_runtime import LegacyBrain

        diagnostic = LegacyBrain(
            self._core, self._model, fast_router_enabled=self._fast_router_enabled
        )
        return diagnostic.predict_intent(
            validate_input(text),
            force_model=force_model,
            context=context or self._model_context(text),
        )


def validate_input(text):
    if not isinstance(text, str):
        raise IntentValidationError("input must be text")
    clean = text.strip()
    if not clean or len(clean) > config.MAX_INPUT_CHARS:
        raise IntentValidationError("input must be nonempty bounded text")
    if any(ord(c) < 32 and c not in "\t\r\n" for c in clean):
        raise IntentValidationError("input contains control characters")
    return clean
