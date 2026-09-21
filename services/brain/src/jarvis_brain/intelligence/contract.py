"""Closed semantic contract between untrusted language output and orchestration."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from jarvis_brain.errors import IntentValidationError, ModelOutputInvalid

MAX_ARGUMENT_CHARS = 256
_WINDOWS_PATH = re.compile(r"(?i)(?:[a-z]:\\|\\\\)[^\r\n]*")
_EXECUTABLE_SUFFIX = re.compile(r"(?i)\.(?:exe|com|bat|cmd|ps1|msi)(?:\s|$)")
_SHELL_SYNTAX = re.compile(r"(?:&&|\|\||[|;&`]|\$\(|>\s*[^=])")
_FORBIDDEN_APP_TERMS = re.compile(
    r"(?i)\b(?:cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?|run_shell|whoami)\b"
)


class IntentName(StrEnum):
    OPEN_APPLICATION = "open_application"
    SYSTEM_STATUS = "system_status"
    CLARIFY = "clarify"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class IntentContext:
    max_context_tokens: int = 2048
    max_generated_tokens: int = 128

    def __post_init__(self) -> None:
        if not 1 <= self.max_context_tokens <= 2048:
            raise ValueError("max_context_tokens must be between 1 and 2048")
        if not 1 <= self.max_generated_tokens <= 128:
            raise ValueError("max_generated_tokens must be between 1 and 128")


@dataclass(frozen=True)
class IntentResult:
    intent: IntentName
    confidence: float
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class BrainResponse:
    intent: IntentName
    confidence: float
    route: str
    executed: bool
    message: str
    data: Any = None


def validate_intent_object(value: Any, *, model_output: bool) -> IntentResult:
    """Validate exact keys, types, and the per-intent argument schema."""

    error_type = ModelOutputInvalid if model_output else IntentValidationError
    if not isinstance(value, dict):
        raise error_type("intent result must be a JSON object")
    if set(value) != {"intent", "confidence", "arguments"}:
        raise error_type("intent result must contain only intent, confidence, and arguments")

    raw_intent = value["intent"]
    try:
        intent = IntentName(raw_intent)
    except (TypeError, ValueError) as error:
        raise error_type("intent is not in the supported semantic enum") from error

    confidence = value["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise error_type("confidence must be a number")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise error_type("confidence must be finite and between 0 and 1")

    arguments = value["arguments"]
    if not isinstance(arguments, dict):
        raise error_type("arguments must be an object")

    if intent is IntentName.OPEN_APPLICATION:
        _require_exact_arguments(arguments, {"query"}, error_type)
        query = _bounded_string(arguments["query"], "query", error_type)
        if contains_unsafe_application_query(query):
            raise error_type("application query contains a path, executable, or shell directive")
        clean_arguments: dict[str, object] = {"query": query}
    elif intent is IntentName.CLARIFY:
        _require_exact_arguments(arguments, {"question"}, error_type)
        clean_arguments = {
            "question": _bounded_string(arguments["question"], "question", error_type)
        }
    else:
        _require_exact_arguments(arguments, set(), error_type)
        clean_arguments = {}

    return IntentResult(intent=intent, confidence=confidence, arguments=clean_arguments)


def contains_unsafe_application_query(query: str) -> bool:
    return any(
        pattern.search(query) is not None
        for pattern in (_WINDOWS_PATH, _EXECUTABLE_SUFFIX, _SHELL_SYNTAX, _FORBIDDEN_APP_TERMS)
    )


def _require_exact_arguments(
    arguments: dict[str, Any],
    expected: set[str],
    error_type: type[Exception],
) -> None:
    if set(arguments) != expected:
        expected_names = ", ".join(sorted(expected)) or "(none)"
        raise error_type(f"arguments must contain exactly: {expected_names}")


def _bounded_string(value: Any, name: str, error_type: type[Exception]) -> str:
    if not isinstance(value, str):
        raise error_type(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise error_type(f"{name} must not be empty")
    if len(normalized) > MAX_ARGUMENT_CHARS:
        raise error_type(f"{name} exceeds {MAX_ARGUMENT_CHARS} characters")
    if any(ord(character) < 32 for character in normalized):
        raise error_type(f"{name} contains control characters")
    return normalized
