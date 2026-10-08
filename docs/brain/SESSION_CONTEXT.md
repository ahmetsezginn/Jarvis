# Session conversation context (2026-10-05)

Each JarvisBrain owns an ephemeral ConversationMemory. Successful completed responses,
including clarify/unsupported and low-confidence responses, retain user text and the actual
assistant message. Raw Core payloads, IDs and model predictions are not copied into memory. Candidate lists
are represented by a neutral clarification message; their names remain in the separate
120-second SelectionSession, never replayed as expired model evidence.
Both ONNX and GGUF receive immutable IntentContext.history serialized as JSON reference data.
Strict parsing, confidence checks, fresh Rust resolution and Core policy remain mandatory.

Retain at most six complete pairs and 2400 text characters. Evict oldest whole pairs;
an oversized pair clears history. Existing token caps fail explicitly on oversized prompts;
no silent token truncation, summarization, disk storage, training or runtime network calls.
Special Qwen tokens in current text or history are rejected. History is not a permission source.

/reset clears both conversation and pending candidate selection. Cancellation clears old
conversation. SelectionSession keeps its existing 120-second expiry and same-ID verification.
With nonempty history the legacy Fast Router is bypassed so contextual requests reach the model.
The reset API is reset_context(). New Brain instances start empty; separate ask invocations
cannot share context. Use the existing REPL/launcher for multi-turn interaction.

Limits: context delivery does not guarantee model understanding or general conversation.
The closed open_application/system_status/clarify/unsupported contract is unchanged.
Oldest context can be forgotten at the budget boundary. Inference errors are still typed;
there is no hard native inference deadline or persistent user memory.

## Validation

- 131 ordinary tests passed, four opt-in integration tests skipped.
- Ruff check, format check and git diff --check passed.
- Real GGUF and ONNX single-turn + English contextual reference tests passed.
- Real GGUF offline session correction passed through mocked Core: Chrome -> Turkish Firefox
  correction -> fresh resolve_app/open_app ID; cancel/reset produced no further calls.
- Known failing diagnostic: historical 0.6B ONNX returns clarify for the Turkish Firefox
  correction instead of opening it (3 passed / 1 failed in the four-test real integration run).
  The failing opt-in assertion is retained; contextual language quality is not accepted for ONNX.
- ONNX originally repeated its JSON on the English reference probe. Generation now stops only
  when the complete current output independently passes the strict parser. It never strips prose
  or extracts a JSON prefix from invalid output. Mock tests cover invalid fields and trailing data.
- Python socket APIs were blocked in the offline session test. This is not native DLL network
  isolation or OS-firewall proof. Rust is mocked; no real applications were launched.
- Rust code/protocol/policy were not changed. No new dependencies or model artifacts.

Exact validation commands, from repository root:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/brain/src')
.\services\brain\.venv\Scripts\python.exe -m ruff check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m ruff format --check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests -o addopts='-q -p no:cacheprovider'
git diff --check

$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration -ra -o addopts=''
# The ONNX Turkish correction assertion currently fails as documented above.

Remove-Item Env:JARVIS_RUN_MODEL_TESTS
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration/test_real_session_context.py -ra -o addopts=''
# Final GGUF session check: one passed, ONNX skipped.
```

Changed implementation: contract.py, conversation.py, runtime.py, session.py, prompts.py,
qwen_onnx.py, qwen_gguf.py and CLI reset help. Tests cover memory, strict stopping and real
model sessions. Architecture, development process, Brain README and agent working index updated.

Try session memory with the provisioned model:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/brain/src')
.\jarvis.ps1 -Model gguf
```

This environment's editable-package path was stale after moving the repository; explicit
PYTHONPATH selected the current source during validation. No package reinstall was performed.
