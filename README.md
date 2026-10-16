# JARVIS

To start from any directory with `jarvis`, register the command once in your Windows user PATH:

```powershell
./scripts/shell/install-jarvis-command.ps1
```

Open a new terminal and run `jarvis`. All launchers default to GGUF, overriding any inherited
`JARVIS_MODEL_BACKEND` value for that session, and forward launcher arguments such as
`jarvis -Model gguf` or `jarvis "Help me find my invoice"`. ONNX is disabled in the launcher
and provider factory. The registration preserves existing
PATH entries and changes only the user PATH; it does not change PowerShell execution policy.
The repository must stay at its registered location; rerun registration if you move it.

Current architecture (2026-10-16): production uses a capability-driven agent loop. The model sees
actual tool results and chooses its next step, rather than passing through the old intent/TurnPlan
classifier chain. The local default is Qwen3.5-9B GGUF; ONNX is disabled. See [the current design,
acceptance evidence and limits](docs/brain/AGENT_LOOP.md) and [setup](services/brain/README.md).
Earlier examples/pass counts below describe their historical revisions, not general acceptance.
The new model is already provisioned on this development host; restart `jarvis` to load source
changes. `jarvis -Profile qwen3-4b` explicitly selects the old model for comparison.

The current product language is **English**, as requested after the Turkish model evaluation.
Prompts, active result/error messages and CLI startup use English; filenames in Turkish or any
other language remain unchanged. Windows known-folder display labels are Desktop, Documents
and Downloads regardless of the OS language. Custom root labels remain user-configured.
Try “I saved my presentation somewhere and can't find it”, then “Open the second one, please”.
Omitting an app uses the Windows default association. “Open it with Google Chrome” explicitly
selects the existing local PDF adapter. English-primary behavioral acceptance is measured
separately; this change does not establish that all model reasoning failures are solved.

The following Turkish examples document earlier iterations; use English for the active profile.

File/folder skills support scoped metadata search, folder listing and catalog-backed document
opening through Rust Core. Run `./jarvis.ps1 -Model gguf` and try “Belgeler klasörünü aç”, “teklif
PDF dosyasını bul”, “en büyük dosyaları göster” or “dosya kataloğunu yenile”. Default scope is
Windows Desktop/Documents/Downloads. Optional `JARVIS_FILES_CONFIG` selects a local root TOML
based on `config/files.example.toml` (Core restart required). Document-content reading and file
moving/deletion are not implemented. See `docs/brain/FILE_SKILLS.md`.

Interactive file follow-ups now keep a folder context for 120 seconds: after opening Downloads,
“orada CV klasörünü bul” searches inside it; a following “orada CV dosyamı bul” uses a single found
folder. Select displayed files with names such as “ahmet sezgin cv tr yi açar mısın”; separators and
extensions need not be exact. Multiple matches ask for selection. Within displayed results,
“TR olanı Chrome ile aç” opens a local PDF through Chrome's registered adapter; Microsoft Edge is
also supported. “Google ile aç” clarifies local Chrome opening and accepts “evet”. Google Docs
uploading and other application-specific file adapters remain unsupported. Exit and restart `jarvis`
after source updates; an already loaded Brain session keeps its old code.

Natural file references such as “TR olan benimkisi, onu açar mısın” also use model reasoning over
the displayed names. Ordinary file opening uses Windows' default associated application; PDF does
not require a browser. A named browser is an explicit alternative, not a condition for opening
documents. See `docs/brain/FILE_REASONING.md` for validation.

Numbered follow-ups such as “2. olanı açar mısın” address the current displayed page, not filenames
containing “2”. Opening uses the default Windows application unless an explicit supported opener
is requested. Invalid/expired list selections ask for clarification instead of starting a new search.
See `docs/brain/FILE_SELECTION.md` for the selection contract and validation.

JARVIS is a secure, modular, voice-first AI assistant for company-managed Windows computers. It provides a controlled layer between the user, AI models, and the operating system.

The assistant is designed to understand requests such as:

- “Open Google Chrome.”
- “Show the current system status.”
- “Open my Downloads folder.”
- “Prepare my computer for the next meeting.”

## Core Principle

> The AI may request an action. The native core validates, authorizes, and executes it.

JARVIS never gives an AI model unrestricted shell access. Every machine action is exposed as an explicit, typed tool and passes through validation, policy, and execution layers.

```text
Voice / Text / UI
       |
       v
AI Brain / Command Router
       |
       v
Structured Tool Request
       |
       v
Validation + Policy
       |
       v
Native Tool Execution
       |
       v
Windows / Applications
```

## Architecture

JARVIS uses different languages for clearly separated responsibilities:

- **Rust native core:** trusted execution boundary, OS integration, tool registry, policy enforcement, application discovery, audit events, and IPC server.
- **Python brain service:** natural-language interpretation, reasoning, planning, provider integrations, and structured tool selection.
- **TypeScript desktop UI:** optional user interface layer; it does not own permissions or privileged execution.

The Python service cannot launch applications or perform privileged OS operations directly. Machine actions are sent to the Rust core through the local control protocol.

More detail is available in [agent/ARCHITECTURE.md](agent/ARCHITECTURE.md).
Engineering rules, tasks and session context are indexed in [agent/README.md](agent/README.md).

## Current Features

