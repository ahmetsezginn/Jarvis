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
    RESPOND = "respond"
    OPEN_APPLICATION = "open_application"
    SEARCH_FILES = "search_files"
    SELECT_FILE = "select_file"
    LIST_FOLDER = "list_folder"
    OPEN_FILE = "open_file"
    OPEN_DIRECTORY = "open_directory"
    FILE_CATALOG_STATUS = "file_catalog_status"
    REFRESH_FILE_CATALOG = "refresh_file_catalog"
    SYSTEM_STATUS = "system_status"
    CLARIFY = "clarify"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ConversationTurn:
    user: str
    assistant: str


@dataclass(frozen=True)
class FileCandidate:
    name: str
    kind: str
    number: int | None = None


@dataclass(frozen=True)
class IntentContext:
    max_context_tokens: int = 2048
    max_generated_tokens: int = 128
    history: tuple[ConversationTurn, ...] = ()
    file_candidates: tuple[FileCandidate, ...] = ()
    requested_file_number: int | None = None
    locating_file: bool = False
    pending_file_question: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.pending_file_question, str) or len(self.pending_file_question) > 400:
            raise ValueError("pending file question must be bounded text")
        if type(self.locating_file) is not bool:
            raise ValueError("locating_file must be a boolean")
        if not 1 <= self.max_context_tokens <= 2048:
            raise ValueError("max_context_tokens must be between 1 and 2048")
        if not 1 <= self.max_generated_tokens <= 128:
            raise ValueError("max_generated_tokens must be between 1 and 128")
        if not isinstance(self.history, tuple) or len(self.history) > 6:
            raise ValueError("history must be a tuple of at most six turns")
        if any(not isinstance(turn, ConversationTurn) for turn in self.history):
            raise ValueError("history must contain ConversationTurn values")
        if any(
            not isinstance(s, str) for turn in self.history for s in (turn.user, turn.assistant)
        ):
            raise ValueError("conversation text must be strings")
        if sum(len(t.user) + len(t.assistant) for t in self.history) > 2400:
            raise ValueError("history exceeds character budget")
        if (
            not isinstance(self.file_candidates, tuple)
            or len(self.file_candidates) > 20
            or any(
                not isinstance(c, FileCandidate)
                or not isinstance(c.kind, str)
                or c.kind not in {"file", "directory"}
                or (c.number is not None and (type(c.number) is not int or not 1 <= c.number <= 20))
                or not isinstance(c.name, str)
                or not 1 <= len(c.name) <= 256
                or any(ord(ch) < 32 for ch in c.name)
                for c in self.file_candidates
            )
            or sum(len(c.name) for c in self.file_candidates) > 1200
        ):
            raise ValueError("invalid bounded file candidates")
        numbers = [c.number for c in self.file_candidates if c.number is not None]
        if len(numbers) != len(set(numbers)):
            raise ValueError("duplicate displayed file numbers")
        if self.requested_file_number is not None and (
            type(self.requested_file_number) is not int
            or not 0 <= self.requested_file_number <= 999
        ):
            raise ValueError("invalid requested file number")


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
    if raw_intent == IntentName.RESPOND:
        raise error_type("respond is a conversation response, not an executable intent")
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

    if intent in {
        IntentName.OPEN_APPLICATION,
        IntentName.SEARCH_FILES,
        IntentName.LIST_FOLDER,
        IntentName.OPEN_FILE,
        IntentName.OPEN_DIRECTORY,
    }:
        optional = (
            {"sort", "extension", "kind"}
            if intent is IntentName.SEARCH_FILES
            else {"application"}
            if intent is IntentName.OPEN_FILE
            else set()
        )
        if (
            model_output
            and intent is IntentName.SEARCH_FILES
            and set(arguments) != {"query", "sort", "extension", "kind"}
        ):
            raise error_type("model file search requires query, sort, extension and kind")
        if "query" not in arguments or set(arguments) - {"query"} - optional:
            raise error_type("query is required; only supported search filters may be supplied")
        query = _bounded_string(arguments["query"], "query", error_type)
        if contains_unsafe_application_query(query):
            raise error_type("query contains a path, executable, or shell directive")
        if intent is not IntentName.OPEN_APPLICATION and any(c in query for c in "\\/:"):
            raise error_type("file requests use human names, never paths")
        clean_arguments: dict[str, object] = {"query": query}
        if intent is IntentName.OPEN_FILE and "application" in arguments:
            application = arguments["application"]
            if application != "":
                application = _bounded_string(application, "application", error_type)
                if contains_unsafe_application_query(application) or any(
                    c in application for c in "\\/:"
                ):
                    raise error_type("application must be a human name, never an execution target")
            clean_arguments["application"] = application
        if intent is IntentName.SEARCH_FILES:
            for key, choices in (
                ("sort", {"name", "newest", "largest"}),
                ("kind", {"any", "file", "directory"}),
            ):
                if key in arguments:
                    if not isinstance(arguments[key], str) or arguments[key] not in choices:
                        raise error_type(f"invalid file search {key}")
                    clean_arguments[key] = arguments[key]
            if "extension" in arguments:
                extension = arguments["extension"]
                if (
                    not isinstance(extension, str)
                    or re.fullmatch(r"[a-zA-Z0-9]{0,16}", extension) is None
                ):
                    raise error_type("invalid file extension filter")
                clean_arguments["extension"] = extension.lower()
    elif intent is IntentName.SELECT_FILE:
        _require_exact_arguments(arguments, {"number", "action", "application"}, error_type)
        number = arguments["number"]
        if type(number) is not int or not 1 <= number <= 20:
            raise error_type("selection number must be an integer from 1 to 20")
        if not isinstance(arguments["action"], str) or arguments["action"] not in {
            "open",
            "list",
            "parent",
        }:
            raise error_type("invalid displayed file action")
        application = arguments["application"]
        if application != "":
            application = _bounded_string(application, "application", error_type)
            if contains_unsafe_application_query(application) or any(
                c in application for c in "\\/:"
            ):
                raise error_type("application must be a human name")
        if arguments["action"] != "open" and application:
            raise error_type("application applies only to opening a selected document")
        clean_arguments = {
            "number": number,
            "action": arguments["action"],
            "application": application,
        }
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
