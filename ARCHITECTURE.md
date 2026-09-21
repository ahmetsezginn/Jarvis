# JARVIS Architecture

## 1. Purpose

This document defines the initial architecture for JARVIS.

JARVIS is a voice-first, secure AI assistant intended to live on company-managed computers.

The architecture must optimize for:

- modularity
- low perceived latency
- security
- auditability
- replaceable AI providers
- native operating-system access
- future enterprise administration

## 2. Architectural Principle

The most important separation is between intelligence and authority.

```text
AI = Intelligence
Native Core = Authority
```

The AI layer understands and reasons.

The native core validates, authorizes, and executes.

This separation must remain true regardless of which AI provider or UI is used.

## 3. High-Level Architecture

```text
                               USER
                                |
                   +------------+------------+
                   |                         |
                 Voice                    Keyboard
                   |                         |
                   +------------+------------+
                                |
                                v
                      +-------------------+
                      |   JARVIS CLIENT   |
                      |  Desktop / CLI    |
                      +---------+---------+
                                |
                                v
                      +-------------------+
                      |  COMMAND ROUTER   |
                      +-----+--------+----+
                            |        |
                      Fast  |        | AI
                      Path  |        | Path
                            |        |
                            |        v
                            |   +----------------+
                            |   | JARVIS BRAIN   |
                            |   |     Python     |
                            |   +-------+--------+
                            |           |
                            |    Structured Action
                            |           |
                            +-----------+
                                |
                                v
                       +--------------------+
                       | JARVIS NATIVE CORE |
                       |        Rust        |
                       +---------+----------+
                                 |
                    +------------+-------------+
                    |            |             |
                    v            v             v
                Policy       Tool Registry   Audit
                    |            |
                    +-----+------+
                          |
                          v
                       Executor
                          |
                          v
                   Platform Adapter
                          |
                          v
                 Operating System
```

## 4. Repository Layout

Initial target monorepo:

```text
jarvis/
|
├── README.md
├── AGENTS.md
├── ARCHITECTURE.md
|
├── apps/
│   ├── desktop/
│   │   ├── src-tauri/
│   │   └── ui/
│   └── cli/
|
├── core/
│   └── native/
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs
│           ├── lib.rs
│           ├── executor/
│           ├── tools/
│           ├── policy/
│           ├── permissions/
│           ├── platform/
│           │   ├── windows/
│           │   ├── macos/
│           │   └── linux/
│           ├── ipc/
│           │   ├── protocol.rs
│           │   ├── codec.rs
│           │   ├── server.rs
│           │   ├── transport.rs
│           │   └── windows/
│           ├── audit/
│           ├── audio/
│           └── events/
|
├── services/
│   └── brain/
│       ├── pyproject.toml
│       ├── src/jarvis_brain/
│       │   ├── core/
│       │   ├── ipc/
│       │   ├── intelligence/
│       │   │   ├── models/
│       │   │   ├── contract.py
│       │   │   ├── fast_router.py
│       │   │   ├── parser.py
│       │   │   ├── orchestrator.py
│       │   │   └── runtime.py
│       │   └── cli.py
│       └── tests/
|
├── protocols/
│   ├── action.proto
│   ├── events.proto
│   └── brain.proto
|
├── integrations/
│   ├── calendar/
│   ├── mail/
│   ├── teams/
│   ├── slack/
│   └── knowledge/
|
├── policies/
│   └── default.yaml
|
├── config/
|
├── tests/
│   ├── core/
│   ├── brain/
│   ├── contract/
│   └── e2e/
|
└── scripts/
```

This structure may evolve, but responsibility boundaries should not be collapsed without an explicit architecture decision.

## 5. Native Core

### Language

Rust.

### Role

The native core is the long-running trusted local service responsible for interacting with the computer.

Suggested process name:

```text
jarvis-core
```

On Windows this may eventually run as a startup/background application or service depending on product requirements.

### Responsibilities

The core may own:

- tool registry
- input validation
- policy evaluation
- confirmation requirements
- permission enforcement
- application operations
- file operations
- process operations
- clipboard operations
- notifications
- system status
- audio device operations
- global hotkeys
- event subscriptions
- audit events
- local IPC

### Non-Responsibilities

The native core should not own:

