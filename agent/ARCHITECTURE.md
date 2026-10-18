# JARVIS Architecture

## Current desktop/voice revision (2026-10-16)

Latest normal-answer follow-up: asynchronous SAPI output remains busy until WaitUntilDone(0)
reports the entire queue completed. RunningState=0 is waiting, not completion. speech_poll
adds output_phase queued/speaking/idle and conservatively retains speaking=true while pending
for older clients. Qt shows queued as processing and cannot rearm its automatic microphone
until completion. The live QML test uses the real Send button, actual agent worker, Core and
SAPI, observing the final rearm callback without opening a microphone. See
[voice/discovery evidence](../docs/brain/VOICE_AND_DISCOVERY_FOLLOWUP.md).

The user authorized Qt for the current host. `jarvis -Desktop` starts Qt Quick/QML with PySide6,
replacing the earlier planned TypeScript UI for this delivery. Qt owns presentation only and
spawns the fixed Python stdio session worker with bounded JSON messages. That worker retains
one existing JarvisBrain session; it has no shell fallback. Explicit card selections bind to a
fresh per-page token plus the existing 120-second private Core IDs. Old pages cannot select a
new row with the same number. Detailed path cards, conversational text and speech presentation
are separate. Model inference does not run in the GUI event loop.

Speech device requests use JarvisCoreClient -> Named Pipe -> registered AudioTool validation ->
policy -> AudioService -> Windows adapter. CPAL/WASAPI microphone streams and SAPI speech output
belong to Rust threads. Whisper small is checksum-pinned, CPU-only, loaded on demand with no
download. This native speech inference is a voice-layer implementation; Python retains task
planning. Captured PCM never leaves bounded Rust memory, so this phase needs no bulk audio IPC.
Only the final transcript crosses the existing control pipe and enters the same agent path as
typed text. Partial transcription is never dispatched. Decoder diagnostics are disabled to avoid
transcript logging; normal typed Core errors and audit remain active.

Voice reliability follow-up: QML no longer forces English recognition during startup; Auto is
bound to the controller, and explicit en/tr selection reaches the native decoder. speech_finish
also returns the decoder's detected language. speech_status discovers installed SAPI plus
OneCore voice tokens and speech-output devices inside the COM thread. speech_speak accepts
only validated en/tr and an optional bounded output index; trusted tokens remain inside Rust.
Missing voice/device errors do not silently select another language. Qt exposes independent
recognition, pronunciation and output controls, route feedback and a fixed Test voice sentence.
The product's English text behavior is unchanged. No registry writes, OS mixer changes, model
download or cloud inference are added. Synthetic fixture WAVs are explicit developer outputs,
not saved microphone recordings. See the current follow-up in DESKTOP_VOICE.md.

Both push-to-talk and explicitly enabled automatic conversation are available. Automatic mode
uses checksum-pinned Silero v6.2.0 GGML through the same native CPU whisper.cpp runtime (no ONNX).
A bounded callback queue feeds a separate capture worker: no blocking mutex, VAD inference or IPC
inside the audio callback. Typed CPAL Xrun/route/scheduling notices differ from fatal device errors;
isolated xruns are tolerated, while queue loss or eight xruns reject the utterance. A rolling
960ms model window and 800ms preroll preserve onset, two 100ms speech frames start listening,
and 900ms silence ends a turn. A 30-second utterance limit discards incomplete speech. Idle
listening can continue while the explicit mode is on, with bounded memory and a six-second
client heartbeat lease; abandoned pending PCM is discarded, including completed turns.

`speech_poll` is a validated registered Low-risk control/lease tool returning only phase, level,
xrun count and actual SAPI running state. It exposes no PCM. Qt serializes voice control calls,
discards stale capture/output callbacks and maps real states to three persistent animations:
waiting orbit, input-level bars, speaking flow. Processing has its own visual state. Capture
pauses during ASR/agent reasoning/speech; automatic rearm follows actual SAPI completion with a
short echo tail delay. This is half duplex; acoustic echo cancellation, wake words and neural
Kokoro output remain unimplemented. Manual hold-to-talk can interrupt output. Cancelled or
expired recordings never become agent input; hitting the manual deadline cancels rather than
sending a clipped command. See [desktop setup](../services/desktop/README.md) and
[verification](../docs/brain/DESKTOP_VOICE.md).

