"""Explicit model choice for synthetic agent acceptance; never downloads or connects to Core."""

from jarvis_brain.intelligence.models.qwen35_gguf import Qwen35GgufAgentModel

from scripts.evaluation.analyze_file_assistance import TracedModel, TraceMixin


class TracedReference(TraceMixin, Qwen35GgufAgentModel):
    pass


def test_model(profile):
    if profile == "qwen35":
        return TracedReference()
    if profile == "qwen3-4b":
        return TracedModel()
    raise ValueError("test profile must be qwen3-4b or qwen35")


test_model.__test__ = False
