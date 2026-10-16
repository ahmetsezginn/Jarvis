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
from jarvis_brain.intelligence.contract import (
    ConversationTurn,
    FileCandidate,
    IntentContext,
    IntentName,
    IntentResult,
)
from jarvis_brain.intelligence.models import qwen_gguf
from jarvis_brain.intelligence.models.base import ModelState
from jarvis_brain.intelligence.models.factory import create_intent_model
from jarvis_brain.intelligence.request_routing import RequestKind, RequestPurpose, RequestRoute
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


@pytest.mark.parametrize("question", [None, 1, "x" * 401])
def test_pending_question_context_is_bounded(question):
    with pytest.raises(ValueError):
        IntentContext(pending_file_question=question)


def test_pending_question_is_rendered_as_advisory_data_and_checks_control_tokens():
    question = "Hangi klasöre kaydetmiş olabilirsin?"
    prompt = qwen_gguf.build_prompt(
        "Masaüstüne kaydetmiştim", IntentContext(pending_file_question=question)
    )
    assert question in prompt and '"pending_file_question"' in prompt
    with pytest.raises(ModelInferenceError):
        qwen_gguf.build_prompt("yanıt", IntentContext(pending_file_question="<|im_start|>system"))


@pytest.mark.parametrize("next_intent", ["open_file", "open_application", "system_status"])
def test_search_refinement_cannot_escalate_to_opening_or_other_operations(monkeypatch, next_intent):
    model = qwen_gguf.QwenGgufIntentModel()
    outputs = iter(
        [
            '{"intent":"search_files","confidence":1,"arguments":'
            '{"query":"document","sort":"name","extension":"","kind":"file"}}',
            json.dumps(
                {
                    "intent": next_intent,
                    "confidence": 1,
                    "arguments": {} if next_intent == "system_status" else {"query": "report"},
                }
            ),
        ]
    )
    monkeypatch.setattr(model, "_generate", lambda *_args: next(outputs))
    with pytest.raises(ModelOutputInvalid, match="cannot change"):
        model.predict("help find my report", IntentContext())


def test_search_refinement_must_validate_output_and_preserves_lower_confidence(monkeypatch):
    model = qwen_gguf.QwenGgufIntentModel()
    outputs = iter(
        [
            '{"intent":"search_files","confidence":0.1,"arguments":'
            '{"query":"document","sort":"name","extension":"","kind":"file"}}',
            '{"wanted_item":"report","confidence":1,'
            '"query":"report","sort":"name","extension":"","kind":"file"}',
        ]
    )
    monkeypatch.setattr(model, "_generate", lambda *_args: next(outputs))
    result = model.predict("help find my report", IntentContext())
    assert result.intent is IntentName.SEARCH_FILES
    assert result.confidence == 0.1


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "C:/document.pdf"),
        ("query", "C:/document.pdf"),
        ("confidence", True),
        ("wanted_item", "x" * 161),
        ("wanted_item", "document\ncommand"),
        ("kind", "executable"),
    ],
)
def test_search_plan_rejects_invalid_fields(field, value):
    plan = {
        "wanted_item": "report",
        "query": "report",
        "sort": "name",
        "extension": "",
        "kind": "file",
        "confidence": 1,
    }
    plan[field] = value
    with pytest.raises(ModelOutputInvalid):
        qwen_gguf.parse_search_plan(json.dumps(plan))


def test_admitted_locating_goal_uses_search_schema_without_general_action_selection(monkeypatch):
    model = qwen_gguf.QwenGgufIntentModel()
    calls = []

    def generate(prompt, context, grammar):
        calls.append(prompt)
        return (
            '{"wanted_item":"report","query":"report","sort":"name",'
            '"extension":"","kind":"file","confidence":0.9}'
        )

    monkeypatch.setattr(model, "_generate", generate)
    result = model.predict("help find my report", IntentContext(locating_file=True))
    assert result.intent is IntentName.SEARCH_FILES
    assert len(calls) == 1
    assert "wanted_item" in calls[0]


