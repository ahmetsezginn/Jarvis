# TASK_001 — Native JARVIS Core (UPDATED)

**Status:** Ready  
**Revision:** 2 — Dynamic Application Discovery  
**Milestone:** M001 — Trusted Execution Core  
**Primary language:** Rust  
**Target:** Windows-first, cross-platform-ready  
**Depends on:** `README.md`, `agent/AGENTS.md`, `agent/ARCHITECTURE.md`

---

## 0. Important Revision

This revision supersedes the original static application allow-list design.

JARVIS must **not** require developers or users to predefine every installed application in TOML before it can be opened.

Old conceptual design:

```text
apps.toml
  spotify = "C:\\...\\Spotify.exe"
  chrome  = "C:\\...\\chrome.exe"
  vscode  = "C:\\...\\Code.exe"

open_app("spotify")
```

New required design:

```text
Windows
   |
   v
Application Discovery
   |
   v
Application Catalog
   |
   v
Application Resolver
   |
   v
ResolvedApplication
   |
   v
Policy Engine
   |
   v
open_app(app_id)
   |
   v
Platform Launcher
```

JARVIS should discover installed applications from the operating system, maintain a trusted internal catalog, resolve a user's query against that catalog, and launch only an application identity that came from that trusted catalog.

Configuration files may still contain preferences, aliases, exclusions, or policy overrides, but they must not be required to enumerate every application on the machine.

---

## 1. Objective

Build the first executable version of the **JARVIS Native Core**.

TASK-001 does not create an AI assistant yet.

TASK-001 establishes the trusted execution boundary that every future JARVIS client, voice layer, AI model, automation, and integration will use.

At the end of this task, the Rust-native core must support:

- deterministic tool execution
- policy enforcement
- audit events
- Windows platform abstraction
- dynamic application discovery
- trusted application catalog
- application name resolution
- safe application launching by internal `app_id`
- folder opening
- system status

Mandatory execution flow:

```text
ToolRequest
    |
    v
Input Validation
    |
    v
Tool Registry
    |
    v
Policy Engine
    |
    +---- DENY
    |
    +---- REQUIRE_CONFIRMATION
    |
    +---- ALLOW
              |
              v
           Executor
              |
              v
             Tool
              |
              v
        Platform Adapter
              |
              v
        Operating System
              |
              v
          ToolResult
              |
              v
           Audit Event
```

Application requests add an internal trusted-resolution flow:

```text
query: "spotify"
      |
      v
AppResolver
      |
      v
AppCatalog
      |
      v
ResolvedApplication(app_id)
      |
      v
open_app(app_id)
```

No public request may provide an arbitrary executable path for launching.

---

## 2. Scope

TASK-001 includes:

- Rust workspace initialization
- `jarvis-core` executable
- core request/result types
- tool abstraction
- tool registry
- policy abstraction
- executor
- audit abstraction
- platform abstraction
- Windows platform implementation
- application discovery abstraction
- Windows application discovery implementation
- trusted application catalog
- application resolver
- stable internal `app_id`
- initial tools:
  - `system_status`
  - `open_folder`
  - `resolve_app`
  - `open_app`
- minimal local CLI/testing interface
- unit tests
- integration tests
- structured error handling
- basic structured logging
- documentation updates required by this revision

TASK-001 does **not** include:

- Python
- LLM integration
- semantic AI application resolution
- OpenAI / Claude / Gemini
- voice
- STT / TTS
- wake word
- IPC
- gRPC
- named pipes
- desktop UI
- Tauri
- reminders
- RAG
- autonomous agents
- browser automation
- arbitrary shell execution
- file deletion
- file moving
- network access

Do not implement later milestones early.

---

## 3. Mandatory Documentation Update

Before declaring TASK-001 complete, update these files if they contain the old static application allow-list design:

```text
README.md
agent/AGENTS.md
agent/ARCHITECTURE.md
```

The documentation must reflect:

```text
Application Discovery
        |
        v
Application Catalog
        |
        v
Application Resolver
        |
        v
Resolved app_id
        |
        v
Policy
        |
        v
Launcher
```

Remove or rewrite statements implying that every installed application must be manually declared in `apps.toml`.

Configuration may be described as optional for:

