"""Opt-in Handy 0.9.8 engine benchmark: existing fixtures only, no device or agent.

Uses the official 0.2.4 Python bindings and signed native DLL extracted into
.cache/handy-trial. These are diagnostic dependencies, not production providers.
No microphone input, post-correction, network, or audio output files are used.
"""

from __future__ import annotations

import argparse
import array
import json
import os
import struct
import sys
import time
import wave
from pathlib import Path


def normalize(text: str) -> str:
    text = text.replace("İ", "i").lower().replace("ı", "i")
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def distance(reference: str, actual: str) -> int:
    observed = actual.split()
    previous = list(range(len(observed) + 1))
    for row, expected in enumerate(reference.split(), 1):
        current = [row]
        for col, word in enumerate(observed, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[col] + 1,
                    previous[col - 1] + (expected != word),
                )
            )
        previous = current
    return previous[-1]


def read_fixture(path: Path) -> array.array:
    with wave.open(str(path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (
            16000,
            1,
            2,
        ):
            raise ValueError("Fixture must be 16 kHz mono signed 16-bit PCM")
        if source.getnframes() > 30 * 16000:
            raise ValueError("Fixture exceeds 30 seconds")
        return array.array(
            "f",
            (
                value[0] / 32768.0
                for value in struct.iter_unpack("<h", source.readframes(480000))
            ),
        )


def quiet_noise(samples: array.array) -> array.array:
    # Same deterministic LCG and amplitudes as native audio_pipeline.rs.
    random = 1949
    result = array.array("f")
    for value in samples:
        random = (random * 1664525 + 1013904223) & 0xFFFFFFFF
        result.append(value * 0.12 + (random / 0xFFFFFFFF * 2 - 1) * 0.003)
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "nvidia"), default="nvidia")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.limit <= 8:
        parser.error("--limit must be 1..8")
    trial = root / ".cache/handy-trial"
    sys.path.insert(0, str(trial / "python-bindings"))
    os.environ["TRANSCRIBE_LIBRARY"] = str(trial / "app/transcribe.dll")
    os.environ["VK_LOADER_LAYERS_DISABLE"] = "~implicit~"
    import transcribe_cpp as transcribe

    if transcribe.native_version() != "0.2.4":
        raise RuntimeError("Expected Handy's transcribe.cpp 0.2.4")
    devices = transcribe.backends()
    selected = next(
        (
            d
            for d in devices
            if (d.kind == "cpu" if args.backend == "cpu" else "4070" in d.description)
        ),
        None,
    )
    if selected is None:
        raise RuntimeError(f"Requested device unavailable: {devices}")
    print(
        json.dumps(
            {"native": transcribe.native_version(), "device": selected.description}
        )
    )
    model_path = root / "models/whisper-large-v3-turbo/ggml-large-v3-turbo.bin"
    started = time.perf_counter()
    model = transcribe.Model(model_path, backend=selected.kind, device=selected)
    load_seconds = time.perf_counter() - started
    print(
        json.dumps({"load_seconds": load_seconds, "bound_backend": model.backend}),
        flush=True,
    )
    fixture_root = root / "target/voice-quality-fixtures"
    cases = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    report: dict = {
        "handy_version": "0.9.8",
        "native_version": transcribe.native_version(),
        "device": selected.description,
        "load_seconds": load_seconds,
        "synthetic_only": True,
        "vad_included": False,
        "hints": False,
        "cases": [],
    }
    try:
        for case in cases[: args.limit]:
            original = read_fixture(fixture_root / case["file"])
            for variant, samples in (
                ("clean", original),
                ("quiet_noise", quiet_noise(original)),
            ):
                started = time.perf_counter()
                # Fresh session for each utterance, as in JARVIS. No prompt or replacement.
                with transcribe.Session(model, n_threads=6) as session:
                    result = session.run(samples, language=case["language"])
                seconds = time.perf_counter() - started
                reference, actual = normalize(case["text"]), normalize(result.text)
                row = {
                    "file": case["file"],
                    "language": case["language"],
                    "variant": variant,
                    "reference": case["text"],
                    "transcript": result.text,
                    "audio_seconds": len(samples) / 16000,
                    "decode_seconds": seconds,
                    "word_errors": distance(reference, actual),
                    "reference_words": len(reference.split()),
                    "missing_keywords": [
                        word
                        for word in case["keywords"]
                        if normalize(word) not in actual
                    ],
                }
                report["cases"].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        model.close()
    rows = report["cases"]
    report["summary"] = {
        "decodes": len(rows),
        "critical_failures": sum(bool(row["missing_keywords"]) for row in rows),
        "word_errors": sum(row["word_errors"] for row in rows),
        "reference_words": sum(row["reference_words"] for row in rows),
        "decode_seconds": sum(row["decode_seconds"] for row in rows),
    }
    output = trial / f"benchmark-{args.backend}.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
