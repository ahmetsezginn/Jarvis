"""Real local model; invented cross-domain metadata, no Core connection or OS actions."""

import os
import time

import pytest
from scripts.evaluation.agent_test_model import test_model
from scripts.evaluation.analyze_file_assistance import SyntheticCore

from jarvis_brain.desktop.worker import Session

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_RECOMMENDATION_TESTS") != "1":
        pytest.skip("opt-in local model suggestion dialogue")
    value = test_model("qwen35")
    yield value
    value.unload()


class Core(SyntheticCore):
    def __init__(self, topic, extension):
        super().__init__()
        self.entries = [e for e in self.entries if e["kind"] == "directory"]
        self.entries.extend(
            {
                "entry_id": f"synthetic-{i}",
                "name": f"{topic}-{suffix}.{extension}",
                "kind": "file",
                "location": f"Downloads/{topic}-{suffix}.{extension}",
            }
            for i, suffix in enumerate(["2024-archive", "2026-draft", "2026-final"])
        )


def request(session, text):
    core = session.brain._core
    core.calls.clear()
    start = time.monotonic()
    result = session.request({"op": "chat", "text": text})
    print(
        "elapsed:",
        round(time.monotonic() - start, 2),
        "trace:",
        session.brain._agent.trace,
        "rejected:",
        session.brain._agent.builtins.recommendations.view()["rejected_names"],
        flush=True,
    )
    print(text, "=>", result["text"], "cards:", [r["name"] for r in result["items"]], flush=True)
    return result


@pytest.mark.parametrize(
    "topic,extension", [("budget", "xlsx"), ("presentation", "pptx"), ("recipe", "txt")]
)
def test_one_suggestion_rejection_identity_and_explicit_list(model, topic, extension):
    session = Session(Core(topic, extension), model)
    first = request(session, f"I saved a {topic} file somewhere. Could you help me find it?")
    assert len(first["items"]) == 1, first
    rejected = first["items"][0]["name"]
    for entry in session.brain._files._entries:
        if entry["name"] != rejected:
            assert entry["name"] not in first["text"] + first["speech_text"]
    second = request(session, "No, that isn't it. Could you try another one?")
    assert len(second["items"]) == 1 and second["items"][0]["name"] != rejected, second
    assert rejected not in second["text"] + second["speech_text"]
    assert not any(c["tool"].startswith("open_") for c in session.brain._core.calls)
    identity = request(session, "Yes, that's the file I meant.")
    assert not any(c["tool"].startswith("open_") for c in session.brain._core.calls)
    assert not identity["executed"]
    listing = request(session, "Show me all the remaining options, please.")
    assert len(listing["items"]) == 2, listing
    assert rejected not in {r["name"] for r in listing["items"]}


def test_metadata_preference_and_pronoun_default_opening(model):
    session = Session(Core("certificate", "pdf"), model)
    first = request(
        session, "Help me locate my certificate. I'd prefer the final version from 2026."
    )
    assert len(first["items"]) == 1 and first["items"][0]["name"] == "certificate-2026-final.pdf", (
        first
    )
    request(session, "Yes, that's it.")
    assert not any(c["tool"].startswith("open_") for c in session.brain._core.calls)
    opened = request(session, "Please open that one with its default app.")
    assert opened["executed"], opened
    assert session.brain._core.calls[-1] == {
        "tool": "open_file",
        "arguments": {"entry_id": "synthetic-2"},
    }


def test_explicit_full_list_on_first_request_finishes_after_presentation_selection(model):
    session = Session(Core("budget", "xlsx"), model)
    result = request(session, "Please list all the budget files you can find.")
    assert len(result["items"]) == 3 and result["presentation"] == "all", result
    assert not any(c["tool"].startswith("open_") for c in session.brain._core.calls)


def test_pending_app_opening_still_resumes_after_rejecting_one_suggestion(model):
    from services.brain.tests.integration.test_english_agent_acceptance import AppCore

    from jarvis_brain.ipc.protocol import ToolResult

    class Apps(AppCore):
        def execute_tool(self, tool, args):
            if tool == "resolve_app" and args["query"] == "Studio Alpha":
                self.calls.append({"tool": tool, "arguments": dict(args)})
                return ToolResult("fixture", tool, "success", {"app": {"app_id": "alpha"}}, None)
            return super().execute_tool(tool, args)

    session = Session(Apps(ambiguous=True), model)
    first = request(session, "Open the Studio app, please.")
    assert len(first["items"]) == 1 and not first["executed"]
    first_name = first["items"][0]["name"]
    second = request(session, "No, that isn't the app I meant.")
    assert len(second["items"]) == 1 and second["items"][0]["name"] != first_name
    assert not second["executed"]
    name = second["items"][0]["name"]
    opened = request(session, "Yes, that's the app.")
    assert opened["executed"], opened
    assert session.brain._core.calls[0]["arguments"] == {"query": name}
    assert [c["tool"] for c in session.brain._core.calls] == ["resolve_app", "open_app"]
