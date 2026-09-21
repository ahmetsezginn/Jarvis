"""Intent model adapters."""

from jarvis_brain.intelligence.models.base import IntentModel, ModelState
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel

__all__ = ["FakeIntentModel", "IntentModel", "ModelState", "QwenOnnxIntentModel"]
