"""Opt-in real local model, read-only/mocked Core; no OS actions."""

import os
import socket

import pytest
from scripts.evaluation.analyze_file_assistance import TracedModel

from jarvis_brain.errors import ModelInferenceError
from jarvis_brain.intelligence.contract import IntentName
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel
from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult


@pytest.mark.integration
@pytest.mark.parametrize(
    "factory,flag",
    [
        (QwenGgufIntentModel, "JARVIS_RUN_GGUF_TESTS"),
        (QwenOnnxIntentModel, "JARVIS_RUN_MODEL_TESTS"),
    ],
)
def test_real_conversation_cannot_activate_core_tools(factory, flag, monkeypatch):
    if os.environ.get(flag) != "1":
        pytest.skip("opt-in real local inference")

    def blocked(*args, **kwargs):
        pytest.fail("Python network access attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, arguments):
            self.calls.append((tool, arguments))
            if tool == "resolve_app":
                data = {"app": {"app_id": "trusted-chrome", "name": "Google Chrome"}}
            elif tool == "open_app":
                data = {"name": "Google Chrome", "opened": True}
            elif tool == "search_files":
                data = {"entries": [], "total": 0, "partial": False}
            else:
                data = {"cpu_usage_percent": 12, "memory": {"usage_percent": 50}}
            return ToolResult("id", tool, "success", data, None)

    core = Core()
    model = TracedModel() if factory is QwenGgufIntentModel else factory()
    try:
        brain = JarvisBrain(core, model, fast_router_enabled=True)
        for text in ("nasılsın", "How are you?", "What is RAM?", "How do I open Chrome?"):
            if factory is QwenOnnxIntentModel:
                try:
                    response = brain.handle_text(text)
                except ModelInferenceError as error:
                    assert "Conversation replies are not validated" in str(error)
                else:
                    assert response.intent is IntentName.CLARIFY
                    assert not response.executed
                assert core.calls == []
                continue
            response = brain.handle_text(text)
            assert response.intent is IntentName.RESPOND, (text, response)
            assert not response.executed
            assert response.message
            assert core.calls == []
        brain.reset_context()
        try:
            folder = brain.handle_text("indirilenler klasörünü açar mısın")
        except ModelInferenceError as error:
            assert factory is QwenOnnxIntentModel
            assert "Conversation replies are not validated" in str(error)
        else:
            assert not folder.executed
        assert all(tool == "search_files" for tool, _ in core.calls)
        core.calls.clear()
        if factory is QwenOnnxIntentModel:
            with pytest.raises(ModelInferenceError, match="Conversation replies are not validated"):
                brain.handle_text("ben sana hangi klasörü aç demiştim?")
            assert core.calls == []
        else:
            model.events.clear()
            recalled = brain.handle_text("ben sana hangi klasörü aç demiştim?")
            print("Recall trace:", model.events)
            assert recalled.intent is IntentName.RESPOND
            recalled_text = recalled.message.casefold().replace("\u0307", "")
            assert "indirilenler" in recalled_text or "downloads" in recalled_text
            assert "a\u00e7t\u0131m" not in recalled_text
            assert "i opened" not in recalled_text
            assert core.calls == []
        brain.reset_context()
        assert brain.handle_text("Open Google Chrome").executed
        assert [c[0] for c in core.calls] == ["resolve_app", "open_app"]
        core.calls.clear()
        assert brain.handle_text("Check my computer's RAM usage").executed
        assert [c[0] for c in core.calls] == ["system_status"]
        if factory is QwenGgufIntentModel:
            brain.reset_context()
            core.calls.clear()
            for text in ("nasılsın", "ne yapabilirsin", "uygulama açabilir misin"):
                response = brain.handle_text(text)
                assert response.intent is IntentName.RESPOND
                assert not response.executed
                assert core.calls == []
                if text == "uygulama açabilir misin":
                    reply = response.message.casefold()
                    assert "hangi" in reply
                    assert "desteklenmiyor" not in reply and "yapamıyorum" not in reply
            for text in ("crome u açar mısın", "google chromu u açar mısın"):
                core.calls.clear()
                response = brain.handle_text(text)
                assert response.executed, (text, response)
                assert [c[0] for c in core.calls] == ["resolve_app", "open_app"]
            core.calls.clear()
            assert brain.handle_text("sistem status ü mü söyler misin").executed
            assert [c[0] for c in core.calls] == ["system_status"]
    finally:
        model.unload()
