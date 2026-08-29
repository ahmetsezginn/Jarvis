import pytest

from jarvis_brain.errors import ProtocolViolationError
from jarvis_brain.ipc.protocol import ResponseEnvelope, ToolMetadata, ToolResult


def test_response_and_tool_models_parse_typed_fields() -> None:
    response = ResponseEnvelope.from_value(
        {
            "protocol_version": 1,
            "request_id": "request",
            "message_type": "tool_result",
            "ok": True,
            "payload": {
                "request_id": "request",
                "tool": "system_status",
                "status": "success",
                "data": {},
            },
            "error": None,
        }
    )
    result = ToolResult.from_value(response.payload)
    assert result.tool == "system_status"
    assert ToolMetadata.from_value({"name": "resolve_app", "risk_level": "read_only"}).name == (
        "resolve_app"
    )


@pytest.mark.parametrize(
    "response",
    [
        {},
        {
            "protocol_version": True,
            "request_id": "id",
            "message_type": "pong",
            "ok": True,
            "payload": {},
            "error": None,
        },
        {
            "protocol_version": 1,
            "request_id": "id",
            "message_type": "error",
            "ok": False,
            "payload": None,
            "error": None,
        },
    ],
)
def test_malformed_response_models_are_rejected(response: object) -> None:
    with pytest.raises(ProtocolViolationError):
        ResponseEnvelope.from_value(response)
