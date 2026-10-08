"""Opt-in live Core refresh; no real applications may be launched."""

import os
from uuid import uuid4

import pytest

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.runtime import JarvisBrain


@pytest.mark.integration
def test_live_catalog_refresh_preserves_connection_and_recovers_missing_request():
    if os.environ.get("JARVIS_RUN_CORE_REFRESH_TESTS") != "1":
        pytest.skip("opt-in live Rust Core")
    with JarvisCoreClient() as core:
        assert core.ping() == "ok"
        refreshed = core.execute_tool("refresh_app_catalog", {})
        assert refreshed.data["refreshed"] is True
        assert refreshed.data["discovered"] > 0
        assert core.ping() == "ok"  # Same established connection, no Core restart.

        class ReadOnlyCore:
            def __init__(self):
                self.calls = []

            def execute_tool(self, tool, arguments):
                assert tool in {"resolve_app", "refresh_app_catalog"}, "unexpected launch"
                self.calls.append(tool)
                return core.execute_tool(tool, arguments)

        recorder = ReadOnlyCore()
        query = "JARVIS Nonexistent Catalog Probe " + uuid4().hex
        brain = JarvisBrain(
            recorder,
            FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": query})),
        )
        assert not brain.handle_text("bu uygulamayı aç").executed
        response = brain.handle_text("ben daha yeni yükledim")
        assert not response.executed
        assert "Katalog yenilendi." in response.message
        assert "bulunamadı" in response.message
        assert recorder.calls == ["resolve_app", "refresh_app_catalog", "resolve_app"]
        assert core.ping() == "ok"
