# Personal tasks and notes

**Adversarial acceptance is FAILED.** The later
[stress review](PERSONAL_ORGANIZER_STRESS_2026-10-18.md) reproduced ambiguous-target updates,
wrong inferred dates and other contract/context failures. The historical 17-case feature
acceptance below is insufficient evidence of general task-assistant reliability.

User request, 2026-10-18: JARVIS should manage its own persistent notes and to-do list,
including conversational questions about what is planned for today.

## Behavior

- Save tasks with an optional day, and notes with optional body text. No invented deadlines.
- List pending, done or archived items, by today/tomorrow/date/overdue/undated/all, with an
  optional title/body text search. Five rows per page, next page available.
- Complete, reopen, reschedule, rename or edit a selected item. Archive hides it reversibly;
  listing archived items and reopening restores it. Notes cannot be completed or dated.
- Recall notes in a fresh session. Conversation `/reset` does not delete personal records.
- Use the same CLI/Qt/voice conversation and current-action permission assessment.

Examples are ordinary requests, not required command phrases:

> Put booking the dentist on my list for tomorrow, please.
>
> What do I need to do today?
>
> I've finished preparing the project demo. Mark that task as done.
>
> Move paying the electricity bill to today, please.
>
> Save a note: the spare watering can is in the greenhouse.
>
> What did I note down about the watering can?

The configured response language remains English; the local model may answer Turkish requests
in Turkish (also seen in the live check). Unicode input/content is preserved. Today
is the exact local date; overdue and undated work is available separately. Saved tasks never
prove what has been done on the computer. Date-only records do not schedule notifications.
No alarms, reminders that ring, recurrence, calendar integration, cloud sync or permanent
deletion are implemented. Long responses are fully visible; existing local TTS speaks at
most 1024 characters. There is no dedicated task-board UI in this delivery.

## Implementation and privacy

`services/brain/.../agent/organizer.py` is a separately registered trusted capability bundle.
The loop selects tools using their schemas; no sentence/document-specific routing is added.
Native tools: `organizer_clock`, `organizer_list`, `organizer_add`, `organizer_update`.
Every request still passes Named Pipe handshake, native typed validation, policy and audit.
Read tools are ReadOnly; local mutations are Low. An action also needs current-request
assessment by the agent. It is not a new security guarantee about the local model's reasoning.

Windows: `%LOCALAPPDATA%\JARVIS\organizer.sqlite3`. Linux: `$XDG_DATA_HOME/JARVIS` or
`~/.local/share/JARVIS`. The path comes from the process/OS environment, never the model.
This is a local SQLite file, without application-level encryption or online backup. Personal
text is not included in structured audit events. Database/sidecars are excluded from Git;
production tests use temporary or in-memory stores rather than adding sample user records.

The store has a schema version, SQLite transactions, two-second lock timeout, maximum
10,000 records, 160-character titles and 512-character bodies. Unknown/newer schemas and
corruption return errors without recreating the database. List-before-first-save is empty
and does not create storage. Parameterized SQL keeps saved text separate from SQL syntax.
SQLite was added for atomic durable writes and cross-process transactions; Chrono handles
valid calendar dates and OS-local time. Primary API references:
[rusqlite](https://docs.rs/rusqlite/0.40.2/rusqlite/) and
[Chrono](https://docs.rs/chrono/0.4.45/chrono/).

Only private Core-returned IDs/versions may implement updates. A five-row page expires after
120 seconds; edits preserve row numbers and that original deadline. A stale concurrent version
fails without overwriting. Selections are consumed before a mutation and discarded on errors.
The registry's generic reference focus prevents file/task number collisions. Bare numbers
only inspect personal records. Saved title/body text is bounded, treated as untrusted data,
and never converted to commands or permissions. Same-name rows remain distinct records;
the model should ask for a distinguishing number/detail rather than guess.

## Validation

Current results and unresolved behavior are recorded in agent/STATE.md. Reproducible commands
(add the repository root and Brain source/venv packages to PYTHONPATH on this host):

```powershell
python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider --basetemp target/personal-tests -q
cargo test -p jarvis-core -j 2 --target-dir target/organizer-validation
cargo fmt --all --check
cargo clippy --all-targets -j 2 --target-dir target/organizer-validation -- -D warnings
services/brain/.venv/Scripts/ruff.exe check services/brain/src services/brain/tests scripts/evaluation/personal_core.py
```

Opt-in real Qwen3.5-9B tests use invented tasks/notes and a synthetic Core, no actual user data,
file opening or cloud access:

```powershell
$env:JARVIS_RUN_PERSONAL_AGENT_TESTS='1'
python -m pytest services/brain/tests/integration/test_personal_agent.py -o addopts= -p no:cacheprovider --basetemp target/personal-model-tests -v
```

Tests cover durable restart, date boundaries/leap years, notes/tasks separation, malformed
arguments, query/paging, complete/reopen/archive, concurrency versions, corrupt/newer stores,
policy allow/deny/confirmation over the IPC contract, private identity bounds, expiration,
Qt text/speech delivery, cross-bundle focus, negatives/quotes, duplicate titles and note
instruction injection. Synthetic speech/microphone accuracy and historical file-model failures
remain outside this feature's acceptance; their existing failure reports are preserved.

Acceptance on this host: 16/16 actual 9B personal-agent cases passed (186.54s). The last
schema separates a closed period enum from a YYYY-MM-DD calendar date, so note-name words
cannot be passed as date filters. Earlier iterations/failures remain in ignored target logs:
row-renumbering, hidden update capability, old/new field confusion, progress narration without
tools, and a note-name word used as a date. No sentence-specific routing was introduced.
The generic loop also reports successful earlier mutations if a later action fails; a
regression test reproduced the misleading old executed=false response before the fix.
The additional Turkish sequence (empty agenda, tomorrow's veterinary task, note containing
4826) passed separately in 42.38s: 17 personal-agent cases verified. Final ordinary Brain/Qt
is 536 passed /192 opt-in skipped; Ruff check/format covers 92 files.

Additional file-model review remains FAILED: 7/8 varied discovery scenarios passed. The photo
case was reproduced alone: the model supplied `kind=image` rather than `kind=file` with
`category=image`; schema validation rejected it before any Core call. Default photo opening
passed separately. This remains an open model schema-adherence regression, not a native
storage failure; no unsafe coercion or per-photo production patch was applied. Historical
file/voice failures are not superseded by personal-organizer acceptance.

`python scripts/tests/smoke_personal_core.py` passed 11 separate production Core CLI processes
using only an isolated LOCALAPPDATA under target: initial empty/no-create, save task/note,
restart/list, date filtering, complete, completed list, note recall and stale-version rejection.
This diagnostic never writes to the current user's personal database. Ordinary Rust checks
passed 107 tests with 7 opt-in cases ignored; fmt and all-target Clippy passed. Final ordinary
Brain/Qt counts and the additional file-model regression are recorded in agent/STATE.md.
The final live actual-model/actual-Core/Named-Pipe test also passed for “Jarvis bugün
yapacaklarım neler?”: it called the personal list tool and reported today's empty agenda
without any mutation. The updated Core is running; restart the CLI/Qt session to load the
new Brain capability source. The development model's host-buffer diagnostic during unload
was nonfatal; the live check exited successfully.
