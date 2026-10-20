from pathlib import Path

from jarvis_brain.intelligence.models.qwen35_gguf import FILENAME, Qwen35GgufAgentModel
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel
from jarvis_brain.runtime_paths import models_directory


def test_installed_model_path_does_not_depend_on_build_checkout(monkeypatch, tmp_path):
    import sys

    monkeypatch.delenv("JARVIS_MODELS_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "JarvisWorker.exe"))
    model = Qwen35GgufAgentModel(gpu_layers=0)
    assert model.model_path == tmp_path / "models/qwen35-9b-reference" / FILENAME
    assert model.gpu_layers == 0


def test_explicit_local_resource_root_keeps_pinned_model_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_MODELS_DIR", str(tmp_path))
    model = Qwen35GgufAgentModel()
    assert model.model_path == tmp_path / "qwen35-9b-reference" / FILENAME
    assert len(model.artifact["sha256"]) == 64 and model.gpu_layers == 32


def test_source_checkout_remains_default_outside_frozen_runtime(monkeypatch):
    import sys

    monkeypatch.delenv("JARVIS_MODELS_DIR", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert models_directory() == Path(__file__).resolve().parents[3] / "models"


def test_cpu_does_not_inspect_or_preload_cuda_libraries(monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(
        importlib.metadata,
        "distribution",
        lambda _name: (_ for _ in ()).throw(AssertionError("CPU must not load CUDA")),
    )
    QwenGgufIntentModel(gpu_layers=0)._prepare_cuda_dlls()
