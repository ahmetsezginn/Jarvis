# Publication review — 20 October 2026

The user authorized publishing all accumulated changes after the task-routines work and
refreshing the repository presentation. The starting HEAD was `b9ab758`; after fetching,
local `main` and `origin/main` had no divergence. No force push is needed.

## Included work

- Independent native Windows wake service, pinned LiteRT/openWakeWord provisioning and
  protected SCM/task installation within this product.
- Windows-default microphone changes, model preload and the activation countdown that
  gates capture on actual readiness and completed welcome output.
- Catalog/policy-backed Steam game shortcut opening.
- Persistent daily tasks, per-day completion, idempotent day copying and transactional
  recurrence groups, plus bounded model-decision and current-request checks.
- A rewritten root README describing the current Rust/Python/Qt design, setup entry points,
  capabilities and limitations. The development-process document now labels its old milestone
  sequence as historical. Detailed evidence remains in the individual reports.

GitHub About now describes the local Windows assistant, Rust Core, Python agent, Qt,
offline voice, wake service and personal tasks/notes. Relevant repository topics were added.
The API response was read back to verify both updates. No repository name, visibility,
branch protection or unrelated account setting was changed.

## Publication checks

| Check | Result |
|---|---|
| All ordinary Rust workspace tests | 134 passed / 7 opt-in ignored |
| Ordinary Brain and Qt tests | 593 passed / 204 opt-in skipped |
| Workspace all-target Clippy, warnings denied | Passed |
| Rust formatting | Passed |
| Ruff check / format | Passed, 133 Python files formatted |
| PowerShell parser | 7 setup/launch/smoke scripts, no syntax errors |
| Candidate-file review | 315 before this report; no model, native binary, recording or database artifacts |
| Credential-pattern scan | No matches in the inspected candidate files; not a complete security audit |
| README relative file links | All targets exist |
| Git diff whitespace check | Passed |

The full Rust run found a stale production-registry integration expectation: it omitted
`organizer_copy_tasks` and `organizer_set_recurrence` and their low-risk classifications.
The exact-name/risk assertions were updated to match the already registered, validated tools;
assertions were not removed. The entire workspace then passed.

An initial linker run could not overwrite an old `target/.../organizer_probe.exe` on this
OneDrive-hosted checkout. Only that verified build-output file was renamed after checking
for a running probe. A later executor-test linker attempt also failed to overwrite its output;
on the next attempt that old file was already absent and compilation succeeded. No recursive
cleanup, security setting, production binary or running application was changed for publication.

Commands ran from the repository root with the existing documented Python package paths,
offscreen Qt, and CMAKE/LIBCLANG_PATH/CXXFLAGS native build environment:

```powershell
cargo test --workspace --locked --target-dir target/organizer-validation -j2
cargo clippy --workspace --all-targets --locked --target-dir target/organizer-validation -j2 -- -D warnings
cargo fmt --all --check
python -m pytest -o addopts='' -p no:cacheprovider --basetemp <fresh-target-dir> services/brain/tests scripts/tests/test_desktop_qt.py -q
python -m ruff check services/brain services/desktop/main.py scripts
python -m ruff format --check services/brain services/desktop/main.py scripts
git diff --check
```

Local evidence: `target/publication-rust-tests-verified.log`,
`target/publication-python-tests.log`, `target/publication-clippy.log`.
The real 9B task-routines result remains the earlier same-day 12/12 state/dispatch matrix
with 19 permission and 9 meaning checks; it was not rerun for presentation-only edits.
See [the complete report](TASK_ROUTINES_2026-10-20.md).

No personal organizer data, microphone recording or production machine action was used in
these publication checks. Earlier ASR/wake and ambiguous-target/date failures remain documented;
this publication does not establish general assistant acceptance.

This report is part of the publication commit. Use Git history and `git status` for the final
commit identifier, remote synchronization and working-tree state, rather than older historical
uncommitted-work entries in the handoff.
