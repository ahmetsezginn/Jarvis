"""Intent model adapters."""

from jarvis_brain.intelligence.models.base import AgentModel, IntentModel, ModelState
from jarvis_brain.intelligence.models.fake import FakeIntentModel

__all__ = ["AgentModel", "FakeIntentModel", "IntentModel", "ModelState"]