- preferred apps
- user aliases
- enterprise policy
- exclusions
- explicit overrides

It must not be the primary source of installed-app truth.

---

## 4. Security Invariants

### 4.1 No Arbitrary Shell

Forbidden:

```rust
Command::new("cmd")
    .args(["/C", user_or_model_generated_string])
```

Forbidden:

```text
shell=true
eval
exec arbitrary command
powershell <untrusted string>
cmd /C <untrusted string>
```

Do not expose generic tools such as:

```text
run_command
run_shell
execute_terminal
powershell
bash
```

### 4.2 No Arbitrary Executable Launch

Public input must not be able to launch:

```text
C:\\random\\program.exe
\\\\server\\share\\payload.exe
powershell.exe
cmd.exe
```

merely by supplying the path to `open_app`.

`open_app` must accept a trusted internal application identity:

```json
{
  "app_id": "app_..."
}
```

The `app_id` must resolve to an entry created by JARVIS application discovery or an explicitly trusted administrative override.

### 4.3 AI Is Untrusted

Future AI output must be treated as untrusted input.

Even if a future model claims:

```text
Spotify is at C:\\Users\\...\\Spotify.exe
```

the Native Core must ignore that path and resolve Spotify through its own application catalog.

### 4.4 Explicit Tools Only

Every OS action must be represented by a registered tool.

### 4.5 Path Validation

`open_folder` must:

- require an existing directory
- validate/canonicalize where appropriate
- reject file paths
- avoid shell command construction
- return typed errors

---

## 5. Target Repository Structure

Evolve the repository toward:

```text
jarvis/
|
├── README.md
├── AGENTS.md
├── ARCHITECTURE.md
├── TASK_001.md
|
├── core/
│   └── native/
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs
│           ├── lib.rs
│           │
│           ├── core/
│           │   ├── mod.rs
│           │   ├── request.rs
│           │   ├── result.rs
│           │   ├── error.rs
│           │   └── risk.rs
│           │
│           ├── tools/
│           │   ├── mod.rs
│           │   ├── tool.rs
│           │   ├── registry.rs
│           │   │
│           │   ├── system/
│           │   │   └── system_status.rs
│           │   │
│           │   ├── apps/
│           │   │   ├── resolve_app.rs
│           │   │   └── open_app.rs
│           │   │
│           │   └── files/
│           │       └── open_folder.rs
│           │
│           ├── apps/
│           │   ├── mod.rs
│           │   ├── model.rs
│           │   ├── discovery.rs
│           │   ├── catalog.rs
│           │   ├── resolver.rs
│           │   └── windows/
│           │       ├── mod.rs
│           │       └── discovery.rs
│           │
│           ├── policy/
│           │   ├── mod.rs
│           │   ├── engine.rs
│           │   └── decision.rs
│           │
│           ├── executor/
│           │   ├── mod.rs
│           │   └── executor.rs
│           │
│           ├── platform/
│           │   ├── mod.rs
│           │   ├── desktop.rs
│           │   └── windows/
│           │       ├── mod.rs
│           │       └── desktop.rs
│           │
│           ├── audit/
│           │   ├── mod.rs
│           │   ├── event.rs
│           │   └── sink.rs
│           │
│           └── config/
│               ├── mod.rs
│               └── preferences.rs
|
├── config/
│   └── preferences.example.toml
|
├── policies/
│   └── default.yaml
|
└── tests/
    └── core/
```

Small idiomatic Rust deviations are allowed.

Do not collapse the responsibility boundaries.

---

## 6. Core Types

Define typed request and result models.

Conceptual request:

```rust
pub struct ToolRequest {
    pub request_id: RequestId,
    pub tool: ToolName,
    pub arguments: serde_json::Value,
    pub source: RequestSource,
}
```

Suggested request sources:

```rust
pub enum RequestSource {
    Cli,
    Desktop,
    Voice,
    Brain,
    Internal,
}
```

Only `Cli` and/or `Internal` need active usage in TASK-001.

Conceptual result:

```rust
pub struct ToolResult {
    pub request_id: RequestId,
    pub tool: ToolName,
    pub status: ToolStatus,
    pub data: serde_json::Value,
}
```

Suggested status:

