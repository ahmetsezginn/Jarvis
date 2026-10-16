"""Explicit pinned local agent GGUF provisioning; never invoked by product startup."""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

REPOSITORY = "unsloth/Qwen3.5-9B-GGUF"
REVISION = "99a1b2185534379e6e8b5ec869da25d3e7b3f73c"
FILENAME = "Qwen3.5-9B-Q4_K_M.gguf"
SHA256 = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"
ROOT = Path(__file__).resolve().parents[2] / "models/qwen35-9b-reference"
URL = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{FILENAME}"


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    pointer_url = f"https://huggingface.co/{REPOSITORY}/raw/{REVISION}/{FILENAME}"
    with urllib.request.urlopen(pointer_url, timeout=30) as response:
        pointer = response.read(1024).decode("ascii")
    fields = dict(line.split(" ", 1) for line in pointer.strip().splitlines())
    if fields.get("oid") != "sha256:" + SHA256:
        raise ValueError("reference pointer does not match the pinned SHA256")
    size = int(fields["size"])
    if not 5_000_000_000 < size < 6_000_000_000:
        raise ValueError("unexpected reference size")
    target = ROOT / FILENAME
    partial = target.with_suffix(".gguf.part")
    if not target.exists():
        if shutil.disk_usage(ROOT).free < size + 1024**3:
            raise RuntimeError("insufficient space for model reference")
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > size:
            raise ValueError("partial model exceeds pinned size")
        if offset < size:
            request = urllib.request.Request(URL, headers={"Range": f"bytes={offset}-"})
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206:
                    offset = 0
                elif not response.headers.get("Content-Range", "").startswith(
                    f"bytes {offset}-"
                ):
                    raise ValueError("invalid partial range")
                progress = offset + 256 * 1024**2
                with partial.open("ab" if offset else "wb") as output:
                    for chunk in iter(lambda: response.read(4 * 1024**2), b""):
                        offset += len(chunk)
                        if offset > size:
                            raise ValueError("download exceeds pinned model size")
                        output.write(chunk)
                        if offset >= progress:
                            print(f"Downloaded {offset}/{size}", flush=True)
                            progress = offset + 256 * 1024**2
        source = partial
    else:
        source = target
    if source.stat().st_size != size:
        raise ValueError("reference size mismatch")
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SHA256:
        raise ValueError("reference SHA256 mismatch")
    if source == partial:
        partial.replace(target)
    manifest = {
        "repository": REPOSITORY,
        "revision": REVISION,
        "filename": FILENAME,
        "sha256": SHA256,
        "size_bytes": size,
        "role": "local_agent",
    }
    (ROOT / "MODEL_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("Reference verified:", target, flush=True)


if __name__ == "__main__":
    main()
