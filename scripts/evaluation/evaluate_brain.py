"""Evaluate current intent interfaces without constructing a Core client."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path

from jarvis_brain import config
from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import (
    IntentName,
    IntentResult,
    validate_intent_object,
)
from jarvis_brain.intelligence.fast_router import FastIntentRouter
from jarvis_brain.intelligence.models.factory import create_intent_model
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel
from jarvis_brain.intelligence.runtime import JarvisBrain

from scripts.benchmarks.benchmark_intents import _memory_bytes

DATASET = Path(__file__).with_name("brain_cases.json")


class NoCore:
    def execute_tool(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("Evaluation must never execute a Core request")


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not data.get("cases"):
        raise ValueError("Expected nonempty version-1 cases")
    ids = set()
    for case in data["cases"]:
        if case["id"] in ids:
            raise ValueError("Duplicate case ID")
        ids.add(case["id"])
        if case["split"] not in {"regression", "diagnostic"}:
            raise ValueError("Unknown split")
        if case["language"] not in {"tr", "en"}:
            raise ValueError("Unknown language")
        if not isinstance(case["text"], str) or not case["text"].strip():
            raise ValueError("Empty input")
        if type(case["requires_context"]) is not bool:
            raise ValueError("requires_context must be boolean")
        if not all(isinstance(case[k], list) for k in ("history", "catalog")):
            raise ValueError("Context must use lists")
        expected = case["expected"]
        if expected["intent"] not in {
            "open_application",
            "system_status",
            "clarify",
            "unsupported",
        }:
            raise ValueError("Unknown expected intent")
        queries = expected["queries"]
        if not isinstance(queries, list) or not all(
            isinstance(q, str) and q.strip() for q in queries
        ):
            raise ValueError("Invalid expected queries")
        if bool(queries) != (expected["intent"] == "open_application"):
            raise ValueError("Only application cases need accepted queries")
    return data["cases"]


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def score(result: IntentResult, expected: dict) -> tuple[bool, bool]:
    result = validate_intent_object(
        {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "arguments": dict(result.arguments),
        },
        model_output=True,
    )
    match = result.intent.value == expected["intent"]
    if result.intent.value == "open_application":
        match = match and normalized(str(result.arguments["query"])) in {
            normalized(q) for q in expected["queries"]
        }
    actionable = result.intent.value in {"open_application", "system_status"}
    allowed = actionable and result.confidence >= config.MIN_INTENT_CONFIDENCE
    return match and (not actionable or allowed), allowed and not match


def percentile(values: list[float], fraction: float) -> float | None:
    return (
        sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]
        if values
        else None
    )


def evaluate(cases: list[dict], mode: str, backend: str = "onnx") -> dict:
    model = (
        (QwenOnnxIntentModel() if backend == "onnx" else create_intent_model(backend))
        if mode != "router"
        else FakeIntentModel(IntentResult(IntentName.UNSUPPORTED, 1.0, {}))
    )
    brain = JarvisBrain(NoCore(), model)
    router = FastIntentRouter()
    idle_memory = _memory_bytes()
    load_ms = None
    if mode != "router":
        start = time.perf_counter()
        model.load()
        load_ms = (time.perf_counter() - start) * 1000
    loaded_memory = _memory_bytes()
    rows = []
    for case in cases:
        row = {
            "id": case["id"],
            "split": case["split"],
            "language": case["language"],
            "capability": case["capability"],
            "correct": False,
            "wrong_action_proposal": False,
            "status": "unsupported_context_interface",
        }
        if not case["requires_context"]:
            start = time.perf_counter()
            try:
                # No expected label, history or catalog is injected into the current interface.
                if mode == "router":
                    result, route = router.route(case["text"]), "fast"
                else:
                    result, route = brain.predict_intent(
                        case["text"], force_model=mode == "model"
                    )
                row["route"] = route
                row["status"] = "fallback" if result is None else "predicted"
                if result is not None:
                    row["correct"], row["wrong_action_proposal"] = score(
                        result, case["expected"]
                    )
                    row["prediction"] = {
                        "intent": result.intent.value,
                        "arguments": dict(result.arguments),
                        "confidence": result.confidence,
                    }
            except JarvisBrainError as error:
                row["status"] = type(error).__name__
                row["error"] = str(error)
            finally:
                row["elapsed_ms"] = (time.perf_counter() - start) * 1000
        rows.append(row)
    groups = defaultdict(lambda: {"correct": 0, "total": 0})
    for row in rows:
        for dimension in ("split", "language", "capability"):
            group = groups[f"{dimension}:{row[dimension]}"]
            group["correct"] += int(row["correct"])
            group["total"] += 1
    times = [r["elapsed_ms"] for r in rows if "elapsed_ms" in r]
    return {
        "mode": mode,
        "total": len(rows),
        "attempted": len(times),
        "correct": sum(r["correct"] for r in rows),
        "wrong_action_proposals": sum(r["wrong_action_proposal"] for r in rows),
        "load_ms": load_ms,
        "memory": {
            "idle_rss_bytes": idle_memory[0],
            "loaded_rss_bytes": loaded_memory[0],
            "peak_rss_bytes": _memory_bytes()[1],
        },
        "request_ms": {
            "p50": percentile(times, 0.5),
            "p95": percentile(times, 0.95),
            "max": max(times) if times else None,
        },
        "groups": dict(groups),
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument(
        "--mode", choices=["router", "model", "combined"], default="router"
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--backend", choices=["onnx", "gguf"], default="onnx")
    parser.add_argument("--output", type=Path, help="write generated measurement JSON")
    args = parser.parse_args()
    cases = load_cases(args.dataset)
    if args.validate_only:
        print(f"Validated {len(cases)} cases")
        return 0
    report = evaluate(cases, args.mode, args.backend)
    report["backend"] = args.backend
    report["dataset_sha256"] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    report["model_id"] = config.MODEL_ID
    report["model_revision"] = config.MODEL_REVISION
    report["runtime_version"] = config.ONNXRUNTIME_GENAI_VERSION
    if args.backend == "gguf":
        from jarvis_brain.intelligence.models import qwen_gguf

        report["model_id"] = qwen_gguf.MODEL_ID
        report["model_revision"] = qwen_gguf.MODEL_REVISION
        report["runtime_version"] = qwen_gguf.RUNTIME_VERSION
        report["prompt_adapter_sha256"] = hashlib.sha256(
            Path(qwen_gguf.__file__).read_bytes()
        ).hexdigest()
    report["prompt_sha256"] = hashlib.sha256(
        (
            Path(__file__).parents[2]
            / "services/brain/src/jarvis_brain/intelligence/prompts.py"
        ).read_bytes()
    ).hexdigest()
    report["scope"] = (
        "Intent diagnostic only; no Core, no OS actions; context unsupported"
    )
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0  # Completed measurement; this is not a product release-gate verdict.


if __name__ == "__main__":
    raise SystemExit(main())
