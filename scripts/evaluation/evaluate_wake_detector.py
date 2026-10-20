"""Opt-in synthetic WAV benchmark of the native keyword ABI; never launches anything."""

import argparse
import array
import ctypes
import json
import time
import wave
from pathlib import Path


def evaluate(runtime: Path, fixtures: Path, threshold: float = 1e-10) -> list[dict]:
    dll = ctypes.CDLL(str(runtime / "pocketsphinx.dll"))
    pointer = ctypes.c_void_p
    for name, result, arguments in [
        ("ps_config_init", pointer, [pointer]),
        ("ps_config_set_str", pointer, [pointer, ctypes.c_char_p, ctypes.c_char_p]),
        ("ps_config_set_float", pointer, [pointer, ctypes.c_char_p, ctypes.c_double]),
        ("ps_init", pointer, [pointer]),
        ("ps_config_free", ctypes.c_int, [pointer]),
        ("ps_start_utt", ctypes.c_int, [pointer]),
        (
            "ps_process_raw",
            ctypes.c_int,
            [
                pointer,
                ctypes.POINTER(ctypes.c_int16),
                ctypes.c_size_t,
                ctypes.c_int,
                ctypes.c_int,
            ],
        ),
        ("ps_get_hyp", ctypes.c_char_p, [pointer, pointer]),
        ("ps_free", ctypes.c_int, [pointer]),
    ]:
        function = getattr(dll, name)
        function.restype, function.argtypes = result, arguments
    results = []
    for file in sorted(fixtures.glob("*.wav")):
        config = dll.ps_config_init(None)
        for key, value in {
            "hmm": runtime / "en-us",
            "dict": runtime / "wake.dict",
            "kws": runtime / "wake.kws",
            "logfn": "NUL",
        }.items():
            dll.ps_config_set_str(config, key.encode(), str(value).encode("mbcs"))
        dll.ps_config_set_float(config, b"kws_threshold", threshold)
        decoder = dll.ps_init(config)
        dll.ps_config_free(config)
        if not decoder:
            raise RuntimeError("Cannot load native keyword model")
        try:
            with wave.open(str(file), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    raise ValueError("Fixtures must be mono PCM16")
                rate = wav.getframerate()
                original = array.array("h", wav.readframes(wav.getnframes()))
            # Offline synthetic fixtures only, never actual user microphone recordings.
            pcm = array.array(
                "h",
                (
                    original[min(int(i * rate / 16000), len(original) - 1)]
                    for i in range(int(len(original) * 16000 / rate))
                ),
            )
            pcm.extend([0] * 16000)
            dll.ps_start_utt(decoder)
            started = time.perf_counter()
            detected = False
            for offset in range(0, len(pcm), 800):
                chunk = pcm[offset : offset + 800]
                frame = (ctypes.c_int16 * len(chunk))(*chunk)
                if dll.ps_process_raw(decoder, frame, len(chunk), 0, 0) < 0:
                    raise RuntimeError("Native keyword decoding failed")
                detected |= bool(dll.ps_get_hyp(decoder, None))
            results.append(
                {
                    "file": file.name,
                    "expected": file.name.startswith("wake-"),
                    "detected": detected,
                    "decode_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        finally:
            dll.ps_free(decoder)
    if not results:
        raise ValueError("No WAV fixtures supplied")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.runtime.resolve(), args.fixtures.resolve())
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(
        0 if all(row["detected"] == row["expected"] for row in result) else 1
    )


if __name__ == "__main__":
    main()
