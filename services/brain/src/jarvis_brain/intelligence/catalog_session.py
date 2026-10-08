"""One-shot recovery for an immediately preceding failed application resolution."""

import re
import time
from collections.abc import Callable


def _normalized(text: str) -> str:
    return " ".join(text.casefold().translate(str.maketrans("çğıöşü", "cgiosu")).split()).rstrip(
        ".!?"
    )


def explicit_refresh(text: str) -> bool:
    value = _normalized(text).removeprefix("jarvis ")
    return value in {
        "katalogu yenile",
        "uygulama katalogunu yenile",
        "uygulama listesini yenile",
        "uygulamalari yeniden tara",
        "katalogu guncelle",
        "uygulama listesini guncelle",
        "refresh app catalog",
        "refresh application catalog",
    }


def installed_followup(text: str) -> bool:
    # Whole-turn matching avoids treating quotes, negations or explanations as permission.
    return (
        re.fullmatch(
            r"(?:(?:evet|ben|bunu|onu|uygulamayi) ){0,2}"
            r"(?:daha )?(?:yeni|az once|simdi|demin|biraz once) (?:yukledim|kurdum)"
            r"(?: (?:bunu|onu|zaten))?"
            r"(?:[, ]+(?:tekrar bak|yeniden ara|bir daha dene|tekrar dener misin))?",
            _normalized(text),
        )
        is not None
    )


class CatalogRecovery:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._query: str | None = None
        self._expires = 0.0

    def clear(self) -> None:
        self._query = None

    def remember(self, query: str) -> None:
        self._query = query
        self._expires = self._clock() + 120

    def consume(self, text: str) -> tuple[bool, str | None]:
        query = self._query if self._clock() < self._expires else None
        self.clear()  # Any unrelated turn, expiry, or attempt consumes the pending recovery.
        if explicit_refresh(text):
            return True, query
        if query and installed_followup(text):
            return True, query
        return False, None