- LLM prompts
- provider-specific reasoning logic
- RAG pipelines
- large semantic document processing
- conversation personality

## 6. Brain Service

### Language

Python.

### Role

The brain service provides intelligence and AI orchestration.

Suggested process name:

```text
jarvis-brain
```

### Responsibilities

- natural-language understanding
- tool selection
- structured action generation
- conversational state
- multi-step reasoning
- task decomposition
- provider routing
- document understanding
- company knowledge retrieval
- summarization
- optional STT/TTS provider integration

### Provider Abstraction

The brain must not hardcode a single LLM vendor into application logic.

Conceptual interface:

```python
class AIProvider:
    async def respond(self, request, tools, context):
        ...
```

Possible implementations:

```text
OpenAIProvider
AnthropicProvider
GeminiProvider
LocalProvider
```

The brain should produce typed actions rather than executable shell text.

### M003 Local Intent Runtime

M003 selects Qwen3-0.6B, converted to a CPU-compatible INT4 ONNX Runtime GenAI artifact. The
artifact is provisioned explicitly from a pinned upstream revision; runtime startup never
downloads it. PyTorch, Transformers, and model conversion packages exist only in the isolated
builder environment and are not production Brain dependencies.

```text
Validated user text
        |
        v
Small deterministic Fast Router
        |
        +---- match -> semantic IntentResult
        |
        +---- fallback -> lazy QwenOnnxIntentModel
                              |
                              v
                     constrained non-thinking output
                              |
                              v
            strict JSON + schema + semantic validation
                              |
                              v
                       confidence policy
```

The model adapter uses a 2,048-token maximum input context and a 128-token maximum output by
default. Loading is lazy and exposes `unloaded`, `loading`, `ready`, and `failed` states. The
Fast Router never loads the model. ONNX Runtime GenAI preview APIs and imports stay inside
`QwenOnnxIntentModel`.

The semantic contract is closed to `open_application`, `system_status`, `clarify`, and
`unsupported`. This is intentionally not the Rust tool registry. The model cannot supply Core
tool names, app IDs, executable paths, shell commands, or policy decisions. Invalid output fails
closed and cannot reach the orchestrator.

### Local-model replacement decision (2026-09-15)

The user explicitly relaxed M003's ONNX-only selection to evaluate a stronger lightweight local
model. `QwenGgufIntentModel` adds Qwen3-4B-Instruct-2507 Q4_K_M with a pinned llama-cpp-python
CUDA runtime **in the Brain process**. The existing ONNX adapter remains a reproducible baseline.
This is an explicit model/runtime deviation from M003, not a change to Core or IPC authority.
There is no HTTP inference server, download-on-start, Python OS control or new Rust tool.
Both providers implement IntentModel, use the same semantic contract and independent parser,
and retain the 2048 input / 128 output token budgets. GGUF integrity is checked before native
loading. Instruct-2507 uses its non-thinking-only chat template without the old think prefix.

The CLI `repl` retains one Brain/model and Core connection for the session, releasing the model
on exit. IntentContext still carries only budgets, not general conversation history.
The 2026-09-17 bounded selection session adds one pending Rust ambiguity list (up to ten safe
names/IDs, 120-second monotonic TTL, memory-only, private to each Brain instance). It displays
numbered options and handles explicit ordinal/name replies before model inference, independently
of the disabled Fast Router. This is a clarification state machine, not general language routing.
The model never receives or chooses trusted IDs. A selected name is re-resolved through Rust;
only a fresh ID matching the displayed candidate may reach open_app. Changed IDs fail closed.
Selection is consumed before IPC, and cancellation, expiry or a new request clears it. Ambiguous
"other" without a reference asks again instead of guessing. No state persists across CLI processes.
The old stateless evaluation's context cases remain unmeasured by that harness; dedicated session
tests cover the new interaction. General conversational memory is not implemented.
Token budgets bound generation length; an in-process native inference call currently has no
hard wall-clock cancellation guarantee. Process isolation/cancellation is a separate hardening item.

## 7. IPC Boundary

### Brain Process

`jarvis-brain` is an independent Python 3.12+ process. TASK-002 established protocol models, the
transport, `JarvisCoreClient`, and a development CLI. TASK-003 adds local intent understanding and
orchestration, but no application discovery, launcher, folder operation, system-status
implementation, shell execution, or copy of the Rust tool registry.