## Current production revision: capability agent loop (2026-10-16)

`JarvisBrain.handle_text` now runs a bounded `AgentRuntime`, not the historical classifier/TurnPlan
pipeline described in dated sections below. The model receives registered semantic capability
schemas, bounded conversation and verified name/kind/number metadata. It chooses one tool or a
reply; validated tool results return to the same model for its next step (five-step limit).
`AgentModel` is the provider boundary. Provider-native chat templates/tool protocols are parsed
and then independently validated by `CapabilityRegistry`; reply text is output only.

Capabilities register schema, handler, effect/permission metadata, required Core tools and optional
context/reset/turn hooks. The registry is the shared source of model descriptions and dispatch;
adding a trusted local capability does not require editing the loop or a closed intent enum.
No remote skill downloader, untrusted plugin execution or additional OS access is implemented.
Core remains the final authority: JarvisCoreClient -> Named Pipe -> registry -> validation ->
policy -> executor -> platform. Model IDs, paths and shell commands never establish authority.
Side effects have an independent current-message/target/application assessment before dispatch.
Bounded private file/app bindings and explicit confirmations remain outside model text.

The user-selected product language is now English. Presentation renders typed verified results,
separately from archived Turkish messages. Original Unicode names and private catalog bindings
are preserved. Parameter schemas document defaults/limitations and validate declared defaults;
free text is an explicit field format, not a special field name. Cross-turn verified observations
retain native assistant-tool-call/tool-result roles with their originating conversation turn,
within the existing TTL and memory bounds; rendered filesystem paths never enter model history.

Identification now uses progressive recommendations. The model ranks current name/kind/number
metadata and calls suggest_result for one candidate; it never supplies a path/ID. A private
Recommendations context retains the proposed identity and up to 100 rejected IDs until their
original 120s expiry. reject_suggestion removes only that item; subsequent searches include its
trusted exclusion ID automatically. confirm_suggestion confirms file identity without opening. An already-requested application
opening keeps its separate pending-action binding; affirmative target selection can complete
that original request through normal assessment and fresh Core resolution.
show_results exposes the full remaining page only after current-request assessment of an explicit
list/alternatives request. Original numbers stay stable, and desktop selection requires membership
in the actually visible cards plus a fresh page token.

A generic registry response-check hook prevents a raw prose draft from bypassing the structured
presentation choice after discovery. If needed, AgentModel repairs that same next-step decision
using a schema restricted to registered presentation actions; the model still chooses the item.
Capability contexts refresh after every observation. Prose enumerations of known candidates
cannot silently expand a single-card presentation; ordinary prose comparisons remain allowed.
Tentative suggest_result questions have an advisory confidence threshold; registry validation
forbids overriding the execution threshold for acting/Core-dependent capabilities. Correctable in-memory transition errors may
explicitly allow retry; validation prohibits this flag for Core-backed/effectful/terminal calls.
The five-step budget, side-effect assessment and Rust policy remain. Qt/CLI share the contract;
voice speaks the selected suggestion and no longer replaces it with a page-count summary.
Inline comma/semicolon enumerations of actual names also obey this presentation contract;
ordinary prose comparisons remain allowed.
Explicit full lists use typed original numbers/names for speech and separate locations for CLI/UI;
partial/scope notices remain visible, and the model name budget does not hide full-page UI cards.
See [recommendation behavior and checks](../docs/brain/RECOMMENDATIONS.md).

