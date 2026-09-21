"""Model-neutral interface for local intent inference."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from jarvis_brain.intelligence.contract import IntentContext, IntentResult


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
