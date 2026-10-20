# Windows distribution and cleanup — 2026-10-20

The user requested model cleanup, readable installation instructions, a shareable installer
and a final source push. CPU support was explicitly added despite slower execution.
All installer generation scripts, compiler tools, packaging environments, staged payloads,
QA installations and output binaries remain under ignored `.local-distribution/`.
They are **not part of the Git publication**. Source portability fixes and documentation are.

## Product layout

Local artifact: **641,012,772 bytes**, SHA-256
`17fca7a60c5f386cb39ae5c2cdb93d4ef3a07f011d37aa904cf72aa829d3c1be`.
The adjacent local-only `KURULUM.txt` and `SHA256SUMS.txt` accompany sharing.

`JarvisInstaller-0.3.0-preview.1.exe` is a per-user Windows x64 preview installer. Recipients
need neither Python nor Rust installed. It contains the Python interpreter, Qt, Brain,
native Core, speech runtime and optional wake package. Setup explicitly provisions the pinned
Qwen3.5-9B Q4_K_M, Whisper Turbo Q5 and Silero VAD files, about 6.3 GB in total. Normal startup
does not download models or call an inference API. Verified exact model files can instead
be provided in `offline-models` beside the installer.

CPU and NVIDIA are explicit setup choices. CPU uses the official pinned CPU-only
llama-cpp-python 0.3.35 library and CPU speech; its install excludes CUDA/Vulkan compute DLLs.
NVIDIA installs the GPU runtime without installing a driver. Neither mode silently falls
back to the other. The source CPU requirements are in
`scripts/models/requirements-gguf-cpu.txt`; use a separate environment from CUDA requirements.

The trusted installed bootstrap selects fixed resources, starts a fixed Core when needed,
and uses a fixed sibling Brain worker for Qt. Agent effects still go through
`JarvisCoreClient -> Named Pipe -> registry -> validation -> policy -> executor`.
No model-generated paths, shell commands or trusted IDs are introduced. Native speech resolves
installed models independently of the build checkout. Organizer data remains outside appDir
under `%LOCALAPPDATA%/JARVIS`; uninstall retains it. Wake is optional and reuses the protected
LocalService/fixed limited user-task setup with actual administrator consent.

## Model cleanup

Removed only these previously provisioned, verified-unused local directories:

| Directory | Reason |
|---|---|
| `models/qwen3-0.6b-int4` | Disabled ONNX provider |
| `models/qwen3-4b-gguf` | Superseded by active 9B profile |
| `models/whisper-small` | Superseded speech profile |
| `models/whisper-large-v3-turbo` | Superseded by active Q5 profile |
| `scripts/models/source/qwen3-0.6b-pinned` | Old conversion source |

Total removed: **6,534,116,969 bytes (6.085GiB)**. Each absolute path was checked inside its
intended workspace root, with no tracked files or reparse children. Active 9B, Turbo Q5,
VAD/native speech assets and wake runtime were retained. Historical source tests/reports
were retained. The separate Handy trial cache was preserved because it can contain recordings.
After final packaging, another 5,211,156,711 bytes of generated duplicate/pruned payload
copies were removed from the verified local `discarded` directory. These were build copies,
not additional source models. Final installer, active runtime and private build scripts remain.

## Validation

- Full Rust workspace: **136 passed / 9 opt-in ignored**; release workspace build, fmt and
  all-target Clippy with `-D warnings` passed.
- Brain and scripts/Qt: **616 passed / 209 skipped**; Ruff check/format passed for 135 files. Initial
  pytest setup failed because the existing Windows temporary directory was inaccessible;
  a fresh workspace-local basetemp passed without changing ACLs or skipping affected tests.
- Actual installer installed into a separate path containing spaces and Turkish characters.
  All three installed model hashes matched. The frozen CPU worker ran without external Python.
  The final CPU installation contained no NVIDIA llama/CUDA DLLs or Vulkan speech backend.
- Actual packaged 9B workers produced a greeting in both CPU and NVIDIA modes through the same
  worker protocol. CPU loaded no CUDA modules; NVIDIA loaded `ggml-cuda.dll` and the NVIDIA
  driver/runtime. One sequential greeting trial measured 152.41s CPU and 33.51s NVIDIA from worker
  launch through reply and exit; model_ready was 6.97s and 23.30s respectively. Cache/load order
  affects these measurements. They are not warm latency or cross-hardware benchmarks.