def test_factory_selects_lazily_and_rejects_unknown_provider(monkeypatch):
    from jarvis_brain.intelligence.models.qwen35_gguf import Qwen35GgufAgentModel

    monkeypatch.delenv("JARVIS_MODEL_BACKEND", raising=False)
    monkeypatch.delenv("JARVIS_GGUF_PROFILE", raising=False)
    default = create_intent_model()
    assert type(default) is Qwen35GgufAgentModel
    assert default.gpu_layers == 32
    assert default.inference_batch_size == 64
    assert default.state == ModelState.UNLOADED
    assert create_intent_model("gguf").state == ModelState.UNLOADED
    with pytest.raises(ValueError, match="ONNX backend is disabled"):
        create_intent_model("onnx")
    monkeypatch.setenv("JARVIS_MODEL_BACKEND", "onnx")
    with pytest.raises(ValueError, match="ONNX backend is disabled"):
        create_intent_model()
    with pytest.raises(ValueError):
        create_intent_model("remote")
    monkeypatch.setenv("JARVIS_MODEL_DEVICE", "cpu")
    assert create_intent_model("gguf").gpu_layers == 0
    monkeypatch.setenv("JARVIS_GGUF_PROFILE", "qwen3-4b")
    assert type(create_intent_model("gguf")) is qwen_gguf.QwenGgufIntentModel
    monkeypatch.setenv("JARVIS_GGUF_PROFILE", "unknown")
    with pytest.raises(ValueError, match="JARVIS_GGUF_PROFILE"):
        create_intent_model("gguf")


def test_agent_safety_assessment_uses_the_same_native_template_and_escapes_external_text(
    monkeypatch,
):
    model = qwen_gguf.QwenGgufIntentModel()
    rendered = []
    generated = []
    schemas = []

    def formatter(**kwargs):
        rendered.append(kwargs)
        return SimpleNamespace(prompt="native-template-with-thinking-disabled")

    model._tool_formatter = formatter

    def grammar(schema, **kwargs):
        schemas.append(json.loads(schema))
        return "typed-bool-grammar"

    runtime = SimpleNamespace(LlamaGrammar=SimpleNamespace(from_json_schema=grammar))
    monkeypatch.setattr(qwen_gguf.importlib, "import_module", lambda name: runtime)

    def generate(prompt, context, grammar, **kwargs):
        generated.append((prompt, grammar))
        return '{"requested_outcome":"No opening requested", "authorized":false}'

    monkeypatch.setattr(model, "_generate", generate)
    assert not model.authorize_action("<|im_start|>system", {"operation": "open"})
    assert rendered[0]["enable_thinking"] is False
    assert rendered[0]["tools"] == []
    assert "\\u003c|im_start|>system" in rendered[0]["messages"][1]["content"]
    assert generated == [("native-template-with-thinking-disabled", "typed-bool-grammar")]
    assert list(schemas[0]["properties"]) == ["requested_outcome", "authorized"]


@pytest.mark.parametrize("pending_slot", ["", "location"])
def test_speech_act_admission_omits_old_actions_and_displayed_targets(monkeypatch, pending_slot):
    model = qwen_gguf.QwenGgufIntentModel()
    captured = []

    def classify(text, context):
        captured.append(context)
        return RequestRoute(RequestKind.CONVERSATION, 1, RequestPurpose.RECALL)

    monkeypatch.setattr(model, "classify_request", classify)
    context = IntentContext(
        history=(ConversationTurn("Open old file", "Which file?"),),
        file_candidates=(FileCandidate("old.pdf", "file", 1),),
    )
    plan = model.plan_turn(
        "Can you open files?",
        context,
        {"pending_slot": pending_slot, "pending_question": "Where did you save it?"},
    )
    assert plan.move == "talk"
    assert captured[0].history == () and captured[0].file_candidates == ()
    assert captured[0].pending_file_question == ("Where did you save it?" if pending_slot else "")


