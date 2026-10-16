"""Explicit provider selection; deprecated backends cannot enter execution."""

import os

from jarvis_brain.intelligence.models.base import AgentModel


def create_agent_model(backend: str | None = None) -> AgentModel:
    selected = backend or os.environ.get("JARVIS_MODEL_BACKEND", "gguf")
    if selected == "onnx":
        raise ValueError("ONNX backend is disabled. Use JARVIS_MODEL_BACKEND=gguf.")
    if selected == "gguf":
        from jarvis_brain.intelligence.models.qwen35_gguf import Qwen35GgufAgentModel
        from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

        device = os.environ.get("JARVIS_MODEL_DEVICE", "gpu")
        if device not in ("gpu", "cpu"):
            raise ValueError("JARVIS_MODEL_DEVICE must be gpu or cpu")
        profile = os.environ.get("JARVIS_GGUF_PROFILE", "qwen35-9b")
        providers = {"qwen35-9b": Qwen35GgufAgentModel, "qwen3-4b": QwenGgufIntentModel}
        if profile not in providers:
            raise ValueError("JARVIS_GGUF_PROFILE must be qwen35-9b or qwen3-4b")
        return providers[profile](gpu_layers=-1 if device == "gpu" else 0)
    raise ValueError("JARVIS_MODEL_BACKEND must be gguf; ONNX is disabled")


def create_intent_model(backend: str | None = None) -> AgentModel:
    """Compatibility name for callers; execution uses AgentModel, not intent routing."""
    return create_agent_model(backend)