```rust
pub enum ToolStatus {
    Success,
    Denied,
    ConfirmationRequired,
    Failed,
}
```

---

## 7. Error Model

Create typed errors.

At minimum support categories such as:

```text
UnknownTool
InvalidArguments
PolicyDenied
ConfirmationRequired
PlatformUnsupported

FolderNotFound
NotADirectory

ApplicationDiscoveryFailed
ApplicationNotFound
ApplicationAmbiguous
InvalidApplicationId
ApplicationLaunchFailed

SystemInformationUnavailable
ConfigurationError
Internal
```

Do not use human-readable message parsing as control flow.

---

## 8. Risk Model

Suggested:

```rust
pub enum RiskLevel {
    ReadOnly,
    Low,
    Medium,
    High,
}
```

Initial risk assignment:

```text
system_status -> ReadOnly
resolve_app   -> ReadOnly
open_folder   -> Low
open_app      -> Low
```

---

## 9. Tool Interface

Create a common tool abstraction.

Conceptual interface:

```rust
pub trait Tool: Send + Sync {
    fn name(&self) -> &'static str;

    fn risk_level(&self) -> RiskLevel;

    fn validate(
        &self,
        arguments: &serde_json::Value,
    ) -> Result<(), JarvisError>;

    fn execute(
        &self,
        context: &ToolContext,
        arguments: &serde_json::Value,
    ) -> Result<ToolOutput, JarvisError>;
}
```

Mandatory principles:

- explicit registration
- stable names
- validation before execution
- policy-visible risk metadata
- typed results
- no UI printing in tools
- no LLM/provider knowledge in tools

---

## 10. Tool Registry

Registry must:

- register a tool
- resolve a tool by stable name
- reject duplicate names
- return typed `UnknownTool`
- expose tool metadata for future Brain/IPC usage

Expected registered names:

```text
system_status
open_folder
resolve_app
open_app
```

---

## 11. Application Discovery Architecture

This is the major change in revision 2.

### 11.1 Goal

JARVIS must discover applications installed or launchable on the local machine without requiring manual enumeration.

### 11.2 Discovery Interface

Create an abstraction similar to:

```rust
pub trait ApplicationDiscovery: Send + Sync {
    fn discover(&self) -> Result<Vec<DiscoveredApplication>, JarvisError>;
}
```

### 11.3 Windows Discovery

Implement a Windows-first discovery provider.

The implementation may inspect safe OS-managed application sources such as:

- Start Menu application shortcuts
- registered installed applications
- Windows application registrations
- known packaged applications / Microsoft Store app registrations
- other documented Windows application metadata sources

Do not recursively scan the entire disk for `.exe` files.

Do not treat every executable on disk as a trusted user application.

The objective is **discover installed user-facing applications**, not enumerate arbitrary binaries.

### 11.4 Discovery Result

Conceptual model:

```rust
pub struct DiscoveredApplication {
    pub app_id: ApplicationId,
    pub canonical_name: String,
    pub aliases: Vec<String>,
    pub publisher: Option<String>,
    pub source: ApplicationSource,
    pub launch: TrustedLaunchTarget,
}
```

`TrustedLaunchTarget` must remain internal to the Native Core.

Never serialize raw executable paths unnecessarily to untrusted callers.

---

## 12. Stable Application Identity

Each discovered application must receive an internal stable identity.

Conceptual:

```text
app_7d922...
```

The exact ID strategy is implementation-defined.

Desired properties:

- stable enough across catalog refreshes when the same app is discovered from the same source
- opaque to callers
- not a raw path
- cannot be supplied to bypass catalog validation

The catalog must verify that an incoming `app_id` exists before launch.

---

## 13. Application Catalog

Create a trusted in-memory catalog abstraction.

Conceptual API:

```rust
pub trait ApplicationCatalog: Send + Sync {
    fn refresh(&mut self) -> Result<(), JarvisError>;

    fn get(
        &self,
        id: &ApplicationId,
    ) -> Option<&DiscoveredApplication>;

    fn search(
        &self,
        query: &str,
    ) -> Vec<ApplicationCandidate>;
}
```

Initial implementation may build the catalog:

- at process startup
- lazily on first use
- or with an explicit refresh command

Choose the simplest reliable approach and document the choice.

