# Generated local models

Model weights and native runtime DLLs are provisioned artifacts, excluded from Git.
Only this README is versioned in this directory. Runtime startup never downloads them.

| Directory | Role | Explicit setup |
|---|---|---|
| `qwen35-9b-reference/` | Current GGUF agent | `scripts/models/provision_agent_reference.py` |
| `qwen3-4b-gguf/` | Alternative GGUF agent | `scripts/models/provision_qwen_gguf.py` |
| `whisper-large-v3-turbo-q5_0/` | Current Windows speech model | `scripts/models/provision_speech.py` |
| `whisper-small/`, `whisper-large-v3-turbo/` | Explicit speech comparisons | `provision_speech.py --profile <profile>` |
| `whisper-vad/` | Native CPU Silero GGML | Included in speech provisioning |
| `transcribe-runtime/` | Pinned transcribe.cpp CPU/Vulkan DLLs and import library | `scripts/models/provision_transcribe.ps1` |
| `qwen3-0.6b-int4/` | Historical ONNX diagnostic artifacts; disabled in production | `scripts/models/build_qwen3_int4.ps1` |

Provisioning pins artifact identity and checksums in the scripts/manifests. The native runtime
file allowlist is versioned as `scripts/models/transcribe-runtime-pins.json`; the DLLs are not.
See [native speech setup](../docs/brain/NATIVE_SPEECH_PROVIDER.md) and
[agent loop](../docs/brain/AGENT_LOOP.md) for current defaults and acceptance limits.