Discovery now distinguishes name_is_constraint (user-supplied mandatory saved name) from a
model-inferred name/topic hypothesis. On a hypothesis miss, one bounded metadata query may
retrieve alternatives inside the same verified folder, preserving kind/type/extension,
recursive, sorting and rejected IDs. It cannot widen to global roots or open anything. Tool
evidence explicitly separates original_name_matches=0 from same-scope alternatives; the model
chooses a tentative candidate, never a Python filename/type keyword branch. A mandatory name
miss remains empty. Failed folder spelling can return verified catalog root names through
file_catalog_status for the model to evaluate equivalence; find_files declares both Core
dependencies. Five model steps, 20-row pages, original 120s bindings and Rust policy remain.

`LegacyBrain` retains old diagnostics and historical tests only. It is not a production fallback.
ONNX remains disabled. See [AGENT_LOOP.md](../docs/brain/AGENT_LOOP.md) for current model evaluation,
limits and exact validation; older dated acceptance counts apply only to their old implementations.

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
├── AGENTS.md               # Automatic agent entry point
├── agent/
│   ├── AGENTS.md           # Canonical engineering rules
│   ├── ARCHITECTURE.md
│   ├── README.md           # Document index
│   ├── STATE.md            # Handoff notes
│   └── TASK_*.md           # Milestone specs and follow-up tasks
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

### Session conversation context (2026-10-05)

User-authorized session-only memory now passes bounded conversation pairs through IntentContext
to both local adapters. See docs/brain/SESSION_CONTEXT.md. Six pairs / 2400 characters; no disk
persistence, IDs or raw Core payloads. History is untrusted advisory data and never grants
permission. /reset clears history and pending selection. Contextual turns bypass legacy Fast
Router; strict validation and Rust execution authority remain unchanged.

### Request interpretation refinement (2026-10-06)

The GGUF adapter uses a provider-specific decision prompt for capability checks, negation,
corrections and app/folder distinctions. ONNX keeps its compact historical prompt after a
shared-prompt regression. Both retain the same strict four-intent contract. No new machine
capabilities or ordinary conversation intent were added. Evidence: docs/brain/REASONING_DIAGNOSTIC.md.

### Conversation/task admission (2026-10-06)

The user explicitly requested independent conversation and task paths. Every new executable
request in handle_text first passes a typed, read-only modality classifier. Conversation returns
a bounded text reply without task prediction or tool dispatch. Task output retains the existing
four-intent contract and all Rust authority checks. BrainResponse.respond is a response event,
not a Core or task intent. Legacy fast routing no longer shortcuts execution. GGUF supports
conversation replies; ONNX refuses unvalidated conversation generation with a typed error.
See docs/brain/REQUEST_ROUTING.md for contracts, limits and validation.

### Windows packaged application discovery (2026-10-08)

Rust now merges scoped Start Menu shortcuts with packaged applications enumerated through
native Windows AppsFolder Shell/COM interfaces. Only validated package-family/application
identities are accepted from this platform metadata. Packaged launch targets have no filesystem
path; IApplicationActivationManager activates the catalog-owned AUMID after unchanged tool
validation and policy. Brain still supplies only a human query to resolve_app and a returned
trusted app_id to open_app. AUMIDs and launch targets are not exposed through IPC.
The Windows-only windows crate provides typed COM bindings; windows-sys retains transport APIs.
Discovery is bounded by 10,000 Shell items and an elapsed-time check between COM calls (not
a hard timeout on an individual Windows API call; elapsed limit is 60 seconds). If AppsFolder fails, a structured warning
records degraded discovery while existing shortcuts remain available; empty failed discovery
still returns a typed error. Tests can disable live enumeration through from_roots, with a
separate opt-in live test. See docs/brain/WINDOWS_PACKAGED_APPS.md for validation and limitations.

### Explicit application catalog refresh (2026-10-08)

refresh_app_catalog({}) is a read-only registered Rust tool. It validates an empty object and
passes through the same policy, executor and audit pipeline; catalog replacement is atomic and
failed discovery retains the previous catalog. Refresh changes internal metadata only.
Brain supports narrow deterministic session follow-ups, separate from model task decoding:
an explicit catalog-refresh command, or an affirmative newly-installed statement immediately
after a real application_not_found result. One validated human query is retained for 120 seconds,
without IDs or raw Core data, and consumed on any subsequent turn. /reset and cancellation clear
it. Recovery refreshes once, re-resolves the query, then continues the original user-authorized
opening request through policy; ambiguity still requires selection. No retry loop or post-launch
verification is added. The model's four-intent contract and conversation isolation are unchanged.
See docs/brain/CATALOG_REFRESH.md for accepted phrases, tests and limitations.

