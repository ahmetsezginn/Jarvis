"""Real Named Pipe E2E for natural-language application and status requests."""

from __future__ import annotations

import json
from dataclasses import asdict

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.intelligence.models.factory import create_intent_model
from jarvis_brain.intelligence.runtime import JarvisBrain


def main() -> int:
    with JarvisCoreClient() as core:
        brain = JarvisBrain(core, create_intent_model())
        application = brain.handle_text(
            "Google Chrome uygulamasını benim için başlatabilir misin?",
            force_model=True,
        )
        status = brain.handle_text("Bilgisayarım nasıl durumda?")
    if not application.executed or not status.executed:
        raise SystemExit("natural-language E2E did not execute both supported actions")
    print(
        json.dumps(
            {"application": asdict(application), "status": asdict(status)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
