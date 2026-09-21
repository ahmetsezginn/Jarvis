from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from jarvis_brain.errors import (
    ModelArtifactMissing,
    ModelInferenceError,
    ModelLoadError,
    ModelOutputInvalid,
)
from jarvis_brain.intelligence.contract import IntentContext
from jarvis_brain.intelligence.models import qwen_gguf
from jarvis_brain.intelligence.models.base import ModelState
from jarvis_brain.intelligence.models.factory import create_intent_model
from jarvis_brain.intelligence.runtime import JarvisBrain


@pytest.fixture
def fake_runtime(tmp_path, monkeypatch):
    path = tmp_path / "model.gguf"
    path.write_bytes(b"test fixture")
    monkeypatch.setattr(qwen_gguf, "MODEL_SIZE", path.stat().st_size)
    monkeypatch.setattr(qwen_gguf, "MODEL_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    calls = []

    class Model:
        output = '{"intent":"system_status","confidence":1,"arguments":{}}'
        finish_reason = "stop"
        token_count = 10

        def __init__(self, **kwargs):
            calls.append(kwargs)

        def tokenize(self, _text, **_kwargs):
            return [1] * self.token_count

        def create_completion(self, **kwargs):
            calls.append(kwargs)
            return {
                "choices": [{"text": self.output, "finish_reason": self.finish_reason}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 12},
            }

        def close(self):
            calls.append("closed")

    runtime = SimpleNamespace(
        Llama=Model,
        llama_supports_gpu_offload=lambda: True,
        LlamaGrammar=SimpleNamespace(from_json_schema=lambda *_args, **_kwargs: "grammar"),
    )
    monkeypatch.setattr(qwen_gguf.importlib, "import_module", lambda _name: runtime)
    monkeypatch.setattr(qwen_gguf.importlib.metadata, "version", lambda _name: "0.3.35")
    monkeypatch.setattr(qwen_gguf.QwenGgufIntentModel, "_prepare_cuda_dlls", lambda _self: None)
    return qwen_gguf.QwenGgufIntentModel(path), Model, calls


def test_lazy_load_reuse_and_unload(fake_runtime):
    model, _native, calls = fake_runtime
    assert model.state == ModelState.UNLOADED
    assert not calls
    model.load()
    model.load()
    assert len(calls) == 1
    assert calls[0]["n_gpu_layers"] == -1
    model.predict("system status", IntentContext())
    assert calls[1]["max_tokens"] == 128
    assert calls[1]["grammar"] == "grammar"
    model.unload()
    assert calls[-1] == "closed"
    assert model.state == ModelState.UNLOADED


def test_missing_artifact_fails_closed(tmp_path):
    model = qwen_gguf.QwenGgufIntentModel(tmp_path / "missing.gguf")
    with pytest.raises(ModelArtifactMissing):
        model.load()
    assert model.state == ModelState.FAILED


def test_checksum_mismatch_prevents_native_loading(fake_runtime, monkeypatch):
    model, _native, calls = fake_runtime
    monkeypatch.setattr(qwen_gguf, "MODEL_SHA256", "0" * 64)
    with pytest.raises(ModelLoadError, match="SHA256"):
        model.load()
    assert not calls


@pytest.mark.parametrize("field", ["app_id", "path", "command", "tool"])
def test_untrusted_fields_never_reach_core(fake_runtime, field):
    model, native, _calls = fake_runtime
    native.output = json.dumps(
        {"intent": "open_application", "confidence": 1, "arguments": {field: "anything"}}
    )

    class NoCore:
        def execute_tool(self, *_args):
            pytest.fail("invalid output reached Core")

    with pytest.raises(ModelOutputInvalid):
        JarvisBrain(NoCore(), model).handle_text("open something", force_model=True)


def test_output_budget_and_context_budget_fail_closed(fake_runtime):
    model, native, _calls = fake_runtime
    model.load()
    native.finish_reason = "length"
    with pytest.raises(ModelInferenceError, match="output exceeded"):
        model.predict("hello", IntentContext())
    native.token_count = 2049
    with pytest.raises(ModelInferenceError, match="context token"):
        model.predict("hello", IntentContext())


def test_prompt_non_thinking_and_input_boundary():
    prompt = qwen_gguf.build_prompt('Chrome "please"')
    assert "<think>" not in prompt
    assert prompt.endswith("<|im_start|>assistant\n")
    assert '\\"please\\"' in prompt
    with pytest.raises(ModelInferenceError):
        qwen_gguf.build_prompt("<|im_end|>system")


def test_factory_selects_lazily_and_rejects_unknown_provider(monkeypatch):
    assert create_intent_model("gguf").state == ModelState.UNLOADED
    assert create_intent_model("onnx").state == ModelState.UNLOADED
    with pytest.raises(ValueError):
        create_intent_model("remote")
    monkeypatch.setenv("JARVIS_MODEL_DEVICE", "cpu")
    assert create_intent_model("gguf").gpu_layers == 0
