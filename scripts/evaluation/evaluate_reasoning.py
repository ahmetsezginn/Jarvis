"""Non-executing reasoning diagnostic; exposed regression cases, not a release benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from jarvis_brain import config
from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import ConversationTurn, IntentContext
from jarvis_brain.intelligence.models.factory import create_intent_model
from jarvis_brain.intelligence.prompts import (
    CONTEXT_PROMPT,
    REASONING_PROMPT,
    SYSTEM_PROMPT,
)


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    cases = json.loads(
        Path(__file__).with_name("reasoning_cases.json").read_text(encoding="utf-8")
    )["cases"]
    model = create_intent_model()
    results = []
    try:
        model.load()
        for case in cases:
            context = IntentContext(
                history=tuple(ConversationTurn(**t) for t in case["history"])
            )
            started = time.perf_counter()
            try:
                result = model.predict(case["text"], context)
                correct = result.intent.value == case["expected"]
                if result.intent.value in {"open_application", "system_status"}:
                    correct = (
                        correct and result.confidence >= config.MIN_INTENT_CONFIDENCE
                    )
                if "queries" in case:
                    correct = correct and str(
                        result.arguments.get("query", "")
                    ).casefold() in {q.casefold() for q in case["queries"]}
                row = {
                    "id": case["id"],
                    "intent": result.intent.value,
                    "arguments": dict(result.arguments),
                    "correct": correct,
                }
            except JarvisBrainError as error:
                row = {
                    "id": case["id"],
                    "error": type(error).__name__,
                    "correct": False,
                }
            row["ms"] = round((time.perf_counter() - started) * 1000)
            results.append(row)
    finally:
        model.unload()
    report = {
        "results": results,
        "correct": sum(r["correct"] for r in results),
        "total": len(results),
        "prompt_sha256": hashlib.sha256(
            (
                (
                    REASONING_PROMPT
                    if type(model).__name__ == "QwenGgufIntentModel"
                    else SYSTEM_PROMPT
                )
                + CONTEXT_PROMPT
            ).encode()
        ).hexdigest(),
        "model": type(model).__name__,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    run()
