"""Real semantic result-address planning; all Core calls are mocked, no personal files opened."""

import os

import pytest
from scripts.evaluation.analyze_file_assistance import TracedModel

from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult


@pytest.mark.integration
def test_real_gguf_seven_cv_results_select_second_without_new_search():
    if os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1":
        pytest.skip("opt-in real GGUF inference")

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, args):
            self.calls.append((tool, args))
            if tool == "search_files":
                names = [
                    "Ahmet-Sezgin-CV-EN.pdf",
                    "Ahmet-Sezgin-CV-TR.pdf",
                    "Ahmet_Sezgin_CV.pdf",
                    "CV-Grafik-tr.pdf.pdf",
                    "CV-tr.pdf",
                    "CV.pdf",
                    "Grey Clean CV Resume Photo_TR.pdf.pdf",
                ]
                data = {
                    "entries": [
                        {
                            "entry_id": f"core-{i}",
                            "name": name,
                            "kind": "file",
                            "location": f"private/{i}",
                        }
                        for i, name in enumerate(names, 1)
                    ],
                    "total": 7,
                    "partial": True,
                }
            elif tool == "resolve_app":
                data = {"resolved": True, "app": {"app_id": "trusted-edge"}}
            elif tool in {"open_file", "open_file_with_app", "open_containing_folder"}:
                data = {"opened": True, "entry": {"name": "fixture-folder"}}
            else:
                pytest.fail(f"unexpected tool: {tool}")
            return ToolResult("id", tool, "success", data, None)

    class RecordingModel(TracedModel):
        def plan_turn(self, text, context, state):
            result = super().plan_turn(text, context, state)
            self.latest_result = result
            return result

    core = Core()
    model = RecordingModel()
    try:
        runtime = JarvisBrain(core, model, fast_router_enabled=False)
        for text, expected_tool, application in [
            ("2. olanı açar mısın", "open_file", ""),
            ("2 numaralı olanı varsayılan uygulamayla aç", "open_file", ""),
            ("İkinci sıradaki dosyayı açabilir misin", "open_file", ""),
            ("Listeden ikinci sonucu açmanı istiyorum", "open_file", ""),
            ("2. dosyayı Microsoft Edge ile açar mısın", "open_file_with_app", "Microsoft Edge"),
            ("2. dosyanın bulunduğu klasörü açar mısın", "open_containing_folder", ""),
        ]:
            runtime.reset_context()
            core.calls.clear()
            response = runtime.handle_text(
                "benim cv mi bulmama yardımcı olur musun "
                "bilgisayarıma kaydetmiştim şuanda bulamıyorum"
            )
            assert "7 sonuç" in response.message, response
            before = len(core.calls)
            saved_context = runtime._model_context(text)
            response = runtime.handle_text(text)
            print(text, response.message, model.latest_result, core.calls[before:])
            assert response.executed, (text, response, model.latest_result, core.calls)
            assert model.latest_result.move == "select", (text, model.latest_result)
            assert model.latest_result.arguments["number"] == 2
            assert model.latest_result.arguments["application"] == application
            assert core.calls[before:], (text, response, model.latest_result)
            if core.calls[-1][0] != expected_tool:
                print("Legacy selection comparison:", model.predict(text, saved_context))
            assert core.calls[before:][0][0] == ("resolve_app" if application else expected_tool)
            assert core.calls[-1][0] == expected_tool
            assert core.calls[-1][1]["entry_id"] == "core-2"
            assert not any(tool == "search_files" for tool, _ in core.calls[before:]), core.calls
    finally:
        model.unload()
