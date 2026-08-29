"""Non-AI development CLI for validating the local Core bridge."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from jarvis_brain.core.client import JarvisCoreClient, open_application
from jarvis_brain.errors import JarvisBrainError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS Core IPC development client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ping", help="perform handshake and ping the Rust Core")
    commands.add_parser("tools", help="list tool metadata from the Rust registry")
    commands.add_parser("status", help="execute the Rust system_status tool")
    open_app = commands.add_parser("open-app", help="resolve and open a catalog application")
    open_app.add_argument("query")
    tool = commands.add_parser("tool", help="execute one structured registered Rust tool")
    tool.add_argument("name")
    tool.add_argument("arguments", help="JSON object containing typed tool arguments")
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(arguments)
    with JarvisCoreClient() as core:
        if parsed.command == "ping":
            print(core.ping())
        elif parsed.command == "tools":
            _print_json([asdict(tool) for tool in core.list_tools()])
        elif parsed.command == "status":
            _print_json(asdict(core.execute_tool("system_status", {})))
        elif parsed.command == "open-app":
            _print_json(asdict(open_application(core, parsed.query)))
        elif parsed.command == "tool":
            tool_arguments = _json_object(parsed.arguments)
            _print_json(asdict(core.execute_tool(parsed.name, tool_arguments)))
        else:
            raise AssertionError(f"unhandled command: {parsed.command}")
    return 0


def main() -> int:
    try:
        return run()
    except (JarvisBrainError, TypeError, ValueError) as error:
        details = getattr(error, "details", None)
        _print_json(
            {
                "ok": False,
                "error": {
                    "code": getattr(error, "code", error.__class__.__name__),
                    "message": str(error),
                    "details": details,
                },
            },
            stream=sys.stderr,
        )
        return 1


def _json_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("tool arguments must be a JSON object")
    return decoded


def _print_json(value: Any, *, stream: Any = sys.stdout) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream)


if __name__ == "__main__":
    raise SystemExit(main())