Future tasks may add OS event watching and incremental refresh.

---

## 14. Application Resolver

Create an application resolver separate from the launcher.

Responsibility:

> Determine which discovered application best matches a user-provided query.

Not responsibility:

> Execute an executable path supplied by the caller.

Conceptual API:

```rust
pub trait ApplicationResolver: Send + Sync {
    fn resolve(
        &self,
        query: &str,
        catalog: &ApplicationCatalog,
    ) -> Result<ResolvedApplication, JarvisError>;
}
```

### TASK-001 Matching

Implement deterministic local matching only.

At minimum:

1. normalize whitespace
2. case-insensitive exact canonical-name match
3. case-insensitive alias match
4. basic deterministic fuzzy match

AI/semantic matching is explicitly deferred.

### Resolution Outcomes

#### One strong candidate

Return:

```text
ResolvedApplication
```

#### No candidate

Return:

```text
ApplicationNotFound
```

#### Multiple plausible candidates

Return:

```text
ApplicationAmbiguous
```

with candidate metadata suitable for future user clarification.

Do not silently open an arbitrary candidate when confidence is insufficient.

---

## 15. `resolve_app` Tool

### Purpose

Resolve a human application query against the trusted catalog.

### Input

```json
{
  "query": "spotify"
}
```

### Output — resolved

```json
{
  "resolved": true,
  "app": {
    "app_id": "app_7d922",
    "name": "Spotify",
    "publisher": "Spotify AB"
  }
}
```

### Output — ambiguous

Represent ambiguity through the typed result/error contract.

Candidate metadata may include:

```json
{
  "candidates": [
    {
      "app_id": "app_a",
      "name": "Visual Studio Code"
    },
    {
      "app_id": "app_b",
      "name": "CodeBlocks"
    }
  ]
}
```

Do not expose trusted launch targets to the caller.

---

## 16. `open_app` Tool

### Purpose

Launch an application already resolved/discovered by JARVIS.

### Input

Required:

```json
{
  "app_id": "app_7d922"
}
```

### Validation

Reject:

- missing `app_id`
- unknown `app_id`
- raw paths
- app IDs not present in current trusted catalog
- malformed IDs

### Internal Flow

```text
app_id
  |
  v
Trusted AppCatalog lookup
  |
  v
DiscoveredApplication
  |
  v
Policy
  |
  v
Platform launch
```

### Important

`open_app` must **not** accept:

```json
{
  "path": "C:\\..."
}
```

or:

```json
{
  "executable": "..."
}
```

from external callers.

### Result

Example:

```json
{
  "opened": true,
  "app_id": "app_7d922",
  "name": "Spotify"
}
```

---

## 17. Optional Convenience Flow

The CLI may provide a development-only convenience command:

```bash
jarvis-core app open spotify
```

But internally it must perform:

```text
resolve_app("spotify")
      |
      v
resolved app_id
      |
      v
open_app(app_id)
```

The CLI must not bypass resolver, policy, executor, or catalog.

Future Brain requests may choose to call `resolve_app` and `open_app` separately.

---

## 18. Configuration

Configuration is no longer the primary application catalog.

Optional configuration may contain:

```toml
[preferences]
browser = "Google Chrome"
music = "Spotify"
editor = "Visual Studio Code"

[aliases]
code = "Visual Studio Code"
music = "Spotify"
```

Possible future enterprise policy:

```toml
[applications]
deny = ["Some Application"]
```

These are:

- preferences
- aliases
- overrides
- policy inputs

They are **not required definitions for every installed application**.

JARVIS must function without manually listing Spotify, Chrome, VS Code, Notion, etc.

---

## 19. `system_status` Tool

Purpose and behavior remain unchanged.

Input:

```json
{}
```

Output should include typed CPU, memory, and disk information.

Requirements:

- no elevated privileges
- no shell invocation
- no process panic on errors
- serialization-ready output

---

## 20. `open_folder` Tool

Purpose and behavior remain unchanged.

Input:

```json
{
  "path": "C:\\Users\\User\\Downloads"
}
```

Validation:

- path required
- string required
- must exist
- must be a directory
- safely normalize/canonicalize where appropriate

Windows launch must use a trusted explicit platform method, not shell string construction.

---

## 21. Policy Engine

