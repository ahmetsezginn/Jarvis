# AGENTS.md

This file defines mandatory engineering rules for any coding agent or developer working on JARVIS.

Canonical location: `agent/AGENTS.md`. The root `AGENTS.md` is only an entry point.
Architecture and task documents live alongside this file; code paths and commands are relative
to the repository root. Update the engineering rules here, not in the root entry point.

Read this file and `ARCHITECTURE.md` before making architectural changes.

## 1. Primary Rule

JARVIS is a secure, modular, polyglot system.

Do not collapse the architecture into a single Python application.

The default responsibility split is:

```text
Rust       -> execution, OS access, security boundary
Python     -> AI, reasoning, planning, model integrations
TypeScript -> desktop UI when needed
```

## 2. Security Boundary

The Rust native core is the trusted execution boundary.

The AI service is not trusted to directly control the operating system.

Never implement architecture equivalent to:

```python
os.system(model_output)
```

or:

```python
subprocess.run(model_generated_command, shell=True)
```

Model-generated arbitrary shell commands are forbidden unless a future explicitly approved sandboxed subsystem is designed for that purpose.

## 3. Tool Rule

Every operating-system action initiated by AI must be represented as an explicit registered tool.

Examples:

```text
open_app
open_folder
find_file
system_status
set_volume
create_notification
lock_computer
```

A tool must have:

- a unique name
- a typed input schema
- a typed result
- a risk classification
- policy metadata
- validation
- error handling
- audit behavior when relevant

Do not add hidden or unregistered execution paths.

### Application Discovery Rule

Installed applications must be discovered from trusted platform-managed application metadata and
stored in an internal catalog. Do not require a static configuration entry for every application.

Application requests use two explicit tools:

```text
resolve_app(query) -> catalog-backed app_id
open_app(app_id)   -> policy -> platform launcher
```

`open_app` must never accept a caller-provided executable path. Raw launch targets remain inside
the Native Core. Configuration may add preferences, aliases, exclusions, administrative
overrides, or policy, but it is not the primary source of installed-application truth.

## 4. Policy Rule

All actionable tool requests must pass through the policy layer before execution.

Expected flow:

```text
ToolRequest
    |
    v
Tool Registry
    |
    v
Validation
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
```

Do not call OS adapters directly from the AI service.

Do not bypass policy checks from UI code.

## 5. AI Service Rules

AI-related code belongs under the brain service.

The AI layer may:

- interpret natural language
- maintain conversation context
- perform reasoning
- select tools
- create plans
- summarize information
- query permitted knowledge sources

The AI layer must not:

- directly perform privileged OS operations
- own company authorization logic
- decide final permissions
- assume model output is safe
- require one specific model provider throughout the codebase

All providers must be implemented behind a provider interface.

### Local Intelligence Rule

M003's historical runtime is Qwen3-0.6B INT4 CPU through `QwenOnnxIntentModel`.
The user-authorized local-model comparison (2026-09-15) also permits Qwen3-4B-Instruct-2507
Q4_K_M through `QwenGgufIntentModel`, using in-process llama-cpp-python (CUDA or CPU).
Select providers only through the IntentModel interface/factory. No inference server or network
listener is needed. Importing Brain modules must not load either model; runtime must not download
models or require PyTorch or Transformers. Provisioning verifies pinned artifact checksums.
Conversion-only dependencies belong in the isolated model-build environment.

User-authorized temporary diagnostic exception: CLI ask/repl/predict disable the Fast Router
by default; --fast-router opts back in. Library/evaluation defaults retain historical routing.
This bypass changes routing only, never strict validation or Core policy.
Bounded application clarification is separate from the Fast Router: a Brain session may retain
one Rust-provided candidate list for 120 seconds and interpret explicit numbered/name selections.
Re-resolve the selected name and require the same trusted ID before opening. Never infer an ID
from model text, persist this state across sessions, or guess ambiguous relative references.
When enabled, the deterministic Fast Router runs before model fallback. Model output is untrusted and is limited
to the closed semantic intent enum:

```text
open_application
system_status
clarify
unsupported
```

Every model result must pass strict JSON parsing, exact schema validation, semantic validation,
and the confidence policy. Unknown keys, prose, code fences, duplicate keys, non-finite numbers,
paths, executable names, shell directives, arbitrary Core tool names, and caller-supplied app IDs
must fail closed without a Core request.

For `open_application`, the model may provide only a human query. Brain must send that query to
Rust `resolve_app` and may send only the returned trusted `app_id` to Rust `open_app`. The model
must never choose the ID. `system_status` must use the Rust tool and must not be reimplemented with
Python system APIs.

## 6. Native Core Rules

Native core code should favor:

- explicit types
- deterministic behavior
- bounded execution
- minimal privilege
- clear failure modes
- testability

OS-specific code must stay behind platform adapters.

Preferred structure:

```text
core/native/src/
├── executor/
├── tools/
├── policy/
├── permissions/
├── platform/
├── ipc/
├── audit/
└── events/
```

Do not spread Windows-specific APIs throughout generic modules.

## 7. Platform Rule

Cross-platform logic belongs in shared modules.

Platform-specific implementations belong under platform modules such as:

```text
platform/windows/
platform/macos/
platform/linux/
```

Initial implementation may be Windows-first, but abstractions should not make macOS/Linux impossible.

## 8. IPC Rule

Rust and Python must communicate using a defined protocol.

Do not create ad-hoc coupling where Python imports native-core internals or Rust depends on Python implementation details.

The TASK-002 control protocol is:

- local Windows Named Pipe only
- 4-byte big-endian length prefix plus UTF-8 JSON
- protocol version in every request and response
- hard frame-size limit
- handshake before normal requests

