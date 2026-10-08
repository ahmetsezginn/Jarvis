"""Opt-in offline real inference + mocked Rust, with no machine actions."""

import os
import socket

import pytest

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
def test_real_offline_session_correction(factory, flag, monkeypatch):
    if os.environ.get(flag) != "1":
        pytest.skip("opt-in real local model")

    def forbidden(*args, **kwargs):
        pytest.fail("Python network access attempted")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, arguments):
            self.calls.append((tool, arguments))
            if tool == "resolve_app":
                name = arguments["query"]
                data = {"app": {"app_id": "rust-" + name, "name": name}}
            else:
                data = {"app_id": arguments["app_id"]}
            return ToolResult("id", tool, "success", data, None)

    core = Core()
    model = factory()
    try:
        brain = JarvisBrain(core, model, fast_router_enabled=False)
        assert brain.handle_text("Open Google Chrome").executed
        assert brain.handle_text("Hay\u0131r, Firefox demek istemi\u015ftim; onu a\u00e7.").executed
        assert core.calls[-2] == ("resolve_app", {"query": "Firefox"})
        assert core.calls[-1] == ("open_app", {"app_id": "rust-Firefox"})
        before = len(core.calls)
        brain.handle_text("cancel")
        brain.handle_text("/reset")
        assert len(core.calls) == before
    finally:
        model.unload()
