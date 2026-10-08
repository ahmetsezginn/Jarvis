"""Strict parser for untrusted model output."""

from __future__ import annotations

import json
from typing import Any

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.contract import IntentResult, validate_intent_object

MAX_MODEL_OUTPUT_CHARS = 2048


def parse_model_output(raw_output: str) -> IntentResult:
    return validate_intent_object(parse_json_object(raw_output), model_output=True)


def parse_json_object(raw_output: str) -> dict[str, Any]:
    if not isinstance(raw_output, str):
        raise ModelOutputInvalid("model output must be text")
    stripped = raw_output.strip()
    if not stripped or len(stripped) > MAX_MODEL_OUTPUT_CHARS:
        raise ModelOutputInvalid("model output is empty or exceeds the hard character limit")
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise ModelOutputInvalid("model output must be one bare JSON object without prose")
    if "<think>" in stripped.lower() or "</think>" in stripped.lower():
        raise ModelOutputInvalid("thinking output is forbidden")
    try:
        value = json.loads(
            stripped,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ModelOutputInvalid("model output is not strict JSON") from error
    if not isinstance(value, dict):
        raise ModelOutputInvalid("model output must be an object")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")
