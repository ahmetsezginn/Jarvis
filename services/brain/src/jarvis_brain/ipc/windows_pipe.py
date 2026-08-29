"""Local-only Windows Named Pipe transport used to reach the Rust Core."""

from __future__ import annotations

import ctypes
import struct
import sys
import time
from ctypes import wintypes

from jarvis_brain.errors import (
    ConnectTimeoutError,
    DisconnectedError,
    FrameError,
    FrameTooLargeError,
    RequestTimeoutError,
    TransportError,
)
from jarvis_brain.ipc.codec import HEADER_SIZE, MAX_FRAME_SIZE

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
SECURITY_SQOS_PRESENT = 0x00100000
SECURITY_IDENTIFICATION = 0x00010000
TOKEN_QUERY = 0x0008
TOKEN_USER_CLASS = 1
ERROR_FILE_NOT_FOUND = 2
ERROR_BROKEN_PIPE = 109
ERROR_PIPE_BUSY = 231
ERROR_NO_DATA = 232
ERROR_PIPE_NOT_CONNECTED = 233
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("user", _SidAndAttributes)]


def _windows_libraries() -> tuple[ctypes.WinDLL, ctypes.WinDLL]:
    if sys.platform != "win32":
        raise TransportError("Windows Named Pipes are supported only on Windows")
    return ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL(
        "advapi32", use_last_error=True
    )


def current_user_sid() -> str:
    kernel32, advapi32 = _windows_libraries()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
    ):
        raise TransportError(
            f"could not open current process token: {ctypes.WinError(ctypes.get_last_error())}"
        )
    try:
        required = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, None, 0, ctypes.byref(required))
        if required.value == 0:
            raise TransportError(
                f"could not size current-user token: {ctypes.WinError(ctypes.get_last_error())}"
            )
        buffer = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token,
            TOKEN_USER_CLASS,
            buffer,
            required,
            ctypes.byref(required),
        ):
            raise TransportError(
                f"could not read current-user token: {ctypes.WinError(ctypes.get_last_error())}"
            )
        token_user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
        string_sid = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(token_user.user.sid, ctypes.byref(string_sid)):
            raise TransportError(
                f"could not convert current-user SID: {ctypes.WinError(ctypes.get_last_error())}"
            )
        try:
            return str(string_sid.value)
        finally:
            kernel32.LocalFree(ctypes.cast(string_sid, wintypes.HLOCAL))
    finally:
        kernel32.CloseHandle(token)


def current_user_pipe_endpoint() -> str:
    return rf"\\.\pipe\jarvis-core-{current_user_sid()}-v1"


class WindowsNamedPipeTransport:
    """Persistent synchronous pipe with deadline-based response polling."""

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or current_user_pipe_endpoint()
        if not self.endpoint.startswith(r"\\.\pipe\jarvis-core-S-1-") or not self.endpoint.endswith(
            "-v1"
        ):
            raise TransportError("pipe endpoint does not match the trusted JARVIS per-user format")
        self._handle: int | None = None
        self._kernel32: ctypes.WinDLL | None = None

    def connect(self, timeout: float) -> None:
        if self._handle is not None:
            return
        if timeout <= 0:
            raise ConnectTimeoutError("connect timeout must be positive")
        kernel32, _ = _windows_libraries()
        self._configure_api(kernel32)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ConnectTimeoutError(f"timed out connecting to {self.endpoint}")
            wait_ms = max(1, min(int(remaining * 1000), 250))
            if kernel32.WaitNamedPipeW(self.endpoint, wait_ms):
                handle = kernel32.CreateFileW(
                    self.endpoint,
                    GENERIC_READ | GENERIC_WRITE,
                    0,
                    None,
                    OPEN_EXISTING,
                    SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION,
                    None,
                )
                if handle != INVALID_HANDLE_VALUE:
                    self._kernel32 = kernel32
                    self._handle = handle
                    return
            error = ctypes.get_last_error()
            if error not in (ERROR_FILE_NOT_FOUND, ERROR_PIPE_BUSY):
                raise TransportError(f"could not connect to Core pipe: {ctypes.WinError(error)}")
            time.sleep(min(0.01, remaining))

    def send(self, frame: bytes) -> None:
        handle, kernel32 = self._connected()
        view = memoryview(frame)
        total = 0
        while total < len(view):
            written = wintypes.DWORD()
            chunk = view[total:]
            buffer = (ctypes.c_ubyte * len(chunk)).from_buffer_copy(chunk)
            if not kernel32.WriteFile(handle, buffer, len(chunk), ctypes.byref(written), None):
                self._raise_io("write")
            if written.value == 0:
                raise DisconnectedError("Core pipe closed during write")
            total += written.value

    def receive(self, timeout: float) -> bytes:
        if timeout <= 0:
            raise RequestTimeoutError("request timeout must be positive")
        deadline = time.monotonic() + timeout
        self._wait_for_available(HEADER_SIZE, deadline)
        header = self._read_exact(HEADER_SIZE)
        (payload_length,) = struct.unpack(">I", header)
        if payload_length == 0:
            raise FrameError("zero-length payloads are not valid control messages")
        if payload_length > MAX_FRAME_SIZE:
            raise FrameTooLargeError(
                f"frame payload of {payload_length} bytes exceeds the {MAX_FRAME_SIZE} byte limit"
            )
        self._wait_for_available(payload_length, deadline)
        return header + self._read_exact(payload_length)

    def close(self) -> None:
        if self._handle is not None and self._kernel32 is not None:
            self._kernel32.CloseHandle(self._handle)
        self._handle = None
        self._kernel32 = None

    def _wait_for_available(self, minimum: int, deadline: float) -> None:
        handle, kernel32 = self._connected()
        while True:
            available = wintypes.DWORD()
            if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                self._raise_io("read")
            if available.value >= minimum:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RequestTimeoutError("timed out waiting for Core response")
            time.sleep(min(0.01, remaining))

    def _read_exact(self, size: int) -> bytes:
        handle, kernel32 = self._connected()
        output = bytearray()
        while len(output) < size:
            requested = size - len(output)
            buffer = (ctypes.c_ubyte * requested)()
            read = wintypes.DWORD()
            if not kernel32.ReadFile(handle, buffer, requested, ctypes.byref(read), None):
                self._raise_io("read")
            if read.value == 0:
                raise DisconnectedError("Core pipe closed during read")
            output.extend(buffer[: read.value])
        return bytes(output)

    def _connected(self) -> tuple[int, ctypes.WinDLL]:
        if self._handle is None or self._kernel32 is None:
            raise DisconnectedError("Core pipe is not connected")
        return self._handle, self._kernel32

    def _raise_io(self, operation: str) -> None:
        error = ctypes.get_last_error()
        self.close()
        if error in (ERROR_BROKEN_PIPE, ERROR_NO_DATA, ERROR_PIPE_NOT_CONNECTED):
            raise DisconnectedError(f"Core pipe disconnected during {operation}")
        raise TransportError(f"Core pipe {operation} failed: {ctypes.WinError(error)}")

    @staticmethod
    def _configure_api(kernel32: ctypes.WinDLL) -> None:
        kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        kernel32.WaitNamedPipeW.restype = wintypes.BOOL
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.ReadFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.WriteFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        kernel32.WriteFile.restype = wintypes.BOOL
        kernel32.PeekNamedPipe.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.PeekNamedPipe.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