- Dynamic discovery of Windows Start Menu shortcuts and packaged applications from Windows AppsFolder
- Trusted in-memory application catalog
- Explicit catalog refresh without restarting Core; after a missing app, “ben daha yeni yükledim” refreshes and retries that request
- Deterministic application resolution
- Policy-controlled application launching
- Folder opening through a registered tool
- System status reporting
- Local Windows Named Pipe communication
- Versioned, length-prefixed JSON protocol
- Python client and command-line interface
- Structured errors and audit-ready execution flow

Registered native tools:

- `system_status`
- `resolve_app`
- `open_app`
- `open_folder`

## Repository Structure

```text
jarvis/
├── core/
│   └── native/              # Rust native core
├── services/
│   └── brain/               # Python brain service
├── config/
│   └── preferences.example.toml
├── AGENTS.md                # Agent entry point
├── agent/                   # Rules, architecture, tasks and session context
├── Cargo.toml
└── README.md
```

## Requirements

- Windows 10 or later
- Rust toolchain with Cargo
- Python 3.12 or later

## Setup

### Native core

Build the Rust workspace from the repository root:

```powershell
cargo build
```

Start the local core service:

```powershell
cargo run --manifest-path .\core\native\Cargo.toml -- serve
```

The server listens on a local, current-user Windows Named Pipe. It does not expose a TCP port.

### Python brain service

Create an isolated environment and install the service:

```powershell
py -3.12 -m venv .\services\brain\.venv
.\services\brain\.venv\Scripts\python.exe -m pip install -e ".\services\brain[dev]"
```

With the native core running, use another terminal to verify the connection:

```powershell
cd .\services\brain
.\.venv\Scripts\python.exe -m jarvis_brain.cli ping
.\.venv\Scripts\python.exe -m jarvis_brain.cli tools
.\.venv\Scripts\python.exe -m jarvis_brain.cli status
.\.venv\Scripts\python.exe -m jarvis_brain.cli open-app "Google Chrome"
```

The `open-app` command first resolves the requested name to a trusted catalog ID, then asks the native core to launch that ID. Caller-provided executable paths are not accepted.

For local model provisioning and the interactive `./jarvis.ps1` launcher, see the
[Brain setup guide](services/brain/README.md).
Use `.\jarvis.ps1 -Model gguf` to explicitly select the provisioned 4B model; terminal Fast Router
is temporarily disabled by default for diagnosis.
With the PowerShell profile integration installed, simply run `jarvis` from any directory.

## Native CLI Examples

```powershell
cargo run -p jarvis-core -- tools list
cargo run -p jarvis-core -- apps refresh
cargo run -p jarvis-core -- apps search blender
cargo run -p jarvis-core -- tool resolve_app '{"query":"blender"}'
cargo run -p jarvis-core -- tool system_status '{}'
cargo run -p jarvis-core -- tool open_folder '{"path":"C:\\Users\\User\\Downloads"}'
```

## Local Preferences

Copy the example file to create machine-specific preferences:

```powershell
Copy-Item .\config\preferences.example.toml .\config\preferences.toml
```

`config/preferences.toml` is ignored by Git. It may contain aliases, exclusions, and local preferences, but it is not the source of installed-application truth. You can also select another file with the `JARVIS_PREFERENCES_CONFIG` environment variable.

## Security Model

- The Rust core is the trusted execution boundary.
- Every OS action is implemented as a registered tool.
- Tool arguments are validated before execution.
- Every actionable request passes through the policy engine.
- Sensitive actions can require confirmation or be denied.
- Windows-specific behavior remains behind platform adapters.
- The AI service never executes arbitrary model-generated shell commands.
- The control pipe rejects remote clients and is restricted to authorized local identities.
- Secrets and unnecessary sensitive data must not be written to logs.

## Control Protocol

Rust and Python communicate through a local Windows Named Pipe:

```text
\\.\pipe\jarvis-core-<current-user-SID>-v1
```

Messages use UTF-8 JSON with a 4-byte big-endian length prefix. Every envelope declares protocol version `1`, and the maximum payload size is 1 MiB. A handshake is required before normal requests.

Supported requests are:

- `hello`
- `ping`
- `list_tools`
- `execute_tool`

This channel carries control messages only; it is not intended for raw audio streaming.

## Validation

Run the Rust checks from the repository root:

```powershell
cargo fmt --check --manifest-path .\core\native\Cargo.toml
cargo build --manifest-path .\core\native\Cargo.toml
cargo clippy --manifest-path .\core\native\Cargo.toml --all-targets --all-features -- -D warnings
cargo test --manifest-path .\core\native\Cargo.toml
```

Run the Python checks from `services\brain`:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

## Status

JARVIS currently provides the secure native execution foundation and the local Python-to-Rust control bridge. Voice input, desktop UI, external AI providers, and broader tool coverage can be added without bypassing the same native policy boundary.

Interactive JARVIS responses now appear as readable messages. Add `--json` to the Brain
`ask` or `repl` command for structured diagnostics; see [Brain CLI](services/brain/README.md).

GGUF interactive sessions now separate ordinary conversation from controlled machine tasks.
Conversation replies do not dispatch tools; machine tasks retain Rust validation and policy.
See [conversation/task routing](docs/brain/REQUEST_ROUTING.md) for details.

GGUF sessions also retain a bounded file-search goal: location, type, rejected results and a
pending clarification. A reply can refine that goal; chat and explanations do not repeat machine
operations. See [dialogue acceptance and limits](docs/brain/ASSISTANT_DIALOGUE.md).
After updating this version, rebuild and restart Native Core as well as the Brain: scoped search
now includes typed category/depth/rejection filters. Existing sessions retain their loaded code.
