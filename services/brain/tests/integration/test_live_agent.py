"""Opt-in new agent + actual Named Pipe/Core with isolated synthetic roots only."""

import os

import pytest
from scripts.evaluation.agent_test_model import test_model

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.intelligence.runtime import JarvisBrain


@pytest.mark.integration
def test_live_agent_discovery_and_default_and_explicit_opening():
    if os.environ.get("JARVIS_RUN_FILE_CONTEXT_LIVE") != "1":
        pytest.skip("opt-in synthetic local GUI openings via actual Core")
    model = test_model(os.environ.get("JARVIS_AGENT_TEST_PROFILE", "qwen35"))
    try:
        with JarvisCoreClient(request_timeout=30) as client:
            roots = client.execute_tool("file_catalog_status", {}).data["roots"]
            assert {r["name"] for r in roots} == {"Downloads", "Desktop"}
            assert len(roots) == 2
            for root in roots:
                suffix = (
                    "file-context-live"
                    if root["name"] == "Downloads"
                    else "file-context-desktop-live"
                )
                assert root["path"].rstrip("\\/").endswith("target\\" + suffix)

            class Core:
                def __init__(self):
                    self.calls = []

                def list_tools(self):
                    return client.list_tools()

                def execute_tool(self, tool, args):
                    self.calls.append((tool, dict(args)))
                    return client.execute_tool(tool, args)

            core = Core()
            brain = JarvisBrain(core, model)
            response = brain.handle_text(
                "I cannot find my Toplantı-Sunum meeting presentation. Could you help?"
            )
            print(response.message, core.calls)
            assert {e["name"] for e in brain._files._entries} == {"Toplantı-Sunum.txt"}
            assert all(tool in {"search_files", "file_catalog_status"} for tool, _ in core.calls)
            core.calls.clear()
            response = brain.handle_text("Open that file, please.")
            print(response.message, core.calls)
            assert response.executed
            assert [tool for tool, _ in core.calls] == ["open_file"]
            # A separate explicit browser request: own fixture PDF, never personal data.
            brain.reset_context()
            brain._agent.builtins.find_files({"query": "Ahmet-Sezgin-CV-TR.pdf"})
            assert len(brain._files._entries) == 1
            core.calls.clear()
            response = brain.handle_text("Could you open this with Google Chrome?")
            print(response.message, core.calls)
            assert response.executed
            assert [tool for tool, _ in core.calls] == ["resolve_app", "open_file_with_app"]
            # No UI/window/process probe is performed after either launch.
    finally:
        model.unload()
