# TASK_002 — Local IPC Contract + Python Brain Skeleton

**Status:** Ready  
**Milestone:** M002 — Brain ↔ Core Bridge  
**Primary languages:** Rust + Python  
**Target:** Windows-first  
**Depends on:** Completed `TASK_001`  
**Architecture rule:** Python may request actions; Rust remains the only trusted OS execution boundary.

---

## 0. Objective

Connect the completed Rust Native Core to an isolated Python Brain process through a fast, local, versioned IPC contract.

TASK-002 must prove that JARVIS can be split into two independent processes:

```text
Python Brain
     |
     | Local IPC
     v
Rust Native Core
     |
     v
Policy -> Executor -> Tools -> Windows
```

The Python process must never directly open applications, folders, execute shell commands, inspect OS application launch targets, or bypass the Rust Core.

At the end of TASK-002, the following end-to-end flow must work:

```text
Python:
resolve_app("Google Chrome")
        |
        v
Windows Named Pipe
        |
        v
Rust Core:
resolve_app
        |
        v
ToolResult(app_id)
        |
        v
Python:
open_app(app_id)
        |
        v
Windows Named Pipe
        |
        v
Rust Core:
Validation -> Policy -> Executor -> Platform
        |
        v
Google Chrome opens
```

No LLM is required in this task.

---

## 1. Architectural Decisions

TASK-002 locks the following decisions unless a documented implementation constraint requires a change.

### 1.1 Process Boundary

Run JARVIS as two independent processes:

```text
jarvis-core.exe
    Rust

jarvis-brain
    Python
```

The Python Brain must communicate with the Rust Core only through the IPC client abstraction.

### 1.2 Windows Transport

Primary Windows transport:

```text
Windows Named Pipe
```

Do not expose the Core on a public TCP port.

Do not bind to:

```text
0.0.0.0
LAN
internet-facing interfaces
```

Future platform transports may be:

```text
Windows -> Named Pipe
macOS   -> Unix Domain Socket
Linux   -> Unix Domain Socket
```

The transport layer must therefore remain abstracted from the protocol layer.

### 1.3 Control Protocol

Use:

```text
4-byte length prefix
+
UTF-8 JSON payload
```

for TASK-002 control messages.

This is intentionally chosen because control messages are small, JSON is easy to inspect during development, Rust already uses serde, and Python can handle it without code generation.

The protocol must be designed so serialization can be replaced later if profiling demonstrates a real need.

### 1.4 Voice Is a Separate Future Data Plane

Do not send microphone/audio streams through this control protocol.

Future architecture:

```text
Control plane
    requests, tool calls, events
    -> TASK-002 IPC

Audio/data plane
    microphone/audio streaming
    -> future dedicated channel
```

TASK-002 is control-plane only.

---

## 2. Scope

TASK-002 includes:

### Rust

- long-running Core service mode
- Windows Named Pipe IPC server
- transport abstraction
- framed-message codec
- versioned protocol envelope
- handshake
- ping/health request
- list-tools request
- execute-tool request
- mapping IPC execution into the existing TASK-001 `Executor`
- typed protocol errors
- request correlation
- frame-size limits
- connection isolation
- structured logging
- IPC tests

### Python

- new `services/brain/` Python package
- Python 3.12+ project configuration
- IPC transport abstraction
- Windows Named Pipe client
- framed JSON codec
- protocol models
- Core client
- typed Python errors
- handshake
- ping
- list-tools
- execute-tool
- helper method for resolve + open application
- development CLI/demo
- Python unit tests
- end-to-end smoke test

### Documentation

Update when necessary:

```text
README.md
AGENTS.md
ARCHITECTURE.md
```

to reflect the real Rust ↔ Python process boundary and IPC contract.

---

## 3. Out of Scope

Do not add:

- OpenAI
- Claude
- Gemini
- Ollama
- LLM routing
- natural-language reasoning
- semantic intent classification
- voice
- microphone
- STT
- TTS
- wake word
- desktop UI
- Tauri
- reminders
- RAG
- company knowledge
- browser automation
- arbitrary shell execution
- generic terminal execution
- Python OS-control helpers
- remote network IPC
- WebSocket server
- HTTP server
- gRPC server
- autonomous tool loops

Do not begin TASK-003 features early.

---

