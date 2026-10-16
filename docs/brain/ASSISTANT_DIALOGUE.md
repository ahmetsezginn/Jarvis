# Stateful file assistance — 2026-10-15

**Superseded quality assessment:** the 2026-10-16 user counterexample and new real-model
regressions show this planner is not accepted. ONNX is now disabled. See
[ASSISTANT_REASSESSMENT.md](ASSISTANT_REASSESSMENT.md) for current changes, passes and failures.

This follows [ASSISTANT_BEHAVIOR_ANALYSIS.md](ASSISTANT_BEHAVIOR_ANALYSIS.md). The user authorized
implementation and evaluation before trying the assistant again. Previous test counts in the
other reports are historical, not evidence that arbitrary dialogue already worked.

## What changed

GGUF `handle_text` now maintains a file goal instead of independently classifying every sentence
as a command. Closed `TurnPlan` moves separate talking, explaining, finding, choosing a displayed
item, cancelling and asking for missing information. Current-message target, operation, scope and
application extraction are separate from the retained task. Short intermediate object/action
descriptions are strictly checked and discarded; they cannot become tools.
Communicative-purpose admission gets the current message and an actual pending slot question, without old
commands or displayed filenames. Reference binding and conversation replies keep their respective
bounded context. A concrete target quote must come from the current message; a generic capability
question cannot borrow a displayed item as its target. The existing validated result selector
handles language/version, numbered and containing-folder references within the new goal flow.
An additional target-only pass copies the exact matching displayed filename; Python binds only
a unique existing page record, preserving its original number. It sees no previous commands or
application planning. This separates target identity from a decoder's guessed row index. Invented
or duplicate names ask for a number. Literal numeric addresses remain exact private-page bindings.
An unsupported paraphrase in the optional admission quote is discarded, so it supplies no target
evidence and cannot activate capability-question selection; it does not block a valid search goal.
New filename/topic clues must also occur in the normalized current utterance (base-form substrings
permit Turkish suffixes). Missing clues inherit through task state, not model replay. Unsupported
translations/synonyms may therefore need another clue. Scope corrections preserve the current
operation; a generic locating classification cannot overwrite `keep` with a new search.

`AssistantSession` owns one goal with human location/type/name clues, a pending clarification and
at most 100 rejected Core identities. Private bindings expire after 120 seconds. The last verified
outcome is bounded input for explanation, retained in memory until reset. A location answer fills
the pending slot. Chat discards active bindings; explanation returns recorded evidence without
calling tools. A correction does not repeat a previous opening.

Directory resolution uses Core metadata. A missing or ambiguous directory never silently falls
back to a computer-wide search. Native `search_files` adds `recursive`, closed `category` and
bounded `exclude_ids`. Direct searches require a trusted folder ID. Desktop discovery defaults
to immediate children; listing uses `list_directory`. No document contents are inspected.

A failed name search can make one additional type search within the same resolved directory.
Such recovery never auto-opens a result. Rejected page identities are excluded; an explicit new
filename can reconsider them. A useful name/topic allows a bounded search even when the exact
filename was forgotten. With neither name nor location, ask for a location rather than guessing.
An omitted ordering has its own `keep` value: a scope correction preserves newest/largest;
an explicit alphabetical order can replace it. A new unscoped goal drops an older directory binding.

Target identity and current action remain separate. Numeric addresses cannot become new filename
searches or a different row. Bare UI numbers select the corresponding unexpired displayed row.
Other opening plans also require a current-message positive opening operation; identity statements,
finding, how-to, recall and prohibitions do not supply that permission. Named applications are
separate from document formats. Empty application uses Windows association; existing explicit
PDF/Chrome/Edge adapters retain their limits. Concrete browser confirmations remain bounded.
Application preference is independently extracted for both selection routes. A successful target
selection cannot silently discard a named app; an unmentioned inferred browser cannot override
default association. This was caught with the live three-result CV page, not only a two-row mock.

All machine requests still use `JarvisCoreClient -> Named Pipe -> Rust registry -> validation ->
policy -> executor -> platform`. Models supply human clues, never paths, trusted IDs, executables
or shell commands. No contents reading, cloud upload, mutation or post-launch checking was added.
Historical ONNX and the diagnostic `predict` interface remain independent from this GGUF path.

## Acceptance

The existing natural-language corpus was retained, including its held-out group. Its oracle now
requires a meaningful query, the expected metadata match, at most three matches and the correct
tool. Mocked catalogs honor format/category restrictions. This would previously accept a blind
`query="*"` on every input; that deliberately broken control now fails. Fixed previous-query and
scope-ignoring controls must also fail (`audit_file_goal_assertions.py`).
The historical held-out examples were visible during this follow-up. These final scores are
regression acceptance, not an independent blind measure of model generalization.

The additional frozen conversations cover CV search/selection, an unrelated tournament workbook,
a randomly named desktop note, a nested-note distractor, 40 irrelevant images, result rejection,
filename correction without opening, direct desktop listing, scope correction, missing-location
question/answer, cancellation, feelings, how-to, hypothetical requests, negation and explanation.
Generic capability questions are checked both with an active displayed page and in ordinary chat.
Further controls distinguish ownership statements from opening and reject substitution for
unavailable content reading, file deletion or uploading.
Assertions inspect exact identities, scope, precision and absence of unintended tools, not just
whether a target happens to occur somewhere in the results.

