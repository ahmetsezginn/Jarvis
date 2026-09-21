"""Repeatable Turkish/English router and real Qwen INT4 benchmark."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any

from jarvis_brain import config
from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import IntentContext
from jarvis_brain.intelligence.fast_router import FastIntentRouter
from jarvis_brain.intelligence.models.qwen_onnx import QwenOnnxIntentModel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path(__file__).with_name("intents.json")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--router-only", action="store_true")
    arguments = parser.parse_args()
    dataset = json.loads(arguments.dataset.read_text(encoding="utf-8"))
    router = FastIntentRouter()
    routed = [(item, router.route(item["text"])) for item in dataset]
    fast_hits = sum(result is not None for _, result in routed)

    model = QwenOnnxIntentModel()
    idle = _memory_bytes()
    load_ms: float | None = None
    after_load = idle
    if not arguments.router_only:
        started = time.perf_counter()
        model.load()
        load_ms = (time.perf_counter() - started) * 1000.0
        after_load = _memory_bytes()

    correct_intents = 0
    query_cases = 0
    correct_queries = 0
    invalid_outputs = 0
    unsafe_outputs = 0
    inference_latencies: list[float] = []
    generated_tokens: list[int] = []
    results: list[dict[str, Any]] = []
    context = IntentContext(config.MAX_CONTEXT_TOKENS, config.MAX_GENERATED_TOKENS)
    for item, fast_result in routed:
        result = fast_result
        route = "fast"
        error: str | None = None
        if result is None and not arguments.router_only:
            route = "model"
            try:
                result = model.predict(item["text"], context)
                unsafe_outputs += int(model.last_output_unsafe_fields)
                if model.last_metrics is not None:
                    inference_latencies.append(model.last_metrics.inference_ms)
                    generated_tokens.append(model.last_metrics.generated_tokens)
            except JarvisBrainError as failure:
                invalid_outputs += 1
                error = f"{failure.__class__.__name__}: {failure}"
        intent = None if result is None else result.intent.value
        correct_intents += int(intent == item["intent"])
        expected_query = item.get("query")
        if expected_query is not None:
            query_cases += 1
            actual_query = None if result is None else result.arguments.get("query")
            correct_queries += int(actual_query == expected_query)
        results.append(
            {
                "text": item["text"],
                "expected_intent": item["intent"],
                "actual_intent": intent,
                "confidence": None if result is None else result.confidence,
                "arguments": None if result is None else dict(result.arguments),
                "route": route,
                "error": error,
            }
        )

    peak = _memory_bytes()[1]
    fallback_count = len(dataset) - fast_hits
    artifact_manifest = _manifest(model.model_path)
    report = {
        "runtime": {
            "model": config.MODEL_ID,
            "revision": config.MODEL_REVISION,
            "precision": "INT4",
            "execution_provider": "CPUExecutionProvider",
            "onnxruntime_genai_version": config.ONNXRUNTIME_GENAI_VERSION,
            "context_tokens": config.MAX_CONTEXT_TOKENS,
            "output_tokens": config.MAX_GENERATED_TOKENS,
            "cpu": platform.processor()
            or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        },
        "artifact_size_bytes": artifact_manifest.get("artifact_size_bytes"),
        "memory": {
            "idle_rss_bytes": idle[0],
            "after_load_rss_bytes": after_load[0],
            "peak_rss_bytes": peak,
        },
        "latency_ms": {
            "cold_load": load_ms,
            "first_inference": inference_latencies[0] if inference_latencies else None,
            "warm_inference_median": (
                statistics.median(inference_latencies[1:])
                if len(inference_latencies) > 1
                else None
            ),
        },
        "routing": {
            "cases": len(dataset),
            "fast_hits": fast_hits,
            "fast_hit_rate": fast_hits / len(dataset),
            "model_fallbacks": fallback_count,
            "model_fallback_rate": fallback_count / len(dataset),
        },
        "quality": {
            "intent_accuracy": correct_intents / len(dataset),
            "argument_accuracy": correct_queries / query_cases,
            "invalid_structured_output_rate": (
                invalid_outputs / fallback_count if fallback_count else 0.0
            ),
            "unsafe_field_generation_rate": (
                unsafe_outputs / fallback_count if fallback_count else 0.0
            ),
        },
        "generated_tokens": {
            "first": generated_tokens[0] if generated_tokens else None,
            "median": statistics.median(generated_tokens) if generated_tokens else None,
            "maximum": max(generated_tokens) if generated_tokens else None,
        },
        "results": results,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded + "\n", encoding="utf-8")
    return 0


def _manifest(model_path: Path) -> dict[str, Any]:
    path = model_path / "MODEL_MANIFEST.json"
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _memory_bytes() -> tuple[int, int]:
    if os.name != "nt":
        return 0, 0

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    process = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return counters.WorkingSetSize, counters.PeakWorkingSetSize


if __name__ == "__main__":
    raise SystemExit(main())
