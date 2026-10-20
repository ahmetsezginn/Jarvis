"""Provider boundaries: production AgentModel and archived intent diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from jarvis_brain.intelligence.contract import IntentContext, IntentResult
from jarvis_brain.intelligence.dialogue import TurnPlan
from jarvis_brain.intelligence.request_routing import RequestRoute


class ModelState(StrEnum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


class IntentModel(Protocol):
    @property
    def state(self) -> ModelState: ...

    def load(self) -> None: ...

    def unload(self) -> None: ...

    def predict(self, text: str, context: IntentContext) -> IntentResult: ...

    def classify_request(self, text: str, context: IntentContext) -> RequestRoute: ...

    def respond(self, text: str, context: IntentContext) -> str: ...


class DialogueModel(IntentModel, Protocol):
    """Optional stateful planning capability; legacy providers keep IntentModel."""

    def plan_turn(self, text: str, context: IntentContext, state: dict) -> TurnPlan: ...

    def opening_requested(self, text: str, context: IntentContext) -> bool: ...


class AgentModel(Protocol):
    """Provider-neutral contextual decision plus current-effect safety assessment."""

    def load(self) -> None: ...

    def unload(self) -> None: ...

    def next_step(
        self, snapshot: dict, tools: list[dict], schema: dict, context: IntentContext | None = None
    ) -> str: ...

    def authorize_action(
        self, text: str, effect: dict, context: IntentContext | None = None
    ) -> bool | EffectAssessment: ...


class AnswerReviewModel(Protocol):
    """Optional semantic check for a registered, parameterless action omitted by a reply."""

    def assess_omitted_action(
        self, text: str, effect: dict, context: IntentContext | None = None
    ) -> bool | EffectAssessment: ...


@dataclass(frozen=True)
class EffectAssessment:
    """Bounded requested-outcome description and judgment; never a plan or permission token."""

    authorized: bool
    requested_outcome: str
    veto_reason: str = ""

    def __bool__(self):
        return self.authorized
