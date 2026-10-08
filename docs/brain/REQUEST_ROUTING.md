# Conversation/task separation (2026-10-06)

User explicitly requested a separation layer so ordinary questions do not activate Rust tools.
This supersedes the earlier assumption that every message enters the four-intent task decoder.

## Execution paths

```
input -> validation -> read-only request classifier
  conversation -> bounded reply generator -> strict reply validation -> text response
  task + confidence policy -> task decoder -> strict intent validation -> orchestrator -> Rust
```

Conversation returns before task prediction, the legacy Fast Router or the orchestrator.
It cannot dispatch a tool. RequestKind has only conversation/task, with finite numeric confidence.
Malformed/unknown/duplicate fields fail closed. Low-confidence task routing asks for clarification;
low-confidence conversation routing may return text, but still cannot execute anything.
Classifier output is advisory, not permission: actionable tasks still pass confidence and Rust
Registry -> Validation -> Policy -> Executor. An explicit live machine-inspection question is a
task; a greeting, conceptual question, how-to question or recall question is conversation.

Task model output retains exactly open_application/system_status/clarify/unsupported.
The response-only BrainResponse intent respond represents a text reply. It is explicitly rejected
by the task intent parser. Reply output contains only message, at most 256 characters; unknown
keys, tool fields, prose outside JSON, duplicate keys and reserved control tokens fail closed.
The runtime revalidates provider-returned route/reply objects. No new Rust tool or IPC schema.

The provider interface adds classify_request() and respond(). GGUF implements both using the
same provisioned local model and separate constrained JSON grammars/prompts. GGUF reply history
uses actual bounded chat-template turns; request classification and task inference use JSON
reference data. ONNX implements the admission classifier and task prediction, but conversational
reply generation is deliberately unavailable: the attempted implementation fabricated completed
actions in an opt-in probe. It now raises typed ModelInferenceError rather than emitting those
replies. No cloud, dependency, model replacement or inference server was introduced.

Legacy Fast Router remains in read-only predict diagnostics, but is never an execution shortcut
in handle_text(), even when --fast-router is passed. This avoids the demonstrated folder -> app
bypass. New non-session requests need one modality inference and one task/reply inference; this
increases inference latency. Existing explicit candidate selections remain a deterministic task
path with 120-second expiry and fresh matching Rust ID. Reset/cancellation stay non-executing.

Six complete pairs / 2400 characters are still retained only in memory. No auto-persistence or
training. Replies cannot observe live machine state; prior assistant messages are evidence of
prior outcomes only. Classification and reply language quality remain model-dependent: this
separation prevents a conversation branch from dispatching actions, not all possible false
positive classifications. Confidence is an operational score, not calibrated probability.
The CLI still connects its control transport at startup; chat produces no execute_tool requests.

## Local runtime recovery

During final checks the venv console launcher python.exe disappeared; copying the trusted venv
launcher back was denied even in approved elevated execution. No security settings were changed.
The existing base interpreter plus the installed venv packages can run the current source.
jarvis.ps1 now uses the base executable recorded in local pyvenv.cfg when the redirector is absent;
it downloads nothing, retains installed packages, and restores PYTHONPATH at exit. The launcher
header displays the request gate rather than claiming legacy fast execution is enabled.

## Validation

Final results: 156 ordinary tests passed, six opt-in tests skipped; Ruff check/format and
 git diff --check passed. Both parameterized real routing tests passed (51.23 seconds).
GGUF: greetings, conceptual/how-to questions and folder recall produced no Core calls; the
folder name was recalled without claiming it opened. Explicit Chrome and RAM-inspection
requests produced resolve_app/open_app and system_status respectively, through a mock Core.
ONNX: conversational generation was refused with its typed capability error; no conversational
Core calls occurred, and explicit app/status task probes passed. This validates refusal, not
ONNX chat quality. PowerShell AST parsing of jarvis.ps1 had no errors; the fallback base
interpreter successfully ran lint/unit tests and both real-model probes with existing packages.
Real-model tests never launch applications and block Python socket APIs. This does not prove
OS-firewall/native-DLL isolation. Earlier experimental ONNX chat produced fabricated completions
and was not retained. Historical ONNX Turkish correction quality remains a separate limitation.

Commands from repository root used for final validation with the existing interpreter/packages:

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$brainCheckPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $brainCheckPython -m ruff check services/brain scripts
& $brainCheckPython -m ruff format --check services/brain scripts
& $brainCheckPython -m pytest services/brain/tests -o addopts='-q -p no:cacheprovider'
git diff --check
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $brainCheckPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py -o addopts='-q -p no:cacheprovider'
```

Changes: request_routing.py, runtime, provider protocol/fake and both adapters, shared strict
JSON parser and chat prompt helper, CLI header/help, launcher recovery, routing safety tests and
a real-model mocked-Core conversation transcript. Architecture, rules and operational docs updated.

Follow-up: the user's Turkish capability/action transcript exposed admission misrouting and
incorrect global capability denials. See CONVERSATION_DIAGNOSIS.md for measured before/after
recordings, GGUF-specific prompt refinement, and the explicit opt-in mocked diagnostic command.