## 4. Non-Negotiable Security Boundary

The architecture from TASK-001 must remain intact.

Forbidden:

```python
subprocess.Popen(...)
os.startfile(...)
os.system(...)
ctypes -> arbitrary OS execution
win32api -> application launch
```

inside the Brain for OS actions.

Python may use OS APIs only where required to connect to the local IPC transport.

Python must not implement:

```text
open_app
open_folder
system_status
application discovery
application launching
```

Those remain Native Core responsibilities.

The only valid action path is:

```text
Python
   |
   v
IPC Request
   |
   v
Rust IPC Server
   |
   v
Existing ToolRequest
   |
   v
Existing Registry
   |
   v
Validation
   |
   v
Policy
   |
   v
Executor
   |
   v
Tool
   |
   v
Platform
```

The IPC server must never call platform functions directly.

---

## 5. Repository Structure

Evolve the repository toward:

```text
jarvis/
|
├── README.md
├── AGENTS.md
├── ARCHITECTURE.md
├── TASK_001.md
├── TASK_002.md
|
├── core/
│   └── native/
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs
│           ├── lib.rs
│           │
│           ├── ... existing TASK-001 modules ...
│           │
│           └── ipc/
│               ├── mod.rs
│               ├── protocol.rs
│               ├── codec.rs
│               ├── server.rs
│               ├── transport.rs
│               └── windows/
│                   ├── mod.rs
│                   └── named_pipe.rs
|
├── services/
│   └── brain/
│       ├── pyproject.toml
│       ├── README.md
│       ├── src/
│       │   └── jarvis_brain/
│       │       ├── __init__.py
│       │       ├── cli.py
│       │       ├── errors.py
│       │       ├── config.py
│       │       │
│       │       ├── core/
│       │       │   ├── __init__.py
│       │       │   └── client.py
│       │       │
│       │       └── ipc/
│       │           ├── __init__.py
│       │           ├── protocol.py
│       │           ├── codec.py
│       │           ├── transport.py
│       │           └── windows_pipe.py
│       │
│       └── tests/
│           ├── test_protocol.py
│           ├── test_codec.py
│           └── test_client.py
|
└── tests/
    └── e2e/
```

Small deviations are allowed when they improve maintainability.

Do not merge the Python Brain into the Rust crate.

---

## 6. Rust Service Mode

Add a long-running service command.

Expected development command:

```powershell
cargo run --manifest-path .\core\native\Cargo.toml -- serve
```

Conceptual lifecycle:

```text
start process
    |
    v
load configuration
    |
    v
build application catalog
    |
    v
create Tool Registry
    |
    v
create Policy Engine
    |
    v
create Executor
    |
    v
start Named Pipe server
    |
    v
accept Brain connections
```

The existing TASK-001 CLI commands should continue to work unless there is a strong documented reason to change them.

The service must reuse the same production registry, policy, executor, catalog, and platform implementations as the CLI.

No duplicate execution pipeline.

---

## 7. Named Pipe Endpoint

Use a local Windows Named Pipe.

Conceptual endpoint:

```text
\\.\pipe\jarvis-core-<user>-v1
```

Prefer a per-user endpoint derived safely from the current Windows user identity/SID so simultaneous users do not collide.

The exact naming strategy may differ if documented.

### Required Properties

- local machine only
- reject remote pipe clients
- prevent accidental cross-user access where practical
- stable enough for the Python Brain to discover
- not user-controlled arbitrary pipe names in production mode

Optional environment override for development:

```text
JARVIS_CORE_PIPE
```

If implemented, validate the override.

---

## 8. Named Pipe Security

At minimum:

- reject remote clients
- do not expose TCP/LAN access
- use Windows pipe security appropriate for the current user/session
- document the effective access-control behavior

Preferred:

```text
Current user
SYSTEM
Administrators
```

only, with current-user access being the normal Brain connection path.

If full current-user ACL restriction cannot be implemented reliably in TASK-002, the agent must:

1. still reject remote clients,
2. document the exact limitation,
3. not claim stronger isolation than actually exists.

Do not silently ignore Named Pipe security.

---

## 9. Framing

Every protocol message must be framed as:

```text
[4-byte unsigned payload length][JSON bytes]
```

Choose one byte order and document it.

Recommended:

