"""Explicit provider selection without loading either native runtime."""

import os

from jarvis_brain.intelligence.models.base import IntentModel


def create_intent_model(backend: str | None = None) -> IntentModel:
    selected = backend or os.environ.get("JARVIS_MODEL_BACKEND", "onnx")
    if selected == "onnx":
        from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel

        return QwenOnnxIntentModel()
    if selected == "gguf":
        from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

        device = os.environ.get("JARVIS_MODEL_DEVICE", "gpu")
        if device not in ("gpu", "cpu"):
            raise ValueError("JARVIS_MODEL_DEVICE must be gpu or cpu")
        return QwenGgufIntentModel(gpu_layers=-1 if device == "gpu" else 0)
    raise ValueError("JARVIS_MODEL_BACKEND must be onnx or gguf")
