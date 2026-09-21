"""Natural-language E2E with Python network calls denied in-process."""

from __future__ import annotations

import argparse
import os
import socket


class OfflineSocket(socket.socket):
    def connect(self, _address: object) -> None:
        raise OSError("offline E2E denied outbound network access")

    def connect_ex(self, _address: object) -> int:
        raise OSError("offline E2E denied outbound network access")


def _network_denied(*_args: object, **_kwargs: object) -> None:
    raise OSError("offline E2E denied outbound network access")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", action="store_true")
    args = parser.parse_args()
    guard = os.environ.get("JARVIS_NETWORK_GUARD")
    if guard not in {"firewall", "process"}:
        raise SystemExit(
            "run through run_offline_e2e.ps1 so an outbound network guard is active"
        )
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    socket.socket = OfflineSocket
    socket.create_connection = _network_denied  # type: ignore[assignment]
    socket.getaddrinfo = _network_denied  # type: ignore[assignment]
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=0.1)
    except OSError:
        pass
    else:
        raise SystemExit("network guard canary unexpectedly connected")

    if args.session:
        from scripts.tests.session_e2e import main as windows_e2e_main
    else:
        from scripts.tests.windows_e2e import main as windows_e2e_main

    raise SystemExit(windows_e2e_main())