```text
big-endian u32
```

### Frame Limits

Define a hard maximum frame size.

Recommended initial limit:

```text
1 MiB
```

Reject:

- zero/invalid frames when not meaningful
- frames above maximum size
- truncated frames
- malformed JSON
- unexpected trailing/partial payload state

Never allocate arbitrary memory based on an untrusted length prefix.

---

## 10. Protocol Versioning

Every request/response must include:

```json
{
  "protocol_version": 1
}
```

Define a constant in both implementations.

Example:

```text
JARVIS_CONTROL_PROTOCOL_VERSION = 1
```

Unsupported versions must return a typed protocol error and must not execute a tool.

Do not silently reinterpret incompatible versions.

---

## 11. Request Envelope

Conceptual request:

```json
{
  "protocol_version": 1,
  "request_id": "uuid",
  "message_type": "execute_tool",
  "payload": {}
}
```

Required fields:

```text
protocol_version
request_id
message_type
payload
```

`request_id` must be echoed in the response.

---

## 12. Response Envelope

Conceptual response:

```json
{
  "protocol_version": 1,
  "request_id": "uuid",
  "message_type": "tool_result",
  "ok": true,
  "payload": {},
  "error": null
}
```

Failure example:

```json
{
  "protocol_version": 1,
  "request_id": "uuid",
  "message_type": "error",
  "ok": false,
  "payload": null,
  "error": {
    "code": "unknown_tool",
    "message": "..."
  }
}
```

Do not require Python to parse human-readable strings to determine error type.

---

## 13. Required Message Types

TASK-002 must support at least:

```text
hello
ping
list_tools
execute_tool
```

### `hello`

Client request:

```json
{
  "protocol_version": 1,
  "request_id": "...",
  "message_type": "hello",
  "payload": {
    "client": "jarvis-brain",
    "client_version": "0.1.0"
  }
}
```

Server response should include:

```json
{
  "core": "jarvis-core",
  "core_version": "...",
  "protocol_version": 1
}
```

A client should perform handshake before normal operations.

### `ping`

Purpose:

```text
health / connection check
```

Response example:

```json
{
  "status": "ok"
}
```

### `list_tools`

Must return metadata from the existing Tool Registry.

Do not maintain a separate hard-coded Python tool list.

Example conceptual payload:

```json
{
  "tools": [
    {
      "name": "system_status",
      "risk_level": "read_only"
    },
    {
      "name": "resolve_app",
      "risk_level": "read_only"
    }
  ]
}
```

### `execute_tool`

Payload:

```json
{
  "tool": "system_status",
  "arguments": {}
}
```

Rust must convert this into the existing TASK-001 `ToolRequest`.

Set source appropriately:

```text
RequestSource::Brain
```

Then call the existing executor.

---

## 14. Critical IPC Execution Rule

The implementation must conceptually be:

```rust
match message_type {
    ExecuteTool => {
        let request = ToolRequest {
            source: RequestSource::Brain,
            ...
        };

        executor.execute(request)
    }
}
```

Forbidden:

```rust
if tool == "open_app" {
    windows_platform.open_application(...)
}
```

inside IPC code.

IPC does not own execution.

IPC only transports requests to the trusted Core.

---

## 15. Connection Behavior

The server should support a persistent connection.

Python must not reconnect for every individual tool request.

Expected:

```text
connect
handshake
request
response
request
response
...
disconnect
```

This reduces latency and prepares the architecture for conversational Brain use.

### Multiple Connections

TASK-002 should be designed so one bad client connection does not crash the Core process.

At minimum:

- client disconnect must not stop server
- malformed frame must close/reject that connection safely
- subsequent clients can still connect

Supporting many high-volume simultaneous clients is not required yet.

---

## 16. Timeouts

Do not allow the Brain to wait forever.

Python client should support:

```text
connect timeout
request timeout
```

Use conservative defaults suitable for local IPC.

Timeouts must produce typed Python exceptions.

The Rust server must not block forever waiting for a malformed/incomplete frame where practical.

Exact values may be implementation-defined and configurable.

---

## 17. Rust Error Mapping

Protocol errors should distinguish at least:

```text
unsupported_protocol_version
invalid_frame
frame_too_large
invalid_message
unknown_message_type
handshake_required
internal_protocol_error
```

