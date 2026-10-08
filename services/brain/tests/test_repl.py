from __future__ import annotations

import pytest

from jarvis_brain import cli
from jarvis_brain.errors import TransportError
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.models.fake import FakeIntentModel


@pytest.mark.parametrize("command", [["ask", "hello"], ["predict", "hello"], ["repl"]])
def test_cli_router_is_opt_in(command):
    assert cli.build_parser().parse_args(command).fast_router is False
    assert cli.build_parser().parse_args([*command, "--fast-router"]).fast_router is True


def test_repl_reuses_model_and_recovers_from_bad_input(monkeypatch, capsys):
    model = FakeIntentModel(IntentResult(IntentName.UNSUPPORTED, 1, {}))

    class Core:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute_tool(self, *_args):
            pytest.fail("unsupported request reached Core")

    inputs = iter(["a\x00b", "a non-action", "another non-action", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "create_intent_model", lambda: model)
    monkeypatch.setattr(cli, "JarvisCoreClient", Core)
    assert cli.run(["repl", "--json"]) == 0
    assert model.load_count == 1
    assert model.predict_count == 2
    assert '"intent_validation_failed"' in capsys.readouterr().out


def test_repl_reports_transport_errors_without_code_attribute(monkeypatch, capsys):
    model = FakeIntentModel(IntentResult(IntentName.SYSTEM_STATUS, 1, {}))

    class Core:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute_tool(self, *_args):
            raise TransportError("disconnected")

    inputs = iter(["system status", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(cli, "create_intent_model", lambda: model)
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