### Scoped file/folder skills (2026-10-12)

User-authorized TASK-004 extends the historical four-intent contract with search_files, list_folder,
open_file, open_directory, file_catalog_status and refresh_file_catalog. Model search requires a
human query and sort/extension/kind fields; targeted opening/listing requires only a human query.
The model cannot supply paths, roots, IDs or executable instructions. Conversation admission,
strict parsing, confidence checks and Native Core authority remain mandatory.

Rust owns an in-memory FileCatalog using locally configured roots or native Windows Known Folder
paths. Scans start on first search/explicit refresh and inspect metadata only. Scans/results are
bounded with explicit scope, partial state and timestamps. Refresh replaces snapshots atomically;
total failure retains the old snapshot. No persistent index or filesystem watcher is introduced.
Read-only status/refresh/search/list and low-risk open tools use the production registry, validation,
policy, executor and audit. Opening uses catalog IDs and revalidates ancestry, canonical paths and
metadata. Reparse/cloud-only targets are excluded. Supported document/media extensions use a fixed
native Windows open verb; scripts/programs/shortcuts are rejected. Legacy open_folder(path) remains
for explicit Core callers, never model-produced Brain paths.

Brain retains one private result page (20 entries, 120s) for numbered/unique-name selection,
folder/containing-folder follow-ups and pagination. IDs/locations never enter model history.
Selection is consumed before IPC; reset/cancel/expiry/unrelated turns clear it. No post-launch
verification. Content reading and file mutation remain later deliveries. See TASK_004.md and
docs/brain/FILE_SKILLS.md for evidence and limits.

### File context and selected browser opening (2026-10-12)

Brain keeps an active catalog-backed directory for 120 seconds after opening/listing, or after an
explicit relative reference to a single displayed directory. Relative searches receive that private
folder_id; unknown or ambiguous folder references ask for selection instead of a global search.
Natural displayed-name selection tolerates separators, extensions and Turkish selection words;
multiple matches never auto-open. Concrete Google-to-local-Chrome clarification retains target and
application until affirmative reply, cancellation, changed request, reset or expiry. Unrelated turns
clear file context. IDs and locations remain outside model history; no semantic intent expansion.

open_file_with_app is a low-risk registered tool. Both catalogs validate IDs; Native Core rechecks
the document and supports only PDF with Google Chrome/Microsoft Edge. Windows resolves trusted
Shell links through IShellLinkW/IPersistFile, rejects shortcut arguments, checks the expected browser
executable and passes exactly one Core-owned document argument without a shell. Packaged targets,
other applications/types, arbitrary flags and Google Docs upload are unsupported. No post-launch
verification. Natural Core filename search also matches words across separators, retaining ambiguity.

### Semantic file planning (2026-10-12)

IntentContext has a bounded file_candidates view containing only displayed name/kind pairs
(<=20, <=1200 name characters, per-name <=256). IDs/locations remain private. Request admission
and intent prediction receive this data for semantic references; filenames are untrusted JSON data,
not instructions. Explicit relative searches omit previous candidates so the previous folder kind
cannot override the type requested inside it. For active file planning, keep at most two recent
user turns/700 characters and exclude free-form assistant replies, preventing capability hallucinations
from becoming task rules. Conversation replies/recall retain the original bounded conversation memory.

The model proposes the human target and optional open_file.application (human name, never path,
executable, flags or ID). Empty/omitted application uses normal Windows association for all existing
supported document/media types; it does not impose a PDF/browser restriction. Typed validation,
confidence and unique matching bind displayed targets to private Core IDs. Unknown natural references
reach the model before selection is discarded; ambiguity never opens the first match. Application
qualification is removed from native search arguments and, for a supported explicit adapter, routed
through resolve_app -> open_file_with_app. No new intent or machine execution path is introduced.
See docs/brain/FILE_REASONING.md for reproduction, verification and remaining limits.