Existing Core errors remain existing Core errors:

```text
unknown_tool
invalid_arguments
policy_denied
confirmation_required
application_not_found
application_ambiguous
invalid_application_id
...
```

Do not collapse every error into:

```text
internal_error
```

---

## 18. Python Brain Project

Create a real installable Python project.

Suggested:

```text
services/brain/pyproject.toml
```

Target:

```text
Python >= 3.12
```

Keep dependencies minimal.

No AI SDK dependency in TASK-002.

Potential dependencies should be limited to what is actually needed for:

- Windows Named Pipe connectivity
- development/testing
- optional typed validation if justified

Prefer Python standard library where practical.

---

## 19. Python IPC Abstraction

Create a transport interface.

Conceptual:

```python
class IPCTransport(Protocol):
    def connect(self) -> None: ...
    def send(self, payload: bytes) -> None: ...
    def receive(self) -> bytes: ...
    def close(self) -> None: ...
```

Then:

```text
WindowsNamedPipeTransport
```

implements it.

Future:

```text
UnixSocketTransport
```

can be added without changing Brain business logic.

---

## 20. Python Protocol Types

Do not pass unstructured dictionaries through the entire Brain.

Create clear protocol/request/response models.

At minimum represent:

```text
HelloRequest
HelloResponse
PingRequest
ToolMetadata
ExecuteToolRequest
ExecuteToolResponse
ProtocolError
```

Dataclasses are acceptable.

A validation library may be used if justified, but do not add heavy dependencies without need.

---

## 21. Python Core Client

Create a high-level client such as:

```python
class JarvisCoreClient:
    def connect(self) -> None: ...
    def ping(self) -> ...: ...
    def list_tools(self) -> ...: ...

    def execute_tool(
        self,
        tool: str,
        arguments: dict,
    ) -> ToolResult:
        ...
```

The client must hide:

```text
pipe framing
JSON encoding
request IDs
handshake details
```

from future AI code.

Future Brain code should be able to do:

```python
core.execute_tool(
    "system_status",
    {},
)
```

without knowing how Named Pipes work.

---

## 22. Python Application Helper

For TASK-002 demonstration, create a non-AI helper:

```python
def open_application(
    core: JarvisCoreClient,
    query: str,
) -> ToolResult:
    ...
```

Internally:

```text
execute_tool("resolve_app", {"query": query})
        |
        v
app_id
        |
        v
execute_tool("open_app", {"app_id": app_id})
```

This helper must not access the Windows application catalog directly.

### Ambiguity

If Rust returns:

```text
application_ambiguous
```

Python should surface the candidates to the caller.

Do not automatically choose a random candidate.

---

## 23. Development CLI

Create a minimal Brain-side developer CLI.

Expected examples:

```powershell
python -m jarvis_brain.cli ping
```

```powershell
python -m jarvis_brain.cli tools
```

```powershell
python -m jarvis_brain.cli status
```

```powershell
python -m jarvis_brain.cli open-app "Google Chrome"
```

This CLI exists to validate IPC.

It is not the final JARVIS conversational interface.

Expected development flow:

Terminal 1:

```powershell
cargo run --manifest-path .\core\native\Cargo.toml -- serve
```

Terminal 2:

```powershell
cd .\services\brain
python -m jarvis_brain.cli ping
python -m jarvis_brain.cli open-app "Google Chrome"
```

---

## 24. No Python Tool Duplication

Do not create Python implementations like:

```python
def open_app_windows(...):
    ...

def system_status_windows(...):
    ...

def find_installed_apps(...):
    ...
```

Python may define semantic helper functions, but all actual machine state/action must come from Rust tools.

Correct:

```python
def get_system_status(core):
    return core.execute_tool("system_status", {})
```

Incorrect:

```python
import psutil

def get_system_status():
    return psutil.cpu_percent()
```

The Brain is intelligence/orchestration, not the native system layer.

---

## 25. Catalog Lifetime

When the Rust service starts:

```text
build/refresh application catalog
```

before serving normal Brain requests.

This ensures:

```text
resolve_app
```

and later:

```text
open_app(app_id)
```

operate against the same long-running Core process/catalog.

Document the chosen refresh behavior.

TASK-002 does not need real-time Windows install/uninstall watching.

---

## 26. Logging

