# Local model comparison — 2026-09-15

## Decision

Qwen3-4B-Instruct-2507 Q4_K_M is installed and available as an **opt-in development backend**.
It improves this diagnostic substantially, but does not meet the zero-wrong-action-proposal gate.
Do not promote it as a reliable conversational assistant. The ONNX baseline remains selectable
and the default is unchanged; that default is not a claim that the old model is safer or better.

Hardware: 32 GB RAM, NVIDIA RTX 4070 Laptop GPU, 8188 MiB VRAM. GGUF uses GPU offload;
historical ONNX numbers use CPU, so the latency comparison is a stack comparison, not a
controlled model-size experiment. No fine-tuning was performed.

## Same public seed dataset, same system prompt

28 single-turn cases were attempted. Eight history/catalog-context cases remain unsupported
and are included in the report's 36-case denominator. This is exposed diagnostic data, not a
held-out test or a general intelligence score. Queries use exact case/space-normalized matching.

| Stack | Correct / 28 | Wrong action proposals | Invalid output | p50 / p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Historical 0.6B ONNX, model only | 2 | 9 | 14 | 3980 / 4205 |
| 4B GGUF CUDA, model only | 19 | 3 | 1 | 1373 / 2370 |
| Historical router + ONNX | 11 | 10 | 5 | 0.086 / 4069 |
| Unchanged router + 4B GGUF | 19 | 8 | 0 | 0.099 / 2031 |

Wrong proposals are semantic mismatches, **not observed OS launches**: this evaluator cannot
construct a Core client. Some mismatches concern extra query words rather than a different app.
However, negation and conditional-command errors are material. A high self-reported confidence
does not establish correctness. The router increases wrong proposals from 3 to 8: it can capture
complex sentences as app names before the model sees them. Rust does not cause those extraction
errors. Conversely, application availability and ambiguity still correctly belong to Rust.

The new model still fails `vs cod` and some Turkish negation/correction examples. Adding model
parameters alone cannot supply missing conversation history, evidence or unsupported capabilities.
Next work should separately address narrow fast-path admission and bounded session/candidate
context, then rerun independent evaluation before expanding tools or considering fine-tuning.

## Measured resources and provenance

- Artifact: 2,497,281,120 bytes (2.33 GiB).
- Model-only cold load including SHA256 verification: 3532 ms.
- Model-only process RSS after load: 2,887,180,288 bytes; peak: 3,323,412,480 bytes.
- Observed whole-GPU usage during evaluation: 4333 MiB; other applications also use VRAM,
  so this is not attributable model-only VRAM.
- Quantization repository: `unsloth/Qwen3-4B-Instruct-2507-GGUF`.
- Revision: `a06e946bb6b655725eafa393f4a9745d460374c9`.
- Artifact SHA256: `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.
- Runtime: official llama-cpp-python 0.3.35 CUDA 12.4 Windows wheel, pinned digest in requirements.
- Dataset SHA256: `e744fed53137e30e03b79e06aca743113f7d9f7ab2195d3eee1935298e119628`.
- System/schema prompt file SHA256: `1982526046c4b34955138195b6ac85ca2618b31fb80c4b82731b19b05cbefb12`.

GGUF uses its non-thinking-only template, a different decoding implementation and no old forced
think prefix. Results therefore do not isolate ONNX conversion, decoding, prompt template and
model capacity individually. Reports are reproducible via the Brain README commands, saved at
`reports/benchmarks/gguf-model.json` and `gguf-combined.json` (generated files ignored by Git).

## Sources

- [Official model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Quantizer artifact](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)
- [Official runtime](https://github.com/abetlen/llama-cpp-python)

No HTTP port, firewall exception, runtime download or direct Python machine-action API was added.
The architecture deviation from M003 is documented in ARCHITECTURE and AGENTS.

## Validation

Passed: Rust build/fmt/clippy and 61 tests; Python 99 unit tests (two opt-in tests skipped in the
default run); both opt-in real GGUF and historical ONNX tests; new-model Windows E2E and
process-guard offline E2E. Real E2E opened Chrome and read status through the existing Rust tools.
No Core process was started or stopped by this comparison; the existing user Core was reused.

The offline run blocks Python socket APIs and uses offline flags. It is **not** an OS firewall
isolation proof and does not intercept native DLL network calls; the host previously denied
firewall-rule creation. No firewall exception was added. CPU-only performance and hard native
inference cancellation remain unverified/unsupported respectively.

Exact checks from repository root:

```powershell
cargo fmt --check
cargo build
cargo clippy --all-targets --all-features -- -D warnings
cargo test
.\services\brain\.venv\Scripts\python.exe -m ruff check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m ruff format --check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration
$env:JARVIS_MODEL_BACKEND = 'gguf'
.\services\brain\.venv\Scripts\python.exe -m scripts.tests.windows_e2e
.\scripts\tests\run_offline_e2e.ps1 -ProcessGuardOnly
```

Implementation files: GGUF adapter/factory, CLI and launcher model reuse, provisioning script
and CUDA requirements, evaluation reporting, real E2E provider selection, adapter/REPL/integration
tests, AGENTS/ARCHITECTURE/process/Brain documentation and a minimal main README setup link.
Rust application resolution, policy and executor code were not changed in this comparison.