### Displayed-result addresses (2026-10-14)

Search and displayed-result selection now have distinct semantic contracts. select_file carries
number (1..20), action (open/list/parent), application (human name or empty for default). It never
accepts query/path/entry_id/app_id. This is not a new Core tool or transport version. Brain binds
the number to the current unexpired displayed page, consumes selection before IPC, then dispatches
existing open_file/open_directory/list_directory/open_containing_folder or resolve_app followed
by open_file_with_app. The selection executor has no filesystem-search fallback.

FileCandidate includes its original UI number. Budgeted model views can omit names without changing
the positions of remaining rows. A compact GGUF file-planning prompt describes the independent target,
operation and application fields; ordinary fresh-name searches retain the existing task prompt.
Literal numeric list notation is also parsed into a reference constraint (not an action). After
normal admission, runtime requires the proposed select_file number to match it and the page to be
valid; even a faulty search_files(query="2") cannot overwrite the CV page with a global search.
Quantity/filename queries remain searches. Relative folder search, numbered selection and ordinary
conversation are different paths. Existing explicit unambiguous shorthand selection remains available.
See docs/brain/FILE_SELECTION.md for tests and limits.

### Natural file goals and memory provenance (2026-10-14)

GGUF admission now uses a closed purpose schema instead of directly guessing a binary route:
locate_file/perform_action map to task; how_to/capability/recall/prohibition/discussion map to
conversation. Exact-key parsing, finite confidence checks and existing admission thresholds remain
mandatory. RequestRoute optionally retains this validated purpose; ONNX retains its compact
historical binary prompt/schema. A purpose is not a tool, target identity or permission.
For locate_file, runtime suppresses displayed candidates in the planning view and accepts only
search_files/clarify, preventing a repeated search from opening or implicit folder listing.
Private catalog-backed scope/page state remains with FileSession. Other providers without a
purpose preserve the historical routing contract. No execution boundary was changed.

An internal validated IntentContext.locating_file flag selects focused search planning directly
for admitted locating requests. Other fresh actions retain their existing reasoning prompt;
displayed selections retain their separate planner. The flag adds no execution authority.
Locating tasks use this focused planner for indirect, colloquial lost-file requests. Metadata
search uses a short name/topic clue, with explicit filters separated from the topic; search does
not imply opening. Displayed references still use the separate numbered/semantic selection planner.
Recency can affect sorting, not an invented exact-date filter. No content reading was added.
GGUF search plans have a focused inference: a bounded wanted_item description precedes
query/sort/extension/kind/confidence in a separate exact schema. The description is discarded;
only the existing validated search intent leaves the adapter. It cannot introduce opening or
another operation. Locating admission goes directly to this search schema, avoiding a competing
general action interpretation. Other admitted actions which select search_files receive the same
focused extraction, without increasing the capability-choice confidence. Numeric page addresses
skip extraction and remain subject to the current-page guard. No tool, network call, training
or execution authority is added.

ConversationMemory maintains two parallel bounded views. Conversation/recall preserves user and
assistant text; planning preserves user references, clarifications and execution outcomes but omits
chat replies and unsupported claims. Thus a hallucinated refusal cannot become a capability rule
on the next retry. Existing candidate redaction, lifetime, reset and character limits remain.
See docs/brain/NATURAL_FILE_GOALS.md for evaluation evidence and limitations.

### Stateful assistant dialogue (2026-10-15)

The GGUF execution path now uses validated dialogue moves before any file action. A read-only
speech-act decision is followed by separate target, operation and constraint extraction. Closed
TurnPlan fields carry human clues/location/type/depth and never executable paths or IDs. Missing
information may yield a focused slot question. Replies fill that slot without reinterpreting the
answer as a new operation. Legacy ONNX and diagnostic predict/classify APIs remain independent.

