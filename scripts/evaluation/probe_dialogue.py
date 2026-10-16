"""Real local dialogue trace on invented metadata, without a Core connection or OS actions."""

import argparse
import json
from pathlib import Path

from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.runtime import JarvisBrain

from scripts.evaluation.analyze_file_assistance import SyntheticCore, TracedModel

SEQUENCES = (
    (
        "ben cv mi bilgisayara bir yere koydum şimdi bula mıyorum bana yardımcı olur musun",
    ),
    ("cv dosyalarımı bul", "tr olan benimkisi onu açar mısın"),
    ("bütçe Excel dosyasını aç",),
    ("What is RAM?",),
    (
        "kargoyla ilgili makbuzu bilgisayara atmıştım, nereye koyduğumu çıkaramadım bulsana",
    ),
    (
        "şimdi bana indirilenler klasörünü açar mısın",
        "orada cv min olduğu bir klasör var onu bulur musun",
    ),
    ("cv dosyalarımı bul", "Türkçe sürümü Microsoft Edge üzerinden görüntüle"),
    ("nasılsın", "ne yapabilirsin", "uygulama açabilir misin"),
    ("en büyük dosyaları göster",),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sequence", type=int, nargs="*", choices=range(len(SEQUENCES))
    )
    args = parser.parse_args()
    model = TracedModel()
    rows = []
    try:
        for index, sequence in enumerate(SEQUENCES):
            if args.sequence is not None and index not in args.sequence:
                continue
            core = SyntheticCore()
            brain = JarvisBrain(core, model, fast_router_enabled=False)
            for text in sequence:
                model.events.clear()
                core.calls.clear()
                try:
                    response = brain.handle_text(text)
                    result = {
                        "message": response.message,
                        "executed_mock": response.executed,
                    }
                except (JarvisBrainError, AssertionError, StopIteration) as error:
                    result = {"error": f"{type(error).__name__}: {error}"}
                row = {
                    "input": text,
                    **result,
                    "events": list(model.events),
                    "tools": list(core.calls),
                }
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        model.unload()
        Path("target/assistant-analysis/dialogue-probe.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
