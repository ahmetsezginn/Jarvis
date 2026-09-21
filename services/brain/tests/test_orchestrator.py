from __future__ import annotations

from typing import Any

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.orchestrator import IntentOrchestrator
from jarvis_brain.ipc.protocol import ToolResult


class FakeCore:
    def __init__(self, *, ambiguous: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.ambiguous = ambiguous

    def execute_tool(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((tool, arguments))
        if tool == "resolve_app":
            if self.ambiguous:
                raise CoreToolError(
                    "application_ambiguous",
                    "ambiguous",
                    {"candidates": [{"app_id": "trusted-one", "name": "Chrome"}]},
                )
            data: Any = {"app": {"app_id": "trusted-from-rust", "name": "Chrome"}}
        elif tool == "open_app":
            data = {"app_id": arguments["app_id"], "name": "Chrome"}
        else:
            data = {
                "cpu_usage_percent": 12.5,
                "memory": {"usage_percent": 44.0},
                "disks": [],
            }
        return ToolResult("request", tool, "success", data, None)


def test_open_application_always_resolves_human_query_then_uses_rust_app_id() -> None:
    core = FakeCore()
    response = IntentOrchestrator(core).execute(
        IntentResult(IntentName.OPEN_APPLICATION, 0.99, {"query": "Google Chrome"}),
        route="model",
    )
    assert response.executed
    assert core.calls == [
        ("resolve_app", {"query": "Google Chrome"}),
        ("open_app", {"app_id": "trusted-from-rust"}),
    ]


def test_ambiguity_surfaces_candidates_and_never_opens() -> None:
    core = FakeCore(ambiguous=True)
    response = IntentOrchestrator(core).execute(
        IntentResult(IntentName.OPEN_APPLICATION, 1.0, {"query": "Chrome"}),
        route="fast",
    )
    assert response.intent is IntentName.CLARIFY
    assert not response.executed
    assert response.data == {"candidates": [{"app_id": "trusted-one", "name": "Chrome"}]}
    assert core.calls == [("resolve_app", {"query": "Chrome"})]


def test_system_status_uses_only_rust_tool_result() -> None:
    core = FakeCore()
    response = IntentOrchestrator(core).execute(
        IntentResult(IntentName.SYSTEM_STATUS, 1.0, {}), route="fast"
    )
    assert response.executed
    assert core.calls == [("system_status", {})]
    assert "%12.5" in response.message


def test_clarify_and_unsupported_never_call_core() -> None:
    core = FakeCore()
    orchestrator = IntentOrchestrator(core)
    clarify = orchestrator.execute(
        IntentResult(IntentName.CLARIFY, 0.5, {"question": "Hangisi?"}), route="model"
    )
    unsupported = orchestrator.execute(IntentResult(IntentName.UNSUPPORTED, 1.0, {}), route="model")
    assert not clarify.executed and not unsupported.executed
    assert core.calls == []
