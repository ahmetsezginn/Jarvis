"""In-process local Qwen GGUF inference. No server, network, or OS action API."""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from jarvis_brain.errors import ModelArtifactMissing, ModelInferenceError, ModelLoadError
from jarvis_brain.intelligence.contract import IntentContext, IntentResult
from jarvis_brain.intelligence.models.base import ModelState
from jarvis_brain.intelligence.parser import parse_model_output
from jarvis_brain.intelligence.prompts import (
    CONTEXT_PROMPT,
    INTENT_JSON_SCHEMA,
    REASONING_PROMPT,
    build_conversation_messages,
    build_user_payload,
)
from jarvis_brain.intelligence.request_routing import (
    GGUF_ROUTE_PROMPT,
    REPLY_PROMPT,
    REPLY_SCHEMA,
    ROUTE_SCHEMA,
    RequestRoute,
    parse_reply,
    parse_route,
)

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "a06e946bb6b655725eafa393f4a9745d460374c9"
MODEL_FILENAME = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
MODEL_SHA256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
MODEL_SIZE = 2497281120
RUNTIME_VERSION = "0.3.35"


def default_gguf_path() -> Path:
    return Path(__file__).resolve().parents[6] / "models/qwen3-4b-gguf" / MODEL_FILENAME


def build_prompt(
    text: str,
    context: IntentContext | None = None,
    *,
    system_prompt: str | None = None,
    chat_history: bool = False,
) -> str:
    payload = build_user_payload(text, context)
    user_messages = (
        build_conversation_messages(text, context)
        if chat_history
        else f"<|im_start|>user\n{payload}<|im_end|>\n"
    )
    system = system_prompt or REASONING_PROMPT
    if system_prompt is None and context is not None and context.history:
        system += "\n" + CONTEXT_PROMPT
    return f"<|im_start|>system\n{system}<|im_end|>\n{user_messages}<|im_start|>assistant\n"


