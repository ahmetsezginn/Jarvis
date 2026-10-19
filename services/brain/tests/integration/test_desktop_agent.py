"""Real local model semantic lifecycle checks; synthetic Core, no OS side effects."""

import os

import pytest
from scripts.evaluation.agent_test_model import test_model
from scripts.evaluation.personal_core import PersonalCore

from jarvis_brain.desktop.worker import Session
from jarvis_brain.ipc.protocol import ToolResult


class DesktopCore(PersonalCore):
    def execute_tool(self, tool, args):
        if tool != "desktop_close":
            return super().execute_tool(tool, args)
        self.calls.append({"tool": tool, "arguments": args})
        return ToolResult(
            "synthetic",
            tool,
            "success",
            {"closing": True, "revision": 2},
            None,
        )


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_DESKTOP_MODEL") != "1":
        pytest.skip("opt-in real local model; synthetic desktop only")
    model = test_model("qwen35")
    yield model
    model.unload()


@pytest.mark.parametrize(
    "text,close",
    [
        ("Jarvis, you can close yourself now.", True),
        ("Dismiss your window, please. I'll call you when I need you.", True),
        ("You may go away now, Jarvis.", True),
        ("Jarvis kendini kapatabilirsin.", True),
        ("Jarvis pencereni kapatır mısın?", True),
        ("Don't close yourself. Keep this window open.", False),
        ("Jarvis kendini kapatma, burada kal.", False),
        ("How can I close the assistant window? Explain without doing it.", False),
        ("If I said 'you can close yourself', what would happen? Don't do anything.", False),
        ("Thank you, that's helpful.", False),
    ],
)
def test_real_model_understands_dismissal_and_negative_controls(model, text, close):
    model.events.clear()
    core = DesktopCore()
    session = Session(core, model)
    response = session.request({"op": "chat", "text": text})
    closed = any(c["tool"] == "desktop_close" for c in core.calls)
    print(text, "=>", response["text"], core.calls)
    if closed is not close:
        print("Omission/dispatch trace:", session.brain._agent.trace, model.events)
    assert closed is close
    assert bool(response.get("desktop_event")) is close
