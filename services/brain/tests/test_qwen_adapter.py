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


@pytest.mark.parametrize(
    "output,accepted",
    [
        ('{"intent":"system_status","confidence":1,"arguments":{}}', True),
        ('{"intent":"system_status","confidence":1,"arguments":{}}!{}', False),
        ('{"intent":"open_application","confidence":1,"arguments":{"app_id":"fake"}}', False),
    ],
)
def test_generation_stops_only_at_whole_validated_object(output, accepted):
    from types import SimpleNamespace

    from jarvis_brain.errors import ModelOutputInvalid
    from jarvis_brain.intelligence.contract import IntentContext, IntentName

    states = ["{", output, output + "!{}"]
    calls = []

    class Generator:
        def __init__(self, *_args):
            self.index = -1

        def append_tokens(self, _tokens):
            pass

        def is_done(self):
            return self.index == 2

        def generate_next_token(self):
            self.index += 1
            calls.append(self.index)

        def get_sequence(self, _index):
            return [99, self.index]

    class Params:
        def __init__(self, *_args):
            pass

        def set_search_options(self, **_kwargs):
            pass

        def set_guidance(self, *_args):
            pass

    model = QwenOnnxIntentModel()
    model._state = ModelState.READY
    model._runtime = SimpleNamespace(Generator=Generator, GeneratorParams=Params)
    model._tokenizer = SimpleNamespace(
        encode=lambda _text: [99], decode=lambda tokens: states[tokens[0]]
    )
    if accepted:
        assert model.predict("status", IntentContext()).intent is IntentName.SYSTEM_STATUS
        assert calls == [0, 1]
    else:
        with pytest.raises(ModelOutputInvalid):
            model.predict("status", IntentContext())
        assert calls == [0, 1, 2]


def test_onnx_conversation_refuses_unvalidated_replies_without_inference():
    from jarvis_brain.errors import ModelInferenceError
    from jarvis_brain.intelligence.contract import IntentContext

    model = QwenOnnxIntentModel()
    with pytest.raises(ModelInferenceError, match="Conversation replies are not validated"):
        model.respond("hello", IntentContext())
    assert model.state is ModelState.UNLOADED
