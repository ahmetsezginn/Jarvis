# Scoped file/folder skills — 2026-10-12

First delivery of the user-authorized roadmap: metadata inventory, recursive filename search,
folder children, document/folder opening, ambiguity selection and containing-folder navigation.
No document contents are read, no files are modified, and no post-launch GUI verification occurs.

## Usage

```powershell
./jarvis.ps1 -Model gguf
```

Examples: “bilgisayarımda hangi dosyalar var?”, “Belgeler klasörünün içinde ne var?”, “teklif PDF
dosyasını bul”, “en büyük dosyaları göster”, “bütçe Excel dosyasını aç”, “İndirilenler klasörünü aç”,
“dosya kataloğunu yenile”. After a result list: “ikincisini aç”, “ikincisinin bulunduğu klasörü aç”,
“ikincisinin içini göster”, or “sonraki sayfa”. Numbering restarts on each displayed page.

Windows defaults use Desktop/Documents/Downloads Known Folder paths, preserving redirection.
Copy config/files.example.toml to a local configuration, edit its roots and set JARVIS_FILES_CONFIG
before starting Core to select a different scope. The file replaces defaults; changing it requires
a Core restart. Root selection is trusted local configuration, never a model-produced tool input.
There is no full-disk claim: displayed scope and partial/unavailable status define what was scanned.
Catalogs are snapshots; use explicit refresh after installing/copying/moving files. Refresh expires
all previously returned file IDs, so search again before selecting an old result.

## Implementation

Rust FileCatalog owns paths/metadata and opaque UUIDs. Each scan is memory-only, metadata-only,
bounded to 20,000 entries and depth 16, with 2-second checks between filesystem calls. Individual
OS calls do not have a hard cancellation guarantee. Results are pages of at most 20. Roots,
refresh timestamps and partial/inaccessible/excluded counts are returned. Total refresh failure
retains the previous snapshot. Read-only policy denial prevents a search/refresh from scanning.

Dot folders/files, dependency/build/model folders, private-key/password-store extensions, sensitive
credential roots, reparse targets and cloud-only placeholders are excluded. These rules are a
conservative initial exclusion set, not automatic detection of every sensitive filename. Partial
scans and excluded OneDrive placeholders may limit coverage; discovery never hydrates them.

New tools traverse the production registry -> validation -> policy -> executor -> audit pipeline:
file_catalog_status, refresh_file_catalog, search_files, list_directory, open_file, open_directory,
open_containing_folder. Opening requires a catalog ID and checks ancestry, canonical path, kind,
creation time and file size/modification before native dispatch. Programs, scripts, shortcuts,
macro-specific Office extensions and unknown extensions are not allowed through open_file.
Normal supported documents/media use Windows' fixed open verb and existing file associations.
There is still a check-to-launch race at the pathname-based OS association boundary; this is not
an atomic handle-based launcher. No generated shell text, executable target or argument is used.

Brain's six new intents retain exact independent JSON/schema/semantic/confidence validation.
search_files requires query/sort/extension/kind; other targets use only a human query. IDs, paths
and raw payloads never become model authority. Conversation still returns without task decoding.
One displayed page is private state (20 entries, 120 seconds). Numbered/unique-name choices consume
it before IPC; reset, cancellation, unrelated turns and expiry clear it. ID/path listings are
replaced by a generic summary in conversation memory. File negations fail closed even if the model
tries to interpret them as opening an application. This does not fix the historical Steam negation
regression for application-only requests.