Create deterministic policy boundary.

Suggested decision:

```rust
pub enum PolicyDecision {
    Allow,
    Deny { reason: String },
    RequireConfirmation { reason: String },
}
```

Default TASK-001 behavior:

```text
ReadOnly -> ALLOW
Low      -> ALLOW
Medium   -> REQUIRE_CONFIRMATION
High     -> REQUIRE_CONFIRMATION
```

The executor must support all three outcomes.

A tool must never execute before policy evaluation.

---

## 22. Executor

Required order:

```text
1. receive ToolRequest
2. resolve tool from registry
3. validate arguments
4. obtain tool metadata
5. evaluate policy
6. stop if denied
7. stop if confirmation required
8. execute tool
9. create ToolResult
10. emit audit event
11. return result
```

Do not duplicate this flow in CLI code.

---

## 23. Audit Layer

Audit at minimum:

- allowed execution
- denied execution
- failed execution
- unknown tool
- application resolution failure
- application ambiguity
- successful application launch

Do not log unnecessary raw launch targets or secrets.

---

## 24. Platform Abstraction

OS-specific code stays behind platform interfaces.

Conceptual:

```rust
pub trait DesktopPlatform: Send + Sync {
    fn open_application(
        &self,
        application: &DiscoveredApplication,
    ) -> Result<(), JarvisError>;

    fn open_folder(
        &self,
        path: &Path,
    ) -> Result<(), JarvisError>;

    fn system_status(
        &self,
    ) -> Result<SystemStatus, JarvisError>;
}
```

Windows-specific application discovery may have a separate provider:

```rust
WindowsApplicationDiscovery
```

Generic tools must not contain Windows-specific launch construction.

---

## 25. CLI Development Harness

Expected commands may look like:

```bash
jarvis-core tools list
```

```bash
jarvis-core apps refresh
```

```bash
jarvis-core apps search spotify
```

```bash
jarvis-core tool resolve_app '{"query":"spotify"}'
```

```bash
jarvis-core tool open_app '{"app_id":"app_..."}'
```

```bash
jarvis-core tool system_status '{}'
```

```bash
jarvis-core tool open_folder '{"path":"C:\\Users\\User\\Downloads"}'
```

Optional convenience:

```bash
jarvis-core app open spotify
```

All actionable commands must use the shared core execution pipeline.

---

## 26. Suggested Dependencies

Keep dependencies minimal.

Suggested categories:

```text
serde / serde_json
thiserror
tracing / tracing-subscriber
sysinfo
uuid
```

For deterministic fuzzy matching, a small focused crate may be used if justified.

Prefer standard/platform APIs for application discovery where practical.

Do not add Tokio solely for future IPC.

Do not add Python.

---

## 27. Reliability Rules

The core must:

- never panic due to malformed external input
- return typed errors
- survive failed tool invocation
- avoid global mutable state where practical
- not wait for launched GUI apps to exit
- keep business logic independent of CLI formatting
- keep raw trusted launch targets private to the core
- safely handle stale app catalog entries
- return `ApplicationNotFound` or launch failure when an app disappears

Avoid `unwrap()` / `expect()` on external input or OS operations.

---

## 28. Testing Requirements

### Tool Registry

Test:

- registration
- resolution
- duplicate rejection
- unknown tool

### Policy

Test:

- ReadOnly -> allow
- Low -> allow
- Medium -> confirmation
- High -> confirmation

### Executor

Test:

- unknown tool never reaches platform
- invalid args never reach platform
- denied request never executes
- confirmation-required request never executes
- allowed request executes once
- audit emitted

### Application Discovery

Use a fake discovery provider.

Test:

- discovered apps populate catalog
- duplicate discoveries are handled deterministically
- refresh replaces/updates catalog safely
- discovery errors are typed

### Application Resolver

Test:

- exact match
- case-insensitive match
- alias match
- basic fuzzy match
- no match -> ApplicationNotFound
- ambiguous match -> ApplicationAmbiguous
- resolver never invents executable paths

### `resolve_app`

Test:

- query required
- catalog lookup used
- result returns app metadata but not raw launch target

### `open_app`

Test:

