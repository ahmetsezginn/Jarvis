"""Opt-in live Rust catalog through the real Named Pipe; no launches or content reads."""

import os

import pytest

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.errors import CoreToolError


@pytest.mark.integration
def test_live_file_catalog_refresh_search_and_directory_listing():
    if os.environ.get("JARVIS_RUN_FILE_CATALOG_TESTS") != "1":
        pytest.skip("opt-in live file metadata only")
    with JarvisCoreClient(request_timeout=30) as core:
        assert core.ping() == "ok"
        names = {t.name for t in core.list_tools()}
        assert {"search_files", "list_directory", "open_file", "open_directory"} <= names
        status = core.execute_tool("refresh_file_catalog", {}).data
        assert status["indexed"] and not status["contents_read"]
        assert status["scope"] == "configured_roots_only"
        assert status["files"] + status["directories"] > 0
        result = core.execute_tool(
            "search_files", {"query": "*", "kind": "directory", "limit": 1}
        ).data
        assert result["entries"]
        folder = result["entries"][0]
        listing = core.execute_tool("list_directory", {"entry_id": folder["entry_id"]}).data
        assert "entries" in listing
        core.execute_tool("refresh_file_catalog", {})
        with pytest.raises(CoreToolError, match="invalid_arguments"):
            core.execute_tool("list_directory", {"entry_id": folder["entry_id"]})
        with pytest.raises(CoreToolError, match="invalid_arguments"):
            core.execute_tool("open_file", {"entry_id": "invented-test-id"})
        assert core.ping() == "ok"
