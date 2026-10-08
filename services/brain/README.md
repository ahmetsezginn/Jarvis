# JARVIS Brain

This Python 3.12+ package contains the local TASK-003 intent runtime and the TASK-002 client for
the trusted Rust Core. A small deterministic Fast Router handles obvious commands; other commands
fall back lazily to a locally provisioned Qwen3-0.6B INT4 CPU model through ONNX Runtime GenAI.

Brain never discovers or launches applications, implements system status, runs a shell, or copies
the Rust tool registry. Every machine action remains:

```text
JarvisBrain -> JarvisCoreClient -> Named Pipe -> Rust Registry -> Validation
            -> Policy -> Executor -> Tool -> Platform
```

Run the following commands from the repository root to create an isolated environment and install
the package with its development checks:

```powershell
py -3.12 -m venv .\services\brain\.venv
.\services\brain\.venv\Scripts\python.exe -m pip install -e ".\services\brain[dev]"
```

Production inference depends on `onnxruntime-genai==0.15.2`; it does not require PyTorch or
Transformers. Those packages exist only in the isolated provisioning environment.

## One-command terminal launcher

Within one interactive session, application ambiguity is now remembered for 120 seconds.
When JARVIS displays numbered candidates, reply `üstteki`, `ikinci`, `2`, `alttaki`, or an exact
displayed name. Rust re-resolves the chosen name and must return the same ID before launch.
`iptal`, a new request, expiry or a completed selection clears the pending list. `diğeri` without
a clear reference asks for a number. This is bounded selection memory, not general chat history;
separate `ask` processes do not share it. No extra setup or model download is needed.

PowerShell profile integration: `scripts/shell/jarvis-profile.ps1` defines `jarvis` as the
repository launcher with `-Model gguf`. Dot-source it from your user profile to use `jarvis`
from any directory. It starts nothing until invoked and changes no execution-policy/firewall settings.
After installation, open a new PowerShell terminal, or dot-source the integration in the current one.

Fast Router is temporarily **OFF by default** for CLI `ask`, `repl`, and `predict`, at the user's
request. Strict validation and the Rust policy/execution boundary remain enabled. To select the
new model unambiguously without setting environment variables:

```powershell
.\jarvis.ps1 -Model gguf
```

The launcher displays backend/routing selection and restores the previous backend environment
on exit. Use `-Model onnx` for the historical model, or `-FastRouter` to restore legacy routing.
Direct Python CLI commands still use `JARVIS_MODEL_BACKEND` (default `onnx`); `--force-model`
does not select GGUF. `--fast-router` opts into routing. Library/evaluation defaults are unchanged.
These are intent models, not a general chat interface; greetings can still be misclassified.

### Opt-in stronger local model

See [measured comparison and known failures](../../docs/brain/LOCAL_MODEL_COMPARISON.md).

The user-authorized replacement candidate is Qwen3-4B-Instruct-2507 Q4_K_M (2,497,281,120
bytes), running **in-process** with llama-cpp-python 0.3.35. No HTTP server, cloud provider,
runtime download, PyTorch or Transformers is used. The historical ONNX backend remains the
default until comparative quality is accepted. Explicit provisioning on this NVIDIA Windows host:

```powershell
.\services\brain\.venv\Scripts\python.exe -m pip install -r scripts/models/requirements-gguf-cuda.txt
.\scripts\models\.model-build\Scripts\python.exe scripts/models/provision_qwen_gguf.py
$env:JARVIS_MODEL_BACKEND = 'gguf'
.\jarvis.ps1
```

The provisioning script needs `truststore` in the isolated model-build environment; it downloads
one pinned Unsloth quantization and verifies SHA256. The adapter checks the same checksum before
native loading. `JARVIS_MODEL_DEVICE=cpu` disables GPU offload (CPU latency is not yet measured).
The CUDA wheel also needs the pinned NVIDIA runtime dependencies in the requirements file;
no system-wide CUDA Toolkit installation is required. NVIDIA licensing applies to those binaries.

The interactive launcher now retains one Brain and loaded model until exit. It does **not** yet
remember general conversation turns; only the bounded pending selection described above is retained.
For a non-executing comparison:

```powershell
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --backend gguf --mode model --output reports/benchmarks/gguf-model.json
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --backend gguf --mode combined --output reports/benchmarks/gguf-combined.json
$env:JARVIS_RUN_GGUF_TESTS = '1'
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration/test_real_gguf.py
```

Set `JARVIS_MODEL_BACKEND=onnx` to return explicitly to the historical baseline.

From the repository root, run a single request with:

```powershell
.\jarvis.ps1 "Google Chrome'u aç"
```

Or start an interactive prompt:

```powershell
.\jarvis.ps1
```

The launcher starts the exact local `jarvis-core.exe` in a hidden window when the Named Pipe is
not already available. The Core remains available for later commands by default. Use
`-StopCoreOnExit` for a disposable test session. User text still goes through the Brain client,
Named Pipe, Rust validation, policy, executor, tool, and platform path.

## Provision the local model

Provisioning requires network access once and is never performed by Brain at runtime:

```powershell
.\scripts\models\build_qwen3_int4.ps1
```

