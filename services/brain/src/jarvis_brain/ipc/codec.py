"""Big-endian length-prefixed UTF-8 JSON control frames."""

from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from typing import Any

from jarvis_brain.errors import FrameError, FrameTooLargeError

MAX_FRAME_SIZE = 1024 * 1024
HEADER_SIZE = 4


def encode_frame(message: Mapping[str, Any]) -> bytes:
    try:
        payload = json.dumps(dict(message), ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as error:
        raise FrameError(f"message is not JSON serializable: {error}") from error
    if not payload:
        raise FrameError("zero-length payloads are not valid control messages")
    if len(payload) > MAX_FRAME_SIZE:
        raise FrameTooLargeError(
            f"frame payload of {len(payload)} bytes exceeds the {MAX_FRAME_SIZE} byte limit"
        )
    return struct.pack(">I", len(payload)) + payload


def decode_frame(frame: bytes) -> dict[str, Any]:
    if len(frame) < HEADER_SIZE:
        raise FrameError("truncated length prefix")
    (declared_length,) = struct.unpack(">I", frame[:HEADER_SIZE])
    if declared_length == 0:
        raise FrameError("zero-length payloads are not valid control messages")
    if declared_length > MAX_FRAME_SIZE:
        raise FrameTooLargeError(
            f"frame payload of {declared_length} bytes exceeds the {MAX_FRAME_SIZE} byte limit"
        )
    payload = frame[HEADER_SIZE:]
    if len(payload) != declared_length:
        raise FrameError(
            f"frame length mismatch: declared {declared_length} bytes, received {len(payload)}"
        )
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FrameError(f"payload must be valid UTF-8 JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise FrameError("control message must be a JSON object")
    return decoded