### Control Protocol

Protocol version 1 uses a 4-byte big-endian unsigned payload length followed by a UTF-8 JSON
object. A frame payload is at most 1 MiB. Every request contains `protocol_version`, a UUID
`request_id`, `message_type`, and `payload`; every response echoes the request ID and contains an
`ok` flag plus a typed payload or error code. Supported request messages are:

```text
hello
ping
list_tools
execute_tool
```

`hello` is required before other messages on a persistent connection. `list_tools` reads metadata
from the production Rust Tool Registry; Python has no hard-coded tool inventory. Malformed,
oversized, unknown, pre-handshake, and incompatible-version messages produce distinct protocol
errors. Incompatible versions cannot reach an executor.

Length-prefixed JSON is an explicit TASK-002 decision replacing the earlier generic Protocol
Buffers preference for this small control plane. Framing, protocol routing, and transport are
separate modules so a future measured serialization change does not alter the Core client API.
Raw audio is a separate future data plane and never belongs on this control protocol.

### Transport

On Windows, Rust listens on one local byte-mode Named Pipe:

```text
\\.\pipe\jarvis-core-<current-user-SID>-v1
```

The endpoint is derived from the process token SID in both processes and has no production
caller-controlled override. `PIPE_REJECT_REMOTE_CLIENTS` rejects remote pipe connections. The
pipe's protected DACL grants generic-all access to the current user SID, `SYSTEM`, and the local
`Administrators` group only. This is the effective access-control boundary; administrators and
SYSTEM are intentionally trusted. No HTTP, TCP, LAN, or internet listener exists.

The listener creates isolated connection workers, so a malformed or disconnected client does not
stop the server and subsequent clients can connect. Python applies connect and per-response
deadlines. A client that sends only part of a frame can occupy its own synchronous Rust worker
until it disconnects, but cannot block the listener or other workers; a server-side idle deadline
is a documented TASK-002 limitation.

### Security Boundary and Request Flow

The only IPC action path is:

```text
Python JarvisCoreClient
        |
        v
Named Pipe + protocol validation
        |
        v
ToolRequest(source = Brain)
        |
        v
Tool Registry -> Validation -> Policy -> Executor -> Tool -> Platform
        |
        v
ToolResult + existing audit event
```

IPC owns transport and routing only; it has no platform reference and cannot launch anything
directly. `resolve_app(query)` and `open_app(app_id)` remain separate executor calls in the same
long-running Core process, sharing the startup-refreshed trusted catalog. `open_app` still accepts
only a catalog-backed ID and cannot accept a caller-provided executable path.

### Failure Behavior

Framing failures close the offending connection after a best-effort typed error. Invalid messages,
unknown message types, missing handshakes, and tool failures are returned as machine-readable
codes. Client disconnects do not stop the service. Core tool failures preserve their existing
codes and details, including application ambiguity candidates. Audit events remain authoritative
for executor activity and record `RequestSource::Brain`; protocol rejections that never create a
`ToolRequest` cannot execute or emit a tool audit event.

## 8. Action Model

The central contract between intelligence and execution is a structured action request.

Conceptually:

```text
ActionRequest
├── request_id
├── tool_name
├── arguments
├── source
├── user/session context
└── optional reasoning metadata
```

The core must validate all fields.

The model cannot define new tools at runtime.

## 9. Tool Architecture

Each operating-system capability is implemented as a tool.

Example tool set:

```text
system_status
resolve_app
open_app
close_app
open_folder
find_file
set_volume
mute_audio
show_notification
lock_computer
start_workspace
```

Conceptual Rust trait:

```rust
trait Tool {
    fn name(&self) -> &'static str;
    fn risk(&self) -> RiskLevel;
    fn validate(&self, input: &ToolInput) -> Result<(), ToolError>;
    fn execute(&self, ctx: &ExecutionContext, input: ToolInput)
        -> Result<ToolOutput, ToolError>;
}
```

Exact signatures may evolve.

### Application Discovery and Resolution

The Native Core discovers installed user-facing applications from platform-managed sources and
builds a trusted internal catalog. On Windows, TASK-001 uses the current-user and all-users Start
Menu application shortcuts. It does not scan the whole disk for executables.

