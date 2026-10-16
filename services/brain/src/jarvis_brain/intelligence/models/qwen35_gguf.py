"""Pinned local Qwen3.5 provider using its native non-thinking tool protocol."""

from pathlib import Path

from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

MODEL_ID = "Qwen/Qwen3.5-9B"
REVISION = "99a1b2185534379e6e8b5ec869da25d3e7b3f73c"
FILENAME = "Qwen3.5-9B-Q4_K_M.gguf"
SIZE = 5680522464
SHA256 = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"


class Qwen35GgufAgentModel(QwenGgufIntentModel):
    tool_protocol = "qwen35"
    inference_batch_size = 64
    agent_temperature = 0.0
    agent_presence_penalty = 0.0

    def __init__(self, model_path=None, *, gpu_layers=-1):
        path = (
            model_path
            or Path(__file__).resolve().parents[6] / "models/qwen35-9b-reference" / FILENAME
        )
        # Keep the output projection on CPU on this 8GB GPU profile. Full offload can
        # exhaust Windows' dedicated budget as desktop GPU usage changes during a session.
        super().__init__(path, gpu_layers=32 if gpu_layers == -1 else gpu_layers)

    @property
    def artifact(self):
        return {"model_id": MODEL_ID, "revision": REVISION, "size_bytes": SIZE, "sha256": SHA256}
