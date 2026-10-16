"""Explicit local Q4/Q8 diagnosis on synthetic text. Never connects to Core or launches apps."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.contract import ConversationTurn, IntentContext
from jarvis_brain.intelligence.models import qwen_gguf

REFERENCE_REVISION = "e6f794d44f9395d0184a966c27b5ae99ea356fcb"
REFERENCE_SHA256 = "ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1"
REFERENCE_SIZE = 4280403520
REFERENCE_NAME = "qwen3-4b-instruct-2507-q8_0.gguf"
REFERENCE_URL = (
    "https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/resolve/"
    + REFERENCE_REVISION
    + "/"
    + REFERENCE_NAME
)
QUESTION = "Hangi klasöre kaydetmiş olabilirsin?"
# Fixed before loading the comparison artifact; measure raw semantics, not execution guards.
CASES = (
    ("ownership", "operation", "Türkçe olan benim dosyam", "keep", ""),
    ("identity", "operation", "bu dosyadan bahsediyorum", "keep", ""),
    ("scope_only", "operation", "alt klasör araması yapma", "keep", ""),
    ("polite_open", "operation", "İkinci dosyayı açabilir misin", "open", ""),
    (
        "named_view",
        "operation",
        "Türkçe sürümü Microsoft Edge üzerinden görüntüle",
        "open",
        "",
    ),
    ("read_contents", "operation", "bu belgenin içeriğini oku", "unsupported", ""),
    ("size_search", "operation", "en büyük dosyaları göster", "find", ""),
    ("location_answer", "route", "masaüstüne kaydetmiştim", "locate_file", QUESTION),
    ("self_help", "route", "dosyamı kendim nasıl bulurum", "how_to", QUESTION),
    ("capability", "route", "uygulama açabilir misin", "capability", ""),
    (
        "lost_document",
        "route",
        "Başvuruda kullandığım özgeçmişi bulamıyorum yardım eder misin",
        "locate_file",
        "",
    ),
    ("recall", "route", "Az önce senden hangi klasörü açmanı istemiştim", "recall", ""),
    ("emotion", "route", "Bugün güzel bir haber aldım çok mutluyum", "discussion", ""),
    ("prohibition", "route", "Lütfen hiçbir program açma", "prohibition", ""),
)


def artifact_path():
    root = Path(tempfile.gettempdir()).resolve()
    target = (root / "jarvis-reference-models" / REFERENCE_NAME).resolve()
    if not target.is_relative_to(root):
        raise ValueError("reference cache must stay inside the temporary directory")
    return target


def verify(path):
    if path.stat().st_size != REFERENCE_SIZE:
        raise ValueError("reference artifact size mismatch")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != REFERENCE_SHA256:
            raise ValueError("reference artifact SHA256 mismatch")


def provision():
    target = artifact_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        verify(target)
        print("Reference already verified:", target)
        return
    if shutil.disk_usage(target.parent).free < REFERENCE_SIZE + 512 * 1024**2:
        raise RuntimeError("insufficient space for the reference artifact")
    partial = target.with_suffix(".gguf.part")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > REFERENCE_SIZE:
        raise ValueError("unexpected oversized partial artifact")
    if offset < REFERENCE_SIZE:
        request = urllib.request.Request(
            REFERENCE_URL, headers={"Range": f"bytes={offset}-"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 206:
                offset = 0
            elif not response.headers.get("Content-Range", "").startswith(
                f"bytes {offset}-"
            ):
                raise ValueError("unexpected partial response range")
            next_progress = offset + 256 * 1024**2
            with partial.open("ab" if offset else "wb") as destination:
                for chunk in iter(lambda: response.read(4 * 1024**2), b""):
                    offset += len(chunk)
                    if offset > REFERENCE_SIZE:
                        raise ValueError("reference response exceeds pinned size")
                    destination.write(chunk)
                    if offset >= next_progress:
                        print(f"Downloaded {offset}/{REFERENCE_SIZE} bytes", flush=True)
                        next_progress = offset + 256 * 1024**2
    verify(partial)
    partial.replace(target)
    print("Reference verified:", target, flush=True)


def evaluate(profile, repeats):
    reference = artifact_path()
    if profile == "q8":
        verify(reference)
    pins = (
        {"MODEL_SIZE": REFERENCE_SIZE, "MODEL_SHA256": REFERENCE_SHA256}
        if profile == "q8"
        else {}
    )
    report = {"profile": profile, "synthetic_only": True, "core_calls": 0, "rows": []}
    with patch.multiple(qwen_gguf, **pins) if pins else patch.dict({}, {}):
        model = qwen_gguf.QwenGgufIntentModel(reference if profile == "q8" else None)
        try:
            model.load()
            keys = (
                "general.architecture",
                "general.file_type",
                "general.quantization_version",
                "qwen3.block_count",
                "qwen3.embedding_length",
                "qwen3.context_length",
                "tokenizer.ggml.model",
                "tokenizer.ggml.bos_token_id",
                "tokenizer.ggml.eos_token_id",
            )
            report["metadata"] = {k: model._model.metadata.get(k) for k in keys}
            tokens = model._model.tokenize(
                b"Bu benim dosyam. Open the selected file.", special=True
            )
            report["tokenizer_probe_sha256"] = hashlib.sha256(
                json.dumps(tokens).encode()
            ).hexdigest()
            for repeat in range(repeats):
                for name, family, text, expected, question in CASES:
                    history = (
                        (
                            ConversationTurn(
                                "İndirilenler klasörünü aç", "Klasör bulunamadı."
                            ),
                        )
                        if name == "recall"
                        else ()
                    )
                    context = IntentContext(
                        history=history, pending_file_question=question
                    )
                    row = {"case": name, "repeat": repeat, "expected": expected}
                    started = time.perf_counter()
                    try:
                        actual = (
                            model._current_operation(text, context)
                            if family == "operation"
                            else model.classify_request(text, context).purpose.value
                        )
                        row.update(actual=actual, correct=actual == expected)
                    except JarvisBrainError as error:
                        row.update(
                            error=f"{type(error).__name__}: {error}", correct=False
                        )
                    row.update(
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
                        inference=model.last_metrics,
                    )
                    report["rows"].append(row)
                    print(
                        profile,
                        name,
                        row.get("actual", row.get("error")),
                        row["correct"],
                        flush=True,
                    )
        finally:
            model.unload()
    report["correct"] = sum(row["correct"] for row in report["rows"])
    report["total"] = len(report["rows"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-reference", action="store_true")
    parser.add_argument("--run-local-model", action="store_true")
    parser.add_argument("--profile", choices=("q4", "q8"), default="q4")
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.download_reference:
        provision()
    if args.run_local_model:
        if args.output is None:
            parser.error("--output is required for a model comparison")
        report = evaluate(args.profile, args.repeats)
        report.update(
            reference_url=REFERENCE_URL,
            reference_sha256=REFERENCE_SHA256,
            reference_size=REFERENCE_SIZE,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(report["correct"], "/", report["total"], flush=True)
    elif not args.download_reference:
        parser.error("explicit --download-reference or --run-local-model is required")


if __name__ == "__main__":
    main()