AssistantSession retains one FileGoal with 120s private bindings and a bounded, in-memory last
verified outcome until reset. Human constraints
are separate from FileSession's private current page and Core-backed scope. Rejecting results
discards the failed name hypothesis and excludes at most 100 Core IDs. An explicit replacement
name may reconsider earlier candidates. Reset/cancel/expiry clear private bindings. Chat suspends
file selection; explanation reads the last outcome without tool dispatch. Model self-confidence
is not treated as a calibrated probability; strict contracts and operation guards remain required.

Scope resolution searches trusted directory metadata and requires a unique human match, never
a model path or a global fallback after missing scope. Native search adds recursive (default true),
a closed metadata category, and bounded exclude_ids. recursive=false requires a catalog folder_id
and matches immediate children only. list_directory continues to list direct children. All fields
pass registry validation and policy. Categories filter extensions and do not read document contents.

After a failed name search, at most one additional read-only search may broaden the name to a type
within the same resolved scope. Results never auto-open after this recovery. A normal opening
requires a current positive request plus a unique trusted identity. Numbered pages preserve their
reference guard. A current-message positive opening-operation guard checks proposed openings; identity
corrections may show a result without launching it. Default Windows association and explicit PDF
browser adapters remain separate. No post-launch checking or new direct OS path is introduced.

Outcome summaries, pending question and task slots provide feedback to the next turn. Arbitrary
assistant capability claims are not promoted into verified state. Current-message extraction
does not copy old targets; dialogue-move classification sees bounded state flags and current
displayed names/kinds, not a replay of the whole dialogue. Operation extraction includes an
explicit unsupported choice so content reading,
uploading or deleting cannot be substituted with opening. Named app parameters require concrete
names; generic capability category nouns ask which app without a Core request. Literal UI numbers
remain page addresses, while the current action is validated independently. Performance/quality
acceptance must include precision, scope and wrong-action
checks with distractor files and multi-turn corrections; target inclusion alone is insufficient.

Communicative-purpose admission excludes old commands and displayed names; it sees only the current message
and a bounded genuine pending slot question. Target binding receives the separate bounded page
context, while conversational recall receives its history. A model-provided concrete target quote
must occur in the current message. Generic capability questions cannot borrow the displayed row
as a target. The existing validated result selector refines displayed target/action choices; it
does not bypass current-purpose, current-opening, confidence or private-page checks.
Omitted sort constraints use keep inside TurnPlan, preserving existing newest/largest ordering
through scope refinements. Only concrete name/newest/largest reaches the Native Core. Path-free
outcome summaries are separate from the rendered listings that show locations to the user.
Both displayed-selection routes independently extract the current opening application; a valid
target choice cannot discard an explicit app or infer a browser solely from file format.
Target-only matching copies a unique displayed filename using only this page and current reference.
Python maps that existing name to its original number; a decoder's numeric guess is insufficient.
Duplicate/invented names ask for clarification. Literal numeric addresses are checked against
the private unexpired page before model planning. An ungrounded optional admission quote is
discarded and cannot refine generic capability admission into selecting a displayed result.

### Model retirement and metadata discussion (2026-10-16)

User disabled ONNX. The production factory and launcher use GGUF only and reject ONNX explicitly;
no fallback or ONNX runtime import is allowed. GenAI is no longer a mandatory dependency. Archived
adapter/test source does not constitute a selectable production provider.

Conversation replies now receive the current bounded file candidate view (names/kinds/original
numbers only) along with bounded history. Rendering the final conversation message preserves
this metadata without repeating history. Reply text is never dispatched as an action. Discussing
results keeps the current goal/page until their existing deadline; it neither renews lifetime nor
supplies permission. Cancel/reset/expiry still discard bindings. This revises the earlier rule
that all chat consumes a file goal; metadata discussion needs continuity for a subsequent request.

The fragmented production planner is NOT accepted as a general assistant. Real regressions still
misroute recommendations, miss spelling corrections and unnecessarily clarify singleton pronouns.
See docs/brain/ASSISTANT_REASSESSMENT.md; a failed alternative planner was not promoted to production.