- missing app_id rejected
- unknown app_id rejected
- raw path input rejected
- valid app_id resolves through catalog
- platform launch receives only catalog-backed app
- arbitrary executable cannot be launched

### `open_folder`

Test:

- missing path
- nonexistent path
- file rejected
- directory accepted

### `system_status`

Test:

- typed output
- serialization

---

## 29. Fake Implementations

Tests must not depend on opening real apps.

Create fakes such as:

```text
FakeApplicationDiscovery
FakeApplicationCatalog or deterministic in-memory catalog
FakeDesktopPlatform
FakeAuditSink
```

The fake platform should record:

```text
opened_application_ids
opened_folders
system_status_calls
```

This must allow proving that invalid or denied requests never reach the platform.

---

## 30. Acceptance Criteria

TASK-001 is complete only when all pass.

### Build

```bash
cargo build
```

### Formatting

```bash
cargo fmt --check
```

### Linting

```bash
cargo clippy --all-targets --all-features -- -D warnings
```

### Tests

```bash
cargo test
```

### Functional

Developer can:

```text
discover installed Windows applications
refresh/search the local application catalog
resolve "spotify" or another installed app without manually defining it
receive an app_id
launch a catalog-backed app by app_id
open a folder
read system status
```

### Security

Public requests cannot:

```text
run arbitrary shell
launch arbitrary executable path
bypass application catalog
bypass policy
bypass executor
execute unknown tool
```

### Documentation

`README.md`, `agent/AGENTS.md`, and `agent/ARCHITECTURE.md` no longer describe manual static app enumeration as the primary mechanism.

---

## 31. Definition of Done

The coding agent must provide:

1. summary of changed/created files
2. final module tree
3. build/fmt/clippy/test commands used
4. test results
5. Windows application sources currently discovered
6. limitations of current discovery implementation
7. description of the app ID strategy
8. description of resolver matching strategy
9. documentation files updated
10. architecture deviations, if any
11. explicit confirmation that no arbitrary shell execution path exists
12. explicit confirmation that `open_app` cannot launch a caller-provided executable path

If something cannot be completed, report it explicitly.

---

## 32. Coding Agent Instruction

Give the coding agent this instruction:

> Read `README.md`, `agent/AGENTS.md`, `agent/ARCHITECTURE.md`, and the updated `agent/TASK_001.md` completely before editing. This TASK-001 revision supersedes the previous static application allow-list design. Update `README.md`, `agent/AGENTS.md`, and `agent/ARCHITECTURE.md` wherever they still imply that applications must be manually listed in TOML. Implement dynamic Windows application discovery, a trusted internal Application Catalog, deterministic Application Resolver, `resolve_app(query)`, and `open_app(app_id)`. `open_app` must never accept an arbitrary executable path from a caller. Configuration may provide preferences, aliases, overrides, exclusions, or policy, but must not be required to define every installed application. Keep the mandatory Tool Registry -> Validation -> Policy -> Executor -> Tool -> Platform flow. Implement only TASK-001 scope. Do not add Python, AI, semantic resolution, voice, IPC, UI, reminders, or generic shell execution. Add tests and do not declare completion until build, fmt, clippy, and tests pass. Document any architecture deviation explicitly rather than silently changing the design.

---

## 33. Expected Behavioral Example

Future user intent:

```text
"Spotify'ı aç."
```

TASK-001-level core capabilities should support:

```text
query = "spotify"
        |
        v
resolve_app
        |
        v
ApplicationCatalog
        |
        v
app_id = app_7d922
        |
        v
open_app(app_7d922)
        |
        v
Policy
        |
        v
Windows Platform
        |
        v
Spotify
```

If the user says:

```text
"Code'u aç."
```

and multiple candidates are plausible:

```text
Visual Studio Code
CodeBlocks
```

TASK-001 must prefer returning an ambiguity result over opening an unsafe/random candidate.

Future Python Brain logic will handle semantic phrases such as:

```text
"müzik dinlediğim uygulamayı aç"
```

TASK-001 does not implement that semantic reasoning.

---

## 34. Next Task

After this updated TASK-001 is complete and validated:

```text
TASK_002 — Local IPC Contract + Python Brain Skeleton
```

TASK-002 will connect the trusted Rust core to the isolated Python intelligence service.

Do not begin TASK-002 in this task.
