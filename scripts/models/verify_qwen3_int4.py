"""Verify a CPU-loadable GenAI artifact and generate its integrity manifest."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
RUNTIME_VERSION = "0.15.2"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    arguments = parser.parse_args()
    artifact = arguments.artifact.resolve()
    required = ["genai_config.json", "tokenizer.json"]
    missing = [name for name in required if not (artifact / name).is_file()]
    onnx_files = sorted(artifact.glob("*.onnx"))
    if missing or not onnx_files:
        raise SystemExit(
            f"artifact is incomplete; missing={missing}, onnx_files={len(onnx_files)}"
        )
    if importlib.metadata.version("onnxruntime-genai") != RUNTIME_VERSION:
        raise SystemExit(f"onnxruntime-genai must be exactly {RUNTIME_VERSION}")

    import onnxruntime_genai as og

    model = og.Model(str(artifact))
    if str(model.device_type).upper() != "CPU":
        raise SystemExit(f"artifact loaded on unexpected device: {model.device_type}")
    og.Tokenizer(model)
    del model

    files = _file_records(artifact)
    artifact_size = sum(record["size_bytes"] for record in files.values())
    digest = hashlib.sha256()
    for relative_name, record in files.items():
        digest.update(relative_name.encode("utf-8"))
        digest.update(record["sha256"].encode("ascii"))
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "source_model_id": MODEL_ID,
        "source_revision": MODEL_REVISION,
        "source_license": "Apache-2.0",
        "format": "ONNX Runtime GenAI",
        "precision": "INT4",
        "execution_provider": "CPUExecutionProvider",
        "onnxruntime_genai_version": RUNTIME_VERSION,
        "conversion_tool": "onnxruntime_genai.models.builder",
        "conversion_options": {
            "accuracy_level": 4,
            "algo_config": "default",
            "block_size": 32,
            "is_symmetric": True,
        },
        "artifact_size_bytes": artifact_size,
        "artifact_sha256": digest.hexdigest(),
        "files": files,
    }
    if arguments.write_manifest:
        (artifact / "MODEL_MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def _file_records(artifact: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in artifact.rglob("*") if item.is_file()):
        if path.name == "MODEL_MANIFEST.json" or ".cache" in path.parts:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        records[path.relative_to(artifact).as_posix()] = {
            "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        }
    return records


if __name__ == "__main__":
    raise SystemExit(main())
