"""Opt-in app interpretation and live Rust resolution probe; never launches applications."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import ConversationTurn, IntentContext
from jarvis_brain.intelligence.models.factory import create_intent_model

CASES = (
    ("bana antigravity idle uygulamasını açar mısın", "Antigravity"),
    ("Antigravity uygulamasını aç", "Antigravity"),
    ("Antigravity IDE uygulamasını açar mısın", "Antigravity"),
    ("omen gaming hub uygulamasını açar mısın", "Omen Gaming Hub"),
    ("OMEN Gaming Hub aç", "OMEN"),
    ("peki chat gpt masa üstü uygulamasını açar mısın", "ChatGPT"),
    ("ChatGPT uygulamasını aç", "ChatGPT"),
    ("Steam uygulamasını aç", "Steam"),
    ("Chrome nedir?", None),
    ("Steam'i açma", None),
)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model = create_intent_model()
    report = {"model": type(model).__name__, "launches": 0, "cases": []}
    try:
        model.load()
        with JarvisCoreClient() as core:
            for text, query in CASES:
                row = {"text": text, "probes": []}
                for label, context in (
                    ("fresh", IntentContext()),
                    (
                        "after_refusal",
                        IntentContext(
                            history=(
                                ConversationTurn(
                                    "uygulama açabilir misin",
                                    "Uygulama açma işlemi desteklenmiyor.",
                                ),
                            )
                        ),
                    ),
                ):
                    try:
                        route = model.classify_request(text, context)
                        intent = model.predict(text, context)
                        probe = {
                            "context": label,
                            "admission": asdict(route),
                            "intent": intent.intent.value,
                            "confidence": intent.confidence,
                            "arguments": dict(intent.arguments),
                        }
                    except JarvisBrainError as error:
                        probe = {"context": label, "error": type(error).__name__}
                    row["probes"].append(probe)
                if query:
                    try:
                        result = core.execute_tool("resolve_app", {"query": query})
                        row["catalog"] = {
                            "query": query,
                            "status": result.status,
                            "name": result.data.get("app", {}).get("name"),
                        }
                    except JarvisBrainError as error:
                        row["catalog"] = {
                            "query": query,
                            "error": getattr(error, "code", type(error).__name__),
                        }
                report["cases"].append(row)
                print(json.dumps(row, ensure_ascii=True), flush=True)
    finally:
        model.unload()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    run()
