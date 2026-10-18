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

## Active model revision (2026-10-16)

Latest user-authorized milestone: Qt Quick/QML via PySide6 desktop and local voice
on the current host. This supersedes the planned TypeScript desktop choice for this delivery.
Qt may render its fixed resources/fonts and spawn only the fixed Python session worker; it may
not execute model commands. UI device requests use JarvisCoreClient and registered Rust speech
tools through the existing policy/executor. Native whisper.cpp CPU speech inference is permitted;
Python retains task reasoning/planning. PCM stays bounded inside Rust, never in the JSON control
channel. Final transcript is the same agent input as typed text, never a separate voice router.
Latest voice follow-up explicitly authorizes opt-in automatic conversation in addition to
push-to-talk: local Silero GGML VAD, silence endpointing and waiting/listening/speaking animations.
Automatic listening defaults off and ends on explicit stop, client lease expiry or fatal device
failure. Pause capture during recognition/reasoning/output and rearm only after actual SAPI
completion. No persisted recordings, startup microphone/wake word, cloud speech or ONNX restoration.
Initial TTS is local Windows SAPI; Kokoro remains a later alternative, not a completed feature.

Voice reliability follow-up: discover installed SAPI/OneCore voices read-only in the Rust COM
thread; no registry copying/writes. Recognition defaults to Auto with explicit en/tr selection.
Speech pronunciation accepts en/tr and an optional bounded device index, never caller token
IDs. Missing voice/device must report an error rather than silently changing the language.
Keep recognition language, pronunciation voice and English agent text behavior separate.
Normal spoken replies must not be interrupted by automatic rearm during pending synthesis:
use full SAPI queue completion, not only its instantaneous active-speaking flag. Test the real
QML/agent/normal-response path, not just a fixed test sentence or fabricated worker event.

Speech-recognition quality follow-up (2026-10-18): user confirmed normal TTS works, but reported
Steam -> unrelated word and Jarvis -> Javi. Compare checksum-pinned Whisper small and
large-v3-turbo locally through the existing native CPU runtime; explicit setup may provision
the pinned GGML artifact, never startup/download-on-demand. Keep GPU memory for the agent.
Measure word/negation errors and latency on identical clean/noisy fixtures; synthetic speech
does not establish this user's microphone accuracy. Expose only bounded input-route/signal
metadata, never PCM. No transcript word-replacement rules, sentence-specific prompts, saved
microphone audio, cloud ASR or automatic actions from diagnostic transcriptions.
The selected CPU default remains small with beam search and bounded native catalog spelling
context. Only native catalog display names plus the assistant name may supply this context;
callers/models cannot send ASR prompt fields. Completed PCM also passes local Silero VAD in
both manual/automatic modes before Whisper, without trimming or rewriting words.

Standalone ASR trial exception (2026-10-18): user selected ready Handy and explicitly allowed
its LOCAL WAV recordings after being told the app always persists them; no cloud/API speech.
This exception applies only to the isolated portable Handy trial described in HANDY_TRIAL.md.
It does not authorize JARVIS production recording persistence, Python microphone ownership,
ONNX restoration, or changing production ASR defaults. Diagnostic synthetic-file calls to the
same release's native transcribe-cpp DLL are permitted; never dispatch results as agent actions.

