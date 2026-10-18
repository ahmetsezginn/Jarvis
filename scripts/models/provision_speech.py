"""Explicit, checksum-pinned offline speech provisioning. Never called at runtime."""

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "5359861c739e955e79d9a303bcbc70fb988958b1"
SHA256 = "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
SIZE = 487601967
DESTINATION = ROOT / "models/whisper-small/ggml-small.bin"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if not DESTINATION.exists() or digest(DESTINATION) != SHA256:
        if shutil.disk_usage(DESTINATION.parent).free < SIZE * 2:
            raise RuntimeError("Not enough free disk space for speech model")
        url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{REVISION}/ggml-small.bin"
        temporary = DESTINATION.with_suffix(".download")
        with (
            urllib.request.urlopen(url, timeout=120) as source,
            temporary.open("wb") as target,
        ):
            shutil.copyfileobj(source, target, length=1024 * 1024)
        if temporary.stat().st_size != SIZE or digest(temporary) != SHA256:
            raise RuntimeError("Speech artifact checksum/size mismatch")
        temporary.replace(DESTINATION)
    manifest = {
        "model": "whisper-small",
        "revision": REVISION,
        "sha256": SHA256,
        "size": SIZE,
    }
    DESTINATION.with_name("MODEL_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Verified local speech model: {DESTINATION}")
    provision_vad()


def provision_vad():
    revision = "c5c26827b67dfd053856f92e824e14fdcc123daf"
    checksum = "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987"
    destination = ROOT / "models/whisper-vad/ggml-silero-v6.2.0.bin"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or digest(destination) != checksum:
        url = f"https://huggingface.co/ggml-org/whisper-vad/resolve/{revision}/{destination.name}"
        temporary = destination.with_suffix(".download")
        with (
            urllib.request.urlopen(url, timeout=120) as source,
            temporary.open("wb") as target,
        ):
            shutil.copyfileobj(source, target)
        if digest(temporary) != checksum:
            raise RuntimeError("VAD artifact checksum mismatch")
        temporary.replace(destination)
    destination.with_name("MODEL_MANIFEST.json").write_text(
        json.dumps(
            {
                "revision": revision,
                "sha256": checksum,
                "size": destination.stat().st_size,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Verified local VAD model: {destination}")


if __name__ == "__main__":
    main()
