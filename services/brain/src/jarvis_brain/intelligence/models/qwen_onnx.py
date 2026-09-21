"""Qwen3 INT4 adapter; all ONNX Runtime GenAI API details stay in this module."""

from __future__ import annotations

import gc
import importlib
import importlib.metadata
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jarvis_brain import config
from jarvis_brain.errors import (
    ModelArtifactMissing,
    ModelInferenceError,
    ModelLoadError,
    ModelOutputInvalid,
)
from jarvis_brain.intelligence.contract import IntentContext, IntentResult
from jarvis_brain.intelligence.models.base import ModelState
from jarvis_brain.intelligence.parser import parse_model_output
from jarvis_brain.intelligence.prompts import INTENT_JSON_SCHEMA, build_non_thinking_prompt


@dataclass(frozen=True)
class InferenceMetrics:
    prompt_tokens: int
    generated_tokens: int
    inference_ms: float


class QwenOnnxIntentModel:
    """Lazy local CPU adapter for a pre-provisioned Qwen3-0.6B INT4 artifact."""

    def __init__(self, model_path: Path | None = None) -> None:
        self.model_path = (model_path or config.default_model_path()).resolve()
        self._state = ModelState.UNLOADED
        self._runtime: Any = None
        self._model: Any = None
        self._tokenizer: Any = None
        self._lock = threading.RLock()
        self.last_metrics: InferenceMetrics | None = None
        self.last_output_unsafe_fields = False
        self.load_time_ms: float | None = None

    @property
    def state(self) -> ModelState:
        return self._state

    def load(self) -> None:
        with self._lock:
            if self._state is ModelState.READY:
                return
            self._state = ModelState.LOADING
            started = time.perf_counter()
            try:
                self._validate_artifact()
                runtime = importlib.import_module("onnxruntime_genai")
                installed = importlib.metadata.version("onnxruntime-genai")
                if installed != config.ONNXRUNTIME_GENAI_VERSION:
                    raise ModelLoadError(
                        "onnxruntime-genai version mismatch: "
                        f"expected {config.ONNXRUNTIME_GENAI_VERSION}, found {installed}"
                    )
                model = runtime.Model(str(self.model_path))
                tokenizer = runtime.Tokenizer(model)
            except ModelArtifactMissing:
                self._state = ModelState.FAILED
                raise
            except ModelLoadError:
                self._state = ModelState.FAILED
                raise
            except Exception as error:
                self._state = ModelState.FAILED
                raise ModelLoadError(f"could not load local Qwen ONNX artifact: {error}") from error
            self._runtime = runtime
            self._model = model
            self._tokenizer = tokenizer
            self.load_time_ms = (time.perf_counter() - started) * 1000.0
            self._state = ModelState.READY

    def unload(self) -> None:
        with self._lock:
            self._tokenizer = None
            self._model = None
            self._runtime = None
            self.last_metrics = None
            self.last_output_unsafe_fields = False
            self._state = ModelState.UNLOADED
            gc.collect()

    def predict(self, text: str, context: IntentContext) -> IntentResult:
        if self._state is not ModelState.READY:
            raise ModelInferenceError("Qwen model must be loaded before prediction")
        prompt = build_non_thinking_prompt(text)
        try:
            input_tokens = self._tokenizer.encode(prompt)
            prompt_tokens = len(input_tokens)
            if prompt_tokens > context.max_context_tokens:
                raise ModelInferenceError(
                    f"prompt uses {prompt_tokens} tokens; limit is {context.max_context_tokens}"
                )

            parameters = self._runtime.GeneratorParams(self._model)
            parameters.set_search_options(
                do_sample=False,
                min_length=prompt_tokens + 24,
                max_length=prompt_tokens + context.max_generated_tokens,
            )
            schema = json.dumps(INTENT_JSON_SCHEMA, separators=(",", ":"))
            parameters.set_guidance("lark_grammar", f"start: %json {schema}\n")
            generator = self._runtime.Generator(self._model, parameters)
            generator.append_tokens(input_tokens)
            started = time.perf_counter()
            while not generator.is_done():
                generator.generate_next_token()
            sequence = generator.get_sequence(0)
            generated = sequence[prompt_tokens:]
            raw_output = self._tokenizer.decode(generated).strip()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            del generator
            if raw_output.endswith("<|im_end|>"):
                raw_output = raw_output.removesuffix("<|im_end|>").rstrip()
            lowered_output = raw_output.casefold()
            self.last_output_unsafe_fields = any(
                field in lowered_output
                for field in (
                    '"app_id"',
                    '"path"',
                    '"executable"',
                    '"command"',
                    '"shell"',
                    '"powershell"',
                    '"arguments_to_executable"',
                )
            )
            self.last_metrics = InferenceMetrics(
                prompt_tokens=prompt_tokens,
                generated_tokens=len(generated),
                inference_ms=elapsed_ms,
            )
            return parse_model_output(raw_output)
        except (ModelInferenceError, ModelOutputInvalid):
            raise
        except Exception as error:
            raise ModelInferenceError(f"local Qwen inference failed: {error}") from error

    def model_info(self) -> dict[str, Any]:
        manifest: dict[str, Any] | None = None
        manifest_path = self.model_path / "MODEL_MANIFEST.json"
        if manifest_path.is_file():
            try:
                value = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = value if isinstance(value, dict) else None
            except (OSError, json.JSONDecodeError):
                manifest = None
        return {
            "model_path": str(self.model_path),
            "state": self._state.value,
            "artifact_present": self._artifact_files_present(),
            "runtime_version_required": config.ONNXRUNTIME_GENAI_VERSION,
            "manifest": manifest,
            "load_time_ms": self.load_time_ms,
            "last_inference": None if self.last_metrics is None else asdict(self.last_metrics),
            "last_output_unsafe_fields": self.last_output_unsafe_fields,
        }

    def _validate_artifact(self) -> None:
        if not self._artifact_files_present():
            raise ModelArtifactMissing(
                f"Qwen INT4 artifact not found at {self.model_path}; "
                "run scripts/models/build_qwen3_int4.ps1 explicitly"
            )
        manifest_path = self.model_path / "MODEL_MANIFEST.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelLoadError("MODEL_MANIFEST.json is unreadable or invalid") from error
        expected = {
            "source_model_id": config.MODEL_ID,
            "source_revision": config.MODEL_REVISION,
            "precision": "INT4",
            "execution_provider": "CPUExecutionProvider",
            "onnxruntime_genai_version": config.ONNXRUNTIME_GENAI_VERSION,
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise ModelLoadError(f"artifact manifest {key} does not match runtime: {value}")

    def _artifact_files_present(self) -> bool:
        return (
            self.model_path.is_dir()
            and (self.model_path / "genai_config.json").is_file()
            and (self.model_path / "tokenizer.json").is_file()
            and (self.model_path / "MODEL_MANIFEST.json").is_file()
            and any(self.model_path.glob("*.onnx"))
        )
