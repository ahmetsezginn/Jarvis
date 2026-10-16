"""Opt-in local inference, mocked Core only; never launches a real document."""

import os
import socket

import pytest
from scripts.evaluation.analyze_file_assistance import TracedModel

from jarvis_brain.intelligence.contract import IntentName
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult


@pytest.mark.integration
def test_real_gguf_file_requests_and_negative_open(monkeypatch):
    if os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1":
        pytest.skip("opt-in real GGUF inference")

    def blocked(*args, **kwargs):
        pytest.fail("network access attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, arguments):
            self.calls.append((tool, arguments))
            if tool == "search_files":
                kind = arguments.get("kind") or "file"
                data = {
                    "entries": [
                        {
                            "entry_id": "rust-entry",
                            "name": "İndirilenler" if kind == "directory" else "teklif.pdf",
                            "kind": kind,
                            "location": "fixture/location",
                        }
                    ],
                    "total": 1,
                    "partial": False,
                }
            elif tool == "list_directory":
                data = {"entries": [], "total": 0, "partial": False}
            elif tool in {"open_file", "open_directory"}:
                data = {"opened": True, "entry": {"name": "fixture"}}
            else:
                data = {
                    "indexed": True,
                    "roots": [{"name": "Belgeler"}],
                    "files": 1,
                    "directories": 1,
                    "partial": False,
                }
            return ToolResult("id", tool, "success", data, None)

    model = TracedModel()
    core = Core()
    try:
        runtime = JarvisBrain(core, model, fast_router_enabled=False)
        for text, tools in [
            ("indirilenler klasörünü açar mısın", ["search_files", "open_directory"]),
            ("teklif PDF dosyasını bul", ["search_files"]),
            ("Belgeler klasörünün içinde ne var?", ["search_files", "list_directory"]),
            ("bilgisayarımda hangi dosyalar var?", ["file_catalog_status"]),
            ("dosya kataloğunu yenile", ["file_catalog_status", "refresh_file_catalog"]),
            ("bütçe Excel dosyasını aç", ["search_files", "open_file"]),
            ("en büyük dosyaları göster", ["search_files"]),
        ]:
            runtime.reset_context()
            core.calls.clear()
            response = runtime.handle_text(text)
            assert [call[0] for call in core.calls] == tools, (text, response, core.calls)
            assert "resolve_app" not in tools
            if "büyük" in text:
                assert core.calls[0][1]["sort"] == "largest"
                assert core.calls[0][1]["query"] == "*"
        runtime.reset_context()
        core.calls.clear()
        response = runtime.handle_text("rapor dosyasını açma")
        assert not response.executed
        assert not core.calls
        runtime.reset_context()
        response = runtime.handle_text("Dosya nedir?")
        assert response.intent is IntentName.RESPOND
        assert not core.calls
    finally:
        model.unload()


@pytest.mark.integration
def test_real_gguf_cv_transcript_scoped_search_and_chrome_confirmation(monkeypatch):
    if os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1":
        pytest.skip("opt-in real GGUF inference")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, args):
            self.calls.append((tool, args))
            if tool == "search_files":
                if args.get("kind") == "directory":
                    downloads = (
                        "indir" in args["query"].casefold().replace("\u0307", "")
                        or "download" in args["query"].casefold()
                    )
                    entries = [
                        {
                            "entry_id": "downloads" if downloads else "cvfolder",
                            "name": "İndirilenler" if downloads else "cvfolder",
                            "kind": "directory",
                            "location": "fixture/folder",
                        }
                    ]
                else:
                    entries = [
                        {
                            "entry_id": suffix,
                            "name": f"Ahmet-Sezgin-CV-{suffix.upper()}.pdf",
                            "kind": "file",
                            "location": "fixture/file",
                        }
                        for suffix in ("en", "tr")
                    ]
                data = {"entries": entries, "total": len(entries), "partial": False}
            elif tool == "resolve_app":
                data = {"resolved": True, "app": {"app_id": "rust-chrome", "name": "Google Chrome"}}
            elif tool in {"open_directory", "open_file_with_app", "open_file"}:
                data = {"opened": True}
            else:
                pytest.fail(f"unexpected tool: {tool}")
            return ToolResult("id", tool, "success", data, None)

    core = Core()
    model = TracedModel()
    try:
        runtime = JarvisBrain(core, model, fast_router_enabled=False)
        for text in [
            "şimdi bana indirilenler klasörünü açar mısın",
            "orada cv min olduğu bir klasör var onu bulur musun",
            "aynen orada benim cvim var onu bana bulur musun",
        ]:
            response = runtime.handle_text(text)
            assert response.executed, (text, response, core.calls)
        searches = [args for tool, args in core.calls if tool == "search_files"]
        assert len(searches) == 3, core.calls
        assert searches[1]["folder_id"] == "downloads", core.calls
        assert searches[1]["kind"] == "directory", core.calls
        assert searches[2]["folder_id"] == "cvfolder", core.calls
        assert searches[2]["kind"] == "file", core.calls
        assert all(args["query"].casefold() == "cv" for args in searches[1:]), core.calls
        assert not runtime.handle_text("tr olanı google ile aç").executed
        print("Browser reference trace:", model.events[-3:])
        assert runtime.handle_text("evet").executed
        assert core.calls[-1] == ("open_file_with_app", {"entry_id": "tr", "app_id": "rust-chrome"})
    finally:
        model.unload()
