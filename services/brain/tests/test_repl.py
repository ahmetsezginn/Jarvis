from __future__ import annotations

import json

import pytest

from jarvis_brain import cli
from jarvis_brain.errors import TransportError
from jarvis_brain.intelligence.contract import IntentName


class ReplModel:
    def __init__(self, action):
        self.action = action
        self.load_count = self.step_count = 0
        self.loaded = False

    def load(self):
        if not self.loaded:
            self.load_count += 1
            self.loaded = True

    def unload(self):
        self.loaded = False

    def next_step(self, *args):
        self.step_count += 1
        arguments = {"message": "Merhaba."} if self.action == "answer" else {}
        return json.dumps({"action": self.action, "arguments": arguments, "confidence": 1})

    def authorize_action(self, *args):
        return False


@pytest.mark.parametrize("command", [["ask", "hello"], ["predict", "hello"], ["repl"]])
def test_cli_router_is_opt_in(command):
    assert cli.build_parser().parse_args(command).fast_router is False
    assert cli.build_parser().parse_args([*command, "--fast-router"]).fast_router is True


def test_repl_reuses_model_and_recovers_from_bad_input(monkeypatch, capsys):
    model = ReplModel("answer")

    class Core:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute_tool(self, *_args):
            pytest.fail("unsupported request reached Core")

    inputs = iter(["a\x00b", "a non-action", "another non-action", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "create_agent_model", lambda: model)
    monkeypatch.setattr(cli, "JarvisCoreClient", Core)
    assert cli.run(["repl", "--json"]) == 0
    assert model.load_count == 1
    assert model.step_count == 2
    assert '"intent_validation_failed"' in capsys.readouterr().out


def test_repl_reports_transport_errors_without_code_attribute(monkeypatch, capsys):
    model = ReplModel("system_status")

    class Core:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute_tool(self, *_args):
            raise TransportError("disconnected")

    inputs = iter(["system status", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "create_agent_model", lambda: model)
    monkeypatch.setattr(cli, "JarvisCoreClient", Core)
    assert cli.run(["repl", "--json"]) == 0
    assert '"TransportError"' in capsys.readouterr().out


def test_readable_response_hides_diagnostics_and_json_remains_available(capsys):
    import json

    from jarvis_brain.intelligence.contract import BrainResponse

    response = BrainResponse(
        IntentName.OPEN_APPLICATION, 1, "model", True, "Chrome opened.", {"app_id": "private-id"}
    )
    cli._print_response(response, json_output=False)
    assert capsys.readouterr().out == "JARVIS: Chrome opened.\n"
    cli._print_response(response, json_output=True)
    structured = json.loads(capsys.readouterr().out)
    assert structured["executed"] is True
    assert structured["data"]["app_id"] == "private-id"
