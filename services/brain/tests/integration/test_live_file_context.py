"""Opt-in real GGUF + Named Pipe + browser launch using an isolated synthetic PDF fixture."""

import os

import pytest
from scripts.evaluation.analyze_file_assistance import TracedModel

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.runtime import JarvisBrain


def assert_isolated_roots(status):
    roots = status["roots"]
    assert len(roots) == 2
    assert {r["name"] for r in roots} == {"İndirilenler", "Masaüstü"}
    for root in roots:
        expected = (
            "file-context-live" if root["name"] == "İndirilenler" else "file-context-desktop-live"
        )
        assert root["path"].rstrip("\\/").endswith("target\\" + expected)


@pytest.mark.integration
def test_live_cv_context_and_local_chrome_pdf():
    if os.environ.get("JARVIS_RUN_FILE_CONTEXT_LIVE") != "1":
        pytest.skip("opt-in synthetic local PDF GUI launch")
    model = TracedModel()
    with JarvisCoreClient(request_timeout=30) as client:
        status = client.execute_tool("file_catalog_status", {}).data
        # Refuse to launch personal documents or run this against a normal user catalog.
        assert_isolated_roots(status)

        class RecordingCore:
            def __init__(self):
                self.calls = []

            def execute_tool(self, tool, arguments):
                self.calls.append((tool, arguments))
                return client.execute_tool(tool, arguments)

        core = RecordingCore()
        try:
            runtime = JarvisBrain(core, model, fast_router_enabled=False)
            for text, name_fragment in [
                (
                    "ben cv mi bilgisayara bir yere koydum şimdi bula mıyorum "
                    "bana yardımcı olur musun",
                    "CV",
                ),
                ("cv mi bulur musun", "CV"),
                ("cv dosyamı bulur musun dosyayı aramanı istiyorum", "CV"),
                ("dünkü sunumu nereye kaydettiğimi unuttum, bulmama yardım eder misin", "Sunum"),
            ]:
                runtime.reset_context()
                before = len(core.calls)
                response = runtime.handle_text(text)
                print(f"Natural request: {text}: {response.message}")
                assert response.executed, response
                assert [tool for tool, _ in core.calls[before:]] == ["search_files"]
                assert any(name_fragment in entry["name"] for entry in runtime._files._entries)
            runtime.reset_context()
            for text in [
                "şimdi bana indirilenler klasörünü açar mısın",
                "orada cv min olduğu bir klasör var onu bulur musun",
                "aynen orada benim cvim var onu bana bulur musun",
            ]:
                response = runtime.handle_text(text)
                print(f"{text}: {response.message}")
                assert response.executed, response
            assert {e["name"] for e in runtime._files._entries} == {
                "Ahmet-Sezgin-CV-EN.pdf",
                "Ahmet-Sezgin-CV-TR.pdf",
                "Ahmet_Sezgin_CV.pdf",
                "CV-Grafik-tr.pdf.pdf",
                "CV-tr.pdf",
                "CV.pdf",
                "Grey Clean CV Resume Photo_TR.pdf.pdf",
            }
            before = len(core.calls)
            response = runtime.handle_text("2. olanı açar mısın")
            print(response.message)
            assert response.executed, response
            assert [tool for tool, _ in core.calls[before:]] == ["open_file"]
            # Redisplay Core records for a separate, explicitly browser-qualified opening.
            runtime._files.execute(
                IntentResult(
                    IntentName.SEARCH_FILES, 1, {"query": "Ahmet Sezgin CV", "kind": "file"}
                ),
                "CV dosyalarını yeniden göster",
            )
            response = runtime.handle_text("tr olanı google ile aç")
            print("Browser selection:", model.events[-3:], core.calls[-3:])
            assert not response.executed
            assert "Google Chrome" in response.message
            response = runtime.handle_text("evet")
            print(response.message)
            assert response.executed, response
            assert core.calls[-1][0] == "open_file_with_app"
            assert sum(tool == "open_file_with_app" for tool, _ in core.calls) == 1
            # Same real provider and IPC boundary: slot answer, direct scope, rejection, listing.
            runtime.reset_context()
            before = len(core.calls)
            response = runtime.handle_text("bir notumu kaybettim ismini hiç hatırlamıyorum")
            assert not response.executed and len(core.calls) == before
            response = runtime.handle_text("masaüstüne kaydetmiştim")
            assert response.executed, response
            assert {e["name"] for e in runtime._files._entries} == {"New Metin Belgesi.txt"}
            assert core.calls[-1][0] == "search_files"
            assert core.calls[-1][1]["recursive"] is False
            assert core.calls[-1][1]["category"] == "text"
            response = runtime.handle_text("bunlar değil ismini rastgele koymuştum")
            assert runtime._files._entries == (), response
            assert core.calls[-1][1]["exclude_ids"]
            for text in ("neden böyle aradın", "bugün çok mutluyum"):
                before = len(core.calls)
                runtime.handle_text(text)
                assert len(core.calls) == before
            response = runtime.handle_text("bana masa üstümde neler var söyler misin")
            assert response.executed, response
            assert core.calls[-1][0] == "list_directory"
            assert {e["name"] for e in runtime._files._entries} == {
                "New Metin Belgesi.txt",
                "Proje",
            }
            assert client.ping() == "ok"
        finally:
            model.unload()