Keep logs distinct from machine-readable protocol output.

Rust should log:

```text
server startup
pipe endpoint
client connect/disconnect
handshake success/failure
protocol rejection
tool request correlation
```

Existing audit logs remain authoritative for tool execution.

Do not duplicate sensitive tool payloads unnecessarily.

Python should optionally log:

```text
connect
disconnect
request ID
message type
timeout
protocol error
```

Do not log secrets or raw trusted launch targets.

---

## 27. Protocol Safety Tests — Rust

At minimum test:

### Codec

- valid frame encodes/decodes
- length prefix is correct
- partial header rejected/handled
- partial body rejected/handled
- oversized frame rejected
- malformed JSON rejected

### Versioning

- protocol v1 accepted
- unsupported protocol rejected
- unsupported protocol cannot execute tool

### Message Routing

- hello works
- ping works
- list_tools uses production registry metadata
- execute_tool enters existing executor
- unknown message type returns typed error

### Execution Boundary

- IPC open_app cannot launch caller path
- IPC unknown tool does not execute
- IPC invalid arguments do not reach platform
- policy denial still prevents execution
- `RequestSource::Brain` is recorded
- audit is still emitted

### Resilience

- malformed client connection does not crash server
- server can accept another connection after bad client disconnect

---

## 28. Python Tests

At minimum test:

### Codec

- frames encode/decode correctly
- oversized payload rejected
- malformed response rejected

### Client

Using a fake transport:

- handshake occurs
- ping request works
- request IDs correlate
- tool result parsed
- Core error maps to typed Python exception/result
- timeout maps to typed exception
- disconnect is handled

### App Helper

- resolve then open uses returned app_id
- ambiguity is surfaced
- not-found is surfaced
- helper never accepts/creates executable path

Do not require a live Rust server for all Python unit tests.

---

## 29. End-to-End Windows Smoke Test

After unit tests pass, perform a real E2E test on Windows.

### Start Core

```powershell
cargo run --manifest-path .\core\native\Cargo.toml -- serve
```

Expected:

```text
JARVIS Core listening on local named pipe ...
```

### Brain Health

```powershell
python -m jarvis_brain.cli ping
```

Expected:

```text
ok
```

### Tool Discovery

```powershell
python -m jarvis_brain.cli tools
```

Must show TASK-001 tools from Rust.

### System Status

```powershell
python -m jarvis_brain.cli status
```

Must return data produced by Rust.

### Real App Open

```powershell
python -m jarvis_brain.cli open-app "Google Chrome"
```

Expected:

```text
Python
 -> Named Pipe
 -> Rust resolve_app
 -> app_id
 -> Rust open_app
 -> Google Chrome opens
```

### Security Regression

Attempt through Python:

```text
open_app(
    app_id="C:\Windows\System32\cmd.exe"
)
```

Rust must still reject it with:

```text
invalid_application_id
```

No CMD window should open.

---

## 30. Rust Validation Commands

TASK-002 is not complete until these pass:

```powershell
cargo fmt --check --manifest-path .\core\native\Cargo.toml
```

```powershell
cargo build --manifest-path .\core\native\Cargo.toml
```

```powershell
cargo clippy --manifest-path .\core\native\Cargo.toml --all-targets --all-features -- -D warnings
```

```powershell
cargo test --manifest-path .\core\native\Cargo.toml
```

If workspace configuration changes the exact command, document the final commands used.

---

## 31. Python Validation Commands

From:

```text
services/brain/
```

the project should support an isolated environment.

Expected validation:

```powershell
python -m pytest
```

and a formatter/linter such as:

```powershell
python -m ruff check .
python -m ruff format --check .
```

If another lightweight equivalent is chosen, document it.

Avoid adding a large toolchain for TASK-002.

---

## 32. Acceptance Criteria

TASK-002 is complete only when all are true.

### Architecture

```text
Python Brain
     |
Named Pipe IPC
     |
Rust Core
     |
Existing TASK-001 Executor
```

is real and working.

### Rust

- Core has long-running `serve` mode
- local Windows Named Pipe works
- persistent client connection works
- handshake/version check works
- ping works
- list_tools works
- execute_tool works
- malformed clients do not crash service
- existing TASK-001 security pipeline is unchanged

### Python

