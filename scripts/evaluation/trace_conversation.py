"""Explicit opt-in recording of a fixed regression conversation; mocked Core only."""

import argparse
import hashlib
import json
from pathlib import Path

from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import ConversationTurn, IntentContext
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel
from jarvis_brain.intelligence.request_routing import GGUF_ROUTE_PROMPT, REPLY_PROMPT
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult

TRANSCRIPT = (
    ("nasılsın", "Teşekkür ederim, iyiyim! Size nasıl yardımcı olabilirim?"),
    (
        "ne yapabilirsin",
        "Bilgi verme, planlama, görevlerinizi takip etme gibi işler yapabilirim.",
    ),
    ("uygulama açabilir misin", "Uygulama açma işlemi desteklenmiyor."),
    ("crome u açar mısın", "Chrome uygulamasını açma işlemi desteklenmiyor."),
    (
        "google chromu u açar mısın",
        "Google Chrome uygulamasını açma işlemi desteklenmiyor.",
    ),
    ("sistem status ü mü söyler misin", "Sistem durumu bilgisi verilemiyor."),
)


class RecordingModel:
    def __init__(self, model):
        self.model = model
        self.events = []

    def load(self):
        self.model.load()

    def classify_request(self, text, context):
        result = self.model.classify_request(text, context)
        self.events.append(
            {
                "stage": "admission",
                "kind": result.kind.value,
                "confidence": result.confidence,
                "history_pairs": len(context.history),
            }
        )
        return result

    def predict(self, text, context):
        result = self.model.predict(text, context)
        self.events.append(
            {
                "stage": "intent",
                "intent": result.intent.value,
                "confidence": result.confidence,
                "arguments": dict(result.arguments),
            }
        )
        return result

    def respond(self, text, context):
        reply = self.model.respond(text, context)
        self.events.append({"stage": "reply", "message": reply})
        return reply


class MockCore:
    def __init__(self):
        self.calls = []

    def execute_tool(self, tool, arguments):
        # Never record trusted IDs or raw payloads. No real Core connection exists.
        self.calls.append(tool)
        if tool == "resolve_app":
            data = {"app": {"app_id": "diagnostic-only", "name": "Google Chrome"}}
        elif tool == "open_app":
            data = {"name": "Google Chrome", "opened": True}
        else:
            data = {"cpu_usage_percent": 12, "memory": {"usage_percent": 50}}
        return ToolResult("diagnostic", tool, "success", data, None)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model = QwenGgufIntentModel()
    recorder = RecordingModel(model)
    core = MockCore()
    brain = JarvisBrain(core, recorder, fast_router_enabled=False)
    report = {
        "model": type(model).__name__,
        "mock_core": True,
        "prompt_sha256": hashlib.sha256(
            (GGUF_ROUTE_PROMPT + REPLY_PROMPT).encode()
        ).hexdigest(),
        "probes": [],
        "conversation": [],
    }
    try:
        model.load()
        for index, (text, _) in enumerate(TRANSCRIPT):
            history = tuple(ConversationTurn(*pair) for pair in TRANSCRIPT[:index])
            for label, context in (
                ("fresh", IntentContext()),
                ("reported_history", IntentContext(history=history)),
            ):
                route = model.classify_request(text, context)
                report["probes"].append(
                    {
                        "text": text,
                        "context": label,
                        "kind": route.kind.value,
                        "confidence": route.confidence,
                    }
                )
        for text, _ in TRANSCRIPT:
            recorder.events.clear()
            core.calls.clear()
            try:
                result = brain.handle_text(text)
                row = {
                    "text": text,
                    "route": result.route,
                    "intent": result.intent.value,
                    "executed_mock": result.executed,
                    "message": result.message,
                }
            except JarvisBrainError as error:
                row = {"text": text, "error": type(error).__name__}
            row.update(events=list(recorder.events), tools=list(core.calls))
            report["conversation"].append(row)
    finally:
        model.unload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    run()
