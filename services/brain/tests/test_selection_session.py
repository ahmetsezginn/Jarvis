from __future__ import annotations

import pytest

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.intelligence.session import SelectionSession
from jarvis_brain.ipc.protocol import ToolResult


class Core:
    def __init__(self):
        self.calls = []
        self.stale = False
        self.denied = False

    def execute_tool(self, tool, arguments):
        self.calls.append((tool, arguments))
        if tool == "resolve_app":
            if arguments["query"] == "Steam":
                raise CoreToolError(
                    "application_ambiguous",
                    "choose",
                    {
                        "candidates": [
                            {"name": "Steam Client", "app_id": "rust-1"},
                            {"name": "Steam Support", "app_id": "rust-2"},
                        ]
                    },
                )
            app_id = "rust-1" if arguments["query"] == "Steam Client" else "rust-2"
            return ToolResult(
                "id",
                tool,
                "success",
                {"app": {"app_id": "changed" if self.stale else app_id}},
                None,
            )
        if self.denied:
            raise CoreToolError("policy_denied", "denied")
        return ToolResult("id", tool, "success", {}, None)


def setup(clock=lambda: 0):
    core = Core()
    model = FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": "Steam"}))
    brain = JarvisBrain(core, model, fast_router_enabled=False, session=SelectionSession(clock))
    response = brain.handle_text("Steam'i aç")
    assert "1. Steam Client\n2. Steam Support" in response.message
    return brain, core, model


@pytest.mark.parametrize(
    ("text", "name", "app_id"),
    [
        ("üstteki", "Steam Client", "rust-1"),
        ("birinci", "Steam Client", "rust-1"),
        ("1", "Steam Client", "rust-1"),
        ("ikinci açar mısın", "Steam Support", "rust-2"),
        ("alttaki", "Steam Support", "rust-2"),
        ("Steam Support", "Steam Support", "rust-2"),
    ],
)
def test_pending_selection_resolves_again_before_open(text, name, app_id):
    brain, core, model = setup()
    result = brain.handle_text(text)
    assert result.executed and result.route == "session"
    assert model.predict_count == 1
    assert core.calls[-2:] == [("resolve_app", {"query": name}), ("open_app", {"app_id": app_id})]
    assert not brain.handle_text("üstteki").executed
    assert len(core.calls) == 3


@pytest.mark.parametrize("text", ["diğeri", "99", "0"])
def test_ambiguous_or_invalid_selection_never_launches(text):
    brain, core, model = setup()
    assert not brain.handle_text(text).executed
    assert len(core.calls) == model.predict_count == 1
    assert brain.handle_text("2").executed


def test_expiry_and_cancellation():
    now = [0]
    brain, core, _ = setup(lambda: now[0])
    now[0] = 120
    assert not brain.handle_text("üstteki").executed
    assert len(core.calls) == 1
    brain, core, _ = setup()
    assert not brain.handle_text("iptal").executed
    assert not brain.handle_text("ikinci").executed
    assert len(core.calls) == 1


def test_changed_identity_fails_closed():
    brain, core, _ = setup()
    core.stale = True
    assert not brain.handle_text("üstteki").executed
    assert all(tool != "open_app" for tool, _ in core.calls)
    assert not brain.handle_text("üstteki").executed
    assert len(core.calls) == 2


def test_identical_names_and_reordered_fresh_candidates_preserve_selection():
    class DuplicateCore(Core):
        def execute_tool(self, tool, arguments):
            self.calls.append((tool, arguments))
            if tool == "resolve_app":
                candidates = [
                    {"name": "Steam", "app_id": "rust-1"},
                    {"name": "Steam", "app_id": "rust-2"},
                ]
                if len(self.calls) > 1:
                    candidates.reverse()
                raise CoreToolError("application_ambiguous", "choose", {"candidates": candidates})
            return ToolResult("id", tool, "success", {}, None)

    core = DuplicateCore()
    model = FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": "Steam"}))
    brain = JarvisBrain(core, model, fast_router_enabled=False)
    brain.handle_text("Steam'i aç")
    assert brain.handle_text("üstteki").executed
    assert core.calls[-1] == ("open_app", {"app_id": "rust-1"})


def test_policy_denial_consumes_selection():
    brain, core, _ = setup()
    core.denied = True
    with pytest.raises(CoreToolError, match="policy_denied"):
        brain.handle_text("üstteki")
    assert not brain.handle_text("üstteki").executed
    assert len(core.calls) == 3


def test_new_topic_and_separate_session_cannot_use_old_selection():
    brain, core, model = setup()
    # Fake model's next response is deliberately non-actionable.
    other = JarvisBrain(core, FakeIntentModel(IntentResult(IntentName.UNSUPPORTED, 1, {})))
    assert not other.handle_text("üstteki").executed
    assert len(core.calls) == 1
    brain._model = FakeIntentModel(IntentResult(IntentName.UNSUPPORTED, 1, {}))
    brain.handle_text("selam")
    assert not brain.handle_text("üstteki").executed
    assert len(core.calls) == 1