The supported ONNX Runtime GenAI builder converts pinned revision
`c1899de289a04d12100db370d81485cdf75e47ca` of `Qwen/Qwen3-0.6B` to symmetric INT4 for CPU. The
generated `models/qwen3-0.6b-int4/MODEL_MANIFEST.json` records source, tool versions, measured size,
and SHA-256 checksums. Model weights are intentionally ignored by Git. Override the local artifact
location only with `JARVIS_QWEN_MODEL_PATH`; no configured path triggers a download.

With `jarvis-core serve` running, use:

```powershell
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli ping
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli tools
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli status
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli open-app "Google Chrome"
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli ask "Google Chrome'u aç"
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli ask "Bilgisayarım nasıl durumda?"
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli model-info
.\services\brain\.venv\Scripts\python.exe -m jarvis_brain.cli predict --force-model "Google Chrome uygulamasını benim için başlatabilir misin?"
```

`predict` performs validated inference only and cannot execute a Core tool. `--force-model`
bypasses only the Fast Router. `ask` can execute supported intents, but application opening always
sends the human name to Rust `resolve_app` and only passes Rust's returned `app_id` to `open_app`.

## Validation and benchmarks

```powershell
.\services\brain\.venv\Scripts\python.exe -m ruff format --check services\brain scripts
.\services\brain\.venv\Scripts\python.exe -m ruff check services\brain scripts
.\services\brain\.venv\Scripts\python.exe -m pytest services\brain\tests
$env:JARVIS_RUN_MODEL_TESTS = '1'
.\services\brain\.venv\Scripts\python.exe -m pytest services\brain\tests\integration\test_real_qwen.py
.\services\brain\.venv\Scripts\python.exe -m scripts.benchmarks.benchmark_intents --output reports\benchmarks\m003.json
```

For Windows E2E, start `jarvis-core serve`, then run:

```powershell
.\services\brain\.venv\Scripts\python.exe -m scripts.tests.windows_e2e
.\scripts\tests\run_offline_e2e.ps1
```

The offline script's default path creates and verifies a temporary outbound Windows Firewall rule
for the Brain Python executable and removes it in `finally`; run it from an elevated shell. On a
managed host that forbids firewall changes, `-ProcessGuardOnly` denies Python socket creation and
connect calls, verifies the denial with a network canary, sets offline flags, and repeats the same
real model + Named Pipe flows. It is a weaker process-level substitute and is reported as such.

The current 20-case Turkish/English benchmark records artifact size, RSS, cold/warm latency,
generated tokens, routing rates, intent/argument accuracy, invalid structured output, and unsafe
field generation. A rejected model result is a safe failure and never reaches Core.

## Brain requirements and diagnostic assessment

See [requirements and evaluation design](../../docs/brain/REQUIREMENTS.md) and
[baseline findings](../../docs/brain/BASELINE.md). The old benchmark is not a held-out quality test.
The public 36-case seed corpus separates known regressions from new diagnostic probes; it is not
training data or a sealed release test. Contextual cases are explicitly unsupported by the current
interface. These commands do not connect to Core or open applications:

```powershell
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --validate-only
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --mode router
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --mode model
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --mode combined
```

Run from the repository root. Model/combined modes require the already provisioned artifact.
Exit zero means measurement completed, not that the Brain meets release targets. Model-load
failure terminates the run; per-request failures remain visible in its JSON report.

## Session conversation memory

The interactive `repl` keeps up to six recent user/assistant pairs within a 2400-character
budget in memory. Both local models receive that context; model quality is still evaluated
separately. Type `/reset` to clear conversation and pending app selection. Exiting discards
memory. Separate `ask` commands do not share context. With history, contextual turns use the
model even when `--fast-router` is enabled. See ../../docs/brain/SESSION_CONTEXT.md.

## Readable terminal responses

`ask` and `repl` now show the response message directly by default, after the existing
Core result. Use `--json` on either command to retain full structured diagnostics.
`predict`, `status`, `tool` and other diagnostic commands keep their JSON output.
Application success notifications are deterministic Core-backed messages; this display
change does not add general chat or change the closed intent contract.

## No-action interpretation diagnostic

Run `python -m scripts.evaluation.evaluate_reasoning --output reports/benchmarks/reasoning.json`
from the repository root with the configured local provider. It never connects to Core.
GGUF uses a refined decision prompt; ONNX retains its compact prompt. General chat and ordinary
recall replies remain outside the four-intent contract. See ../../docs/brain/REASONING_DIAGNOSTIC.md.

## Conversation versus tasks

Interactive GGUF sessions first distinguish ordinary conversation from positive action/live
inspection requests. Conversation gets a short local reply and never dispatches tools. Tasks
continue through validated intents and Rust policy. `--json` exposes route=conversation and
executed=false for replies. `--fast-router` is now diagnostic-only; executing sessions always
use modality admission and task validation. ONNX is command-only and refuses conversation
generation with a typed error. Session reset and memory limits remain unchanged.

If the venv console launcher is missing but its base interpreter and packages still exist,
jarvis.ps1 can use the existing interpreter recorded in pyvenv.cfg, with no download or reinstall.
See ../../docs/brain/REQUEST_ROUTING.md for validation and limits.
