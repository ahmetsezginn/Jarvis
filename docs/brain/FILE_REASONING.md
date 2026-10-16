# Semantic file selection and opening

User report: after displaying EN/TR CV files, “tr olan benimkisi onu açar mısın” produced a false
claim that Turkish files could not open and that all files required Chrome/Edge. Reproduced this
with real GGUF, mocked Core and a prior false assistant claim: response=conversation, executed=false,
“TR dosyası açılamaz; sadece PDF'ler açılabiliyor.” No model training or artifact changes were made.

## Changes

- IntentContext exposes bounded displayed names/kinds, without IDs/locations: <=20 candidates,
  <=1200 total name characters, <=256 per name. Reserved template tokens fail closed.
- For active file planning, keep at most two recent user references/700 characters and exclude
  free-form assistant replies. Conversation memory itself is unchanged and remains available for
  chat/recall. Prior capability hallucinations cannot become file-planning rules.
- Natural unmatched selections reach request admission and intent prediction with current metadata.
  The model interprets language/version references and proposes a human filename. Python validates
  it, requires a unique displayed match and uses the stored Core ID. No new sentence-specific regex
  was added for the reported phrase. Existing explicit numeric/name selections remain available.
- Model open_file optionally adds application (human name). Empty/omitted means Windows default
  association. Explicit supported browser requests use resolve_app -> open_file_with_app. Paths,
  IDs, executables, shell syntax and unknown arguments still fail closed. Ordinary document/media
  opening is not restricted to browser PDFs; browser adapters remain PDF-only.
- Prompt capabilities distinguish normal opening from the explicit browser alternative. TR/EN
  describe filename/language, not prohibited formats. Explicit relative searches omit previous
  candidates so a previously found folder does not change the next file search's target kind.
- Local ambiguity responses report executed=false and never select the first match.

## Validation

218 ordinary Brain tests passed; 13 opt-in entries skipped. Ruff check/format and diff checks passed.
Four real GGUF integration entries passed: semantic/default selection across PDF/TXT/DOCX/JPG with
prior false assistant claims, explicit semantic Edge selection, prior file-skills cases/negation,
and the full Downloads -> cvfolder -> files -> Chrome clarification flow. Tests use mocked Core
and check exact tools/IDs, including the absence of browser resolution for normal opening.
Existing GGUF conversation/task safety and ONNX smoke passed. The ONNX conversation test initially
exposed a false task launch under expanded prompts (mocked Core only); restoring its historical
compact command/admission prompts fixed the regression, and its targeted rerun passed. New file
reasoning guidance is GGUF-only; ONNX file-language quality is not claimed.

The normal-user live GGUF -> Named Pipe -> Rust validation/policy -> Windows test passed using only
synthetic blank PDFs under ignored target/file-context-live. The reported natural phrase selected
the TR PDF and invoked only open_file. A separate explicitly qualified request invoked
resolve_app/open_file_with_app for Chrome. No personal CV contents were read and no post-launch UI
verification was added. Pytest emitted a cache-write warning; assertions passed. The fixture Core
was stopped and normal Core restored. Native Rust source was unchanged in this follow-up; the
preceding 77-entry Rust result remains historical evidence, not a newly repeated run.

Commands (repository root; existing interpreter/packages):

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython -m pytest services/brain/tests -o addopts='' -q
& $taskPython -m ruff check services/brain/src services/brain/tests
& $taskPython -m ruff format --check services/brain/src services/brain/tests
$env:JARVIS_RUN_GGUF_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_file_reasoning.py services/brain/tests/integration/test_real_file_skills.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_GGUF_TESTS
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py services/brain/tests/integration/test_real_qwen.py -o addopts='' -q
# After restoring compact ONNX prompts, the previously failing entry was rerun:
& $taskPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py -k QwenOnnx -o addopts='' -q
Remove-Item Env:JARVIS_RUN_GGUF_TESTS
Remove-Item Env:JARVIS_RUN_MODEL_TESTS
# Opt-in actual opening of synthetic PDFs; stop only the path-verified project Core beforehand:
./scripts/shell/test-file-context.ps1 -RestoreCore
git diff --check
```

Restart the Brain session (`exit`, then `jarvis`) to load new source. No commit/push was made.

## Limits

This is a tested prompt/context/orchestration correction, not a general language-quality guarantee.
Metadata candidates expire after 120s; missing or ambiguous references still need clarification.
The model only sees names/kinds, not document contents or locations; long pages may expose fewer
names to fit the context budget. Arbitrary applications, Google Docs upload, content reading and
general unconstrained confirmation/planning remain unsupported. No model weights were changed.
