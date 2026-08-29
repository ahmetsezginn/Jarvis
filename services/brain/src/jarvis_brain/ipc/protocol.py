"""Typed models for JARVIS control protocol version 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jarvis_brain.errors import ProtocolViolationError

CONTROL_PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class ErrorDetail:
    code: str
    message: str
    details: Any = None

    @classmethod
    def from_value(cls, value: Any) -> ErrorDetail:
        if not isinstance(value, dict):
            raise ProtocolViolationError("response error must be an object")
        code = value.get("code")
        message = value.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            raise ProtocolViolationError("response error code and message must be strings")
        return cls(code=code, message=message, details=value.get("details"))


@dataclass(frozen=True)
class ResponseEnvelope:
    protocol_version: int
    request_id: str
    message_type: str
    ok: bool
    payload: Any
    error: ErrorDetail | None

    @classmethod
    def from_value(cls, value: Any) -> ResponseEnvelope:
        if not isinstance(value, dict):
            raise ProtocolViolationError("response envelope must be an object")
        protocol_version = value.get("protocol_version")
        request_id = value.get("request_id")
        message_type = value.get("message_type")
        ok = value.get("ok")
        if not isinstance(protocol_version, int) or isinstance(protocol_version, bool):
            raise ProtocolViolationError("response protocol_version must be an integer")
        if not isinstance(request_id, str) or not isinstance(message_type, str):
            raise ProtocolViolationError("response request_id and message_type must be strings")
        if not isinstance(ok, bool):
            raise ProtocolViolationError("response ok must be a boolean")
        raw_error = value.get("error")
        error = None if raw_error is None else ErrorDetail.from_value(raw_error)
        if ok and error is not None:
            raise ProtocolViolationError("successful response cannot contain an error")
        if not ok and error is None:
            raise ProtocolViolationError("failed response must contain an error")
        return cls(
            protocol_version=protocol_version,
            request_id=request_id,
            message_type=message_type,
            ok=ok,
            payload=value.get("payload"),
            error=error,
        )


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    risk_level: str

    @classmethod
    def from_value(cls, value: Any) -> ToolMetadata:
        if not isinstance(value, dict):
            raise ProtocolViolationError("tool metadata must be an object")
        name = value.get("name")
        risk_level = value.get("risk_level")
        if not isinstance(name, str) or not isinstance(risk_level, str):
            raise ProtocolViolationError("tool name and risk_level must be strings")
        return cls(name=name, risk_level=risk_level)


@dataclass(frozen=True)
class ToolResult:
    request_id: str
    tool: str
    status: str
    data: Any
    error: ErrorDetail | None

    @classmethod
    def from_value(cls, value: Any) -> ToolResult:
        if not isinstance(value, dict):
            raise ProtocolViolationError("tool result must be an object")
        request_id = value.get("request_id")
        tool = value.get("tool")
        status = value.get("status")
        if not all(isinstance(item, str) for item in (request_id, tool, status)):
            raise ProtocolViolationError("tool result identifiers and status must be strings")
        raw_error = value.get("error")
        return cls(
            request_id=request_id,
            tool=tool,
            status=status,
            data=value.get("data"),
            error=None if raw_error is None else ErrorDetail.from_value(raw_error),
        )


def request_envelope(request_id: str, message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": CONTROL_PROTOCOL_VERSION,
        "request_id": request_id,
        "message_type": message_type,
        "payload": payload,
    }
