# Task copying and daily recurrence

User reported `invalid capability choice` for copying yesterday's three tasks to today,
and missing tasks after asking for daily repetition. The old period enum excluded yesterday;
the store had no recurrence support. These were missing contracts, not a Rust limitation.

## Delivered behavior

- Native yesterday/today/tomorrow use the OS local calendar, including year/leap boundaries.
- Whole-day copying keeps non-archived originals, including their completed status, and makes
  open one-time copies. Expected count is mandatory; mismatch/capacity failures roll back.
  Stored source-ID/source-day/target-day provenance prevents duplicate copies on repeated calls.
  Results return up to five actual linked target records, not source statuses, so follow-ups
  use the new private bindings. Previously moved/edited copies are reported in their real state.
- Daily rules and per-day overrides live in native schema v2. V1 migrates transactionally
  without changing old IDs/content/dates/status/version. No Python SQLite or model paths.
- Daily tasks start on the supplied day, or today when added without one. Completing a day
  leaves other days open. Editing title/body/status changes one day; stopping repetition ends
  the rule after the selected day. Old completions remain queryable after restart/reset.
- Complete selections of two to five verified tasks can change recurrence atomically. Private
  IDs/versions/dates come only from Core; a stale member or invalid note rolls back the group.
  Partial pages cannot stand in for an entire selection. Ordinary-to-daily conversion requires
  open tasks; completed daily occurrences may still have their future repetition stopped.
- Reads project daily dates without creating records. All-date views include saved per-day
  history plus the relevant current/start/last occurrence, without generating a missed-day backlog.

Tools: organizer_clock/list/add/update/copy_tasks/set_recurrence. All retain registry, typed
validation, policy, executor and audit. Reads are ReadOnly; writes Low. Storage remains the
current user's existing JARVIS AppData location, outside the source checkout. Base task/note
rows plus occurrence overrides share a 10,000-record cap. Day copies are bounded to 100 tasks.

No scheduler, alarms, notifications, weekly/monthly rules or permanent deletion were added.
Single-day rescheduling of a daily occurrence and restarting a stopped routine remain unsupported.

## Failures found during implementation

The real 9B model proposed a copy despite a Turkish prohibition and changed an explicit requested
count of three to the single source task it found. An assessment exposed to that same proposal
approved both. A proposal-blind current-message interpretation now supplies only bounded meaning,
effect category and explicit item count. It can veto, never authorize or route tools. Positive
requests still require independent target/field assessment and native policy. Whole-set count
constraints are checked before dispatch as well as against actual native source rows.

The first coarse polarity schema wrongly blocked stopping an existing daily rule. Categories
now distinguish performing a change, stopping existing state, direct permission, forbidding a
new action, discussion and unclear requests. There are no sentence/subject/locale regex patches.
Pure prohibitions end without workarounds; earlier completed effects are still reported if a
later proposal is vetoed. This guard adds a local inference call per effect assessment.

Three separate update XML calls in one model answer were rejected by the existing single-call
protocol. The new atomic recurrence operation represents that domain action directly; the
provider still waits for one registered call's result before choosing another. General arbitrary
multi-call plans were not enabled. An overlong nonexecuting explanation can be redrafted once
through an enforced answer-only response contract, without retrying tools/effects/IPC failures.
One English daily case also emitted a duplicate XML closing tag. Before any acting-capability
attempt, the runtime may consume one normal step for a fresh JSON decision, using the same
current request/verified facts and full registered constraints. It never edits the malformed
text or retries an attempted tool. Expanding every capability's bounded string grammar exposed
the installed llama.cpp repetition limit; decoding now uses a compact registered-action/envelope
grammar. Full argument/confidence/current-request/native-policy validation is still mandatory.
Malformed proposals after effects stop and report completed work; private rendered paths/content
are excluded from model history. Field date/extension patterns explicitly express the full-match
semantics the validator already used. No inference-error retry or provider/model fallback exists.

Diagnostic harness errors (`reset` instead of `reset_context`, and direct inference before model
loading) were corrected separately; their failures are not presented as product failures or
successful tests. The interrupted CPU trial is not performance/acceptance evidence.

## Evidence

Ordinary validation: 84 Rust tests passed (2 opt-in ignored), Clippy all-targets and fmt passed;
593 Brain/Qt tests passed with 204 opt-in skips. Actual local9B + actualRust matrix passed
12/12 state/dispatch scenarios, including19 cross-domain effect and9 meaning checks; exit0.
Evidence: target/organizer-routines-verified-model.log and
target/task-routines-f1d6252f43eb4cfe85079a4d34934de1/results.json.
The fixed Core CLI passed 28 separate processes using only an isolated LOCALAPPDATA under target,
including restart, copy/retry/count mismatch, daily completion, atomic three-task recurrence,
stopping and retained completion. Production Named Pipe handshake/ping/tool discovery/clock
verified 30 tools without reading or changing personal tasks. All model fixtures are invented.

Commands use the recorded base interpreter plus retained Brain/desktop venv site-packages
on PYTHONPATH; use a fresh target directory for pytest's --basetemp on this host:

```powershell
python -m pytest -o addopts='' -p no:cacheprovider --basetemp target/<fresh-name> services/brain/tests scripts/tests/test_desktop_qt.py -q
cargo test -p jarvis-core --lib --test organizer --locked --target-dir target/organizer-validation -j2
cargo clippy -p jarvis-core --all-targets --locked --target-dir target/organizer-validation -j2 -- -D warnings
cargo fmt --all --check
python scripts/tests/smoke_personal_core.py
python -m scripts.evaluation.evaluate_task_routines --run
```

The actual-model matrix covers TR/EN copy/retry, TR/EN daily creation/recall/complete/stop,
ordinary task conversion, a three-task agenda, prohibition/how-to/unsupported-weekly/count
controls, 19 cross-domain effect checks and nine proposal-blind meaning checks. Keep other
loaded 9B sessions closed and preserve the wake service's original state around evaluation.
Ignored evidence lives in target/organizer-routines-*.log and target/task-routines-*/results.json.

This is bounded feature evidence. The older organizer stress report's ambiguous identity and
inferred-date failures are not declared repaired or superseded by this task.
The negative controls primarily assert safe stored state/dispatch, not perfect conversational
wording. The unsupported-weekly reply can still offer an excluded daily alternative without
executing it, and a count mismatch may ask for another clue without explaining the numbers
clearly. These observed wording weaknesses are not declared solved by passing state checks.
The how-to reply also falsely claimed that an individual daily occurrence can be rescheduled;
the native operation correctly rejects that unsupported edit. Explanatory prose is not proof
of an implemented feature. The existing broader organizer acceptance remains failed.
