from pathlib import Path

import pytest

from jarvis_brain.errors import ModelArtifactMissing
from jarvis_brain.intelligence.models.base import ModelState
from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel


def test_qwen_adapter_is_lazy_and_missing_artifact_is_typed(tmp_path: Path) -> None:
    model = QwenOnnxIntentModel(tmp_path / "missing")
    assert model.state is ModelState.UNLOADED
    assert model.model_info()["artifact_present"] is False
    with pytest.raises(ModelArtifactMissing):
        model.load()
    assert model.state is ModelState.FAILED


def test_unload_restores_lazy_state_without_runtime_import(tmp_path: Path) -> None:
    model = QwenOnnxIntentModel(tmp_path / "not-used")
    model.unload()
    assert model.state is ModelState.UNLOADED
