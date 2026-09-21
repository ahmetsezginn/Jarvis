"""Opt-in real local GPU inference; never connects to Core or launches applications."""

import os

import pytest

from jarvis_brain.intelligence.contract import IntentContext, IntentName
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1", reason="opt-in GGUF"),
]


def test_real_local_non_thinking_intents():
    model = QwenGgufIntentModel()
    try:
        model.load()
        result = model.predict("Google Chrome uygulamasını açar mısın?", IntentContext())
        assert result.intent is IntentName.OPEN_APPLICATION
        assert result.arguments["query"].casefold() in {"chrome", "google chrome"}
        result = model.predict("How is my computer doing?", IntentContext())
        assert result.intent is IntentName.SYSTEM_STATUS
    finally:
        model.unload()
