# Displayed-result selection is not a filename search

2026-10-14 user report: seven CV files were displayed, then “2. olanı açar mısın” caused a global
search for “2”, replacing the page with 181 image results. The earlier semantic contract supplied
human queries for file opening but did not represent a displayed result address explicitly.
Natural text could therefore cross from result selection into search.

## Contract change

The additional semantic intent select_file has exact arguments:

```json
{"number":2,"action":"open","application":""}
```

number is 1..20 on the current displayed page. action is open, list or parent. Empty application
uses normal Windows association; an explicit human application name selects a supported adapter.
No query, path, executable, flags or catalog IDs can enter this contract. It is not a Core tool.

The model receives original UI numbers alongside bounded names/kinds, never Core IDs/locations.
Omitting long names for the context budget does not compress the remaining numbers. The selection
executor binds the chosen number to the private, unexpired page and consumes state before IPC.
It only dispatches the existing controlled opening/listing tools. There is no search fallback.
Target, operation and application choice remain independent. A named application must not silently
be replaced with default opening; default opening must not inherit a previous browser preference.

Numeric list notation is also interpreted as a reference constraint, not an executable action.
Admission and confidence checks still decide whether a task is authorized. For such a reference,
a wrong model plan (including search_files(query="2")), wrong row, missing/expired page or invalid
number yields clarification without any machine query. Numeric quantities and actual filenames
remain new-search input. This general address/type boundary is separate from sentence interpretation;
no matching rule for the full reported sentence was added.

## Verification

258 ordinary Brain tests passed, 14 opt-in entries skipped. New tests cover all seven row positions,
faulty model search and redirection, empty/reset/expired/out-of-range/negative references, confidence,
Core rejection without retry, current-page changes, candidate-budget omissions, exact schema errors,
containing-folder opening and separate default/explicit application choices. Ruff check/format passed.

Three targeted real GGUF integration entries passed. The numbered-selection entry runs six variants
against seven CV results, including the exact user search and selection, written ordinals, explicit
Edge and containing-folder requests. It asserts the model's select_file plan and exact second Core
ID, and asserts no search occurs after selection. Existing semantic file cases cover four document/
media types with default opening and explicit semantic Edge selection. Earlier file/catalog tests
also passed in the first run; the explicit semantic Edge regression exposed there was fixed and
retested with the final file-planning prompt.
Three additional real-model regression entries passed: existing GGUF conversation/task safety,
ONNX conversation/task safety and ONNX command/context smoke. Thus the final targeted/regression
runs covered six real-model entries in total. No ONNX file-language quality claim is made.

The live Windows test passed through real GGUF -> Named Pipe -> Rust registry/validation/policy ->
Windows. It displayed seven synthetic blank PDFs and the exact phrase “2. olanı açar mısın” sent
only open_file for the TR PDF; a separate explicit Chrome request used open_file_with_app. Only
generated files under ignored target/file-context-live were opened. No personal CV content was
read and no post-launch UI verification was added. Pytest's cache-write warning did not affect
assertions. Fixture Core was stopped and normal Core restored. Native Rust source was unchanged;
previous Rust suite counts are historical evidence, not a newly repeated suite.
Normal Core restoration was independently confirmed with a normal-user Named Pipe ping (ok).

Commands from the repository root:

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython -m pytest services/brain/tests -o addopts='' -q
& $taskPython -m ruff check services/brain/src services/brain/tests
& $taskPython -m ruff format --check services/brain/src services/brain/tests
$env:JARVIS_RUN_GGUF_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_numbered_files.py services/brain/tests/integration/test_real_file_reasoning.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_GGUF_TESTS
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py services/brain/tests/integration/test_real_qwen.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_GGUF_TESTS
Remove-Item Env:JARVIS_RUN_MODEL_TESTS
# Opt-in GUI test, with only the path-verified project Core stopped beforehand:
./scripts/shell/test-file-context.ps1 -RestoreCore
& $taskPython -m jarvis_brain.cli ping
git diff --check
```

## Limits

The page binding expires after 120s and is consumed before execution. A new page establishes new
local 1..20 numbers. Missing/ambiguous references require clarification. Natural-language quality
outside the tested cases is not guaranteed; the structural guarantee is that select_file cannot
turn into a search and recognized numeric list addresses cannot fall through on wrong model output.
Explicit application opening still needs a supported Native Core adapter (currently local PDF in
Chrome/Edge); this does not add arbitrary application control or upload. No model training/weights
changed. Restart the Brain session to load the new code. No commit or push was performed.
