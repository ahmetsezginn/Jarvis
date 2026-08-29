"""Typed Brain-side transport and protocol failures."""

from __future__ import annotations

from typing import Any


class JarvisBrainError(Exception):
    """Base class for expected Brain client errors."""


class TransportError(JarvisBrainError):
    """The local IPC transport failed."""


class ConnectTimeoutError(TransportError):
    """The Core pipe was unavailable until the connect deadline."""


class RequestTimeoutError(TransportError):
    """The Core did not produce a response before the request deadline."""


class DisconnectedError(TransportError):
    """The Named Pipe connection was closed."""


class FrameError(JarvisBrainError):
    """A control frame violated the framing contract."""


class FrameTooLargeError(FrameError):
    """A control frame exceeded the hard limit."""


class ProtocolViolationError(JarvisBrainError):
    """A response did not satisfy the versioned protocol contract."""


class CoreResponseError(JarvisBrainError):
    """The Rust Core returned a typed protocol-level error."""

    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


class CoreToolError(CoreResponseError):
    """The existing Rust executor returned a typed tool failure."""