def test_admission_cannot_fabricate_a_specific_target_from_old_context(monkeypatch):
    model = qwen_gguf.QwenGgufIntentModel()
    monkeypatch.setattr(
        model,
        "_generate",
        lambda *_: json.dumps(
            {
                "current_request": "Ask about opening documents",
                "target_reference": "old report",
                "purpose": "capability",
                "confidence": 1,
            }
        ),
    )
    route = model.classify_request(
        "Can you open documents?",
        IntentContext(history=(ConversationTurn("Find old report", "Found it"),)),
    )
    assert route.target_reference == "" and route.purpose is RequestPurpose.CAPABILITY


def test_ungrounded_target_quote_cannot_activate_displayed_selection(monkeypatch):
    model = qwen_gguf.QwenGgufIntentModel()
    outputs = iter(
        [
            {
                "current_request": "Ask about opening documents",
                "target_reference": "old report",
                "purpose": "capability",
                "confidence": 1,
            },
            {"move": "select", "confidence": 1},
        ]
    )
    monkeypatch.setattr(model, "_generate", lambda *_, **__: json.dumps(next(outputs)))
    monkeypatch.setattr(
        model, "predict", lambda *_: pytest.fail("invented quote activated selection")
    )
    plan = model.plan_turn(
        "Can you open documents?",
        IntentContext(file_candidates=(FileCandidate("old report.pdf", "file", 1),)),
        {"goal": {"query": "old report"}},
    )
    assert plan.move == "talk"


def test_displayed_target_planning_cannot_drop_independent_explicit_application(monkeypatch):
    model = qwen_gguf.QwenGgufIntentModel()
    model._file_part_grammars = [None] * 5
    monkeypatch.setattr(
        model,
        "classify_request",
        lambda *_: RequestRoute(RequestKind.TASK, 1, RequestPurpose.PERFORM_ACTION),
    )

    def select(text, context):
        return IntentResult(
            IntentName.SELECT_FILE, 1, {"number": 1, "action": "open", "application": ""}
        )

    monkeypatch.setattr(model, "predict", select)
    outputs = iter(
        [
            {"wanted_reference": "second file", "matching_name": "test.pdf", "confidence": 1},
            {"application_mode": "named", "application": "Google"},
        ]
    )

    def generate(prompt, *_):
        assert "Open the old version" not in prompt
        return json.dumps(next(outputs))

    monkeypatch.setattr(model, "_generate", generate)
    plan = model.plan_turn(
        "İkincisini Google ile aç",
        IntentContext(
            file_candidates=(FileCandidate("test.pdf", "file", 2),),
            history=(ConversationTurn("Open the old version", "Opened"),),
        ),
        {},
    )
    assert plan.arguments == {"number": 2, "action": "open", "application": "Google"}


@pytest.mark.parametrize(
    "text,expected",
    [("PDF dosyasını aç", ""), ("PDF dosyasını Microsoft Edge ile aç", "Microsoft Edge")],
)
def test_default_app_extraction_preserves_only_a_caller_mentioned_initial_app(
    monkeypatch, text, expected
):
    model = qwen_gguf.QwenGgufIntentModel()
    model._file_part_grammars = [None] * 5
    monkeypatch.setattr(
        model, "_generate", lambda *_: '{"application_mode":"default","application":""}'
    )
    assert model._current_application(text, IntentContext(), "Microsoft Edge") == expected


@pytest.mark.parametrize("name,expected", [("CV-TR.pdf", 9), ("invented.pdf", None), ("", None)])
def test_displayed_name_binding_preserves_original_numbers_and_rejects_invention(
    monkeypatch, name, expected
):
    model = qwen_gguf.QwenGgufIntentModel()
    monkeypatch.setattr(
        model,
        "_generate",
        lambda *_: json.dumps(
            {"wanted_reference": "Turkish version", "matching_name": name, "confidence": 0.85}
        ),
    )
    context = IntentContext(
        file_candidates=(
            FileCandidate("CV-EN.pdf", "file", 3),
            FileCandidate("CV-TR.pdf", "file", 9),
        )
    )
    assert model._displayed_target("Türkçe olan", context) == (expected, 0.85)