Unit checks cover strict malformed/unsafe plans, confidence, catalogue errors, partial/empty
results, bounded recovery, stale pages after provider failure, expiry, reset and cancellation.
Native checks cover direct/recursive/type/rejection filters, invalid arguments, IPC and policy.
Live Windows checks use isolated synthetic roots and blank PDF fixtures, with production Named
Pipe and registered tools. Personal documents are neither opened nor read. Core launch acceptance
is the existing OS-call result; there is no additional window or process verification.

Validation results are recorded below after the final run.

Live Windows validation passed in the normal user context: four natural lost-file requests,
Downloads -> CV folder -> seven files, exact second-row default opening, explicit Google ->
concrete Chrome confirmation -> `open_file_with_app`, missing-name/location answer, rejection,
chat/explanation without Core calls and direct Desktop listing. Only blank synthetic PDFs and
invented notes were used. A restricted-context attempt could not use the Windows default
association; the normal-user rerun opened it successfully. Pytest reported a cache-write warning,
without failing assertions. Normal Core was restored, ping returned `ok`, three normal roots
were confirmed, and current registered file tools were available. No fixture roots remained
active. `bin/jarvis.cmd` also started the GGUF REPL and returned exit code zero in that context.

## Reproduction

From the repository root, use the existing environment (no dependency installation):

```powershell
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = ((Get-Location).Path, (Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
& $taskPython -m ruff check services/brain scripts/evaluation
& $taskPython -m ruff format --check services/brain scripts/evaluation
& $taskPython -m pytest services/brain/tests -o addopts='' -q
cargo fmt --all -- --check
cargo test -p jarvis-core
cargo clippy --all-targets --all-features -- -D warnings
cargo build -p jarvis-core
& $taskPython scripts/evaluation/audit_file_goal_assertions.py --output target/assistant-analysis/oracle-controls.json
```

Opt-in local-model acceptance (run one model process at a time):

```powershell
$env:JARVIS_RUN_ASSISTANT_TESTS = '1'
$env:JARVIS_RUN_NATURAL_FILE_TESTS = '1'
$env:JARVIS_RUN_GGUF_TESTS = '1'
Remove-Item Env:JARVIS_RUN_MODEL_TESTS -ErrorAction SilentlyContinue
& $taskPython -m pytest services/brain/tests/integration -o addopts='' -q
```

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/shell/test-file-context.ps1 -RestoreCore`
runs the isolated live fixture after stopping
only a verified project Core. The helper refuses an already-running Core and restores a normal
Core in `finally`. Restart Brain (`exit`, then `jarvis`) after source changes. Existing processes
keep previously loaded code; the new search fields also require rebuilding/restarting Core.

## Model-capacity comparison

Before the final admission refinements, an isolated comparison ran the same 14 component probes
twice with the production Q4_K_M and
the same Qwen3-4B-Instruct-2507 checkpoint in Q8_0. Each scored **22/28**: both repeats missed
ownership, identity-only and scope-only operation classification in the same way. These are
14 distinct visible probes, not 28 independent examples. No Core or OS operation was available.
The execution path separately checks current opening language and retained task constraints.
The raw model scores are deliberately reported without those guards masking their mistakes.

Metadata agreed on architecture, block count, embedding size, context size and EOS; a tokenizer
probe had the same hash. The Q8 artifact also declares a BOS token absent from Q4 metadata.
Median probe latency was 2151.50 ms (Q4) and 2051.95 ms (Q8), including their different generated
answer lengths; this small run is not a throughput benchmark. Quantization alone did not fix
these observed errors. This does not measure a larger parameter model or establish that training
is needed. The production model and default remain Q4.

`scripts/evaluation/compare_quantization.py` explicitly downloaded the 4,280,403,520-byte
[ggml-org Q8 artifact](https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/blob/e6f794d44f9395d0184a966c27b5ae99ea356fcb/qwen3-4b-instruct-2507-q8_0.gguf)
to `%TEMP%/jarvis-reference-models` and verified SHA256
`ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1`.
This diagnostic download is separate from product runtime and repository sources. Reports are
`target/assistant-analysis/quant-q4.json` and `quant-q8.json` (ignored local outputs).

```powershell
& $taskPython scripts/evaluation/compare_quantization.py --download-reference
& $taskPython scripts/evaluation/compare_quantization.py --run-local-model --profile q4 --output target/assistant-analysis/quant-q4.json
& $taskPython scripts/evaluation/compare_quantization.py --run-local-model --profile q8 --output target/assistant-analysis/quant-q8.json
```

## Limits

The model remains pinned Qwen3-4B-Instruct-2507 Q4_K_M with the existing llama-cpp-python/CUDA
runtime. No training, production model replacement, inference server or new dependency was used.
Staged inference adds latency in exchange for explicit task state and narrower decisions.
Confidence is not a calibrated correctness probability. Passing this finite corpus is not proof
for every possible wording; independent future language/model comparisons remain appropriate.

Discovery covers configured/allowed catalog roots and bounded metadata scans, not the entire
computer or document contents. A topic absent from the filename cannot be confirmed semantically
without content access. Recency ordering uses modification time, not proven download time or an
exact conversational date. Ambiguous identity still requires a choice. Arbitrary application
automation and explicit opening with every installed application are outside this delivery.

The working tree already contained earlier file-skill and launcher changes. They were preserved.
No commit or push is implied by these results.
