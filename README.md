# JARVIS

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

More detail is available in [ARCHITECTURE.md](ARCHITECTURE.md).

## Current Features

- Dynamic discovery of Windows Start Menu applications
- Trusted in-memory application catalog
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
├── ARCHITECTURE.md
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