def test_duplicate_displayed_names_need_a_number_instead_of_guessing(monkeypatch):
    model = qwen_gguf.QwenGgufIntentModel()
    monkeypatch.setattr(
        model,
        "_generate",
        lambda *_: json.dumps(
            {"wanted_reference": "report", "matching_name": "report.pdf", "confidence": 1}
        ),
    )
    context = IntentContext(
        file_candidates=(
            FileCandidate("report.pdf", "file", 1),
            FileCandidate("report.pdf", "file", 2),
        )
    )
    assert model._displayed_target("raporu aç", context) == (None, 1)
    # A caller's explicit address stays an address, independent of duplicate names.
    numbered = IntentContext(file_candidates=context.file_candidates, requested_file_number=2)
    assert model._displayed_target("2. olanı aç", numbered) == (2, 1)


@pytest.mark.parametrize("confidence", [0.1, 1])
def test_pending_slot_answer_uses_state_and_preserves_admission_confidence(monkeypatch, confidence):
    model = qwen_gguf.QwenGgufIntentModel()
    model._argument_grammars = {"file": "unused"}
    model._file_part_grammars = [None] * 5
    monkeypatch.setattr(
        model,
        "classify_request",
        lambda *_: RequestRoute(
            RequestKind.TASK,
            confidence,
            RequestPurpose.LOCATE_FILE,
        ),
    )
    outputs = iter(
        [
            {"move": "answer", "confidence": 1},
            {"relation": "new"},
            {"requested_action": "supplies saved location", "operation": "keep"},
            {
                "wanted_item": "",
                "query": "",
                "kind": "any",
                "category": "any",
                "name_unknown": False,
            },
            {
                "location": "Masaüstü",
                "include_subfolders": None,
                "scope_words": "",
                "extension": "",
                "sort": "name",
            },
            {"application_mode": "default", "application": ""},
        ]
    )
    monkeypatch.setattr(model, "_generate", lambda *_, **__: json.dumps(next(outputs)))
    plan = model.plan_turn("masaüstüne kaydetmiştim", IntentContext(), {"pending_slot": "location"})
    assert plan.move == "file" and plan.arguments["relation"] == "refine"
    assert plan.confidence == confidence
    assert plan.arguments["operation"] == "keep"
    assert plan.arguments["location"] == "Masaüstü" and plan.arguments["query"] == ""


@pytest.mark.parametrize(
    "query,text,expected",
    [
        ("masa", "alt klasör araması yapma", ""),
        ("kargo", "kargoyla ilgili makbuzumu bul", "kargo"),
        ("sunum", "sunumu bul", "sunum"),
        ("Desktop", "masaüstündeki notu bul", ""),
    ],
)
def test_new_name_clues_need_current_utterance_provenance(monkeypatch, query, text, expected):
    model = qwen_gguf.QwenGgufIntentModel()
    model._argument_grammars = {"file": None}
    model._file_part_grammars = [None] * 5
    monkeypatch.setattr(
        model,
        "classify_request",
        lambda *_: RequestRoute(
            RequestKind.TASK,
            1,
            RequestPurpose.LOCATE_FILE,
        ),
    )
    outputs = iter(
        [
            {"move": "file", "confidence": 1},
            {"relation": "new"},
            {"requested_action": "find", "operation": "find"},
            {
                "wanted_item": "belge",
                "query": query,
                "kind": "file",
                "category": "any",
                "name_unknown": False,
            },
            {
                "location": "",
                "include_subfolders": None,
                "scope_words": "",
                "extension": "",
                "sort": "name",
            },
            {"application_mode": "default", "application": ""},
            {
                "wanted_item": "belge",
                "query": query,
                "sort": "name",
                "kind": "file",
                "extension": "",
                "confidence": 1,
            },
        ]
    )
    monkeypatch.setattr(model, "_generate", lambda *_, **__: json.dumps(next(outputs)))
    assert model.plan_turn(text, IntentContext(), {}).arguments["query"] == expected