The Python Brain must use `JarvisCoreClient` for every machine action. It must not duplicate Rust
tools or directly launch applications, open folders, inspect system state, or execute shell
commands. Python OS API use is limited to connecting to the local control transport.

Every IPC `execute_tool` request must become the existing Rust `ToolRequest` with
`RequestSource::Brain` and pass through Tool Registry -> Validation -> Policy -> Executor -> Tool
-> Platform. IPC code must never call a platform adapter directly.

The control channel is not an audio/data streaming channel. Future raw audio transport must be
separate.

IPC messages must have versionable schemas.

## 9. Performance Rule

Do not route every command through a large AI model.

When safe and deterministic, support a fast path for known commands.

Examples:

```text
mute audio
open known application
lock computer
system status
start predefined workspace
```

Complex natural-language requests belong to the AI path.

Do not prematurely optimize, but avoid architecture that makes low-latency execution impossible.

## 10. Voice Rule

Voice is an input/output layer, not the business logic layer.

Voice modules may handle:

- microphone devices
- audio buffers
- push-to-talk
- wake-word detection
- voice activity detection
- speech-to-text integration
- text-to-speech integration

Voice code must not directly execute OS actions.

Voice input must ultimately produce the same structured requests used by other clients.

## 11. UI Rule

UI code must not become the authority for permissions or execution.

The UI may:

- display results
- request actions
- show confirmation prompts
- display audit-friendly explanations

The UI must not:

- bypass core policy
- contain privileged OS execution logic that belongs in the native core

## 12. Confirmation Rule

Potentially destructive or sensitive actions should support confirmation requirements.

Examples include:

- deleting files
- overwriting files
- sending messages externally
- installing/uninstalling software
- modifying system configuration
- credential-related operations

Confirmation requirements must be represented by policy, not scattered UI conditionals.

## 13. Audit Rule

Security-relevant operations should be auditable.

Audit events should be structured rather than plain free-form strings wherever practical.

Useful fields may include:

- request ID
- timestamp
- user/session
- tool name
- policy decision
- confirmation state
- execution result
- error category
- duration

Never place secrets or unnecessary sensitive data in logs.

## 14. Secrets Rule

Do not hardcode:

- API keys
- tokens
- passwords
- private keys
- company credentials

Use environment variables, OS credential stores, or an approved secret-management mechanism.

`.env` files containing real secrets must not be committed.

## 15. Dependency Rule

Before introducing a large dependency:

1. verify that it solves a real requirement,
2. prefer maintained libraries,
3. avoid overlapping libraries for the same responsibility,
4. keep security-critical dependencies minimal.

## 16. Testing Rule

New core behavior requires tests.

Minimum expectations:

- unit tests for validation and policy behavior
- unit tests for tool execution logic where possible
- mocked platform tests
- IPC contract tests
- end-to-end tests for critical flows when infrastructure exists
- opt-in real ONNX inference and offline tests for local-intelligence changes

Never make tests depend on a real AI provider unless they are explicitly integration tests.

## 17. Error Handling Rule

Do not silently ignore errors.

Errors should be converted into structured categories suitable for both users and logs.

Examples:

```text
permission_denied
application_not_found
invalid_arguments
policy_denied
confirmation_required
platform_not_supported
ipc_unavailable
provider_timeout
```

## 18. Scope Rule

When assigned a task:

- implement only the requested task and necessary supporting infrastructure,
- do not silently begin future milestones,
- do not rewrite unrelated architecture,
- keep interfaces extensible but implementation scope small.

## 19. Documentation Rule

If a change modifies a core architectural assumption, update `ARCHITECTURE.md` in the same change.

If a change alters developer setup or user-visible startup commands, update `README.md`.

## 20. Definition of Done

A task is not complete merely because code compiles.

Before declaring completion:

- format code,
- run relevant tests,
- run static checks where configured,
- verify no architecture rule was bypassed,
- summarize changed files,
- mention known limitations,
- provide exact commands used to validate the work.

## Final Instruction to Coding Agents

When uncertain, preserve this invariant:

> The AI may request an action. The native core validates, authorizes, and executes it.

## Session context follow-up (2026-10-05)

User authorized session-only conversation memory. IntentContext.history may contain at most six
complete user/assistant pairs and 2400 characters, never raw Core payloads or trusted IDs.
History is untrusted advisory data; all predictions still pass existing validation and policy.
/reset clears history and pending choices. Do not persist conversations or use them for training.

## Conversation/task admission follow-up (2026-10-06)

The user's explicit separation request authorizes a read-only RequestRoute schema (kind:
conversation/task, confidence) and a separate bounded reply schema (message only). Both use
strict JSON parsing and exact validation. Task predictions retain the four-intent contract.
BrainResponse.respond is output only, never an executable task intent; task parsing rejects it.
Conversation must return before any task prediction, Fast Router or orchestrator call. Only
validated, sufficiently confident task decisions may reach the unchanged Rust policy boundary.
Never interpret reply text as tools, commands, IDs or permission. Keep session-only limits.
The broad historical Fast Router is diagnostic-only until safe task admission is implemented.

## Catalog refresh follow-up (2026-10-08)

User authorized explicit catalog refresh and newly-installed follow-ups after a missing app.
refresh_app_catalog is a registered Rust read-only tool with empty input; all policy/audit rules
apply. Brain may hold one previously validated human query for 120 seconds after an actual
application_not_found, never IDs or raw payloads. An affirmative recognized next-turn installation
statement refreshes once and retries that original opening request via fresh Rust resolution.
Any other turn, /reset, cancellation or expiry clears this state. Standalone explicit refresh
commands refresh only. No model intent enum expansion or post-launch verification is authorized.
