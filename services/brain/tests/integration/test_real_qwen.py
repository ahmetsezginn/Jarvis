from __future__ import annotations

import os

import pytest

from jarvis_brain.intelligence.contract import ConversationTurn, IntentContext, IntentName
from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_MODEL_TESTS") != "1",
    reason="set JARVIS_RUN_MODEL_TESTS=1 after explicit model provisioning",
)
def test_real_qwen_int4_cpu_produces_validated_semantic_intent() -> None:
    model = QwenOnnxIntentModel()
    model.load()
    result = model.predict(
        "Google Chrome uygulamasını benim için başlatabilir misin?",
        IntentContext(max_context_tokens=2048, max_generated_tokens=128),
    )
    assert result.intent is IntentName.OPEN_APPLICATION
    assert result.arguments == {"query": "Google Chrome"}
    assert model.last_metrics is not None
    assert model.last_metrics.generated_tokens <= 128

    context = IntentContext(
        history=(
            ConversationTurn(
                "I want to use Google Chrome", "Do you want me to open Google Chrome?"
            ),
        )
    )
    try:
        contextual = model.predict("Yes, open that application.", context)
        assert contextual.intent is IntentName.OPEN_APPLICATION
        assert contextual.arguments["query"].casefold() in {"chrome", "google chrome"}
    finally:
        model.unload()
