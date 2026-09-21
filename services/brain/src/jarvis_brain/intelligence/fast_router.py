"""Deliberately small deterministic router for obvious low-latency commands."""

from __future__ import annotations

import re
import unicodedata

from jarvis_brain.intelligence.contract import (
    IntentName,
    IntentResult,
    contains_unsafe_application_query,
)

_STATUS_PHRASES = {
    "system status",
    "show system status",
    "how is my computer doing",
    "bilgisayar durumunu goster",
    "bilgisayarim nasil durumda",
    "sistem durumu",
    "sistem durumunu goster",
}
_ENGLISH_OPEN = re.compile(
    r"^(?:open|launch|start)\s+(?:the\s+)?(.+?)(?:\s+app(?:lication)?)?[.!?]?$",
    re.I,
)
_TURKISH_OPEN = re.compile(
    r"^(?:bana\s+)?(.+?)(?:\s+(?:uygulamas[ıi]n[ıi]|oyununu))?"
    r"(?:(?:['’]|\s)(?:y[ıiuü]|[ıiuü]))?\s+"
    r"(?:(?:aç|ac)(?:ar|er|abilir)?|(?:başlat|baslat))"
    r"(?:\s+m[ıiuü]?s[ıiuü]+n)?(?:\s+lütfen|\s+lutfen)?(?:\s+peki)?[.!?]?$",
    re.I,
)
_MULTI_ACTION = re.compile(r"(?i)\b(?:and then|then|ve sonra|ve)\b")
_PROMPT_ATTACK = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?instructions|\bapp_id\b|\brun_shell\b|skip\s+resolve_app)"
)
_MISSING_TARGETS = {
    "it",
    "something",
    "anything",
    "bir sey",
    "bir şey",
    "bunu",
    "sunu",
    "şunu",
    "uygulama",
}


class FastIntentRouter:
    def route(self, text: str) -> IntentResult | None:
        normalized = _normalize(text)
        if normalized in _STATUS_PHRASES:
            return IntentResult(IntentName.SYSTEM_STATUS, 1.0, {})

        if (
            contains_unsafe_application_query(text)
            or _MULTI_ACTION.search(text)
            or _PROMPT_ATTACK.search(text)
        ):
            return IntentResult(IntentName.UNSUPPORTED, 1.0, {})

        match = _ENGLISH_OPEN.fullmatch(text.strip()) or _TURKISH_OPEN.fullmatch(text.strip())
        if match is None:
            return None
        query = _clean_application_query(match.group(1))
        if not query or contains_unsafe_application_query(query):
            return IntentResult(IntentName.UNSUPPORTED, 1.0, {})
        if _normalize(query) in _MISSING_TARGETS:
            return IntentResult(
                IntentName.CLARIFY,
                1.0,
                {"question": "Hangi uygulamayı açmamı istiyorsun?"},
            )
        return IntentResult(IntentName.OPEN_APPLICATION, 1.0, {"query": query})


def _normalize(value: str) -> str:
    value = value.strip().casefold().rstrip(".!?")
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    without_marks = without_marks.replace("ı", "i")
    return " ".join(without_marks.split())


def _clean_application_query(value: str) -> str:
    query = " ".join(value.strip().strip("'\".,!?").split())
    return re.sub(r"(?i)^(?:please|lütfen|lutfen)\s+", "", query).strip()
