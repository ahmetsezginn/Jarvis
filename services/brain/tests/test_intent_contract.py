from __future__ import annotations

import pytest

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.contract import IntentName, validate_intent_object


def test_valid_open_application_contract_has_only_human_query() -> None:
    result = validate_intent_object(
        {
            "intent": "open_application",
            "confidence": 0.96,
            "arguments": {"query": "Google Chrome"},
        },
        model_output=True,
    )
    assert result.intent is IntentName.OPEN_APPLICATION
    assert dict(result.arguments) == {"query": "Google Chrome"}


@pytest.mark.parametrize(
    "field",
    ["app_id", "path", "executable", "command", "shell", "powershell", "arguments_to_executable"],
)
def test_open_application_rejects_every_untrusted_extra_field(field: str) -> None:
    with pytest.raises(ModelOutputInvalid):
        validate_intent_object(
            {
                "intent": "open_application",
                "confidence": 0.9,
                "arguments": {"query": "Chrome", field: "attacker-controlled"},
            },
            model_output=True,
        )


@pytest.mark.parametrize(
    "query",
    [
        r"C:\Windows\System32\cmd.exe",
        r"\\server\share\program.exe",
        "PowerShell",
        "Chrome && whoami",
        "app.exe",
    ],
)
def test_open_application_rejects_path_executable_and_shell_queries(query: str) -> None:
    with pytest.raises(ModelOutputInvalid):
        validate_intent_object(
            {
                "intent": "open_application",
                "confidence": 0.9,
                "arguments": {"query": query},
            },
            model_output=True,
        )


@pytest.mark.parametrize(
    "value",
    [
        {"intent": "run_shell", "confidence": 1.0, "arguments": {}},
        {"intent": "system_status", "confidence": True, "arguments": {}},
        {"intent": "system_status", "confidence": 1.1, "arguments": {}},
        {"intent": "system_status", "confidence": 1.0, "arguments": {"extra": 1}},
        {"intent": "clarify", "confidence": 0.5, "arguments": {}},
    ],
)
def test_contract_rejects_unknown_intents_bad_confidence_and_wrong_arguments(value: object) -> None:
    with pytest.raises(ModelOutputInvalid):
        validate_intent_object(value, model_output=True)
