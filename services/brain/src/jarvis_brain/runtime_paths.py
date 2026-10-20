"""Fixed application resource layout for source and installed runtimes; no model input."""

import os
import sys
from pathlib import Path


def models_directory() -> Path:
    configured = os.environ.get("JARVIS_MODELS_DIR")
    if configured:
        return Path(configured)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "models"
    return Path(__file__).resolve().parents[4] / "models"
