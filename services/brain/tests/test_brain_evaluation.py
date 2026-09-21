from __future__ import annotations

import copy
import json

import pytest
from scripts.evaluation.evaluate_brain import DATASET, NoCore, evaluate, load_cases, score

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.contract import IntentName, IntentResult


def test_dataset_has_context_and_both_languages() -> None:
    cases = load_cases(DATASET)
    assert len(cases) == 36
    assert {c["language"] for c in cases} == {"tr", "en"}
    assert sum(c["requires_context"] for c in cases) == 8


def test_wrong_application_and_low_confidence_do_not_pass() -> None:
    expected = {"intent": "open_application", "queries": ["Visual Studio"]}
    wrong = IntentResult(IntentName.OPEN_APPLICATION, 1, {"query": "Visual Studio Code"})
    low = IntentResult(IntentName.OPEN_APPLICATION, 0.1, {"query": "Visual Studio"})
    assert score(wrong, expected) == (False, True)
    assert score(low, expected) == (False, False)


def test_invalid_model_keys_cannot_pass_scoring() -> None:
    result = IntentResult(IntentName.OPEN_APPLICATION, 1, {"app_id": "app_fake"})
    with pytest.raises(ModelOutputInvalid):
        score(result, {"intent": "open_application", "queries": ["Calculator"]})


def test_context_gaps_remain_in_denominator() -> None:
    case = next(c for c in load_cases(DATASET) if c["requires_context"])
    result = evaluate([case], "router")
    assert result["total"] == 1
    assert result["attempted"] == 0
    assert result["correct"] == 0
    assert result["results"][0]["status"] == "unsupported_context_interface"


def test_expected_answer_does_not_influence_prediction() -> None:
    case = next(c for c in load_cases(DATASET) if c["id"] == "d02")
    modified = copy.deepcopy(case)
    modified["expected"]["queries"] = ["NeverSentToModel"]
    left = evaluate([case], "router")["results"][0]
    right = evaluate([modified], "router")["results"][0]
    assert left["prediction"] == right["prediction"]
    assert left["correct"] and not right["correct"]


def test_duplicate_case_ids_are_rejected(tmp_path) -> None:
    case = load_cases(DATASET)[0]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"schema_version": 1, "cases": [case, case]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(path)


def test_evaluation_core_has_no_action_path() -> None:
    with pytest.raises(AssertionError):
        NoCore().execute_tool("open_app", {"app_id": "app_fake"})


def test_model_receives_only_user_text_and_failures_keep_latency(monkeypatch) -> None:
    from scripts.evaluation import evaluate_brain

    seen = []

    class FailingModel:
        def load(self):
            pass

        def predict(self, text, context):
            seen.append(text)
            raise ModelOutputInvalid("test malformed output")

    monkeypatch.setattr(evaluate_brain, "QwenOnnxIntentModel", FailingModel)
    case = next(c for c in load_cases(DATASET) if c["id"] == "d02")
    result = evaluate([case], "model")
    assert seen == [case["text"]]
    assert result["correct"] == 0
    assert result["attempted"] == 1
    assert result["results"][0]["status"] == "ModelOutputInvalid"
    assert result["results"][0]["elapsed_ms"] >= 0
