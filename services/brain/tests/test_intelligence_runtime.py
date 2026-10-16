from __future__ import annotations

from typing import Any

import pytest

from jarvis_brain.errors import IntentValidationError
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.legacy_runtime import LegacyBrain as JarvisBrain
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.ipc.protocol import ToolResult


class FakeCore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_tool(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((tool, arguments))
        if tool == "resolve_app":
            data: Any = {"app": {"app_id": "rust-id", "name": "Chrome"}}
        elif tool == "open_app":
            data = {"app_id": arguments["app_id"], "name": "Chrome"}
        else:
            data = {}
        return ToolResult("id", tool, "success", data, None)


def test_execution_still_uses_task_validation_with_legacy_router_enabled() -> None:
    core = FakeCore()
    model = FakeIntentModel(
        IntentResult(IntentName.OPEN_APPLICATION, 1.0, {"query": "Google Chrome"})
    )
    response = JarvisBrain(core, model).handle_text("Open Google Chrome")
    assert response.route == "model"
    assert model.load_count == 1
    assert model.classify_count == 1
    assert model.predict_count == 1
    assert [call[0] for call in core.calls] == ["resolve_app", "open_app"]


def test_fallback_lazy_loads_once_and_force_model_bypasses_router() -> None:
    core = FakeCore()
    model = FakeIntentModel(
        IntentResult(IntentName.OPEN_APPLICATION, 0.95, {"query": "Google Chrome"})
    )
    brain = JarvisBrain(core, model)
    first = brain.handle_text("Chrome'u benim için çalıştırabilir misin?")
    second = brain.handle_text("Open Chrome", force_model=True)
    assert first.route == second.route == "model"
    assert model.load_count == 1
    assert model.predict_count == 2


def test_low_confidence_action_does_not_call_core() -> None:
    core = FakeCore()
    model = FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 0.40, {"query": "Chrome"}))
    response = JarvisBrain(core, model).handle_text("Could you maybe open it?")
    assert response.intent is IntentName.CLARIFY
    assert not response.executed
    assert core.calls == []


def test_disabled_router_never_runs_and_preserves_trusted_resolution() -> None:
    class ForbiddenRouter:
        def route(self, _text):
            pytest.fail("disabled router was called")

    core = FakeCore()
    model = FakeIntentModel(
        IntentResult(IntentName.OPEN_APPLICATION, 0.95, {"query": "Visual Studio Code"})
    )
    brain = JarvisBrain(core, model, router=ForbiddenRouter(), fast_router_enabled=False)
    result = brain.handle_text("vs code u da açar mısın")
    assert result.route == "model"
    assert core.calls == [
        ("resolve_app", {"query": "Visual Studio Code"}),
        ("open_app", {"app_id": "rust-id"}),
    ]


def test_disabled_router_keeps_input_and_output_validation() -> None:
    core = FakeCore()
    model = FakeIntentModel(IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": r"C:\bad.exe"}))
    brain = JarvisBrain(core, model, fast_router_enabled=False)
    with pytest.raises(IntentValidationError):
        brain.handle_text("x\x00")
    assert model.load_count == 0
    with pytest.raises(IntentValidationError):
        brain.handle_text("open Chrome")
    assert core.calls == []


def test_model_path_like_query_is_revalidated_before_orchestration() -> None:
    core = FakeCore()
    model = FakeIntentModel(
        IntentResult(IntentName.OPEN_APPLICATION, 1.0, {"query": r"C:\bad.exe"})
    )
    with pytest.raises(IntentValidationError):
        JarvisBrain(core, model).handle_text("something unknown")
    assert core.calls == []


@pytest.mark.parametrize("value", ["", "   ", "x" * 4097, "hello\x00world"])
def test_input_validation_rejects_empty_oversized_and_control_text(value: str) -> None:
    brain = JarvisBrain(FakeCore(), FakeIntentModel(IntentResult(IntentName.UNSUPPORTED, 1.0, {})))
    with pytest.raises(IntentValidationError):
        brain.handle_text(value)
