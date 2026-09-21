"""Deterministic fake used by normal unit tests and benchmarks."""

from __future__ import annotations

from collections.abc import Callable

from jarvis_brain.intelligence.contract import IntentContext, IntentResult
from jarvis_brain.intelligence.models.base import ModelState


class FakeIntentModel:
    def __init__(self, result: IntentResult | Callable[[str], IntentResult]) -> None:
        self._result = result
        self._state = ModelState.UNLOADED
        self.load_count = 0
        self.predict_count = 0

    @property
    def state(self) -> ModelState:
        return self._state

    def load(self) -> None:
        if self._state is ModelState.READY:
            return
        self.load_count += 1
        self._state = ModelState.READY

    def unload(self) -> None:
        self._state = ModelState.UNLOADED

    def predict(self, text: str, _context: IntentContext) -> IntentResult:
        if self._state is not ModelState.READY:
            raise RuntimeError("fake model must be loaded before prediction")
        self.predict_count += 1
        return self._result(text) if callable(self._result) else self._result
