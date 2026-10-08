"""Model-neutral interface for local intent inference."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from jarvis_brain.intelligence.contract import IntentContext, IntentResult
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