- Brain package installs/runs
- Brain contains no LLM dependency
- Core client hides IPC details
- Brain can ping Core
- Brain can list Rust tools
- Brain can get system status through Rust
- Brain can resolve an application through Rust
- Brain can open a resolved application through Rust
- Brain does not implement direct OS tool execution

### Security

- no TCP/LAN server
- remote pipe clients rejected
- pipe security documented
- no generic shell
- no executable-path launch
- invalid app ID still rejected
- Python cannot bypass policy/executor
- unsupported protocol version cannot execute tools
- oversized/malformed IPC messages are rejected safely

### Quality

- Rust fmt/build/clippy/tests pass
- Python tests/lint/format pass
- Windows E2E smoke test passes

---

## 33. Definition of Done Report

The coding agent must provide:

1. summary of created/changed files
2. final Rust IPC module tree
3. final Python Brain module tree
4. exact Named Pipe naming strategy
5. exact pipe security behavior
6. framing specification
7. protocol versioning behavior
8. list of supported message types
9. Rust validation results
10. Python validation results
11. real Windows E2E results
12. confirmation that Python has no direct application/folder/system execution path
13. confirmation that all IPC tool calls use the existing TASK-001 Executor
14. confirmation that caller-provided executable paths remain impossible
15. limitations or architecture deviations

If any requirement cannot be completed, state it explicitly.

---

## 34. Required Documentation Updates

Update `ARCHITECTURE.md` with a concrete section describing:

```text
Brain Process
Control Protocol
Transport
Security Boundary
Request Flow
Failure Behavior
```

Update `AGENTS.md` with rules such as:

```text
Python Brain MUST NOT directly control the OS.
All machine actions MUST go through JarvisCoreClient.
IPC server MUST forward actions through the existing Executor.
Do not duplicate Rust tools in Python.
Control IPC MUST NOT be used as the future raw audio streaming channel.
```

Update `README.md` with the development commands for starting Core and testing Brain connectivity.

Do not rewrite unrelated documentation unnecessarily.

---

## 35. Coding Agent Instruction

Use this exact high-level assignment:

> Read `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, completed `TASK_001.md`, and `TASK_002.md` completely before editing. Implement TASK-002 only. Add a long-running Rust `jarvis-core serve` mode and a local Windows Named Pipe control server. Use a versioned, length-prefixed UTF-8 JSON protocol with a hard frame-size limit. Support handshake, ping, list-tools, and execute-tool. Every IPC execute-tool request MUST be converted into the existing TASK-001 `ToolRequest` with `RequestSource::Brain` and MUST pass through the existing Tool Registry, Validation, Policy Engine, Executor, Tool, and Platform path. Never call the Windows platform directly from IPC code. Create an isolated Python 3.12+ `services/brain` package containing the IPC transport/client and a non-AI development CLI. Python MUST NOT implement OS actions or duplicate Rust tools. Demonstrate an end-to-end `resolve_app("Google Chrome") -> app_id -> open_app(app_id)` flow through IPC. Preserve TASK-001 security guarantees, reject malformed/oversized/version-incompatible IPC traffic, and document Named Pipe access control. Do not add LLM providers, voice, UI, RAG, reminders, HTTP, gRPC, WebSockets, arbitrary shell execution, or remote network exposure. Update README, AGENTS, and ARCHITECTURE only where needed. Do not declare completion until Rust and Python validation plus the real Windows E2E smoke test pass.

---

## 36. Expected End State

After TASK-002:

```text
                        JARVIS

                   Python Brain
                   (no AI yet)
                        |
                        |
               Local Control IPC
                Windows Named Pipe
                        |
                        v
                   Rust Core
                        |
                 Tool Registry
                        |
                   Validation
                        |
                  Policy Engine
                        |
                    Executor
                        |
              +---------+---------+
              |         |         |
             Apps      Files     System
```

This is the first milestone where JARVIS has a physically separated **Brain** and **Body**.

The intelligence layer is still intentionally empty.

---

## 37. Next Task

After TASK-002 is completed and independently smoke-tested:

```text
TASK_003 — AI Provider Layer + Structured Intent/Tool Planning
```

TASK-003 will introduce the first AI provider abstraction and convert natural-language requests into safe structured tool requests.

Do not begin TASK-003 as part of TASK-002.
