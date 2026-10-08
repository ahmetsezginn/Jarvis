# Interpretation diagnostic (2026-10-06)

Scope: improve request interpretation in the existing GGUF provider before adding tools.
No new model, inference server, OS capability, dependency, persistent memory or intent added.
The strict four-intent output contract and all Rust validation/policy remain unchanged.

## Changes

The GGUF prompt now checks current meaning, bounded conversation context, supported capabilities,
application-versus-folder distinction, negation and corrections before choosing an intent.
Complete JSON examples reinforce those distinctions. This is prompt-level decision guidance,
not enabling a thinking model, retraining, calibrated confidence or a general reasoning upgrade.
Opening folders is still outside Brain's contract despite Core's historical open_folder tool.
Greetings and recall questions must not masquerade as system-status or app-opening requests.
Application notifications use the canonical name in the successful Rust result, falling back
to the validated human query only when the result omits a usable name.

The expanded prompt initially regressed the small ONNX provider's basic launch probe. It is
therefore GGUF-specific (REASONING_PROMPT); ONNX retains the historical compact SYSTEM_PROMPT.
The provider interface, factory, strict parser, output budgets and context limits are unchanged.

## Evidence and limits

A no-action baseline reproduced both greeting -> system_status errors and Turkish folder ->
open_application. A twelve-case exposed regression set was then used during prompt development.
The final GGUF run classified all twelve correctly, including the Cromu spelling case.
Six additional diagnostic cases were added after prompt changes, with no subsequent prompt
changes based on them. Five passed. Overall: 17/18, not a release-quality accuracy estimate.
The remaining case asks which program was mentioned earlier; the model unnecessarily clarifies.
These are now all public/exposed cases, not a sealed holdout or representative population.

IMPORTANT: scoring recall as unsupported only measures safe no-action classification. It does
not mean the assistant answered the recall question. The four-intent contract still cannot
express an ordinary reply. Greetings also return unsupported, not natural conversation.
No claim is made that conversation recall/reasoning is solved. A proposed non-action respond
contract awaits the user's choice and is not implemented by this change.

133 ordinary tests passed (four opt-in tests skipped); lint, formatting and diff checks passed.
Real GGUF intent/reference smoke and mocked-Core offline correction passed. After restoring
its compact prompt, real ONNX intent/reference smoke passed. The earlier ONNX Turkish correction
failure remains a known limitation (see SESSION_CONTEXT.md). No real app launches were performed.
Offline mocked-Core tests block Python socket APIs, not native DLL networking or the OS firewall.
The diagnostic runner never constructs a Core client or executes any tool.

Generated reports (ignored): reports/benchmarks/reasoning-before.json,
reasoning-after-final.json, reasoning-with-diagnostics.json. The final report includes a
prompt SHA256 and the exact model-provider class. Cases and runner are versionable source files.

Exact checks from repository root:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'services/brain/src')
.\services\brain\.venv\Scripts\python.exe -m ruff check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m ruff format --check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests -o addopts='-q -p no:cacheprovider'
git diff --check
$env:JARVIS_MODEL_BACKEND = 'gguf'
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_reasoning --output reports/benchmarks/reasoning-with-diagnostics.json
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration -o addopts='-q -p no:cacheprovider'
# Initial shared-prompt trial: two passed, two ONNX failures. Not accepted for ONNX.
# Restored ONNX compact prompt, then rechecked:
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration/test_real_qwen.py -o addopts='-q -p no:cacheprovider'
```

Implementation: prompts.py, qwen_gguf.py, orchestrator.py and its notification tests.
Added scripts/evaluation/reasoning_cases.json and evaluate_reasoning.py; updated documentation.