- Real QML loaded from the frozen payload with its fixed sibling worker path.
- The final installed CPU speech DLL/model layout passed native synthetic Turkish, English
  and automatic-language transcription in 35.25s total, without microphone access. Individual
  cases were 21.59s, 6.64s and 6.99s; this is fixture evidence, not personal speech acceptance.
- The installed NVIDIA speech layout passed the same fixtures in 32.96s total: 30.71s for
  the cold first case, then 1.08s and 1.13s. These include initialization and model setup.
- Installed native VAD independently loaded its pinned model without a model-directory
  override, rejected silence/noise and segmented/transcribed a public speech fixture in
  27.42s. No microphone was opened.
- Uninstall removed managed application/model files while preserving the exact synthetic
  organizer database in a separate QA user-data directory. The existing developer wake service
  remained running; setup tests did not replace it or alter personal notes/tasks.
- The fixed installed PowerShell wake bridge waited for a three-second synthetic GUI fixture
  to exit. This tested process lifetime without installing/replacing the actual service.
- The exact final artifact completed fresh CPU installation, corrupt-model preflight rejection,
  reinstallation in NVIDIA mode, frozen GPU self-test, QML load and real CLI Named Pipe `ping`.
  The NVIDIA reinstallation reused verified installed models without downloading them again.
  Both mode checks used a cleared Python/model environment and no external Python interpreter.

An adversarial corrupt-sidecar test initially exposed that an exception inside an Inno file
`Check` condition was logged but treated as a skipped entry, allowing an incomplete successful
install. Validation was moved to `PrepareToInstall`, returning a blocking pre-install error.
The repeated corrupt-sidecar test passed: setup exited with code 7 before installing the app.
The actual repair test removed only the installed/supplied small VAD fixture. Setup downloaded
it from the pinned URL, verified it and finished successfully; an independent SHA-256 matched.
The first log assertion expected a different download-success phrase; it was corrected against
the actual `Downloading file from` / `Verification successful` log and the same completed run
was verified without another download.
The installed terminal smoke also exposed a packaging-only CLI entry mismatch: `main()`
accepts no positional arguments. The trusted bootstrap now sets the fixed CLI argument vector
and calls the existing entry point correctly. The rebuilt frozen executable passed real
Named Pipe `ping`; no source CLI or model/action routing change was needed.

## Commands and local evidence

```powershell
cargo build --workspace --release --locked --target-dir target/wake-service -j2
cargo test --workspace --locked --target-dir target/organizer-validation -j2
cargo clippy --workspace --all-targets --locked --target-dir target/organizer-validation -j2 -- -D warnings
cargo fmt --all -- --check
python -m pytest services/brain/tests scripts/tests -q --basetemp .local-distribution/pytest-final-2
python -m ruff check services/brain services/desktop/main.py scripts
python -m ruff format --check services/brain services/desktop/main.py scripts
```

Local-only evidence includes `.local-distribution/{rust-tests-final,python-tests-final-2,
clippy-final,installer-final-qa,installed-cpu-asr,qa-install,qa-uninstall}.log`,
`runtime-qa-results.json`, `corruption-qa.log`, `download-repair-qa-verified.log`, model pins
and `gpu-installer-qa.log`, `wake-bridge-qa.log` and frozen build logs. Packaging tools are intentionally
not versioned. These logs contain only synthetic QA records/fixtures and build diagnostics.

## Remaining limits

This preview has not been tested in a clean Windows VM or on another CPU/GPU. The host has
an RTX 4070 Laptop GPU; CPU-only behavior was checked by library selection, omitted GPU files
and loaded-module inspection, not on a machine physically lacking an NVIDIA driver.
Code signing was not configured for this build, so the installer is unsigned. No security
settings or SmartScreen/antivirus controls were changed. Optional service installation was
not repeated during installer QA to avoid replacing the existing developer service.
Speech/wake accuracy, barge-in room acoustics and earlier semantic failures remain documented
separately; packaging checks do not turn them into general assistant acceptance.

Bundled license texts/notices include Qt/PySide, llama.cpp, native speech, Qwen, Whisper,
Silero and GPU runtime notices. Optional pretrained wake graphs use CC BY-NC-SA 4.0, so this
preview is for personal/non-commercial evaluation. Installed shared Qt libraries remain
replaceable. No private models, audio recordings or organizer databases are distributed.