class QwenGgufIntentModel:
    def __init__(self, model_path: Path | None = None, *, gpu_layers: int = -1) -> None:
        self.model_path = model_path or default_gguf_path()
        if gpu_layers not in (-1, 0):
            raise ValueError("gpu_layers must be -1 (GPU) or 0 (CPU)")
        self.gpu_layers = gpu_layers
        self._state = ModelState.UNLOADED
        self._model: Any = None
        self._grammar: Any = None
        self._route_grammar: Any = None
        self._reply_grammar: Any = None
        self._lock = threading.RLock()
        self.load_time_ms: float | None = None
        self.last_metrics: dict[str, Any] | None = None
        self._dll_directories: list[Any] = []
        self._cuda_libraries: list[Any] = []

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
                if not self.model_path.is_file():
                    raise ModelArtifactMissing(
                        "Local Qwen GGUF missing; "
                        "run scripts/models/provision_qwen_gguf.py explicitly"
                    )
                if self.model_path.stat().st_size != MODEL_SIZE:
                    raise ModelLoadError("GGUF size does not match pinned artifact")
                with self.model_path.open("rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                if digest != MODEL_SHA256:
                    raise ModelLoadError("GGUF SHA256 does not match pinned artifact")
                self._prepare_cuda_dlls()
                runtime = importlib.import_module("llama_cpp")
                if importlib.metadata.version("llama-cpp-python") != RUNTIME_VERSION:
                    raise ModelLoadError("llama-cpp-python version does not match pinned runtime")
                if self.gpu_layers == -1 and not runtime.llama_supports_gpu_offload():
                    raise ModelLoadError("GPU requested but runtime has no GPU offload support")
                self._grammar = runtime.LlamaGrammar.from_json_schema(
                    json.dumps(INTENT_JSON_SCHEMA), verbose=False
                )
                self._route_grammar = runtime.LlamaGrammar.from_json_schema(
                    json.dumps(ROUTE_SCHEMA), verbose=False
                )
                self._reply_grammar = runtime.LlamaGrammar.from_json_schema(
                    json.dumps(REPLY_SCHEMA), verbose=False
                )
                self._model = runtime.Llama(
                    model_path=str(self.model_path),
                    n_ctx=2304,
                    n_batch=512,
                    n_gpu_layers=self.gpu_layers,
                    verbose=False,
                    seed=0,
                )
            except (ModelArtifactMissing, ModelLoadError):
                self._state = ModelState.FAILED
                raise
            except Exception as error:
                self._state = ModelState.FAILED
                raise ModelLoadError(f"Local GGUF load failed: {error}") from error
            self.load_time_ms = (time.perf_counter() - started) * 1000
            self._state = ModelState.READY

    def unload(self) -> None:
        with self._lock:
            if self._model is not None:
                self._model.close()
            self._model = None
            self._grammar = None
            self._route_grammar = None
            self._reply_grammar = None
            self.last_metrics = None
            self._state = ModelState.UNLOADED

    def predict(self, text: str, context: IntentContext) -> IntentResult:
        return parse_model_output(
            self._generate(build_prompt(text, context), context, self._grammar)
        )

    def classify_request(self, text: str, context: IntentContext) -> RequestRoute:
        prompt = build_prompt(text, context, system_prompt=GGUF_ROUTE_PROMPT)
        return parse_route(self._generate(prompt, context, self._route_grammar))

    def respond(self, text: str, context: IntentContext) -> str:
        prompt = build_prompt(text, context, system_prompt=REPLY_PROMPT, chat_history=True)
        return parse_reply(self._generate(prompt, context, self._reply_grammar))

    def _generate(self, prompt: str, context: IntentContext, grammar: Any) -> str:
        with self._lock:
            if self._state is not ModelState.READY:
                raise ModelInferenceError("GGUF model must be loaded before prediction")
            try:
                tokens = self._model.tokenize(prompt.encode("utf-8"), special=True)
                if len(tokens) > context.max_context_tokens:
                    raise ModelInferenceError("prompt exceeds context token limit")
                started = time.perf_counter()
                response = self._model.create_completion(
                    prompt=tokens,
                    max_tokens=context.max_generated_tokens,
                    temperature=0,
                    repeat_penalty=1.0,
                    grammar=grammar,
                    stop=["<|im_end|>"],
                    stream=False,
                )
                choice = response["choices"][0]
                self.last_metrics = {
                    **response["usage"],
                    "inference_ms": (time.perf_counter() - started) * 1000,
                }
                if choice["finish_reason"] == "length":
                    raise ModelInferenceError("model output exceeded token budget")
                output = choice["text"]
            except ModelInferenceError:
                raise
            except Exception as error:
                raise ModelInferenceError(f"Local GGUF inference failed: {error}") from error
            return output

    def model_info(self) -> dict[str, Any]:
        return {
            "model_id": MODEL_ID,
            "quantizer_revision": MODEL_REVISION,
            "model_path": str(self.model_path),
            "artifact_present": self.model_path.is_file(),
            "artifact_size_bytes": MODEL_SIZE,
            "sha256": MODEL_SHA256,
            "runtime": "llama-cpp-python",
            "runtime_version_required": RUNTIME_VERSION,
            "gpu_layers": self.gpu_layers,
            "state": self.state.value,
            "load_time_ms": self.load_time_ms,
            "last_inference": self.last_metrics,
        }

    def _prepare_cuda_dlls(self) -> None:
        """Expose only installed inference dependency directories, never caller launch paths."""
        if sys.platform != "win32" or self._dll_directories:
            return
        libraries = []
        for package, relative, library in (
            ("nvidia-cuda-runtime-cu12", "nvidia/cuda_runtime/bin", "cudart64_12.dll"),
            ("nvidia-cublas-cu12", "nvidia/cublas/bin", "cublas64_12.dll"),
        ):
            try:
                directory = importlib.metadata.distribution(package).locate_file(relative)
            except importlib.metadata.PackageNotFoundError:
                continue  # CPU-only wheels need neither CUDA package.
            self._dll_directories.append(os.add_dll_directory(str(directory)))
            libraries.append(directory / library)
        # The pinned upstream loader uses winmode=256, omitting user DLL directories.
        # Preload these exact installed CUDA dependencies with Python's secure default flags.
        self._cuda_libraries.extend(ctypes.CDLL(str(library)) for library in libraries)