```text
Windows application metadata
          |
          v
Application Discovery
          |
          v
Trusted Application Catalog
          |
          v
Deterministic Resolver -- resolve_app(query)
          |
          v
Opaque app_id -- open_app(app_id)
          |
          v
Policy + Platform Launcher
```

Raw shortcut and executable targets stay inside the Native Core. Configuration may supply optional
aliases, exclusions, preferences, administrative overrides, or policy; it does not need to list
every installed application.

## 10. Policy Engine

Policy decisions are made before execution.

Possible outcomes:

```text
ALLOW
DENY
REQUIRE_CONFIRMATION
```

Policy inputs may include:

- user identity
- company role
- device state
- tool name
- tool arguments
- target path
- target application
- network state
- risk level
- enterprise configuration

Example:

```text
resolve_app("spotify")
    -> ALLOW

open_app("app_7d922...")
    -> ALLOW after catalog validation

open_folder("C:\\Users\\user\\Documents")
    -> ALLOW

delete_file("finance.xlsx")
    -> REQUIRE_CONFIRMATION

read_file("C:\\Users\\user\\.ssh\\id_rsa")
    -> DENY
```

## 11. Platform Adapters

Generic tools must not directly depend on Windows/macOS/Linux APIs.

They call platform abstractions.

Conceptually:

```text
OpenApplicationTool
        |
        v
Trusted Application Catalog
        |
        v
ApplicationPlatform
    /      |      \
Windows  macOS   Linux
```

Initial support may be Windows-first.

## 12. Voice Architecture

Voice is a first-class interface but not the authority layer.

Possible pipeline:

```text
Microphone
    |
    v
Audio Capture
    |
    v
Wake Word / Push-to-Talk
    |
    v
Voice Activity Detection
    |
    v
Speech Recognition
    |
    v
Command Router / Brain
    |
    v
Native Core
    |
    v
Result
    |
    v
Speech Output
```

Latency-sensitive audio device handling may live in Rust.

Model-based speech recognition and synthesis may live in Python/provider modules.

## 13. Fast Path vs AI Path

Temporary user-authorized diagnostic override: CLI `ask`, `repl`, and `predict` now skip the
Fast Router by default. `--fast-router` (launcher `-FastRouter`) explicitly restores it.
`JarvisBrain(fast_router_enabled=False)` makes the bypass explicit; the library/evaluator default
remains enabled to preserve historical comparisons. Input validation, model JSON/semantic checks,
confidence policy and Rust execution boundaries are unchanged. This does not fix model quality
or add conversational support. `jarvis.ps1 -Model gguf` selects the new model for that invocation,
restores the previous environment afterward, and displays the selected backend and routing mode.

JARVIS should avoid unnecessary LLM calls.

### Fast Path

Use for deterministic commands where intent can be safely recognized with high confidence.

Examples:

```text
mute
volume up
open spotify
lock computer
system status
```

M003 implements a deliberately small deterministic router for obvious application-open and
system-status phrases in Turkish and English. Missing application targets produce clarification;
obvious path, shell, multi-action, and prompt-injection cases produce `unsupported`. Anything not
obvious falls back to the local model instead of expanding the router into a second NLP system.

### AI Path

Use for semantic or multi-step requests.

Examples:

```text
"Find the latest presentation related to the Acme account."

"Help me prepare for tomorrow's customer meeting."

"Check these documents and tell me what I need to do today."
```

Both paths converge on the same action/policy/executor boundary.

For application intents, convergence is always:

```text
human application query
    -> JarvisCoreClient
    -> resolve_app(query)
    -> Rust-trusted app_id
    -> open_app(app_id)
```

Ambiguity candidates come from Rust and are surfaced to the user. Brain never selects a candidate
randomly and never launches a path.

## 14. Desktop UI

Preferred approach:

```text
Tauri + TypeScript + Rust
```

Reasons include:

- lightweight desktop distribution
- reuse of Rust ecosystem
- separation of UI from AI service
- native desktop integration

The desktop UI may provide:

- conversation view
- push-to-talk
- listening indicator
- action previews
- confirmation dialogs
- settings
- permission visibility
- audit-friendly activity history

## 15. Enterprise Layer

Future enterprise deployments may add centrally managed policy.

Example controls:

