"""Development CLI for the local Brain and trusted Core bridge."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from jarvis_brain.core.client import JarvisCoreClient, open_application
from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import BrainResponse
from jarvis_brain.intelligence.models.factory import create_agent_model
from jarvis_brain.intelligence.runtime import JarvisBrain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS local Brain development client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ping", help="perform handshake and ping the Rust Core")
    commands.add_parser("tools", help="list tool metadata from the Rust registry")
    commands.add_parser("status", help="execute the Rust system_status tool")
    open_app = commands.add_parser("open-app", help="resolve and open a catalog application")
    open_app.add_argument("query")
    tool = commands.add_parser("tool", help="execute one structured registered Rust tool")
    tool.add_argument("name")
    tool.add_argument("arguments", help="JSON object containing typed tool arguments")
    ask = commands.add_parser(
        "ask", help="understand and safely execute a natural-language command"
    )
    ask.add_argument("text")
    ask.add_argument("--force-model", action="store_true")
    repl = commands.add_parser("repl", help="interactive session retaining the loaded local model")
    for command in (ask, repl):
        command.add_argument("--json", action="store_true", help="show structured diagnostics")
    commands.add_parser("model-info", help="show local artifact and lazy model state")
    predict = commands.add_parser("predict", help="validate intent inference without executing it")
    predict.add_argument("--force-model", action="store_true", help="bypass only the Fast Router")
    predict.add_argument("text")
    for command in (ask, repl, predict):
        command.add_argument(
            "--fast-router",
            action="store_true",
            help="legacy routing for predict diagnostics; execution remains model-gated",
        )
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(arguments)
    model = create_agent_model()
    if parsed.command == "model-info":
        _print_json(model.model_info())
        return 0
    if parsed.command == "predict":
        brain = JarvisBrain(_NoExecutionCore(), model, fast_router_enabled=parsed.fast_router)
        result, route = brain.predict_intent(parsed.text, force_model=parsed.force_model)
        _print_json(
            {
                "intent": result.intent.value,
                "confidence": result.confidence,
                "arguments": dict(result.arguments),
                "route": route,
                "model": model.model_info(),
            }
        )
        return 0

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
        elif parsed.command == "ask":
            response = JarvisBrain(core, model, fast_router_enabled=parsed.fast_router).handle_text(
                parsed.text, force_model=parsed.force_model
            )
            _print_response(response, json_output=parsed.json)
        elif parsed.command == "repl":
            brain = JarvisBrain(core, model, fast_router_enabled=parsed.fast_router)
            print(f"Model: {type(model).__name__}; Agent loop: ON; tool feedback: ON")
            print("JARVIS ready. exit: quit; /reset: clear session context.")
            try:
                while True:
                    try:
                        text = input("JARVIS: ")
                    except (EOFError, KeyboardInterrupt):
                        break
                    if text.strip().casefold() in {"exit", "quit", "çık", "cik"}:
                        break
                    if not text.strip():
                        continue
                    try:
                        _print_response(brain.handle_text(text), json_output=parsed.json)
                    except JarvisBrainError as error:
                        code = getattr(error, "code", type(error).__name__)
                        if parsed.json:
                            _print_json(
                                {"ok": False, "error": {"code": code, "message": str(error)}}
                            )
                        else:
                            print(f"JARVIS: [{code}] {error}")
            finally:
                model.unload()
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


def _print_response(response: BrainResponse, *, json_output: bool) -> None:
    if json_output:
        _print_json(asdict(response))
    else:
        print(f"JARVIS: {response.message}")


def _print_json(value: Any, *, stream: Any = None) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream or sys.stdout)


class _NoExecutionCore:
    def execute_tool(self, _tool: str, _arguments: dict[str, Any]) -> Any:
        raise AssertionError("predict must never execute a Core tool")


if __name__ == "__main__":
    raise SystemExit(main())
