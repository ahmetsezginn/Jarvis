"""High-level persistent client for the JARVIS Rust Core."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from jarvis_brain import config
from jarvis_brain.errors import (
    CoreResponseError,
    CoreToolError,
    ProtocolViolationError,
)
from jarvis_brain.ipc.codec import decode_frame, encode_frame
from jarvis_brain.ipc.protocol import (
    CONTROL_PROTOCOL_VERSION,
    ResponseEnvelope,
    ToolMetadata,
    ToolResult,
    request_envelope,
)
from jarvis_brain.ipc.transport import IPCTransport
from jarvis_brain.ipc.windows_pipe import WindowsNamedPipeTransport


class JarvisCoreClient:
    def __init__(
        self,
        transport: IPCTransport | None = None,
        *,
        connect_timeout: float = config.CONNECT_TIMEOUT_SECONDS,
        request_timeout: float = config.REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = transport or WindowsNamedPipeTransport()
        self._connect_timeout = connect_timeout
        self._request_timeout = request_timeout
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        self._transport.connect(self._connect_timeout)
        self._connected = True
        try:
            response = self._exchange(
                "hello",
                {"client": "jarvis-brain", "client_version": "0.1.0"},
            )
            if response.message_type != "hello_ack" or not isinstance(response.payload, dict):
                raise ProtocolViolationError("Core returned an invalid hello response")
            if response.payload.get("protocol_version") != CONTROL_PROTOCOL_VERSION:
                raise ProtocolViolationError("Core hello reported an incompatible protocol version")
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        self._transport.close()
        self._connected = False

    def __enter__(self) -> JarvisCoreClient:
        self.connect()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def ping(self) -> str:
        response = self._request("ping", {})
        if response.message_type != "pong" or not isinstance(response.payload, dict):
            raise ProtocolViolationError("Core returned an invalid ping response")
        status = response.payload.get("status")
        if not isinstance(status, str):
            raise ProtocolViolationError("Core ping status must be a string")
        return status

    def list_tools(self) -> list[ToolMetadata]:
        response = self._request("list_tools", {})
        if response.message_type != "tools" or not isinstance(response.payload, dict):
            raise ProtocolViolationError("Core returned an invalid list_tools response")
        tools = response.payload.get("tools")
        if not isinstance(tools, list):
            raise ProtocolViolationError("Core tools payload must contain a list")
        return [ToolMetadata.from_value(item) for item in tools]

    def execute_tool(self, tool: str, arguments: Mapping[str, Any]) -> ToolResult:
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("tool must be a non-empty string")
        if not isinstance(arguments, Mapping):
            raise TypeError("tool arguments must be a mapping")
        response = self._request(
            "execute_tool",
            {"tool": tool, "arguments": dict(arguments)},
            tool_response=True,
        )
        if response.message_type != "tool_result":
            raise ProtocolViolationError("Core returned an invalid execute_tool response")
        return ToolResult.from_value(response.payload)

    def _request(
        self,
        message_type: str,
        payload: dict[str, Any],
        *,
        tool_response: bool = False,
    ) -> ResponseEnvelope:
        if not self._connected:
            raise ProtocolViolationError("client must be connected before sending requests")
        return self._exchange(message_type, payload, tool_response=tool_response)

    def _exchange(
        self,
        message_type: str,
        payload: dict[str, Any],
        *,
        tool_response: bool = False,
    ) -> ResponseEnvelope:
        request_id = str(uuid4())
        self._transport.send(encode_frame(request_envelope(request_id, message_type, payload)))
        response = ResponseEnvelope.from_value(
            decode_frame(self._transport.receive(self._request_timeout))
        )
        if response.protocol_version != CONTROL_PROTOCOL_VERSION:
            raise ProtocolViolationError(
                f"Core response protocol version {response.protocol_version} is unsupported"
            )
        if response.request_id != request_id:
            raise ProtocolViolationError(
                f"response request_id {response.request_id!r} does not match {request_id!r}"
            )
        if not response.ok:
            if response.error is None:
                raise ProtocolViolationError("failed Core response omitted its typed error")
            error_type = CoreToolError if tool_response else CoreResponseError
            raise error_type(
                response.error.code,
                response.error.message,
                response.error.details,
            )
        return response


def open_application(core: JarvisCoreClient, query: str) -> ToolResult:
    """Resolve through Rust, then pass only the returned catalog app_id back to Rust."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("application query must be a non-empty string")
    resolution = core.execute_tool("resolve_app", {"query": query})
    if not isinstance(resolution.data, dict):
        raise ProtocolViolationError("resolve_app data must be an object")
    app = resolution.data.get("app")
    if not isinstance(app, dict) or not isinstance(app.get("app_id"), str):
        raise ProtocolViolationError("resolve_app did not return a catalog app_id")
    return core.execute_tool("open_app", {"app_id": app["app_id"]})
