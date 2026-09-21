"""Explicit, checksum-pinned download; never imported by production inference."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

REPO = "unsloth/Qwen3-4B-Instruct-2507-GGUF"
REVISION = "a06e946bb6b655725eafa393f4a9745d460374c9"
FILENAME = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
SHA256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
SIZE = 2497281120


def main() -> None:
    # Use the OS trust store on managed Windows; never disable certificate validation.
    import truststore

    truststore.inject_into_ssl()
    destination = Path(__file__).resolve().parents[2] / "models/qwen3-4b-gguf"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / FILENAME
    if not target.exists():
        partial = target.with_suffix(".gguf.partial")
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}"
        print(f"Downloading {SIZE:,} bytes from pinned {REPO}@{REVISION}", flush=True)
        with (
            urllib.request.urlopen(url, timeout=60) as response,
            partial.open("wb") as output,
        ):
            while chunk := response.read(8 * 1024 * 1024):
                output.write(chunk)
        with partial.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if partial.stat().st_size != SIZE or digest != SHA256:
            raise ValueError(
                "Downloaded model checksum/size mismatch; partial retained, not loaded"
            )
        partial.replace(target)
    with target.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if target.stat().st_size != SIZE or digest != SHA256:
        raise ValueError("Existing model checksum/size mismatch; refusing to overwrite")
    manifest = {
        "source_model_id": "Qwen/Qwen3-4B-Instruct-2507",
        "quantizer_repository": REPO,
        "revision": REVISION,
        "file": FILENAME,
        "sha256": SHA256,
        "size_bytes": SIZE,
        "precision": "Q4_K_M",
    }
    (destination / "MODEL_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
