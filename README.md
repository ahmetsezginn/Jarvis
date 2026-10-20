# JARVIS

A local AI assistant for Windows, built with a Rust execution core, a Python reasoning
service and a Qt desktop interface. Speak or type to find files, open applications and
manage personal tasks and notes without a cloud inference API.

JARVIS is a personal development prototype. It runs locally after explicit model/runtime
provisioning; it is not yet a packaged, generally reliable desktop assistant.

## What it can do

- Discover installed Windows applications, including packaged apps, and open catalog-backed matches.
- Search file/folder metadata within configured roots, browse folders and open supported documents
  with their Windows default application. Explicit PDF opening supports Chrome and Edge.
- Propose one likely result at a time, retain bounded conversational references and offer
  alternatives when a suggestion is rejected.
- Open validated Steam game shortcuts through the registered Windows Steam handler.
- Save personal tasks and notes outside the source checkout, recall daily agendas, complete or
  reopen tasks, copy a previous day's tasks and persist daily recurrence with per-day completion.
- Accept typed input, hold-to-talk or automatic conversation in the Qt interface, with local
  speech recognition and Windows speech output.
- Activate the desktop through an experimental independent **Hey Jarvis** Windows service.
  Closing the desktop exits Qt and its Brain worker, releasing the language model while the
  small native listener remains available.

File discovery reads names and metadata, not document contents. It covers configured roots
(Desktop, Documents and Downloads by default), with bounded scans and explicit partial results.
Timed reminders, cloud sync, file deletion and downloaded executable skills are not implemented.

## How it works

The model chooses a next step from registered semantic capabilities, receives actual tool
results and continues within a bounded agent loop. The current local default is
**Qwen3.5-9B Q4_K_M GGUF**, running in-process. ONNX is disabled in production.

```text
Text / voice / Qt UI
        |
Python Brain: model + capability/result loop
        |
JarvisCoreClient -> Windows Named Pipe
        |
Rust registry -> validation -> policy -> executor
        |
Windows / applications / local organizer storage
```

**The AI may request an action. The native core validates, authorizes and executes it.**
The model cannot supply executable paths, trusted application/file IDs or arbitrary shell
commands. Python and Qt do not bypass native execution policy.

- **Rust Core:** application/file catalogs, OS adapters, SQLite organizer, microphone/audio,
  registered tools, validation, policy and audit.
- **Python Brain:** local model integration, reasoning, capability selection and bounded
  session context. Conversation is not persisted or used for training.
- **Qt Quick / PySide6:** desktop presentation, input and result cards.
- **Native wake service:** independent Windows SCM component using pinned openWakeWord TFLite
  graphs through LiteRT on CPU; no Qt, Python, large language model or full speech recognizer
  remains loaded in the idle listener.

Speech recognition uses Handy's native transcribe.cpp engine inside Rust, a pinned Whisper
large-v3-turbo Q5 model and Vulkan on the current host's dedicated GPU. Local Silero VAD and
Windows SAPI handle turn detection and speech output. Production microphone recordings are
not saved. Setup downloads are explicit; startup does not download models or use cloud speech.

## Run locally

The current development setup targets Windows 10/11, Python 3.12, Rust/MSVC and a dedicated
GPU. The reference host has 8 GB VRAM; this is not a minimum-hardware or latency guarantee.
Model weights, native runtime binaries, environments and personal data are excluded from Git.

Provision the Brain first using [Brain setup](services/brain/README.md#current-runtime-capability-agent-2026-10-16),
then follow [desktop and native speech setup](services/desktop/README.md#explicit-setup).
From a prepared checkout:

```powershell
.\jarvis.ps1                # Terminal conversation
.\jarvis.ps1 -Desktop       # Qt desktop
```

To register the `jarvis` command and install the optional native wake service together:

```powershell
.\install.cmd
```

The service installation requests Windows administrator consent. `-SkipWakeService` registers
only the command; `-RemoveWakeService` removes the service without deleting personal data.
This installer assumes the development prerequisites are already provisioned; it is not an MSI
or a complete dependency/model installer. See [wake service setup](services/wake/README.md).
Keep the checkout at its registered location, or rerun installation after moving it.

Open a new terminal to use `jarvis` or `jarvis -Desktop` from any directory.
The desktop follows Windows' default microphone and starts with Turkish listening/voice and
Auto conversation. While the model loads, the microphone stays closed and an estimated
activation countdown is announced. Listening begins only after actual model readiness and
the completed welcome. Escape or **End conversation** stops automatic listening.

The agent's primary interaction profile is English; filenames retain their original Unicode.
Turkish recognition/output is available, but this does not establish equivalent reasoning quality.
Example requests:

- “I saved a presentation somewhere and can't find it.”
- “Open the second one, please.”
- “What do I need to do today?”
- “Copy yesterday's three tasks to today.”
- “Make these three tasks repeat daily.”

Personal organizer data lives in the Windows user data directory, outside this checkout.
`/reset` clears conversational context and selections, not saved tasks or notes.
See [organizer behavior and storage](docs/brain/PERSONAL_ORGANIZER.md).

## Status and validation

This is an actively tested prototype. Speech recognition, wake accuracy and ambiguous
target/date interpretation still have documented failures. Passing bounded scenarios does
not prove general assistant reliability. In particular, older organizer stress tests reproduced
wrong-target and wrong-date updates; their overall acceptance remains failed.

The 20 October 2026 task-routines validation passed 84 Rust tests, 593 Brain/Qt tests and
12 real-model state/dispatch scenario groups. These are scoped results, not a universal quality
claim. Exact commands, skipped opt-in tests, failed trials and remaining limitations are in
[the task-routines report](docs/brain/TASK_ROUTINES_2026-10-20.md).

- [Current state and handoff](agent/STATE.md)
- [Architecture and execution boundary](agent/ARCHITECTURE.md)
- [Agent loop and model provisioning](docs/brain/AGENT_LOOP.md)
- [Speech integration and known errors](docs/brain/NATIVE_SPEECH_PROVIDER.md)
- [Wake service validation and acoustic limits](docs/brain/WAKE_DAEMON_PLAN.md)
- [Organizer adversarial review](docs/brain/PERSONAL_ORGANIZER_STRESS_2026-10-18.md)
- [Engineering rules and task index](agent/README.md)

## Repository layout

```text
core/native/        Rust Core and Windows adapters
services/brain/     Python reasoning service and capability bundles
services/desktop/   Qt Quick/QML desktop
services/wake/      Independent native Windows wake service
scripts/            Explicit provisioning, installation and evaluation tools
config/             Example configuration; local overrides are ignored
agent/              Engineering rules, architecture, task specifications and state
docs/brain/         Detailed design, validation evidence and known failures
```

Model/runtime and third-party licenses remain applicable. In particular, the pretrained wake
models use CC BY-NC-SA 4.0; see [wake third-party notices](services/wake/resources/THIRD_PARTY.md)
before redistribution or commercial use.