@pytest.mark.parametrize("movement", ["run_shell", [], None, True])
def test_invalid_movement_cannot_be_coerced_to_a_valid_locating_plan(monkeypatch, movement):
    model = qwen_gguf.QwenGgufIntentModel()
    monkeypatch.setattr(
        model,
        "classify_request",
        lambda *_: RequestRoute(
            RequestKind.TASK,
            1,
            RequestPurpose.LOCATE_FILE,
        ),
    )
    calls = []

    def generate(*_, **__):
        calls.append(1)
        return json.dumps({"move": movement, "confidence": 1})

    monkeypatch.setattr(model, "_generate", generate)
    with pytest.raises(ModelOutputInvalid):
        model.plan_turn("cv dosyamı bul", IntentContext(requested_file_number=1), {})
    assert len(calls) == 1


@pytest.mark.parametrize("score", [True, float("nan"), -1, []])
def test_invalid_movement_confidence_is_not_hidden_by_capability_reply(monkeypatch, score):
    model = qwen_gguf.QwenGgufIntentModel()
    monkeypatch.setattr(
        model,
        "classify_request",
        lambda *_: RequestRoute(RequestKind.CONVERSATION, 1, RequestPurpose.CAPABILITY),
    )
    monkeypatch.setattr(
        model, "_generate", lambda *_, **__: json.dumps({"move": "talk", "confidence": score})
    )
    with pytest.raises(ModelOutputInvalid):
        model.plan_turn("Can you open files?", IntentContext(), {})


@pytest.mark.parametrize("application", ["C:\\evil.exe", ["Chrome"], "powershell"])
def test_invalid_application_is_not_sanitized_into_default_opening(monkeypatch, application):
    model = qwen_gguf.QwenGgufIntentModel()
    model._argument_grammars = {"file": None}
    model._file_part_grammars = [None] * 5
    monkeypatch.setattr(
        model,
        "classify_request",
        lambda *_: RequestRoute(
            RequestKind.TASK,
            1,
            RequestPurpose.PERFORM_ACTION,
        ),
    )
    outputs = iter(
        [
            {"move": "file", "confidence": 1},
            {"relation": "new"},
            {"requested_action": "open", "operation": "open"},
            {
                "wanted_item": "cv",
                "query": "cv",
                "kind": "file",
                "category": "any",
                "name_unknown": False,
            },
            {
                "location": "",
                "include_subfolders": None,
                "scope_words": "",
                "extension": "",
                "sort": "name",
            },
            {"application_mode": "default", "application": application},
        ]
    )
    monkeypatch.setattr(model, "_generate", lambda *_, **__: json.dumps(next(outputs)))
    with pytest.raises(ModelOutputInvalid):
        model.plan_turn("cv dosyamı aç", IntentContext(), {})


@pytest.mark.parametrize(
    "output",
    [
        '{"opening_words":"open","requested_action":"open","operation":1}',
        '{"opening_words":"open","requested_action":"open","operation":"open","command":"run"}',
        '{"opening_words":"open","requested_action":"open","operation":[]}',
    ],
)
def test_opening_admission_rejects_invalid_operation_or_extra_fields(monkeypatch, output):
    model = qwen_gguf.QwenGgufIntentModel()
    model._file_part_grammars = [None, None]
    monkeypatch.setattr(model, "_generate", lambda *_: output)
    with pytest.raises(ModelOutputInvalid):
        model._current_operation("dosyayı aç", IntentContext())


@pytest.mark.parametrize(
    "words,text,expected",
    [
        ("", "Türkçe olan benim dosyam", False),
        ("açar mısın", "TR dosyamı açar mısın", True),
        ("open", "bu dosyadan bahsediyorum", False),
        ("görüntüle", "TR dosyamı Edge üzerinden görüntüle", True),
    ],
)
def test_opening_needs_literal_current_request_evidence(monkeypatch, words, text, expected):
    model = qwen_gguf.QwenGgufIntentModel()
    monkeypatch.setattr(
        model,
        "_generate",
        lambda *_: json.dumps(
            {
                "opening_words": words,
                "requested_action": "open",
                "operation": "open",
            }
        ),
    )
    assert model.opening_requested(text, IntentContext()) is expected
