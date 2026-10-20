# Generated local models

Model weights and native runtime DLLs are provisioned artifacts, excluded from Git.
Only this README is versioned in this directory. Runtime startup never downloads them.

| Directory | Role | Explicit setup |
|---|---|---|
| `qwen35-9b-reference/` | Current GGUF agent | `scripts/models/provision_agent_reference.py` |
| `qwen3-4b-gguf/` | Optional comparison; removed from this host's active setup | `scripts/models/provision_qwen_gguf.py` |
| `whisper-large-v3-turbo-q5_0/` | Current Windows speech model | `scripts/models/provision_speech.py` |
| `whisper-small/`, `whisper-large-v3-turbo/` | Optional comparisons; removed from this host | `provision_speech.py --profile <profile>` |
| `whisper-vad/` | Native CPU Silero GGML | Included in speech provisioning |
| `transcribe-runtime/` | Pinned transcribe.cpp CPU/Vulkan DLLs and import library | `scripts/models/provision_transcribe.ps1` |
| `qwen3-0.6b-int4/` | Historical ONNX; disabled and removed from this host | `scripts/models/build_qwen3_int4.ps1` |

Cleanup on 20 October 2026 removed those four unused model directories and the old pinned
0.6B conversion source (6,534,116,969 bytes total). Current 9B, Turbo Q5, VAD and native speech
runtime are retained. Historical comparisons require explicitly reprovisioning their artifacts;
their test/report source is preserved. No personal data or microphone recordings were removed.

Provisioning pins artifact identity and checksums in the scripts/manifests. The native runtime
file allowlist is versioned as `scripts/models/transcribe-runtime-pins.json`; the DLLs are not.
See [native speech setup](../docs/brain/NATIVE_SPEECH_PROVIDER.md) and
[agent loop](../docs/brain/AGENT_LOOP.md) for current defaults and acceptance limits.
