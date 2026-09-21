"""Bounded, in-memory clarification state; never model-generated trusted identifiers."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from jarvis_brain.errors import IntentValidationError
from jarvis_brain.intelligence.contract import BrainResponse, IntentName, validate_intent_object
from jarvis_brain.intelligence.orchestrator import IntentOrchestrator


def normalize(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip(".!?")


@dataclass(frozen=True)
class Candidate:
    name: str
    app_id: str


class SelectionSession:
    """One displayed list, at most ten candidates, expires after two minutes."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._candidates: tuple[Candidate, ...] = ()
        self._expires = 0.0

    def clear(self) -> None:
        self._candidates = ()

    def observe(self, response: BrainResponse) -> BrainResponse:
        self.clear()
        if response.intent is not IntentName.CLARIFY or not isinstance(response.data, dict):
            return response
        values = response.data.get("candidates")
        if not isinstance(values, list) or not 2 <= len(values) <= 10:
            return response
        candidates = []
        for value in values:
            if not isinstance(value, dict):
                return response
            name, app_id = value.get("name"), value.get("app_id")
            if not isinstance(app_id, str) or not 1 <= len(app_id) <= 128:
                return response
            try:
                result = validate_intent_object(
                    {"intent": "open_application", "confidence": 1, "arguments": {"query": name}},
                    model_output=False,
                )
            except IntentValidationError:
                return response
            candidates.append(Candidate(str(result.arguments["query"]), app_id))
        if len({c.app_id for c in candidates}) != len(candidates):
            return response
        self._candidates = tuple(candidates)
        self._expires = self._clock() + 120
        listing = "\n".join(f"{i}. {c.name}" for i, c in enumerate(candidates, 1))
        return replace(
            response, message=f"Hangisini açayım? Numara veya ad seçebilirsin:\n{listing}"
        )

    def handle(self, text: str, orchestrator: IntentOrchestrator) -> BrainResponse | None:
        if self._clock() >= self._expires:
            self.clear()
        value = normalize(text)
        if value in {"iptal", "vazgeç", "vazgec", "boşver", "bosver", "cancel"}:
            self.clear()
            return self._clarify("Bekleyen seçim iptal edildi.")
        ordinals = {
            "üstteki": 0,
            "ustteki": 0,
            "ilk": 0,
            "ilki": 0,
            "birinci": 0,
            "birincisi": 0,
            "first": 0,
            "ikinci": 1,
            "ikincisi": 1,
            "second": 1,
            "üçüncü": 2,
            "ucuncu": 2,
            "üçüncüsü": 2,
            "third": 2,
            "alttaki": -1,
            "sonuncu": -1,
            "last": -1,
        }
        choice = re.sub(r"\s+(?:olanı|olani|aç|ac|açar mısın|acar misin)$", "", value)
        index = ordinals.get(choice)
        numeric = re.fullmatch(r"([0-9]{1,3})(?:\.? seçenek|\.? secenek)?", choice)
        if numeric:
            index = int(numeric[1]) - 1
            if index < 0:
                return self._clarify("Geçerli bir seçenek numarası belirtir misin?")
        relative = choice in {"diğeri", "digeri", "öteki", "oteki", "hayır diğeri", "other"}
        if index is not None or relative:
            if not self._candidates:
                return self._clarify(
                    "Bekleyen seçenek yok veya süresi doldu; uygulama adını belirt."
                )
            if relative:
                # Without a previously selected referent, 'other' is not necessarily item 2.
                return self._clarify("Hangisini kastettin? Seçenek numarasını veya adını söyle.")
            if index is None or not -len(self._candidates) <= index < len(self._candidates):
                return self._clarify("Bu numarada seçenek yok; listedeki numaralardan birini seç.")
            selected = self._candidates[index]
        else:
            matches = [c for c in self._candidates if normalize(c.name) == value]
            if len(matches) != 1:
                self.clear()  # A different request must not inherit an old selection.
                return None
            selected = matches[0]
        self.clear()  # Consume before any IPC: errors must not retain an executable selection.
        return self.observe(orchestrator.open_selected(selected.name, selected.app_id))

    @staticmethod
    def _clarify(message: str) -> BrainResponse:
        return BrainResponse(IntentName.CLARIFY, 1.0, "session", False, message)
