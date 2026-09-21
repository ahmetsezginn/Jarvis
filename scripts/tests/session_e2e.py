"""Opt-in real Steam ambiguity -> ordinal selection through the existing Windows Core."""

import json
from dataclasses import asdict

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.intelligence.models.factory import create_intent_model
from jarvis_brain.intelligence.runtime import JarvisBrain


def main():
    model = create_intent_model("gguf")
    try:
        with JarvisCoreClient() as core:
            brain = JarvisBrain(core, model, fast_router_enabled=False)
            first = brain.handle_text("Steam'i aç")
            assert (
                not first.executed and first.data and len(first.data["candidates"]) >= 2
            )
            expected = first.data["candidates"][0]["app_id"]
            second = brain.handle_text("üstteki")
            assert second.executed and second.route == "session"
            assert second.data["data"]["app_id"] == expected
            third = brain.handle_text("üstteki")
            assert not third.executed
            print(
                json.dumps(
                    [asdict(first), asdict(second), asdict(third)], ensure_ascii=False
                )
            )
    finally:
        model.unload()


if __name__ == "__main__":
    main()
