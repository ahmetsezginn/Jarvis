# Everyday-language file goals

2026-10-14 follow-up: the cross-domain test's inclusion-only oracle is insufficient. A fake
model which always returns query="*" passes all 16 requests without interpreting them. The
results below remain historical execution/regression evidence, not acceptance of general
assistant behavior. See [ASSISTANT_BEHAVIOR_ANALYSIS.md](ASSISTANT_BEHAVIOR_ANALYSIS.md) for the
counterexample, reproduced dialogue failures and proposed acceptance criteria.

2026-10-14: a fresh GGUF session rejected three ordinary requests to help find a saved CV.
The problem was Brain admission/planning, before a Rust search tool was called. Rust had the
file skill; interpreting the user's problem as a practical goal failed. Earlier assistant
denials could also contaminate the next planning turn.

## Changes

- GGUF classifies a closed communicative purpose before existing task admission. Locating an
  actual misplaced document is distinct from instructions for searching, definitions, recall,
  capability discussion and prohibitions. No imperative or exact filename is required.
  The optional validated purpose survives task admission. A locating goal omits displayed
  candidates from planning and can only produce search_files/clarify; existing results cannot
  implicitly authorize opening during a repeated search or topic change.
- Locating tasks directly use a focused search planner via a validated internal context flag.
  Other fresh actions retain their existing reasoning prompt. Search and open remain independent.
- Search uses a focused structured extraction pass: wanted_item, query, sort,
  extension, kind, confidence. Identifying the item precedes choosing a filename clue. The
  bounded explanation is discarded; the remaining fields pass the existing strict search
  validator. Extra fields/operations, paths and invalid confidence fail closed. When a general
  action plan selects search, its refinement cannot increase the prior planning confidence.
  Admitted locating goals use the search schema directly, without another general action
  selection. Numeric result addresses do not enter search extraction.
- Planning history excludes conversation replies and unsupported claims; chat/recall keeps
  the original history. User references, clarification questions and actual execution outcomes
  remain available. Both views share the six-turn/2400-character budget and reset behavior.
- No phrase-specific CV or presentation router, training, model download, Core bypass or new
  execution tool was added. Historical ONNX prompts/schema are independent.

## Evaluation design

`test_natural_file_goals.py` froze 8 development requests, 8 initially held-out requests and
6 no-action controls before prompt changes. Wording and expected goals were kept fixed during
development. The initially held-out group was subsequently inspected during debugging, so the
final result is a regression result, not a claim of independent unseen-language accuracy.

The corpus includes the user's exact three sentences, yesterday's presentation, a missing
spreadsheet, a signed contract, cargo receipt, thesis report, rent agreement, holiday pictures
and colloquial spelling. Mock Core matches the resulting queries against synthetic filenames
using substring/token and extension/kind filtering. A search call alone does not pass: the
expected file must be returned. Fixtures include mixed formats; the presentation expectation
was strengthened to TXT to catch an invented PPTX restriction.

Initial reproduction: the exact long user request made no Core call; 6/16 cross-domain cases
failed to search at all. Subsequent checks caught inappropriate how-to searches, grammatical
suffixes copied into queries and invented format filters. These failures drove the admission,
memory and structured extraction changes. No evaluation transcripts train the model.

Final automated verification: 289 ordinary Brain tests passed (18 opt-in entries skipped).
Twelve real-model entries passed on the final code: 9 natural/file GGUF entries, the existing
GGUF conversation/task regression, and both ONNX regressions. All 16 file goals matched actual
fixture names; all 6 no-action controls made no machine call; the 3 reported sentences searched
for CV despite a prior denial. Sequential repeats followed by a new presentation topic passed.
Existing relative folder/file scope, seven-row numbered selection, four-format default opening,
explicit browser selection, catalog operations and conversation/recall safety also passed.
Ruff check/format and git diff --check passed. Live Windows results are recorded below.

The normal-user live Windows test passed through real GGUF -> Named Pipe -> Rust policy ->
Windows using only ignored synthetic fixtures. Each of the user's exact three sentences made
only search_files and returned 8 CV files. The lost-presentation question returned
Toplantı-Sunum.txt, demonstrating that a presentation topic did not impose a PPTX extension.
Relative folder -> document search then returned the expected 7 CV files. Result 2 opened
through default open_file with no new search; a separate explicit Chrome request used
open_file_with_app. Personal files were not opened/read. The helper restored the normal Core.
Pytest emitted a cache-write permission warning; all live assertions passed. The helper is
UTF-8 with BOM so its Turkish fixture/root names work under Windows PowerShell 5.1.

## Reproduction

From the repository root, with the existing provisioned local environments:

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython -m pytest services/brain/tests -o addopts='' -q
& $taskPython -m ruff check services/brain
& $taskPython -m ruff format --check services/brain
$env:JARVIS_RUN_NATURAL_FILE_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_natural_file_goals.py -o addopts='' -q
$env:JARVIS_RUN_GGUF_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_natural_file_goals.py services/brain/tests/integration/test_real_file_skills.py services/brain/tests/integration/test_real_numbered_files.py services/brain/tests/integration/test_real_file_reasoning.py -o addopts='' -q -x
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py services/brain/tests/integration/test_real_qwen.py -o addopts='' -q -x
```

Existing GGUF regression files: real_numbered_files, real_file_reasoning, real_file_skills,
real_conversation_routing (`JARVIS_RUN_GGUF_TESTS=1`). Existing ONNX regressions:
real_conversation_routing and real_qwen (`JARVIS_RUN_MODEL_TESTS=1`). All are under
services/brain/tests/integration with the test_ prefix and .py suffix.

The opt-in Windows helper `scripts/shell/test-file-context.ps1 -RestoreCore` uses an isolated
catalog of synthetic PDFs and a presentation-note TXT. It verifies the ordinary user sentences
through Named Pipe/Rust, then existing numbered/default and explicit Chrome opening. It requires
the project Core to be stopped first and restores a normal Core in finally. No personal documents
are read/opened and no post-launch UI verification is performed.

## Limits

This is metadata/name search inside configured roots, not whole-computer or document-content
search. A topic absent from a filename may require another clue. Small local-model language
interpretation can still fail; passing this corpus does not cover every possible sentence.
Recency hints are not exact date filters and sorting/format inference are not guaranteed by
this language evaluation. No training weights changed. Restart Brain to load the Python changes.
Native source was unchanged in this follow-up; earlier Rust suite counts remain historical.
