import json
from io import BytesIO

import pytest
from scripts.evaluation.analyze_file_assistance import SyntheticCore

from jarvis_brain.desktop.worker import Session, serve
from jarvis_brain.errors import ModelLoadError


class Model:
    def __init__(self, *actions):
        self.actions = iter(actions)

    def load(self):
        pass

    def next_step(self, *_):
        return json.dumps(next(self.actions))

    def authorize_action(self, *_):
        return True


def action(name, **args):
    return {"action": name, "arguments": args, "confidence": 1}


def test_worker_preloads_before_reading_input_and_then_processes_early_message_once():
    events = []
    core = SyntheticCore()

    class Preloaded(Model):
        initialized = False
        loads = 0

        def load(self):
            if not self.initialized:
                assert events == [{"event": "ready", "model_loading": True}]
                assert not core.calls
                self.initialized = True
                self.loads += 1

    model = Preloaded(action("answer", message="Hello."))

    class EarlyInput(BytesIO):
        def readline(self, limit):
            assert model.initialized
            return super().readline(limit)

    code = serve(core, model, EarlyInput(b'{"op":"chat","text":"Hello"}\n'), events.append)
    assert code == 0 and model.loads == 1
    assert [event["event"] for event in events] == ["ready", "model_ready", "response"]
    assert events[1]["load_time_ms"] >= 0 and events[2]["text"] == "Hello."
    assert not core.calls


def test_worker_loads_without_waiting_for_a_first_message():
    events, loads = [], []

    class Preloaded(Model):
        def load(self):
            loads.append(True)

    assert serve(SyntheticCore(), Preloaded(), BytesIO(), events.append) == 0
    assert loads == [True] and [event["event"] for event in events] == ["ready", "model_ready"]


def test_worker_failed_preload_never_reads_or_executes_a_queued_message():
    core, events = SyntheticCore(), []
    source = BytesIO(b'{"op":"chat","text":"Open an app"}\n')

    class Failed(Model):
        def load(self):
            raise ModelLoadError("Artifact verification failed")

    assert serve(core, Failed(), source, events.append) == 1
    assert source.tell() == 0 and not core.calls
    assert events[-1] == {
        "event": "error",
        "stage": "model_load",
        "message": "Artifact verification failed",
    }
    assert not any(event["event"] == "model_ready" for event in events)


def test_desktop_uses_same_session_and_separates_paths_from_spoken_reply():
    core = SyntheticCore()
    session = Session(
        core,
        Model(action("find_files", query="CV"), action("suggest_result", number=2)),
    )
    page = session.request({"op": "chat", "text": "Find my CV"})
    assert len(page["items"]) == 1 and "Downloads/" in page["items"][0]["location"]
    assert page["items"][0]["number"] == 2
    assert "CV-TR.pdf" in page["speech_text"] and "CV-EN.pdf" not in page["speech_text"]
    assert "Downloads/" not in page["text"] + page["speech_text"]
    assert "entry_id" not in repr(page)
    assert page["page_info"]["total"] == 2
    opened = session.request({"op": "select", "number": 2, "page_token": page["page_token"]})
    assert opened["executed"] and not opened["items"]
    assert core.calls[-1]["arguments"] == {"entry_id": "cv-tr"}


def test_stale_desktop_card_and_reset_never_open_a_different_current_item():
    core = SyntheticCore()
    session = Session(
        core, Model(action("find_files", query="CV"), action("suggest_result", number=1))
    )
    page = session.request({"op": "chat", "text": "Find my CV"})
    session.request({"op": "reset"})
    core.calls.clear()
    with pytest.raises(ValueError, match="page has changed"):
        session.request({"op": "select", "number": 1, "page_token": page["page_token"]})
    assert not core.calls


def test_empty_partial_scan_stays_visible_without_exposing_private_authority():
    class PartialCore(SyntheticCore):
        def execute_tool(self, tool, args):
            result = super().execute_tool(tool, args)
            if tool == "search_files":
                result.data["partial"] = True
            return result

    session = Session(
        PartialCore(),
        Model(
            action("find_files", query="unmatched"),
            action("answer", message="No matches in the scanned catalog."),
        ),
    )
    result = session.request({"op": "chat", "text": "Find unmatched"})
    assert not result["items"]
    assert result["page_info"] == {
        "total": 0,
        "offset": 0,
        "partial": True,
        "scope": "Permitted catalog roots",
    }
    assert "entry_id" not in repr(result)


@pytest.mark.parametrize(
    "payload",
    [
        {"op": "run_shell", "text": "whoami"},
        {"op": "chat", "text": "hello", "executable": "bad"},
        {"op": "select", "number": True, "page_token": "wrong"},
    ],
)
def test_desktop_protocol_cannot_inject_tools_or_executables(payload):
    core = SyntheticCore()
    with pytest.raises(ValueError):
        Session(core, Model()).request(payload)
    assert not core.calls
