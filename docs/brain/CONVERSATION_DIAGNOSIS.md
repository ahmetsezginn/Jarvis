# Capability refusal diagnosis — 2026-10-06

The user supplied a six-turn Turkish conversation and explicitly requested a diagnostic
recording. The fixed regression transcript is recorded only by manually running the diagnostic
with an explicit output path. Normal CLI conversations remain session-only; no training or
automatic logging was added. No real Core connection, app launch or live system inspection occurs.

## Measured cause

Before the fix, GGUF classified both Chrome opening requests and the system-status request as
conversation with confidence 0.95 even in empty history. With the supplied refusal history,
confidence rose to 1.0. All six turns therefore returned before task decoding and made zero
Core calls. This is an admission error, not a Rust execution failure. History can reinforce it,
but is not necessary to reproduce it.

The reply prompt described this path as having no tools without describing the product's
separate task capabilities. Replies denied app opening and system inspection and invented task
tracking. These false claims then entered bounded session history. Earlier validation covered
English explicit actions but missed this Turkish capability-to-action sequence.

## Change and evidence

request_routing.py now explains polite Turkish action requests, separates capability questions
from concrete current actions, and says previous refusals do not change the current purpose.
The reply prompt describes the implemented application/system capabilities and their task path,
without giving the conversation path execution access. No keyword dispatcher, new OS tool,
permission change or provider dependency was introduced.
This guidance is GGUF-specific. A shared expanded prompt regressed ONNX's folder classification;
its previous compact prompt is preserved. Moving the GGUF guidance to the end also regressed
the English how-to case, so it stays alongside the task definition as in the successful probe.

The after-recording classified all three concrete actions as task with confidence 1.0, both
fresh and with the original refusal history. The actual six-turn mocked run produced two
resolve_app/open_app pairs and one system_status call; its three conversation turns produced
no calls. Capability reply: “Evet, hangi uygulamayı açmak istersiniz?” An initial after-recording
answered the capability list in English; a Turkish example was subsequently added to the prompt.
The final recording now answers that list in Turkish and retains all expected routes/tool calls.

Local evidence: artifacts/diagnostics/conversation_before.json and conversation_after.json.
The after-file includes the final prompt SHA-256. These are exposed regression cases, not an
independent quality benchmark or proof that all future requests will route correctly.

## Reproduction and checks

From the repository root, using the existing interpreter/packages:

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$brainCheckPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $brainCheckPython scripts/evaluation/trace_conversation.py --output artifacts/diagnostics/conversation_after.json
& $brainCheckPython -m pytest services/brain/tests -o addopts='-q -p no:cacheprovider'
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $brainCheckPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py -o addopts='-q -p no:cacheprovider'
& $brainCheckPython -m ruff check services/brain scripts
& $brainCheckPython -m ruff format --check services/brain scripts
git diff --check
```

The recording includes input, reply, validated route/confidence, task prediction and tool names.
It omits trusted IDs and raw Core payloads. Mock results are marked executed_mock; they do not
represent actions on this computer. Ordinary tests: 156 passed, six integration tests skipped.
Final real-provider routing checks: two passed in 66.37 seconds, including the new Turkish
multi-turn sequence. Ruff check/format and git diff --check passed. Changed code is limited to
request_routing.py, the GGUF adapter's prompt selection, the opt-in trace script and the existing
real routing regression test; documentation and agent context record the diagnosis.
