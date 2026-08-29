# JARVIS

JARVIS is a secure, modular, voice-first AI assistant designed for company-managed computers.

The goal is not to build a chatbot that happens to run in a terminal. The goal is to create a local AI operating layer between the employee and the computer.

A user should be able to say:

- "Jarvis, open my sales workspace."
- "Find the presentation I used in yesterday's customer meeting."
- "Remind me to send the report at 16:00."
- "Prepare my computer for the next meeting."
- "Why is my computer slow?"
- "What is our company's travel policy?"
- "Check my Downloads folder and suggest how to organize it."

JARVIS must feel fast and natural to the employee while remaining controlled, auditable, and policy-driven for the company.

## Product Principle

> Tell your computer what you want instead of manually operating every application.

The system follows this high-level flow:

```text
Voice / Text / UI
       |
       v
Intent + Reasoning
       |
       v
Structured Action Request
       |
       v
Policy + Permission Check
       |
       v
Native Tool Execution
       |
       v
Operating System / Applications
```

The AI model does not receive unrestricted shell access.

The AI can propose actions. The native JARVIS core decides whether those actions are valid, permitted, and executable.

## Core Design

JARVIS is a polyglot system. Different parts of the product use different languages based on their responsibilities.

### Rust

Rust is used for the native system layer:

- OS integration
- application control
- file system operations
- process management
- window management
- clipboard
- notifications
- audio devices
- global shortcuts
- policy enforcement
- tool execution
- audit logging
- IPC server
- system monitoring

### Python

Python is used for AI and reasoning:

- LLM providers
- intent understanding
- multi-step planning
- conversation context
- model routing
- RAG
- company knowledge
- document understanding
- STT/TTS model integrations
- agent reasoning

Python must not directly perform privileged OS actions that belong to the native core.

### TypeScript

TypeScript may be used for the desktop interface.

The preferred desktop stack is Tauri, allowing the UI to communicate with the Rust core while keeping the application lightweight.

## Repository Direction

```text
jarvis/
|
├── README.md
├── AGENTS.md
├── ARCHITECTURE.md
|
├── apps/
│   ├── desktop/
│   └── cli/
|
├── core/
│   └── native/
|
├── services/
│   └── brain/
|
├── protocols/
|
├── integrations/
|
├── policies/
|
├── config/
|
├── tests/
└── scripts/
```

## Major Components

### JARVIS Native Core

A lightweight long-running Rust process responsible for safe interaction with the operating system.

Expected responsibilities:

- tool registry
- policy engine
- permission engine
- executor
- OS adapters
- system events
- audit logging
- local IPC
- optional hotkey and microphone coordination

The native core is the security boundary of the product.

### JARVIS Brain

A Python service responsible for intelligence.

It converts user requests into structured, bounded actions that can be submitted to the native core.

The brain must be AI-provider independent.

Possible providers include:

- OpenAI
- Anthropic
- Google
- local models
- company-hosted models

### JARVIS Client

The user-facing layer.

Possible interfaces:

- voice
- desktop UI
- command line
- push-to-talk shortcut
- future mobile companion

All interfaces should ultimately use the same core and security model.

## Product Modes

JARVIS should eventually support four primary modes.

### ASK

Ask for information.

Example:

> "What is the company travel policy?"

### DO

Perform a bounded action.

Example:

> "Open Spotify."

### WATCH

Observe a condition and notify the user.

Example:

> "Tell me if disk usage passes 90%."

### ASSIST

Coordinate multiple steps toward a goal.

Example:

> "Help me prepare for tomorrow's management meeting."

## Security Principles

1. No unrestricted shell access for the AI.
2. Every computer action must be implemented as an explicit tool.
3. Every tool call must pass through the policy engine.
4. High-risk actions may require user confirmation.
5. Company policies override model suggestions.
6. Sensitive paths and applications can be denied by policy.
7. Security-relevant actions must be auditable.
8. AI providers must be replaceable.
9. Local-only operation must remain possible for high-security deployments.
10. The native core must not trust model output.

## Performance Principles

JARVIS should feel immediate for common commands.

Not every request should require a large language model.

The architecture may contain two execution paths:

```text
                    User Request
                         |
                         v
                   Command Router
                    /          \
                   /            \
             Fast Path         AI Path
             deterministic     reasoning
                   \            /
                    \          /
                     Native Core
```

Examples of possible fast-path commands:

- mute volume
- increase volume
- open a known application
- lock the computer
- start a known workspace
- show system status

Complex requests should be routed to the AI brain.

## Initial Development Order

### TASK-001 — Native Core

Build the Rust core with:

- tool abstraction
- tool registry
- policy engine
- executor
- audit interface
- platform abstraction
- dynamic Windows application discovery
- trusted application catalog and deterministic resolver

Initial tools:

- `system_status`
- `resolve_app`
- `open_app`
- `open_folder`

### TASK-002 — Brain Service

Add the non-AI Python Brain skeleton and establish versioned local Named Pipe communication with
the native core. AI providers remain TASK-003 scope.

### TASK-003 — Voice Foundation

Add push-to-talk / wake-word architecture, speech input, and speech output without bypassing the core security boundary.

## Current Product Rule

Until explicitly changed by an architectural decision:

> AI thinks. Native core validates and acts.

## TASK-001 Native Core Development

The Rust workspace contains the TASK-001 native execution boundary. It dynamically discovers
user-facing Windows applications from the current user's and all-users Start Menu, builds a
trusted in-memory catalog, and resolves local text queries deterministically. Configuration is
not required to enumerate installed applications.

Application launch follows this boundary:

```text
Windows discovery -> trusted catalog -> resolve_app(query) -> app_id
app_id -> registry -> validation -> policy -> executor -> platform launcher
```

The registered tools are `system_status`, `open_folder`, `resolve_app`, and `open_app`.
`resolve_app` returns safe application metadata; `open_app` accepts only an `app_id` present in
the current catalog. Raw executable paths are never accepted from callers.

From the repository root:

```powershell
cargo build
cargo run -p jarvis-core -- tools list
cargo run -p jarvis-core -- apps refresh
cargo run -p jarvis-core -- apps search blender
cargo run -p jarvis-core -- tool resolve_app '{"query":"blender"}'
cargo run -p jarvis-core -- tool open_app '{"app_id":"app_..."}'
cargo run -p jarvis-core -- app open blender
cargo run -p jarvis-core -- tool system_status '{}'
cargo run -p jarvis-core -- tool open_folder '{"path":"C:\\Users\\User\\Downloads"}'
```

Catalog refresh happens at process startup. `apps refresh` provides an explicit development
refresh as well. Optional aliases and exclusions may be placed in `config/preferences.toml`; use
`config/preferences.example.toml` as a template or set `JARVIS_PREFERENCES_CONFIG`. Preferences
augment or filter discovery and are not an installed-application inventory.

Run all TASK-001 checks from the repository root:

```powershell
cargo fmt --check
cargo build
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

## TASK-002 Local Core Bridge

`jarvis-core serve` is a long-running Windows control service. At startup it refreshes the same
trusted TASK-001 application catalog used by the CLI, builds the production registry/policy/
executor, and listens only on the current user's Named Pipe endpoint:

```text
\\.\pipe\jarvis-core-<current-user-SID>-v1
```

The control protocol is UTF-8 JSON framed by a 4-byte big-endian unsigned payload length. Every
envelope declares protocol version `1`; the hard payload limit is 1 MiB. The supported requests
are `hello`, `ping`, `list_tools`, and `execute_tool`. `execute_tool` creates a normal Rust
`ToolRequest` with source `brain`, so registry lookup, argument validation, policy, executor,
tool, platform, and audit behavior are unchanged.

The pipe uses `PIPE_REJECT_REMOTE_CLIENTS`. Its protected DACL grants access only to the current
user SID, `SYSTEM`, and the local `Administrators` group. There is no TCP listener. One connection
can carry many request/response pairs after its handshake.

Start the Core from the repository root:

```powershell
cargo run --manifest-path .\core\native\Cargo.toml -- serve
```

Create the isolated Python 3.12+ development environment once:

```powershell
py -3.12 -m venv .\services\brain\.venv
.\services\brain\.venv\Scripts\python.exe -m pip install -e ".\services\brain[dev]"
```

Then, in another terminal:

```powershell
cd .\services\brain
.\.venv\Scripts\python.exe -m jarvis_brain.cli ping
.\.venv\Scripts\python.exe -m jarvis_brain.cli tools
.\.venv\Scripts\python.exe -m jarvis_brain.cli status
.\.venv\Scripts\python.exe -m jarvis_brain.cli open-app "Google Chrome"
```

The last command performs two Rust tool calls over IPC: `resolve_app("Google Chrome")`, followed
by `open_app(app_id)` using only the catalog ID returned by Rust. Python contains no direct
application/folder/system implementation and never receives a trusted raw launch target.

Run TASK-002 checks with:

```powershell
cargo fmt --check --manifest-path .\core\native\Cargo.toml
cargo build --manifest-path .\core\native\Cargo.toml
cargo clippy --manifest-path .\core\native\Cargo.toml --all-targets --all-features -- -D warnings
cargo test --manifest-path .\core\native\Cargo.toml

cd .\services\brain
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

TASK-002 intentionally uses length-prefixed JSON instead of the earlier general Protocol Buffers
preference because this channel carries small development control messages. The codec and
transport are separate so serialization can be replaced later. Raw audio is explicitly not sent
on this control channel. No other architecture deviation is introduced.
