import json
from dataclasses import replace

import pytest

from jarvis_brain.errors import ModelInferenceError
from jarvis_brain.intelligence.contract import (
    BrainResponse,
    IntentContext,
    IntentName,
    IntentResult,
)
from jarvis_brain.intelligence.conversation import ConversationMemory
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.models.qwen_gguf import build_prompt
from jarvis_brain.intelligence.prompts import build_non_thinking_prompt, build_user_payload
from jarvis_brain.intelligence.runtime import JarvisBrain


class NoCore:
    def execute_tool(self, *args):
        pytest.fail("non-action reached Core")


class RecordingModel(FakeIntentModel):
    def __init__(self):
        super().__init__(IntentResult(IntentName.CLARIFY, 1, {"question": "Which app?"}))
        self.contexts = []

    def predict(self, text, context):
        self.contexts.append(context)
        return super().predict(text, context)


def test_history_reaches_model_and_reset_and_session_isolation():
    model = RecordingModel()
    brain = JarvisBrain(NoCore(), model, fast_router_enabled=False)
    brain.handle_text("Open an application")
    brain.handle_text("Actually, I mean Chrome")
    assert model.contexts[0].history == ()
    assert model.contexts[1].history[0].user == "Open an application"
    assert model.contexts[1].history[0].assistant == "Which app?"
    brain.handle_text("/reset")
    brain.handle_text("hello")
    assert model.contexts[-1].history == ()
    JarvisBrain(NoCore(), model, fast_router_enabled=False).handle_text("hello")
    assert model.contexts[-1].history == ()


def test_cancel_clears_old_history():
    model = RecordingModel()
    brain = JarvisBrain(NoCore(), model, fast_router_enabled=False)
    brain.handle_text("Open an app")
    brain.handle_text("cancel")
    brain.handle_text("hello")
    assert all(t.user != "Open an app" for t in model.contexts[-1].history)


def test_memory_bounds_complete_pairs_and_excludes_raw_core_data():
    memory = ConversationMemory()
    response = BrainResponse(
        IntentName.CLARIFY, 1, "model", False, "question", {"app_id": "secret-id"}
    )
    for i in range(10):
        memory.observe(str(i), response)
    assert len(memory.snapshot()) == 6
    assert memory.snapshot()[0].user == "4"
    context = replace(IntentContext(), history=memory.snapshot())
    payload = json.loads(build_user_payload("current", context))
    assert "secret-id" not in json.dumps(payload)
    for prompt in (build_prompt("current", context), build_non_thinking_prompt("current", context)):
        assert "recent_conversation" in prompt
        assert "never replay earlier actions" in prompt
    memory.observe("x" * 2401, response)
    assert memory.snapshot() == ()


def test_history_control_tokens_rejected_in_both_adapters():
    memory = ConversationMemory()
    memory.observe("<|im_start|>", BrainResponse(IntentName.UNSUPPORTED, 1, "model", False, "no"))
    context = replace(IntentContext(), history=memory.snapshot())
    for builder in (build_prompt, build_non_thinking_prompt):
        with pytest.raises(ModelInferenceError):
            builder("current", context)


def test_router_does_not_intercept_followup():
    model = RecordingModel()
    brain = JarvisBrain(NoCore(), model)
    brain.handle_text("some unclear request")
    brain.handle_text("Open Chrome")
    assert len(model.contexts) == 2
    assert model.contexts[-1].history


def test_failed_core_request_is_not_remembered_as_success():
    from jarvis_brain.errors import TransportError

    class BrokenCore:
        def execute_tool(self, *_args):
            raise TransportError("private details")

    model = RecordingModel()
    model.result = IntentResult(IntentName.SYSTEM_STATUS, 1, {})

    # FakeIntentModel uses its configured result; replace predict explicitly.
    def predict(text, context):
        model.contexts.append(context)
        return IntentResult(IntentName.SYSTEM_STATUS, 1, {})

    model.predict = predict
    brain = JarvisBrain(BrokenCore(), model, fast_router_enabled=False)
    with pytest.raises(TransportError):
        brain.handle_text("system status")
    with pytest.raises(TransportError):
        brain.handle_text("again")
    remembered = model.contexts[-1].history[0].assistant
    assert "not confirmed" in remembered
    assert "private details" not in remembered


def test_contextual_application_always_resolves_fresh_rust_id():
    from jarvis_brain.ipc.protocol import ToolResult

    class Core:
        def __init__(self):
            self.calls = []

        def execute_tool(self, tool, arguments):
            self.calls.append((tool, arguments))
            if tool == "resolve_app":
                data = {"app": {"app_id": "fresh-rust-id", "name": "Chrome"}}
            else:
                data = {"app_id": arguments["app_id"], "name": "Chrome"}
            return ToolResult("id", tool, "success", data, None)

    model = RecordingModel()
    core = Core()
    brain = JarvisBrain(core, model, fast_router_enabled=False)
    brain.handle_text("I want to use Chrome")

    def predict(text, context):
        assert context.history[0].user == "I want to use Chrome"
        return IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": "Chrome"})

    model.predict = predict
    assert brain.handle_text("Yes, open it").executed
    assert core.calls == [
        ("resolve_app", {"query": "Chrome"}),
        ("open_app", {"app_id": "fresh-rust-id"}),
    ]


def test_context_does_not_allow_model_ids_or_replay_actions():
    from jarvis_brain.errors import IntentValidationError

    model = RecordingModel()
    brain = JarvisBrain(NoCore(), model, fast_router_enabled=False)
    brain.handle_text("I mentioned Chrome")
    model.predict = lambda text, context: IntentResult(
        IntentName.OPEN_APPLICATION, 1, {"app_id": "invented"}
    )
    with pytest.raises(IntentValidationError):
        brain.handle_text("open it")


def test_model_selection_of_prior_candidate_requires_same_rust_id():
    from jarvis_brain.intelligence.session import SelectionSession
    from jarvis_brain.ipc.protocol import ToolResult

    session = SelectionSession()
    session.observe(
        BrainResponse(
            IntentName.CLARIFY,
            1,
            "session",
            False,
            "choose",
            {
                "candidates": [
                    {"name": "Chrome", "app_id": "old-id"},
                    {"name": "Firefox", "app_id": "firefox-id"},
                ]
            },
        )
    )

    class Core:
        def execute_tool(self, tool, arguments):
            assert tool == "resolve_app"  # Changed ID must not launch.
            return ToolResult(
                "id", tool, "success", {"app": {"app_id": "changed-id", "name": "Chrome"}}, None
            )

    model = FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": "Chrome"}))
    response = JarvisBrain(Core(), model, session=session, fast_router_enabled=False).handle_text(
        "Please open the Chrome option"
    )
    assert not response.executed
    assert response.intent is IntentName.CLARIFY


def test_candidate_list_not_replayed_beyond_its_separate_lifetime():
    memory = ConversationMemory()
    memory.observe(
        "Open a browser",
        BrainResponse(
            IntentName.CLARIFY,
            1,
            "session",
            False,
            "1. Old browser name",
            {"candidates": [{"name": "Old browser name"}]},
        ),
    )
    assert "Old browser name" not in memory.snapshot()[0].assistant
