from __future__ import annotations

import pytest

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.contract import IntentName
from jarvis_brain.intelligence.parser import parse_model_output


def test_parser_accepts_one_exact_json_object() -> None:
    result = parse_model_output('{"intent":"system_status","confidence":0.98,"arguments":{}}')
    assert result.intent is IntentName.SYSTEM_STATUS


@pytest.mark.parametrize(
    "raw",
    [
        'Here you go: {"intent":"unsupported","confidence":1,"arguments":{}}',
        '```json\n{"intent":"unsupported","confidence":1,"arguments":{}}\n```',
        '{"intent":"unsupported","confidence":1,"arguments":{}} trailing',
        '{"intent":"unsupported","intent":"clarify","confidence":1,"arguments":{}}',
        '{"intent":"unsupported","confidence":NaN,"arguments":{}}',
        '<think>secret</think>{"intent":"unsupported","confidence":1,"arguments":{}}',
    ],
)
def test_parser_rejects_prose_fences_duplicates_constants_and_thinking(raw: str) -> None:
    with pytest.raises(ModelOutputInvalid):
        parse_model_output(raw)
