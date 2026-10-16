"""Counterexample to the existing file-goal test oracle; no inference, IPC or OS actions."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import runpy
from pathlib import Path

from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.dialogue import TurnPlan
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.request_routing import (
    RequestKind,
    RequestPurpose,
    RequestRoute,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    suite = runpy.run_path(
        str(repository / "services/brain/tests/integration/test_natural_file_goals.py")
    )
    result = {}
    for name, query in [("blind_wildcard", "*"), ("stale_previous_query", "cv")]:
        model = FakeIntentModel(
            IntentResult(
                IntentName.SEARCH_FILES,
                1,
                {"query": query, "sort": "name", "extension": "", "kind": "file"},
            ),
            request_route=RequestRoute(RequestKind.TASK, 1, RequestPurpose.LOCATE_FILE),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                suite["test_everyday_file_goals_across_domains"](model)
            except AssertionError:
                result[name + "_rejected"] = True
            else:
                result[name + "_rejected"] = False

    from scripts.evaluation.analyze_file_assistance import SyntheticCore

    class ScopeBlindCore(SyntheticCore):
        def execute_tool(self, tool, arguments):
            arguments = dict(arguments)
            arguments.pop("folder_id", None)
            arguments.pop("recursive", None)
            return super().execute_tool(tool, arguments)

    class ScopeModel:
        def load(self):
            pass

        def plan_turn(self, *_args):
            return TurnPlan(
                "file",
                1,
                {
                    "relation": "new",
                    "operation": "find",
                    "query": "",
                    "kind": "file",
                    "category": "text",
                    "location": "Masaüstü",
                    "depth": "direct",
                    "extension": "",
                    "sort": "name",
                    "name_unknown": True,
                    "application": "",
                },
            )

    dialogue = runpy.run_path(
        str(repository / "services/brain/tests/integration/test_assistant_scenarios.py")
    )
    dialogue["runtime"].__globals__["SyntheticCore"] = ScopeBlindCore
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            dialogue[
                "test_unknown_name_scope_rejection_and_identification_do_not_open"
            ](ScopeModel())
        except AssertionError:
            result["ignored_scope_rejected"] = True
        else:
            result["ignored_scope_rejected"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if not all(result.values()):
        raise AssertionError(
            "A deliberately faulty control passed an acceptance oracle"
        )


if __name__ == "__main__":
    main()
