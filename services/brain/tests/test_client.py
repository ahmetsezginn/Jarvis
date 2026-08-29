from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from jarvis_brain.core.client import JarvisCoreClient, open_application
from jarvis_brain.errors import (
    CoreToolError,
    ProtocolViolationError,
    RequestTimeoutError,
)
from jarvis_brain.ipc.codec import decode_frame, encode_frame

ResponseFactory = Callable[[dict[str, Any]], dict[str, Any]]


class FakeTransport:
    def __init__(self, handler: ResponseFactory | None = None) -> None:
        self.handler = handler or successful_handler
        self.connected = False
        self.closed = False
        self.requests: list[dict[str, Any]] = []

    def connect(self, _timeout: float) -> None:
        self.connected = True

    def send(self, frame: bytes) -> None:
        assert self.connected
        self.requests.append(decode_frame(frame))

    def receive(self, _timeout: float) -> bytes:
        return encode_frame(self.handler(self.requests[-1]))

    def close(self) -> None:
        self.closed = True
        self.connected = False


def response(
    request: dict[str, Any],
    message_type: str,
    payload: Any,
    *,
    ok: bool = True,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "protocol_version": 1,
        "request_id": request["request_id"],
        "message_type": message_type,
        "ok": ok,
        "payload": payload,
        "error": error,
    }


def tool_result(request: dict[str, Any], data: Any) -> dict[str, Any]:
    tool = request["payload"]["tool"]
    return response(
        request,
        "tool_result",
        {
            "request_id": request["request_id"],
            "tool": tool,
            "status": "success",
            "data": data,
        },
    )


def successful_handler(request: dict[str, Any]) -> dict[str, Any]:
    message_type = request["message_type"]
    if message_type == "hello":
        return response(
            request,
            "hello_ack",
            {"core": "jarvis-core", "core_version": "0.1.0", "protocol_version": 1},
        )
    if message_type == "ping":
        return response(request, "pong", {"status": "ok"})
    if message_type == "list_tools":
        return response(
            request,
            "tools",
            {"tools": [{"name": "system_status", "risk_level": "read_only"}]},
        )
    if message_type == "execute_tool":
        return tool_result(request, {"from": "rust"})
    raise AssertionError(message_type)


def test_client_handshakes_once_then_reuses_connection_for_ping_and_tools() -> None:
    transport = FakeTransport()
    client = JarvisCoreClient(transport)
    client.connect()
    assert client.ping() == "ok"
    assert client.list_tools()[0].name == "system_status"
    assert [request["message_type"] for request in transport.requests] == [
        "hello",
        "ping",
        "list_tools",
    ]
    client.close()
    assert transport.closed


def test_execute_tool_parses_typed_result_and_correlates_ids() -> None:
    transport = FakeTransport()
    client = JarvisCoreClient(transport)
    client.connect()
    result = client.execute_tool("system_status", {})
    assert result.data == {"from": "rust"}
    execute_request = transport.requests[-1]
    assert result.request_id == execute_request["request_id"]


def test_tool_error_is_typed_and_preserves_ambiguity_candidates() -> None:
    candidates = [{"app_id": "app_one", "name": "Chrome"}]

    def handler(request: dict[str, Any]) -> dict[str, Any]:
        if request["message_type"] == "hello":
            return successful_handler(request)
        return response(
            request,
            "tool_result",
            None,
            ok=False,
            error={
                "code": "application_ambiguous",
                "message": "ambiguous",
                "details": {"candidates": candidates},
            },
        )

    client = JarvisCoreClient(FakeTransport(handler))
    client.connect()
    with pytest.raises(CoreToolError) as raised:
        client.execute_tool("resolve_app", {"query": "chrome"})
    assert raised.value.code == "application_ambiguous"
    assert raised.value.details == {"candidates": candidates}


def test_response_id_mismatch_is_rejected() -> None:
    def handler(request: dict[str, Any]) -> dict[str, Any]:
        result = successful_handler(request)
        result["request_id"] = "wrong"
        return result

    client = JarvisCoreClient(FakeTransport(handler))
    with pytest.raises(ProtocolViolationError):
        client.connect()


def test_timeout_is_typed_and_disconnect_closes_transport() -> None:
    class TimeoutTransport(FakeTransport):
        def receive(self, _timeout: float) -> bytes:
            raise RequestTimeoutError("expected timeout")

    transport = TimeoutTransport()
    client = JarvisCoreClient(transport)
    with pytest.raises(RequestTimeoutError):
        client.connect()
    assert transport.closed


def test_application_helper_passes_only_rust_returned_app_id() -> None:
    catalog_id = "app_11111111-1111-1111-1111-111111111111"

    def handler(request: dict[str, Any]) -> dict[str, Any]:
        if request["message_type"] == "hello":
            return successful_handler(request)
        payload = request["payload"]
        if payload["tool"] == "resolve_app":
            return tool_result(
                request,
                {"app": {"app_id": catalog_id, "name": "Google Chrome"}},
            )
        assert payload == {"tool": "open_app", "arguments": {"app_id": catalog_id}}
        return tool_result(request, {"app_id": catalog_id, "name": "Google Chrome"})

    transport = FakeTransport(handler)
    client = JarvisCoreClient(transport)
    client.connect()
    result = open_application(client, "Google Chrome")
    assert result.data["app_id"] == catalog_id
    assert [item["payload"]["tool"] for item in transport.requests[1:]] == [
        "resolve_app",
        "open_app",
    ]


@pytest.mark.parametrize("error_code", ["application_not_found", "application_ambiguous"])
def test_application_helper_surfaces_resolution_errors(error_code: str) -> None:
    def handler(request: dict[str, Any]) -> dict[str, Any]:
        if request["message_type"] == "hello":
            return successful_handler(request)
        return response(
            request,
            "tool_result",
            None,
            ok=False,
            error={"code": error_code, "message": error_code, "details": None},
        )

    client = JarvisCoreClient(FakeTransport(handler))
    client.connect()
    with pytest.raises(CoreToolError) as raised:
        open_application(client, "missing")
    assert raised.value.code == error_code
