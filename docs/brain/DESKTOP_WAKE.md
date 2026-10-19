# Desktop close correction; integrated wake removed

The user rejected the 2026-10-19 integrated wake/tray design because it retained Qt/Python and
the 9B model in memory. The new design request is an independent lightweight Windows listener
that can start a CLOSED assistant. Its [plan is separate](WAKE_DAEMON_PLAN.md); it is not implemented.

Current desktop closing is genuine termination: X closes normally, and close_assistant_window
requests native desktop_close through the usual policy/executor. A typed closing revision reaches
DesktopLifecycle; it calls Qt quit, detaches the private session and shuts down the fixed Brain
worker. The model process exits. Four native lifecycle tools remain: desktop_attach/close/detach/poll.
The native coordinator is only a small mutex-protected expiring session, with no microphone or
worker thread. Legacy hide/configure tools, native wake capture/CPU ASR/matching, tray code,
wake test fixtures/generator and the wake/normal-audio gate were removed. Normal voice code
was restored byte-for-byte to its pre-wake revision. No startup/service entry had been installed.

The generic parameterless-effect omission review remains to handle natural closing requests.
It can request model replanning, never dispatches effects itself and does not replace current-
request authorization or Rust policy. Session conversation ends on close; organizer storage
persists as before. Shared Core is not killed by a desktop that does not own its lifecycle.

The earlier counts and logs in target/wake-*.log describe the RETIRED implementation. They must
not be cited as acceptance of the independent daemon or of the corrected shutdown behavior.
Current checks use target/wake-removal-{python,rust,clippy}.log and desktop-close-live.log.

Validation commands (existing local package paths/build environment configured):

```powershell
cargo test -p jarvis-core --tests -j 2 --target-dir target/organizer-validation
cargo clippy --all-targets -j 2 --target-dir target/organizer-validation -- -D warnings
cargo fmt --all --check
python -m pytest services/brain/tests scripts/tests/test_desktop_qt.py -o addopts= -p no:cacheprovider -q
$env:QT_QPA_PLATFORM='offscreen'; $env:QT_QUICK_BACKEND='software'
python scripts/tests/smoke_desktop_close.py
```

The explicit smoke runs real Qt/QML, the actual Brain worker/local9B, actual Named Pipe/Core
and the user's Turkish close request. It asserts that Qt's event loop exits and the Brain
worker is NotRunning. No microphone or background wake is used in that check.

Correction results: ordinary Brain/Qt 546 passed/202 skipped; native 110 passed/7 ignored;
Clippy/fmt/Ruff passed. The actual Qt/worker/local-model/Core shutdown smoke passed, including
worker NotRunning. Source audio implementation matches pre-wake HEAD exactly; the running
Core no longer advertises hide/configure and the microphone was not recording.

The corrected close capability's real-model suite passed 10/10 in 96.35s, including Turkish/
English positive and negative controls (target/desktop-close-model.log). These are shutdown
tests, not wake detection or future daemon acceptance.