```text
Allowed applications
Denied applications
Allowed directories
Protected directories
External network access
AI provider selection
Local-only mode
Data retention
Audit retention
Confirmation requirements
Integration permissions
```

Enterprise configuration must not depend on prompt instructions alone.

## 16. Local-Only Mode

The architecture should support a high-security deployment in which:

```text
AI model        -> local/company-hosted
Speech          -> local/company-hosted
Knowledge       -> local
Files           -> local
Telemetry       -> disabled or company-controlled
Internet        -> optional/blocked
```

This is a design requirement, even if the first prototype uses cloud AI.

## 17. Reliability

The native core must remain usable if the brain service becomes unavailable.

At minimum, failure of the AI process should not crash the core or desktop UI.

The architecture should support:

- AI provider timeout
- brain restart
- IPC reconnect
- tool execution timeout
- cancellation
- structured errors

## 18. Observability

Important actions should emit structured audit events.

Performance measurements should eventually include:

- speech-to-intent latency
- AI inference latency
- IPC latency
- policy evaluation latency
- tool execution latency
- end-to-end perceived latency

## 19. Initial Milestone

### TASK-001 — Native JARVIS Core

Build the first Rust executable with these modules:

```text
core/native/src/
├── main.rs
├── apps/
├── tools/
├── executor/
├── policy/
├── audit/
├── platform/
└── config/
```

Initial tools:

```text
system_status
resolve_app
open_app
open_folder
```

The first milestone does not require a real LLM.

Acceptance goal:

```text
Client Request
     |
     v
Typed Tool Request
     |
     v
Registry + Validation
     |
     v
Policy + Executor
     |
     v
Catalog-backed Application / Windows Adapter
     |
     v
Result + Audit Event
```

### TASK-002 — Local IPC Contract + Python Brain Skeleton

TASK-002 adds `jarvis-core serve`, the versioned local Windows Named Pipe control plane, and the
non-AI Python client package. The application catalog is refreshed once before the service starts
accepting requests and is shared for the service lifetime; live install/uninstall watching is not
part of this milestone.

### TASK-003 — Local Intelligence Runtime

TASK-003 adds the local Qwen3-0.6B INT4 CPU adapter, strict semantic intent boundary, lazy loading,
Fast Router, fixed orchestrator, natural-language CLI, reproducible model provisioning, benchmark
harness, and online/offline Windows E2E coverage. It does not add voice, UI, cloud providers, RAG,
reminders, autonomous loops, generic shell execution, or new Rust tools.

ONNX Runtime GenAI constrained decoding is used to improve JSON shape, but it is not treated as a
security boundary. The independent strict parser and semantic validator remain mandatory. This is
an implementation detail consistent with, rather than a deviation from, the task architecture.

## 20. Architectural Invariants

These rules should be treated as invariants until explicitly changed:

1. The AI does not receive unrestricted OS execution authority.
2. OS actions are explicit tools.
3. Tools pass through policy before execution.
4. Rust owns the trusted local execution boundary.
5. Python owns AI orchestration, not computer authority.
6. Interfaces communicate through stable contracts.
7. AI providers are replaceable.
8. Voice and UI cannot bypass the native core.
9. Security-sensitive operations are auditable.
10. Fast deterministic commands should not require expensive AI when avoidable.
11. Application names resolve through platform discovery and the trusted catalog.
12. `open_app` accepts only catalog-backed application IDs, never caller-provided paths.
13. A language model emits only the closed semantic intent contract, never trusted Core values.
14. Local model failure, missing artifacts, or invalid output cannot trigger a machine action.
15. Runtime inference performs no model download and does not depend on PyTorch or Transformers.

## Final Architecture Statement

### Brain evaluation before capability expansion (2026-09-15)

`docs/brain/REQUIREMENTS.md` defines proposed conversational requirements and acceptance gates.
The non-executing evaluator under `scripts/evaluation` measures current intent interfaces;
history/evidence scenarios are explicitly reported as unsupported until a session interface exists.
No production tool, model, protocol or semantic enum is changed by this assessment.
Brain may eventually retain bounded safe Core-provided candidate metadata as advisory context;
the authoritative catalog, current resolution, policy and launch targets remain inside Rust.

> AI thinks. JARVIS Core decides. The computer acts.