Latest correction (2026-10-18): user meant integration INTO JARVIS, not a separate Handy app.
Windows production speech now uses pinned transcribe-cpp 0.2.4 (Handy's native engine), Vulkan
on a discovered dedicated GPU and the pinned large-v3-turbo-q5_0 model for this 8GB host.
This supersedes the CPU-only/small default above. Explicit whisper-cpp/small CPU comparison
remains available; no silent provider/device/model fallback. Rust owns bounded PCM, existing
Silero GGML VAD, policy and microphone. Do not invoke Handy, clipboard automation or Python ASR.
Keep native GPU model/session lifetimes within one recognition call so weights are released
before Brain reasoning; cache only a checksum-verified read handle denying writes/deletes.
No production recordings/cloud/ONNX. The separate trial's local-WAV permission does not extend
to production. Explicit setup provisions checksum-pinned native DLLs without ONNX; no runtime
downloads. See NATIVE_SPEECH_PROVIDER.md for integration evidence and unresolved quality failures.

Latest user preference: the JARVIS product interaction is English. Preserve Unicode file/folder
names and user-configured roots. Communicate with this user in Turkish. Keep Turkish evaluation
failures as historical evidence and evaluate English behavior independently; do not claim the
language switch proves general assistant quality. No cloud/API use or model training is implied.

The redesign includes an explicitly provisioned, checksum-pinned Qwen3.5-9B Q4_K_M local GGUF
comparison through AgentModel. Use the existing in-process runtime, no startup downloads/server.
`docs/brain/AGENT_LOOP.md` owns artifact identity and current acceptance evidence. Historical
IntentModel enum/TurnPlan and Fast Router rules below apply to archived diagnostics, not the new
production loop. Do not add sentence/document-specific production branches to satisfy tests.

User-authorized agent-loop redesign (latest): replace production staged speech-act/TurnPlan
classification with one contextual next-step provider and a bounded tool-result feedback loop.
Expose only locally registered semantic capability schemas, never arbitrary Core tool names.
Capabilities own typed validation, private catalog binding and effect metadata. Side-effect
proposals require a separate current-request permission check; Rust remains final policy authority.
Keep IDs/paths out of model observations, bounded session memory and 120s bindings. Provider errors,
step limits and repeated calls must stop without replaying effects. Skills may later register
capabilities through this contract; no downloading, dynamic code loading or new machine permissions
is authorized in this phase. This supersedes the historical requirement to run conversation/task,
intent and TurnPlan classifiers in sequence. Preserve legacy diagnostics separately, not as a
production fallback when the new loop fails.

User explicitly disabled ONNX. Production factory and launcher accept GGUF only, default to GGUF,
and reject an explicit ONNX selection without loading it or silently falling back. ONNX Runtime
GenAI is not a required package dependency. Historical adapter/tests and old notes are archival;
their prior opt-in real inference is not required for current production changes. Preserve the
provider interface and Rust execution boundary. The user's supplied failed session ran GGUF:
do not attribute its semantic failures to an ONNX process that was not involved.

Progressive recommendation follow-up: for file/folder/application identification, the model
chooses one best candidate from current verified metadata with suggest_result. Do not dump every
candidate or default to the first row. Store the proposed identity privately within the existing
120s binding, confirm identity separately from opening, and reject only that proposed candidate
before moving on. Retain at most 100 rejected trusted IDs within their original expiry; never
expose IDs/paths to the model or invent ownership/content evidence. Full-list presentation is
for explicit requests, with current-request assessment; discovery alone does not authorize it.
A tentative, nonexecuting suggestion question may use a separate advisory confidence threshold;
registry validation forbids such overrides for acting or Core-dependent capabilities. This does
not lower machine-action confidence or permission checks. Capabilities may register bounded
response checks; a rejected prose draft can be repaired through
the same AgentModel with a registry-derived presentation schema. This is not a legacy classifier
fallback. Only explicitly nonexecuting in-memory transitions may opt into retry; Core-backed and
side-effecting calls retain no-replay behavior. Keep the five-step limit and Rust execution path.

Discovery follow-up: keep user-supplied mandatory filename constraints distinct from inferred
topic/type queries via name_is_constraint. A guessed-name miss may return one bounded metadata
alternative page only within the same verified folder and other unchanged filters. Explicit
name constraints must not be dropped. Label alternatives separately from actual name matches;
they never prove content/ownership or authorize opening. Verified root-name metadata may help
the model correct a folder label; no global fallback or hand-coded document/language mapping.
Inline name enumerations obey the same single-suggestion contract as numbered lists.

Metadata discussion revision: text replies may see the same bounded current name/kind/number
view as planning and suggest likely candidates without reading contents or claiming ownership.
Conversation preserves the active goal/page until the existing expiry; never extend its lifetime
or infer action permission from reply text. Cancel/reset/expiry still clear bindings. This revises
the historical "chat suspends file selection" behavior below. Keep confidence/validation/Core
policy and current action permission separate. Current assistant acceptance is FAILED; do not
hide unresolved opt-in regression failures or add per-document/per-sentence production patches.

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

## File/folder skills follow-up (2026-10-12)

The user authorized the file-skills roadmap. TASK_004.md defines the first delivery and explicitly
extends the historical four-intent enum with search_files, list_folder, open_file, open_directory,
file_catalog_status and refresh_file_catalog. Human names and validated search filters are model
data; roots, filesystem paths and catalog IDs are never model-produced authority. All file tools
use JarvisCoreClient and the unchanged Rust validation/policy/executor/audit pipeline.
One displayed page is private session state (20 entries, 120s); never send IDs or locations to
model prompts or persist them. Core revalidates targets before opening. Metadata discovery does
not authorize reading contents, moving/deleting files or executing code. No post-launch verification
is added. Scope and partial scans must be visible; never claim a catalog covers the whole computer.

## File context and local browser follow-up (2026-10-12)

User authorized fixing folder references, natural result selection and application-qualified file
opening. Brain may retain one active catalog-backed directory for 120s, apply its ID only to explicit
relative searches, and retain a concrete local-browser clarification across an affirmative reply.
Ambiguous names must ask for selection; unrelated turns/reset/cancel/expiry invalidate state.
open_file_with_app accepts only Core-returned entry_id and app_id; no new model ID/path authority.
Initial adapters support local PDF in Google Chrome/Microsoft Edge, with native catalog shortcut
resolution and fixed executable identity checks. No cloud upload, arbitrary app flags or shell.

## Semantic file planning follow-up (2026-10-12)

User requested model reasoning over capabilities and references instead of sentence-specific
selection rules. Model context may expose only bounded displayed names/kinds (20 entries, 1200
name characters), never catalog IDs or locations. Treat filenames as untrusted data. File planning
uses recent user references and verified metadata; free-form assistant capability claims are excluded
from this planning view. Full conversation memory remains available for conversation/recall.
open_file optionally accepts a human application name; empty/omitted means default Windows
association. Browser/PDF restrictions apply only to explicit selected-browser opening, not ordinary
document opening. Python validates semantic choices and binds unique displayed names to private Core
IDs; ambiguity asks, Core policy remains final. No training/artifact modification was needed.

## Displayed-result target contract (2026-10-14)

User requested a systemic correction of numbered selections becoming new searches. select_file is
an additional semantic intent, not a Native Core tool: exact number (1..20), action (open/list/parent),
application (empty for Windows default or a human name). Bind only against the unexpired current
displayed page; never search/resolve a filename to implement this intent. Candidate metadata may
include original display numbers; omitted names must not renumber surviving candidates. Numeric
list notation constrains identity only, never authorizes an action; admission/confidence still apply.
A literal list-address request must not fall through into a filesystem/application search or a
different row when model inference is wrong. Missing/expired/out-of-range pages ask for clarification.
Defaults and explicit named applications remain separate from target selection. Core IDs/paths
remain private and Rust validation/policy remain final. No post-launch verification is added.

## Natural file goals (2026-10-14)

GGUF admission may classify a closed communicative purpose (locate_file, perform_action, how_to,
capability, recall, prohibition, discussion), strictly parsed into the existing task/conversation
decision. This read-only classification never chooses a tool or establishes execution authority.
Retain the validated locate_file purpose through planning: an existing result page must not turn
another locating request into opening. Only search_files/clarify may follow that purpose;
no file/application opening or implicit folder listing.
Keep the historical ONNX admission contract independent. Interpret indirect lost-file assistance
as a supported goal without requiring command syntax or exact filenames. Do not use per-document
or per-sentence routing patches. A description supplies metadata clues, not document contents.
Planning history excludes conversation replies and unsupported claims as capability evidence;
conversation/recall retains its original bounded history. Preserve genuine clarifications and
execution outcomes. Search-language evaluations must check actual fixture matches, plus how-to,
negation and hypothetical controls, not merely that a search tool was called.

## Stateful assistant follow-up (2026-10-15)

User authorized the dialogue/goal redesign after ASSISTANT_BEHAVIOR_ANALYSIS.md. GGUF may use a
closed TurnPlan separating speech acts, targets and constraints. Validate exact keys and fields
before dispatch. File goals retain bounded human clues and private Core-provided scope/rejected
IDs for 120s; no conversation persistence/training. Discovery may resolve a human folder, list
children or run one same-scope type recovery. Discovery never implies opening. Current opening
intent and unique/page identity are separate requirements. Chat/explanation never replay tasks.
Native search may accept recursive, a closed category and <=100 private rejected IDs; direct
search requires a catalog-backed folder. Models never generate IDs/paths/executable targets.
Legacy ONNX and intent validation remain independent. No contents read, OS bypass, arbitrary
commands, cloud upload or post-launch verification. Acceptance must reject blind wildcard
controls and cover rejection, missing names, scope corrections, negatives, chat, errors and expiry.
Unsupported operations must have a non-executing dialogue result; never substitute finding/opening
for content reading, mutation or uploading. Generic application-category nouns are incomplete
parameters, not concrete installed-app identities. Keep dialogue-provider capability behind the
optional DialogueModel interface and preserve lower admission confidence through planning.
Communicative-purpose admission excludes old commands and displayed names. A bounded target_reference is
an untrusted quote from the current message, never an ID or permission. Active-goal answer,
rejection and scope-refinement acts may continue discovery; generic capability questions cannot
borrow a displayed row as a target. Store path-free verified outcome summaries separately from
user-visible listings; rendered listings must not become model feedback.

The user-authorized analysis also permits an isolated Q8_0 reference comparison for the same
Qwen3-4B-Instruct-2507 checkpoint. scripts/evaluation/compare_quantization.py explicitly provisions
the pinned ggml-org artifact (SHA256 ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1)
in a temporary cache and runs synthetic, non-executing probes with the existing runtime. No Core
connection, inference server, new dependency, training, or production default/pin change is implied.