Native Windows references: [Known Folders](https://learn.microsoft.com/en-us/windows/win32/shell/known-folders)
and [Shell security considerations](https://learn.microsoft.com/en-us/windows/win32/shell/sec-shell).
The existing windows crate supplies the native bindings; only a feature was added, no new package.

## Validation

- 189 ordinary Brain tests passed; nine opt-in integration entries skipped in the ordinary run.
- 74 Rust test entries passed in a fresh target directory (44 library + 1 CLI + 16 executor +
  8 file catalog/IPC + 5 IPC boundary). Live packaged discovery remains opt-in; the symlink fixture
  can return early on Windows without symlink privileges.
- Real GGUF file-skills + existing conversation/task routing tests: two passed, ONNX entry skipped
  in that run. File scenarios use mocked Core; no real documents/applications are launched.
- Existing real ONNX application/context smoke: one passed. New ONNX file-quality acceptance is
  not claimed; use GGUF for interactive file skills.
- Real read-only Named Pipe catalog test: one passed in normal Windows user context. Refresh,
  directory search/list, stale-ID rejection and invalid-ID rejection were verified on one client.
  No GUI launch or content read. Pytest emitted a cache-write warning, unrelated to the test result.
- Ruff check/format and Rust Clippy passed. Final format/diff checks are recorded with the commands
  below. Regular-target test relinking intermittently failed with LNK1104 for existing test EXEs;
  a fresh target directory completed the full suite without changing security settings.
- Restricted-context initial live startup failed to retrieve a default Known Folder. Lookup now
  uses DONT_VERIFY and individual root failures warn while keeping other roots. Normal-user live
  verification distinguishes environment access from code behavior.

Commands from repository root (existing base Python and installed venv packages):

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$taskPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython -m pytest services/brain/tests -o addopts='' -q
& $taskPython -m ruff check services/brain/src services/brain/tests
& $taskPython -m ruff format --check services/brain/src services/brain/tests
cargo fmt --all --check
cargo test --manifest-path core/native/Cargo.toml --target-dir target/file-skills-check
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
cargo build --manifest-path core/native/Cargo.toml
git diff --check

$env:JARVIS_RUN_GGUF_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_file_skills.py services/brain/tests/integration/test_real_conversation_routing.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_GGUF_TESTS
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_qwen.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_MODEL_TESTS

# With the rebuilt Core serving in the same normal-user Windows context:
$env:JARVIS_RUN_FILE_CATALOG_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_live_file_catalog.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_FILE_CATALOG_TESTS
```

Test Core was started hidden, and only that path-verified process was stopped afterward. No
existing user process was terminated. No commit/push occurred during this implementation.

## Context and application follow-up (2026-10-12)

Fixed the exposed Downloads -> cvfolder -> CV -> Turkish PDF flow. Active-directory IDs remain
private for 120s; explicit relative searches use them, while missing/ambiguous directory references
ask which folder instead of searching globally. Natural result selection tolerates punctuation,
omitted extensions and Turkish selection suffixes. Core search also matches multiple name words
across separators. Multiple matches never auto-open. Concrete local-Chrome clarification retains
the selected file and accepts an affirmative reply; cancellation/reset/expiry/unrelated or changed
requests cannot confirm an older target. Unsupported Google Docs upload retains the result list
for a subsequent local opening request. This does not implement arbitrary generic model-question
confirmation or application-only negation recovery.

New low-risk registered open_file_with_app takes entry_id + app_id returned by Core. Both catalogs
are checked; file ancestry and metadata are revalidated. Initial adapters support only local PDF
with Google Chrome/Microsoft Edge. Windows uses native [IShellLinkW](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw)
and IPersistFile to retrieve catalog shortcut targets, rejects shortcut arguments and mismatched
browser executable names, and passes one Core-owned document argument without a shell. Packaged
application targets, other formats/adapters, arbitrary flags and cloud upload are unsupported.

Validation: 202 ordinary Brain tests, 77 Rust entries (45 library, 1 CLI, 16 executor, 10 file,
5 IPC), Ruff and Clippy passed. Five opt-in real-model checks passed (three GGUF and two ONNX).
The exact CV transcript passed with real GGUF and mocked Core.
An opt-in normal-user live test also passed with real GGUF, Named Pipe, registry, policy and native
Chrome launch. It used generated blank PDF fixtures under target/file-context-live, opened the
synthetic Downloads folder and sent the synthetic TR PDF to Chrome. Personal CV contents were
not read; no post-launch UI verification was added. A pytest cache-write warning did not affect
the live result. Fixture Core was stopped and the normal default-scope Core restored; a final
rebuild/reload and Named Pipe ping/tool listing succeeded.

Commands, using the Python/PYTHONPATH setup above:

```powershell
& $taskPython -m pytest services/brain/tests -o addopts='' -q
& $taskPython -m ruff check services/brain/src services/brain/tests
& $taskPython -m ruff format --check services/brain/src services/brain/tests
cargo fmt --all --check
cargo test --manifest-path core/native/Cargo.toml --target-dir target/file-context-check
cargo clippy --manifest-path core/native/Cargo.toml --all-targets -- -D warnings
cargo build --manifest-path core/native/Cargo.toml
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $taskPython -m pytest services/brain/tests/integration/test_real_file_skills.py services/brain/tests/integration/test_real_conversation_routing.py services/brain/tests/integration/test_real_qwen.py -o addopts='' -q
Remove-Item Env:JARVIS_RUN_GGUF_TESTS
Remove-Item Env:JARVIS_RUN_MODEL_TESTS
# Opt-in actual GUI opening, only with a stopped project Core:
./scripts/shell/test-file-context.ps1 -RestoreCore
git diff --check
```

The helper creates synthetic fixtures/config under ignored target/, starts its Core hidden, and
restores environment settings. It refuses to run with any existing Core; the test checks fixture
scope before launching. RestoreCore optionally starts the normal Core afterward. Reopen `jarvis`
to load updated Brain source. No commit/push was made.

## Remaining roadmap (after follow-up)

Document-content reading/summarization, persistent or resumable indexing, change watching and file
mutations are not implemented. Natural date ranges and named-folder search filters are pending
in Brain (native tools already accept timestamp bounds and folder IDs). Scope exclusions and scan
budgets can cause partial inventories. Model evidence covers fixed exposed diagnostic examples,
not general language-quality acceptance; qualifiers and broad application negation issues remain.
