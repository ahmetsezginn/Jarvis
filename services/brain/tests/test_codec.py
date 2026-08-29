import json
import struct

import pytest

from jarvis_brain.errors import FrameError, FrameTooLargeError
from jarvis_brain.ipc.codec import MAX_FRAME_SIZE, decode_frame, encode_frame


def test_frame_round_trip_uses_big_endian_length() -> None:
    frame = encode_frame({"message": "merhaba"})
    assert struct.unpack(">I", frame[:4])[0] == len(frame) - 4
    assert decode_frame(frame) == {"message": "merhaba"}


def test_oversized_outgoing_payload_is_rejected() -> None:
    with pytest.raises(FrameTooLargeError):
        encode_frame({"value": "x" * MAX_FRAME_SIZE})


def test_oversized_incoming_length_is_rejected_without_body() -> None:
    with pytest.raises(FrameTooLargeError):
        decode_frame(struct.pack(">I", MAX_FRAME_SIZE + 1))


@pytest.mark.parametrize(
    "frame",
    [
        b"\x00\x00",
        struct.pack(">I", 0),
        struct.pack(">I", 10) + b"short",
        struct.pack(">I", 2) + b"{}trailing",
    ],
)
def test_invalid_and_truncated_frames_are_rejected(frame: bytes) -> None:
    with pytest.raises(FrameError):
        decode_frame(frame)


def test_malformed_utf8_or_json_response_is_rejected() -> None:
    for payload in (b"\xff", b"{not-json", json.dumps([]).encode()):
        frame = struct.pack(">I", len(payload)) + payload
        with pytest.raises(FrameError):
            decode_frame(frame)
