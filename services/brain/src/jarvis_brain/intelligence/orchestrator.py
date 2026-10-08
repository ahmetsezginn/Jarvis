"""Fixed semantic-intent to trusted Rust Core orchestration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from jarvis_brain.core.client import open_application
from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.contract import BrainResponse, IntentName, IntentResult
from jarvis_brain.ipc.protocol import ToolResult


class CoreToolClient(Protocol):
    def execute_tool(self, tool: str, arguments: dict[str, Any]) -> ToolResult: ...


class IntentOrchestrator:
    def __init__(self, core: CoreToolClient) -> None:
        self._core = core

    def execute(self, result: IntentResult, *, route: str) -> BrainResponse:
        if result.intent is IntentName.OPEN_APPLICATION:
            return self._open_application(result, route)
        if result.intent is IntentName.SYSTEM_STATUS:
            tool_result = self._core.execute_tool("system_status", {})
            return BrainResponse(
                intent=result.intent,
                confidence=result.confidence,
                route=route,
                executed=True,
                message=_format_status(tool_result.data),
                data=asdict(tool_result),
            )
        if result.intent is IntentName.CLARIFY:
            return BrainResponse(
                intent=result.intent,
                confidence=result.confidence,
                route=route,
                executed=False,
                message=str(result.arguments["question"]),
            )
        return BrainResponse(
            intent=IntentName.UNSUPPORTED,
            confidence=result.confidence,
            route=route,
            executed=False,
            message="Bu istek desteklenen yerel komut kapsamının dışında.",
        )

    def open_selected(self, name: str, app_id: str) -> BrainResponse:
        return self._open_application(
            IntentResult(IntentName.OPEN_APPLICATION, 1.0, {"query": name}),
            "session",
            expected_app_id=app_id,
        )

    def refresh_catalog(self) -> None:
        self._core.execute_tool("refresh_app_catalog", {})

    def _open_application(
        self, result: IntentResult, route: str, *, expected_app_id: str | None = None
    ) -> BrainResponse:
        query = str(result.arguments["query"])
        try:
            tool_result = open_application(
                self._core,
                query,
                expected_app_id=expected_app_id,  # type: ignore[arg-type]
            )
        except CoreToolError as error:
            if error.code == "application_selection_stale":
                return BrainResponse(
                    IntentName.CLARIFY,
                    1.0,
                    route,
                    False,
                    "Seçenek değişmiş; uygulama adını yeniden belirtir misin?",
                )
            if error.code == "application_ambiguous":
                return BrainResponse(
                    intent=IntentName.CLARIFY,
                    confidence=result.confidence,
                    route=route,
                    executed=False,
                    message="Birden fazla uygulama eşleşti; lütfen hangisini istediğini belirt.",
                    data=error.details,
                )
            if error.code == "application_not_found":
                return BrainResponse(
                    intent=IntentName.UNSUPPORTED,
                    confidence=result.confidence,
                    route=route,
                    executed=False,
                    message=f"Uygulama Rust kataloğunda bulunamadı: {query}",
                    data=error.details,
                )
            raise
        display_name = query
        if isinstance(tool_result.data, dict):
            name = tool_result.data.get("name")
            if isinstance(name, str) and 0 < len(name) <= 256:
                display_name = " ".join(name.split()) or query
        return BrainResponse(
            intent=result.intent,
            confidence=result.confidence,
            route=route,
            executed=True,
            message=f"{display_name} açıldı.",
            data=asdict(tool_result),
        )


def _format_status(data: Any) -> str:
    if not isinstance(data, dict):
        return "Sistem durumu Rust Core tarafından alındı."
    cpu = data.get("cpu_usage_percent")
    memory = data.get("memory")
    if isinstance(cpu, (int, float)) and isinstance(memory, dict):
        memory_percent = memory.get("usage_percent")
        if isinstance(memory_percent, (int, float)):
            return f"İşlemci kullanımı %{cpu:.1f}, bellek kullanımı %{memory_percent:.1f}."
    return "Sistem durumu Rust Core tarafından alındı."
