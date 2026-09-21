"""Local Brain defaults. Nothing in this module downloads runtime assets."""

from __future__ import annotations

import os
from pathlib import Path

CONNECT_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 15.0

BRAIN_VERSION = "0.2.0"
MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
ONNXRUNTIME_GENAI_VERSION = "0.15.2"
MAX_INPUT_CHARS = 4096
MAX_CONTEXT_TOKENS = 2048
MAX_GENERATED_TOKENS = 128
MIN_INTENT_CONFIDENCE = 0.80


def default_model_path() -> Path:
    """Return an explicit local artifact path without probing or downloading."""

    configured = os.environ.get("JARVIS_QWEN_MODEL_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "models" / "qwen3-0.6b-int4"
