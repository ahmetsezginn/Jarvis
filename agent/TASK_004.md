# TASK-004 — Scoped file and folder skills

User-authorized on 2026-10-12. First delivery: scoped metadata catalog, recursive search,
directory listing and opening. Content reading, semantic content search and file changes follow.

## Contract and acceptance

- Rust owns roots, filesystem metadata, catalog identities, target checks and platform launches.
- Default roots use native Windows Desktop/Documents/Downloads Known Folder paths, including
  redirection. Optional local JARVIS_FILES_CONFIG TOML replaces these roots; Core restart required.
- New exact semantic intents: search_files, list_folder, open_file, open_directory,
  file_catalog_status, refresh_file_catalog. Existing application/conversation flows remain.
- Model search requires query, sort (name/newest/largest), extension (empty or extension), kind
  (file/directory/any). Other targeted intents use a human query; status/refresh use {}.
- Model paths, executable instructions, scope roots and trusted IDs remain forbidden.
- Seven registered Core tools: status, refresh, search, list_directory, open_file, open_directory,
  open_containing_folder. All use existing validation/policy/executor/audit and Named Pipe.
- Legacy open_folder(path) remains for explicit Core callers; Brain uses catalog IDs instead.
- Metadata-only in-memory scans: 20,000 entries, depth 16, 2-second checks between OS calls;
  result pages <=20. Scope, refresh timestamp and partial/inaccessible/excluded counts are explicit.
- Hidden/configuration/dependency/build/model directories, key files, reparse targets and cloud-only
  files are excluded. No placeholder hydration or document-content reads during discovery.
- Ambiguity displays locations and never auto-selects. One result page, 20 entries/120s, is private
  session state. Reset, cancellation, unrelated turns and selection clear it; IDs/locations are
  excluded from model history. Number/unique-name, folder listing, containing-folder and next-page
  follow-ups are bounded and deterministic.
- Opening revalidates ancestors, canonical target, kind, creation time and file size/modification.
  Refresh invalidates IDs. Scripts/programs/shortcuts cannot use open_file. Supported document/media
  types use the fixed native open verb, without generated arguments or post-launch verification.
- Low-confidence/invalid requests fail closed; file-opening negations cannot dispatch.
- Unit/policy/IPC, real GGUF with mocked Core, live read-only Named Pipe checks and static checks.

## Remaining roadmap

Follow-up delivered: active-directory relative searches, natural displayed-name selection,
bounded concrete browser clarification, and registered open_file_with_app for local PDF in
Google Chrome/Microsoft Edge. No model IDs/paths, shell or cloud upload. See FILE_SKILLS.md.

2026-10-14 follow-up: select_file adds a strict displayed-result address contract with number,
operation and application. Unlike fresh-name search, this intent binds only the current page and
cannot search for the number. Literal numeric reference constraints reject wrong model targets
without any search. Evidence: ../docs/brain/FILE_SELECTION.md.

Natural-language date ranges and named-folder search filters are pending in Brain; Core search
already supports timestamp bounds and catalog-backed folder scopes. No persistent index, watcher,
resumable full scan, content extraction or file mutation. Large/deep collections may be partial;
narrowing configured roots is the initial remedy. GGUF is the interactive backend; ONNX remains
the smaller diagnostic baseline. Evidence: ../docs/brain/FILE_SKILLS.md.
