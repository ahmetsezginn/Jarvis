"""Opt-in semantic selection/default-association checks; Core is mocked, no GUI launch."""

import os

import pytest
from scripts.evaluation.analyze_file_assistance import TracedModel

from jarvis_brain.intelligence.contract import BrainResponse, IntentName
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult


@pytest.mark.integration
def test_real_model_semantically_selects_tr_without_imposing_browser():
    if os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1":
        pytest.skip("opt-in real GGUF inference")

    class Core:
        def __init__(self):
            self.calls = []
            self.extension = "pdf"

        def execute_tool(self, tool, arguments):
            self.calls.append((tool, arguments))
            if tool == "search_files":
                data = {
                    "entries": [
                        {
                            "entry_id": language,
                            "name": f"Ahmet-Sezgin-CV-{language.upper()}.{self.extension}",
                            "kind": "file",
                            "location": "private/location",
                        }
                        for language in ("en", "tr")
                    ],
                    "total": 2,
                }
            elif tool == "open_file":
                data = {"opened": True}
            else:
                pytest.fail(f"unexpected browser selection or tool: {tool}")
            return ToolResult("id", tool, "success", data, None)

    core = Core()
    model = TracedModel()
    try:
        runtime = JarvisBrain(core, model, fast_router_enabled=False)
        for extension, text in [
            ("pdf", "tr olan benimkisi onu açar mısın"),
            ("txt", "Türkçe olan benim dosyam, onu açabilir misin"),
            ("docx", "İngilizce sürümü değil, Türkçe sürümünü aç lütfen"),
            ("jpg", "TR sürümünü normal şekilde aç"),
        ]:
            runtime.reset_context()
            core.extension = extension
            runtime.handle_text("cv dosyalarımı bul")
            runtime._conversation.observe(
                "tr dosyası",
                BrainResponse(
                    IntentName.RESPOND,
                    1,
                    "conversation",
                    False,
                    "Türkçe dosya açılamaz; sadece PDF'ler "
                    "Google Chrome veya Microsoft Edge ile açılır.",
                ),
            )
            before = len(core.calls)
            saved_context = runtime._model_context(text)
            response = runtime.handle_text(text)
            if not response.executed:
                print([event["output"] for event in model.events])
                print("Legacy selection comparison:", model.predict(text, saved_context))
            assert response.executed, (extension, text, response)
            assert core.calls[before:] == [("open_file", {"entry_id": "tr"})], core.calls
    finally:
        model.unload()


@pytest.mark.integration
def test_real_model_chooses_named_browser_for_semantic_file_request():
    if os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1":
        pytest.skip("opt-in real GGUF inference")

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, args):
            self.calls.append((tool, args))
            if tool == "search_files":
                data = {
                    "entries": [
                        {
                            "entry_id": lang,
                            "name": f"CV-{lang.upper()}.pdf",
                            "kind": "file",
                            "location": "fixture",
                        }
                        for lang in ("en", "tr")
                    ],
                    "total": 2,
                }
            elif tool == "resolve_app":
                assert args == {"query": "Microsoft Edge"}
                data = {"resolved": True, "app": {"app_id": "trusted-edge"}}
            elif tool == "open_file_with_app":
                data = {"opened": True}
            else:
                pytest.fail(f"wrong opening method: {tool}")
            return ToolResult("id", tool, "success", data, None)

    core = Core()
    model = TracedModel()
    try:
        runtime = JarvisBrain(core, model, fast_router_enabled=False)
        runtime.handle_text("cv dosyalarımı bul")
        response = runtime.handle_text("Türkçe sürümü Microsoft Edge üzerinden görüntüle")
        print(response.message, core.calls, [event["output"] for event in model.events])
        assert response.executed, response
        assert core.calls[-1] == (
            "open_file_with_app",
            {"entry_id": "tr", "app_id": "trusted-edge"},
        )
    finally:
        model.unload()
