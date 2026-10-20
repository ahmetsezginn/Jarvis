# Handoff

LATEST distribution (2026-10-20): user requested unused-model cleanup, readable README,
standalone JarvisInstaller and final source publication, then explicitly added CPU support.
Installer tooling/scripts/staging/output are local-only under ignored `.local-distribution/`;
none may be staged. App portability and pinned source CPU requirements belong in Git.
Removed five verified-unused model/source directories (6,534,116,969 bytes /6.085GiB);
retained active9B, TurboQ5, VAD and native speech/wake runtimes and personal data.
Frozen Qt uses a fixed sibling worker; Brain/native resource paths support installed models.
Separate CPU llama DLLs avoid CUDA lookup; all nonzero GPU requests reject a CPU-only runtime.
README is now end-user-first with source guides linked. Notes/tasks remain outside appDir.
See docs/brain/DISTRIBUTION_2026-10-20.md for final installer tests and measured limitations.
This supersedes the barge-in publication state below; verify git log/status/origin for sync.
Full final source checks: Rust136 passed /9 ignored; Brain plus scripts/Qt616 passed /209
skipped; release build, workspace all-target Clippy/fmt and Ruff135 files passed. Real packaged
9B greetings worked in CPU/NVIDIA; CPU was substantially slower and loaded no CUDA modules.
Installed native CPU and NVIDIA speech passed synthetic TR/EN/auto cases. Installer QA caught
and corrected preflight checksum rejection and frozen CLI argument handling; details in report.
Final installer 0.3.0-preview.1 is 641,012,772 bytes (hash in report), with Turkish sharing
instructions/checksum beside it. Its actual final CPU/GPU installation, model checks, QML/CLI,
no-redownload GPU repair and data-preserving uninstall passed. QA used synthetic local data;
the existing developer wake service remained Running. The unsigned preview is not tested on
another machine; service installation was not repeated over the developer service.
This publication includes the earlier barge-in source changes; installer files stay untracked.

LATEST barge-in (2026-10-20): user authorized speaking over normal Auto conversation replies.
Existing speech_start now validates barge_in=true only with automatic=true and optional bounded
render index. Native Windows Voice Capture DSP source-mode AEC binds exact CPAL/SAPI endpoint
metadata, owns synchronization, and supplies clean16k mono PCM. An all-zero shared render
keeps the same endpoint active without mixer changes. Silero/TurnDetector retain800ms preroll;
native onset purges only this AudioService's SAPI queue before polling/ASR. UI invalidates old
acks and uses the same capture/final transcript/session; no effect replay or new action grant.
Leases, limits, route changes and cancel/close reject partial/stale PCM. Initial preparation
and welcome stay microphone-closed; manual capture stays half duplex. AEC-open failure is
explicitly reported with existing turn-by-turn voice, never unprotected raw duplex.

Rust workspace136 passed /9 opt-in ignored; Brain/Qt608 passed /205 skipped; workspace Clippy,
fmt, Ruff and diff passed. Actual source mic/SAPI9s test passed; native synthetic filter
double-talk passed (speech at6000ms, detected6300ms; one fixture, not latency guarantee).
Actual QML/deployed Core/default AMD input/SAPI test passed19.81s with no self-trigger and
continuous capture. Qt test uses a fixture reply through the normal handler, not new9B inference.
Initial STA/MTA conflict and premature12s live-test deadline were fixed/documented, not skipped.
User's own overlapping speech/room quality remains to be retested; old ASR/model failures remain.
See docs/brain/BARGE_IN.md. No recordings/cloud/ONNX/model artifact or wake-service change.
Validated Core deployed to target/debug, PID7736 at update, source/deployed hashes matched.
Wake service restored to its previous Running state after live tests; verify live state later.
This new feature is uncommitted/unpushed; prior publication is298ffb6 on origin/main.

LATEST publication checkpoint (2026-10-20): user authorized committing/pushing all accumulated
wake/default-mic/preload/activation/Steam/task-routine changes and refreshing GitHub presentation.
README now introduces the actual Rust/Python/Qt product and links to current setup/evidence;
DEVELOPMENT_PROCESS explicitly labels older milestones historical. GitHub About/10 topics were
updated and read back. Full workspace validation: Rust134 passed /7 opt-in ignored; Brain/Qt593
passed /204 skipped; workspace all-target Clippy, fmt, Ruff133 files, seven PS syntax checks and
diff passed. Full Rust run exposed one stale executor registry expectation; both new organizer
tools and their low-risk classifications are now asserted. No production-code change in this
publication pass. Existing actual9B12/12 evidence was not rerun for documentation/test-only edits.
See docs/brain/PRE_PUSH_REVIEW_2026-10-20.md. These accumulated changes are included in this
publication checkpoint; use git log/status and origin/main to verify its final hash/sync state.
Older uncommitted/unpushed notes below describe their historical session boundaries.

LATEST task routines (2026-10-20): copying a day's agenda,
persistent daily rules/per-day completions, and atomic recurrence groups are implemented.
Native tools now include organizer_copy_tasks and organizer_set_recurrence (30 total tools).
Schema v2 transactionally migrates v1 without rewriting saved records. Reads project daily
occurrences without writes/scheduling. Whole-day copies require expected_count, preserve
originals, deduplicate replays and return actual linked target rows for private follow-up
bindings. Two-to-five complete verified tasks may change recurrence in one transaction;
partial pages, stale members, notes and duplicate IDs cannot produce partial group writes.
Details/commands/failures: docs/brain/TASK_ROUTINES_2026-10-20.md.

Real evaluation exposed proposal anchoring: prohibited TR copy and changing explicit three to
one were wrongly approved. Current-message-only meaning can now VETO, never authorize/route;
then independent effect assessment and Rust policy still apply. Categories distinguish
perform/stop_existing/permission/forbid_new/discussion/unclear; a coarse earlier polarity schema
incorrectly blocked stopping routines. Counts constrain whole-set parameters. A pure prohibition
ends without workarounds. Current Qwen tool protocol remains one call per decision/five steps;
the atomic recurrence capability replaces three separate same-setting calls. Overlong prose
alone may redraft once under an answer-only contract; no effect/IPC/provider error is replayed.

Rust84 passed /2 ignored, Clippy all-targets and fmt passed. Native CLI28 separate isolated
LOCALAPPDATA processes passed, including copy/retry/count and atomic three-task repetition/stop.
Final ordinary Brain/Qt593 passed /204 skipped, Ruff check/format and diff passed. A malformed native XML emission
can make one fresh structured decision only before any acting attempt; full schema/permission
validation remains. Compact decoding avoids the SDK grammar repetition limit; no raw XML repair,
effect replay or inference-error retry. Error exits retain verified display/reference focus and
keep rendered data out of model history. Targeted actual-model EN daily flow now passed after
the malformed XML case. Final actual9B + actualRust matrix PASSED12/12 state/dispatch scenarios,
including19 permission and9 meaning checks. Evidence target/organizer-routines-verified-model.log
and target/task-routines-f1d6252f43eb4cfe85079a4d34934de1/results.json. Earlier failed matrices
remain recorded. These are state/dispatch checks, not perfect wording acceptance: weekly
alternatives, count-mismatch explanations and a false daily-rescheduling how-to claim remain
documented response weaknesses. Native daily rescheduling remains correctly blocked.
Interrupted CPU trial is NOT acceptance/performance evidence.
Deployed validated final Core target/debug, current PID25636 at update, hashes matched; actual
Named Pipe ping/discovery/clock verified30 tools without reading/modifying personal tasks.
Qt/Brain were closed by the user for testing. Evaluation ended exit0; no evaluation/Qt/Brain
model processes remain. Wake service restored Running, desktop_running=false; Core25636 still
matches the validated binary hash. No personal records were read/mutated by live deployment
verification. No new service/UAC/model artifact. Reopen JARVIS to load the new Brain source;
old rejected/one-time requests do not magically become daily rules and must be requested again.
This work is included in the publication checkpoint above. Older ambiguous-target/inferred-date stress
failures remain open; this feature is not universal organizer acceptance.

LATEST activation dialogue (2026-10-19): user explicitly replaced listening DURING model
preload with: open window -> spoken estimated activation countdown, microphone CLOSED ->
actual model_ready -> "Sistem aktif. Merhaba, nasıl yardımcı olabilirim?" -> real output
completion -> automatic capture. main.py blocks manual AND automatic speech_start while
loading/pending initialization. Removed the superseded early-audio/deferred-ASR state/path.
Countdown uses a monotonic clock starting at worker ready(model_loading=true), default8s
based on prior measured7.9s host load. It is labelled TAHMINI, not exact progress, persisted
learning or a guaranteed duration. No settings file/registry/OS tool was added. Expiry shows
"Hazırlık devam ediyor" and never asserts readiness; real readiness cancels stale preparation
speech/acknowledgements and welcomes once. Both device discovery and welcome completion gate
capture. Mute/cancel/model error/worker exit/close cannot reactivate via late callbacks.

Final Brain/Qt568 passed /204 skipped; Ruff check/format and diff passed. New coverage includes
early/overdue countdown, no capture before real readiness, stale speech acknowledgements,
queued/actual welcome completion, QML countdown bindings, readiness before discovery, opt-out,
model failure and worker exit with late discovery. Earlier early-audio tests were rewritten
for the user's superseding no-audio-before-ready requirement, not hidden/xfail'ed.
Real 9B + real QML/Core/Turkish Tolga activation test PASSED (16.54s): preparation announcement,
actual model-ready signal, completed welcome and only then AMD default microphone opened;
capture immediately cancelled without dispatch. Speaker was current Windows default BSX output.
Actual SCM/task activation/close during initialization/rearm smoke PASSED; no Qt/Brain worker
left behind, listener restored Running/listening, error=null. No Rust/Core/service binary or
model/prompt changes in THIS activation task; Qt/worker repo source applies on next opening.
Evidence target/desktop-activation-{tests,live,service-smoke}.log. Exact ordinary validation:
python -m pytest -o addopts='' -p no:cacheprovider --basetemp <fresh-target-dir>
services/brain/tests scripts/tests/test_desktop_qt.py -q (documented PYTHONPATH, offscreen Qt).
Live: JARVIS_RUN_DESKTOP_STARTUP_LIVE=1, pytest scripts/tests/test_desktop_qt.py -k
real_startup_worker -q -s; pause/resume original Running listener around direct development
test, no other loaded desktop. All accumulated changes still uncommitted/unpushed.

LATEST Steam shortcut correction (2026-10-19): user found/confirmed Desktop/games/Counter-Strike
2.url but open_file returned policy_denied. Actual local target steam://rungameid/730; native
document-only extension gate was the cause. Added generic files/shortcut metadata adapter and
native typed GameShortcutTarget + Windows fixed Steam handler activation. Max16KiB, supported
text BOM encodings, exactly one URL, positive-u32 rungameid only, no arguments/query/other
commands, stable read handle plus original scope/stale/reparse checks. Never launch raw .url,
IconFile, general .lnk or model URI/ID/path. Existing open_file schema/policy/Brain unchanged.
62 library passed /2 ignored +16 file-catalog integration passed (78 total); Clippy all-targets,
fmt, diagnostic Ruff/diff passed. Two generic-game successes, malicious/stale/injected cases,
policy zero-dispatch and existing IPC contract covered. docs/brain/STEAM_SHORTCUTS.md has exact
commands/evidence. Deployed tested Core under target/debug, restarted owned Core PID36900 at
update; wake service's prior Running state preserved, no Qt was open. Real Core/IPC/policy smoke
opened the user's exact shortcut; separately observed cs2 PID46088 starting, left game open.
This is process-start evidence, not menu/login readiness; no runtime post-launch probe added.
All current service/desktop/shortcut work remains uncommitted/unpushed; prior b9ab758 separate.

LATEST desktop preload (2026-10-19): user selected starting model preparation on wake/open,
rather than the first message. The existing user-context worker now emits ready(model_loading),
loads the same checked provider on its own process thread, then emits model_ready/load_time_ms
BEFORE reading queued requests. No additional inference thread/server, provider/prompt change,
checksum bypass or idle model resident in the small wake service. Close still exits Brain.
Qt greets/listens during preload and shows PREPARING ASSISTANT. Early typed input waits in the
bounded pipe; completed automatic PCM stays bounded in Rust while speech_poll renews its lease.
Only after model_ready does speech_finish allocate ASR, avoiding simultaneous initial GPU loads.
Manual hold-to-talk is disabled until preload completes so button release never extends capture.
Cancel/model failure/close drop pending audio. Default-input change clears the deferred binding;
late readiness cannot submit a replacement unfinished recording. Actual effects retain policy.

Final full Brain/Qt565 passed /204 skipped; Ruff check/format and diff passed. First broad run
had 11 tmp_path SETUP errors in inaccessible external pytest temp folder, then all passed with
a fresh target/desktop-preload-py-<UUID> basetemp; no tests weakened/skipped to fix it.
Three real tests passed separately: preload without any message + first reply (1), actual
Turkish greeting/default AMD capture while loading + early-message real reply (2). Actual fixed
SCM/task activation/close during preload/rearm smoke also passed, no Qt/Brain worker left behind.
Evidence target/desktop-preload-{tests-final,live,early-live,service-smoke}.log and
desktop-preload-live.json. One local sample: model load7919ms, desktop-to-prepared8156ms,
first reply after preparation9938ms, Qt event ticks262. This is NOT a cold-disk/A-B speedup
benchmark or a guarantee of instant first response; normal inference/ASR and very short first
utterances can still wait. Model loading has moved earlier, not been removed.
Exact ordinary command (normal documented PYTHONPATH, QT_QPA_PLATFORM=offscreen):
python -m pytest -o addopts='' -p no:cacheprovider --basetemp <fresh-target-dir>
services/brain/tests scripts/tests/test_desktop_qt.py -q.
Live: JARVIS_RUN_DESKTOP_PRELOAD_LIVE=1, pytest scripts/tests/test_desktop_qt.py -k
real_model_preloads -q -s; pause/resume installed service around direct-development live tests.
No Rust/service binary change or reinstallation in THIS preload change. Service verified listening
on Windows default AMD afterward. All new work remains uncommitted/unpushed.

LATEST microphone correction (2026-10-19): user removed BSX USB and requested Windows' selected
default microphone for wake/Auto conversation. Added explicit install.cmd -DefaultWakeMicrophone
to CLEAR the old protected pin (ordinary upgrades still preserve optional explicit selections).
Wake compares private CPAL default endpoint identity once/second and discards old PCM/features
before reopening. Core capture privately binds its default endpoint; speech_poll adds typed
input_changed on a change/disconnection, cancels the old stream and discards partial audio.
speech_finish independently rejects a changed route. Qt waits for speech_cancel acknowledgement
before rearming default, and respects End conversation during that switch. Fixed manual inputs
do not silently switch. No schema weakening, direct Python audio or recording persistence.

49 related Qt/Brain tests passed /5 skipped; native wake5 passed; Core library60 passed /2 ignored;
all-target Clippy for both crates, fmt, Ruff, PS AST and diff passed. Core was updated after
verifying/stopping only this repository's old process; now PID50348 at update (verify later).
Native build required existing desktop CMAKE/LIBCLANG_PATH/CXXFLAGS environment; Windows
OneDrive output locks resolved by renaming individual verified target EXEs, no security changes.
Evidence target/default-microphone-{rust,clippy,build,install}.log. Real read-only speech_status
confirms USB absent, Windows default Microphone Array (AMD Audio Device), recording=false.
First Windows UAC attempt was cancelled. User then explicitly confirmed "onayladım"; rerun
install.cmd -SkipBuild -DefaultWakeMicrophone SUCCEEDED with actual Windows consent. Protected
config microphone=null, installed EXE hash matches the tested release. Live service PID52916
at installation was listening on Microphone Array (AMD Audio Device), input_peak >0, error=null.
Fixed SCM/task activation, microphone handoff, policy close and rearm smoke PASSED again.
Evidence target/default-microphone-install-final.log, default-microphone-service-final.json,
default-microphone-service-smoke.log. Listener remains Running/listening on Windows default.
Desktop entry point now always starts default input, independent of legacy wake config; removed
the previous PS-to-Qt microphone-name environment transfer. Real Qt/QML + worker/Core/Tolga
startup on Windows DEFAULT AMD input PASSED (48kHz stereo), capture immediately discarded with
no dispatch; target/default-microphone-startup-live.log, 1 passed /39 deselected.
No physical hotplug/default-switch test claimed. All new work remains uncommitted/unpushed;
checkpoint b9ab758 publication remains separate.

Latest desktop startup preference (2026-10-19): user requested Auto conversation with Turkish
listening/voice and "Dinliyorum" on opening. main.py entry point now opts into this startup;
device discovery resolves the exact installed wake microphone, greeting uses registered native
speech_speak, and actual output completion gates automatic speech_start. Escape before discovery
cancels startup, discovery/missing/duplicate-device/output failures never silently switch mics.
jarvis.ps1 passes only the protected configuration's selected human microphone name and restores
its environment afterward. No Rust service reinstall is needed; the bootstrap uses repo sources.
Real Qt/QML + real worker/Core/Tolga TTS passed, then actual BSX 48kHz mono capture opened and was
immediately discarded without dispatch. Log target/desktop-turkish-startup-live.log; command:
JARVIS_RUN_DESKTOP_STARTUP_LIVE=1 plus JARVIS_DESKTOP_MICROPHONE, pytest scripts/tests/test_desktop_qt.py
-k real_startup_worker -q -s (wake service paused/resumed around probe). New deterministic Qt
coverage includes greeting/queued-output gating, Turkish transcription, selected-device UI,
startup cancellation and errors. The older default-off descriptions below are historical.
Final related tests: 45 passed /5 skipped (Qt plus Brain desktop session/capability); live
startup test separately 1 passed. Ruff and PowerShell parse/diff checks passed. Installed fixed
SCM/task activation/close/rearm smoke passed again with the new startup; evidence
target/wake-service-turkish-startup-smoke.log. Listener is running again on BSX.
This change is also uncommitted/unpushed.

LATEST service implementation (2026-10-19): user authorized checkpoint push FIRST, then a
real Windows SCM wake service as part of THIS product/repository/install. Checkpoint b9ab758
was committed/pushed to origin/main and remote HEAD verified. Before that push Brain/Qt546
passed/202 skipped; Rust110 passed/7 ignored; fmt/Clippy/Ruff/diff passed. The NEW service
work described here is not yet committed/pushed; do not infer otherwise from the checkpoint.

services/wake is an independent small Rust crate, no dependency on Core, Qt/Python, GGUF,
full ASR, CUDA/GPU or ONNX. Root install.cmd installs the existing product command and the
native SCM component together. Setup explicitly provisions SHA-pinned openWakeWord v0.5.1
TFLite assets and official LiteRT2.3.0 CPU DLL; only native DLL extracted, no Python installed.
Program Files protected runtime/config; ProgramData bounded non-content status; LocalService
identity. Fixed protected \\JARVIS\\Launch task uses owner InteractiveToken/Limited, no password.
Owner unlock/session check, mic release before launch, single task, pause/resume/stop, bounded
in-memory PCM, recovery/cooldown. Parent kill-on-close job cleans its descendants; shared Core
is preserved. Normal jarvis -Desktop uses the same task; stopped listener still allows manual
desktop use. Config now explicitly selects user-confirmed Mikrofon (BSX USB Audio), no fallback
if it disappears. Qt's ordinary Auto conversation remains opt-in; no UI/tray wake integration.

Real user's OLD PocketSphinx wake failed. Replaced with official native neural detector and
user confirmed "çalıştı" (worked) on a real wake. Status at that point recorded three accepted
launch requests, not proof of three successful end-to-end opens. Synthetic comparison still
FAILS: name-only triggers; Turkish TTS sample missed. EN normal/slow detected; four other
negatives rejected. No threshold lowered to hide failures. A second phonetic-prefix experiment
did not improve failures and was REMOVED. Tract graph-reader experiment was also rejected;
no vendor override/graph modifications/tract dependency remains. Diagnostic artifacts under
target/wake-provider, no production microphone audio saved. General acoustic acceptance is
NOT complete; no long-room-noise/8-hour/latency or post-reboot acceptance claimed.

Fresh native wake unit5 passed; Clippy all targets, fmt and PowerShell syntax passed. Installed
BSX real-service smoke passes pause/resume, fixed activation through LocalService, one instance
after repeated requests, mic handoff, actual Qt/native-policy close and rearm. Separate stopped-
listener/manual-open + forced task-parent termination test PASSED: six owned descendants gone,
pre-existing Core preserved. Evidence target/wake-service-final-smoke.log,
wake-lifecycle-contract.{log,json}, wake-user-confirmed.json, wake-service-final-metrics.json.
Final30.413s continuous BSX idle snapshot: private8.07MiB, working set19.16MiB, normalized
CPU0.491% over16 logical processors. Short snapshot only, no long-run performance claim.
Latest setup/limits and exact commands: services/wake/README.md and WAKE_DAEMON_PLAN.md.

The historical correction/organizer failures below remain relevant; no organizer repair here.

HISTORICAL checkpoint before the service (2026-10-19): user rejected the embedded Core/Qt wake and tray-resident
implementation. They meant an independent lightweight Windows listener that launches a CLOSED
assistant, so the 9B model is not retained. Removed native wake module, CPU wake ASR helpers,
shared audio gate, Qt tray/resident, hidden-window interception and wake-specific generator/tests.
Normal native audio files and their tests restored byte-for-byte to pre-wake HEAD; source and
live-Core checks confirm old desktop_hide/configure absent, desktop_close present, mic off.
No existing desktop/main.py resident was running when checked. No Windows startup entry or
SCM service was installed previously or now. The independent daemon is PLANNING ONLY.

Retained conversational close, changed from hiding to TERMINATING Qt/Brain. Four native tools
attach/poll/close/detach; coordinator now only an expiring UUID/closing revision in a mutex,
no listener thread or audio. Qt quit invokes worker shutdown and releases the LLM process.
Generic parameterless-effect omission review/normal dispatch authorization remain. Real
Qt/QML + actual worker/local9B + actual Pipe/Core with exact Turkish close request PASSED:
Qt event loop exited, worker NotRunning (target/desktop-close-live.log). No microphone used.
Existing Core may remain shared, just as before; desktop never kills unrelated shared clients.
Saved organizer data persists; session-only chat ends. Reopen manually with jarvis -Desktop.

Ordinary Brain/Qt546 passed/202 skipped. Native110 passed/7 ignored. Ruff/format, cargo fmt
and Clippy all targets passed.
Corrected close capability real-model controls:10/10 passed in96.35s, including exact Turkish
dismissal and Turkish/English prohibition/how-to/hypothetical/chat controls; log desktop-close-model.log.
Logs target/wake-removal-{python,rust,clippy}.log. Copied validated
Core and restarted only this project's process, PID37292 at correction, logs
wake-removal-core.{stdout,stderr}.log. Earlier wake/model counts below and target/wake-*.log
belong to the RETIRED design, not the future independent process. No commit/push.

Plan: docs/brain/WAKE_DAEMON_PLAN.md. Separate Rust executable/crate, not a dependency on the
large Core library; optional tiny shared IPC/installation types. While idle only small detector
runs, no Qt/Python/GGUF/full ASR/GPU. First evaluate native PocketSphinx keyword spotting
without opening apps, measure real RAM/CPU/latency/false wakes, then fixed trusted bootstrap,
single-instance/process ownership/mic handoff, and LAST Windows user-logon registration.
No new detector/models/startup integration implemented/installed in this correction. Existing
ONNX/cloud/recording restrictions persist. Proposed memory/CPU numbers are acceptance targets,
not measurements. SCM Session0 UI constraints and source links are in the plan.

The original organizer adversarial failures below remain open and untouched.

LATEST adversarial audit (2026-10-18): user explicitly requested pushing the task system/model
hard. Production source/prompts/weights/policy were frozen; no production repair was attempted.
See [PERSONAL_ORGANIZER_STRESS_2026-10-18.md](../docs/brain/PERSONAL_ORGANIZER_STRESS_2026-10-18.md).
Real 9B + actual Rust registry/validation/policy/executor/SQLite through a test-only framed
stdio ControlSession fixture, all stores canonicalized under target; no personal AppData
read/write, OS app/file execution, microphone or cloud. Native fixture advertises the full
registry but bans all non-organizer execution. Source fingerprint unchanged in all runs:
c4918839b50aa0bc0368d7bd7f5c2dd0a6fde9c35f66256b526504710920219b.

55 defined scenarios,59 executions with repeats/controls: main 37/47 passed (58 turns,121 model
inferences,585.22s); focused 2/9; controls 2/3. ACCEPTANCE FAILED. Three P1 actual durable errors
were each reproduced: ambiguous "Mark it done" chose a task from a four-row list; a same-name
task hidden on the next page was ignored and the visible duplicate completed; "first day of
next month" saved 2024-02-01 instead of 2026-11-01. Valid UUID/version/Low policy do not prove
intended identity/date. Current-request assessment approved these wrong proposals.
Other confirmed gaps: multi-call XML rejected wholesale; a numbered NEW list never reaches
model; narration invents date/count facts and global 6/7/8 vs local 1/2/3 numbering; reopening
fresh completed tasks searches only open; quoted saved markup trips output protocol parser;
>512-character exact notes get a raw validation failure. Turkish prohibition read all tasks
and proposed completion, but assessment blocked the write. Native data was not changed there.
Note body is truncated to120 chars before model reasoning without an incompleteness marker:
long-note sum failed, same 7+9 info in short note correctly gave16. Explicit truthful current
date fixed the relative-month case. This is evidence for orchestration/context flaws alongside
model planning/adherence failures; do not claim model size alone is the cause or train on cases.

Native malformed/concurrent contract:80 invalid requests,167/167 checks passed incl40 inserts
from two real Rust processes and stale-version rejection. Ordinary Brain/Qt536 passed/192
skipped; Rust107 passed/7 ignored, fmt/Clippy all targets and new diagnostic Ruff passed.
The earlier17 happy/bounded feature tests do NOT establish general task assistant acceptance.
Raw evidence: target/personal-stress-181cdf19105d, -d1548c7dc0ca, -60ece61780ee;
target/personal-contract-d30688231e. Diagnostic scripts intentionally exit1 on real failures.
Fixtures: core/native/examples/organizer_probe.rs and scripts/evaluation/{stress_personal_organizer,
stress_personal_followup,probe_personal_contract}.py. No failing cases were skipped/xfail'ed.
Original markup oracle used post-error bindings (reset); repeated test checks actual returned
native items instead and still fails for the real protocol exception. Production remains the
same uncommitted feature revision from the previous turn; no restart/deploy/commit/push here.

Latest feature (2026-10-18): user authorized persistent conversational personal tasks/notes.
Implemented native SQLite Organizer + four registered tools, a separate semantic capability
bundle, local-calendar dates, five-row private selection/version/120s bindings, add/list/edit/
complete/reopen/reschedule/archive, note recall and shared Qt/voice presentation. /reset does
not delete saved items. No sentence routing, Python database access, shell, cloud or scheduler.
See [PERSONAL_ORGANIZER.md](../docs/brain/PERSONAL_ORGANIZER.md).

Final ordinary Brain/Qt: 536 passed /192 skipped (2.45s). Rust: 107 passed /7 ignored;
fmt, Clippy all targets and Ruff check/format (92 files) passed. Core tests used the isolated
target/organizer-validation directory after repeated Windows LNK1104 in old default test EXEs;
no ACL or security setting changed. 11 fresh production CLI processes passed isolated storage
smoke (scripts/tests/smoke_personal_core.py), including restart persistence/stale-version error.
Real 9B: 16/16 personal-agent cases passed (186.54s), plus the additional Turkish empty agenda/
tomorrow-veterinary task/note-with-number sequence passed (42.38s), 17 personal cases total.
Qt worker test verifies full agenda text reaches both display and speech, without stale file
cards; existing SAPI text bound remains 1024. A partial-mutation regression was reproduced
before fixing: first save succeeds, second fails; now the first success is retained/reported.
Read-only discovery is not incorrectly counted as a successful launch by this fix.

IMPORTANT extra file-model regression: 7/8 cross-topic discovery cases passed, graduation-photo
request FAILED and was reproduced alone: planner returned find_files kind=image instead of
kind=file/category=image. Strict schema rejected it before ANY Core call. The separate default
photo opening test passed. This is an OPEN model-schema adherence regression; do not claim
overall assistant/file acceptance. No per-photo mapping/alias or validation weakening was added.
Historical three file semantic failures and ASR quality failures remain unaddressed.
Updated production executable copied from the validated build into target/debug; Core started
hidden, PID 7380 (verify processes rather than assuming). Live real-user Named Pipe registered
all four tools and read today's empty list successfully. Sandbox account SID1008 cannot reach
the real user's SID1001 pipe; same-user verification succeeded without endpoint/ACL changes.
Final actual-model -> actual-Core -> actual-Named-Pipe check also passed for the user's Turkish
"Jarvis bugün yapacaklarım neler?": list_personal_items was called, today's zero saved tasks
were reported, and no mutation occurred. Native host-buffer diagnostic on model unload was
nonfatal (exit 0). The configured English reply preference is unchanged, but this Turkish
request produced a Turkish prose answer; strict response-language adherence is not established.
Working tree started clean at 19fb1ab. This feature is uncommitted; no new commit/push was
requested. Inspect git status/diff for current truth and preserve all prior historical reports.

Latest pre-push review (2026-10-18): user reports voice somewhat improved, still needs work;
requested repository/file-operation analysis and publishing the current update before choosing
another task. See [PRE_PUSH_REVIEW_2026-10-18.md](../docs/brain/PRE_PUSH_REVIEW_2026-10-18.md).
Found/reproduced a numbered-selection bug: an unsupported app override erased file bindings
without any Core call. Pure app preflight now runs before consumption; original TTL preserved,
valid effects still consume before IPC. Three regression tests failed before, pass after.
Final ordinary Brain/Qt: 520 passed /175 skipped (4.40s); Rust: 97 passed /7 ignored. Ruff
check/format (118 files), Rust fmt and all-target Clippy passed. Model/DLL/WAV/log exclusions
verified; README setup/status/model directories corrected. Windows jarvis command targets this repo.
Real 9B file review on synthetic metadata: 61 passed /3 failed,64 cases,686.54s. Baseline was
loaded before the binding fix. Remaining semantic failures are Turkish Desktop scope omission,
inferred Excel for default XLSX opening, and approval of an unrequested WriterPro override.
Do NOT claim overall assistant/file acceptance; voice diagnostic failures remain documented.
Fetched origin/main matched starting HEAD f0e05ed (0/0 ahead/behind). Delivery target main;
use git log/status/remote state as authority for the final commit and push, not historical notes.

LATEST correction/integration (2026-10-18): user wanted Handy's solution INSIDE JARVIS,
not a standalone app. Windows Core now uses official pinned transcribe-cpp 0.2.4 bindings
with checksum-provisioned CPU/Vulkan DLLs (NO ONNX), default turbo Q5 on a discovered dedicated
GPU. Existing capture/Auto/Silero GGML/policy/pipe/SAPI stay in Rust; no Handy/clipboard/Python
ASR or recordings. Session/model drops each utterance before Brain; verified file handle only
is cached against write/delete races. Explicit legacy CPU choice remains; no silent fallback.
Real TR/EN/Auto synthetic controls passed; actual 9B token generation -> three ASR utterances
with 9B still loaded -> token generation passed at unchanged 32 GPU layers (peak7594MiB).
97 ordinary Rust passed /7 ignored, 22 Qt passed /4 skipped, fmt/Clippy passed. Quality16
still FAILS (4 critical,9/102 errors); personal microphone accuracy and old semantic failures
are NOT accepted. Separate Handy and old project Core were stopped for deployment.
See [NATIVE_SPEECH_PROVIDER.md](../docs/brain/NATIVE_SPEECH_PROVIDER.md) for setup/evidence.
The standalone trial notes below are historical. No production recording permission implied.
Deployed Core PID28784, real pipe status Q5/transcribe-cpp/RTX4070 Vulkan, model_available=true,
recording=false; no ONNX DLL loaded. Final quality repeat retains 4/16 critical,9/102 errors
(28.41s). Actual Auto VAD/endpoint path retains 4/6 critical failures (33.16s); no acceptance.

Standalone Handy trial (2026-10-18): user chose option 1, then explicitly allowed the ready
app's LOCAL WAV persistence, with no cloud. This is a trial-only exception, not production
JARVIS recording permission. Signed/checksummed Handy 0.9.8 installed portable under
.cache/handy-trial/app; existing pinned turbo hardlinked, no big model download. Turkish,
RTX4070 Vulkan pinned, Earshot VAD, Ctrl+Alt+Space toggle, clipboard-only output, no auto-submit,
no always-on mic/autostart/API post-processing/updater. App launched (latest PID22204).
Computer Use listed its window; detailed capture approval timed out. Native app headless
path verified. No personal mic started by agent. User microphone retest remains pending.
Handy version uses transcribe-cpp 0.2.4 for Whisper, not transcribe-rs (ONNX alternatives).
16 synthetic engine decodes: 4 critical failures, 9/102 errors; load 2.79s, first decode 12.89s,
warm median 0.282s. This is speed evidence, NOT accuracy acceptance or VAD/mic validation.
See [HANDY_TRIAL.md](../docs/brain/HANDY_TRIAL.md) for setup, limits, authorization and commands.
Production providers/defaults unchanged; no commit/push in this follow-up.

Latest user retest (2026-10-18): ASR remains inadequate on personal speech; new garbled
recognized outputs are recorded in [ASR_QUALITY.md](../docs/brain/ASR_QUALITY.md). Original
audio/verified reference text is unavailable. Historical synthetic improvements below do NOT
establish user acceptance. User requested ready GitHub solutions with no external API.
Researched Handy/transcribe-rs, faster-whisper, Qwen3-ASR and RealtimeSTT; report distinguishes
runtime wrappers from different recognition models. This research installed/downloaded nothing
and changed no production defaults. Native PCM boundary, no persistence and ONNX exclusion remain.

Latest speech-input quality follow-up (2026-10-18): user CONFIRMED normal spoken replies work.
Remaining complaint was ASR in Auto conversation: Steam request became an unrelated word,
Jarvis became Javi. This work changes native recognition, not the Brain/file planner.

Current default remains local CPU Whisper small, now beam_size=5 with bounded native catalog
spelling context (assistant name plus current installed-app display names; no caller prompt,
paths, IDs or transcript word-replacement). Native input route and RMS/peak/clipping diagnostics
reach Qt. Low/clipped input is visible. A new noise control caught white noise producing a
word: completed manual/Auto PCM now also passes the existing Silero speech model, preserving
original samples without trimming. Silence and three noise amplitudes then passed (0.10s).
No personal microphone capture, persistence, cloud ASR, ONNX or model training.

Explicitly provisioned/pinned large-v3-turbo F16 and Q5 comparison models; neither is the
default. Same 16 clean/noisy synthetic fixtures: old small/greedy 5 critical failures and
12/102 word errors; selected small/beam/catalog hints 2 failures and 5/102 errors. F16 had
4 failures/9 errors and Q5 2 failures/5 errors with much higher CPU latency. After final VAD
gate, selected profile repeated 2 failures/5 errors in 89.73s; short Auto language subset
6 decodes/2 failures in 65.16s. Both positive user examples passed clean/noisy in explicit
Turkish and Auto. Remaining failures are the synthetic negative command's app name and noisy
negation. Keep failing opt-in tests; this is NOT general ASR acceptance or microphone proof.

Actual Auto rolling Silero -> TurnDetector/preroll/endpoint -> ASR simulation: positive cases
4/4 passed; same two negative failures retained (61.86s). It did not reproduce clipping in
these fixtures. Public real human JFK recording passed final VAD/ASR (17.56s). Personal-room
and microphone quality remain for user retest. Listen=Türkçe reduces this host's short-clip
decode time versus Auto without changing English agent replies or pronunciation selection.

Final verification: 517 ordinary Brain/Qt passed /175 skipped (2.96s); 95 ordinary Rust passed
/6 opt-in ignored. Ruff check/format (117 files), Rust fmt and all-target Clippy -D warnings
passed. Windows linker transient output locks required serial retries and a fresh target/asr-verify
directory; no ACL/security changes. Verified compiled binary hash when copying to the launcher
path. Core restarted hidden as PID34456; status reports Whisper small CPU, model available,
default Microphone Array (AMD Audio Device), recording=false. Reopen jarvis -Desktop to load UI.
Observed HEAD f0e05ed (jarvis voice fixed); no commit/push by this agent in this follow-up.
See [ASR_QUALITY.md](../docs/brain/ASR_QUALITY.md) for exact commands, pins, logs and limitations.
Earlier file-discovery/default-app/authorization failures below remain unresolved.

Previous normal-output follow-up:

Latest normal-answer voice/discovery follow-up (2026-10-18): user heard Test voice but normal
answers were silent; also reported a natural Turkish Desktop-note request failing. Audit found
speech_start approximately 0.6s after speech_speak. SAPI RunningState=0 means queued, not done.
Rust now keeps output busy until WaitUntilDone(0) completes the whole queue; speech_poll adds
output_phase queued/speaking/idle. Qt waits for completion before automatic microphone rearm.
No fixed speech-duration estimate, saved microphone audio or Python device bypass was added.

Fresh checks: 516 Brain/Qt ordinary passed /175 opt-in skipped (3.60s); 90 Rust ordinary passed
/3 ignored, fmt and debug build passed. Ruff check/format passed (117 files); unchanged native
source passed Clippy on Oct16. Actual QML Send -> separate real 9B agent worker -> normal reply ->
Named Pipe -> Rust SAPI -> completion -> automatic rearm callback passed on Oct18 (25.78s),
also on Oct16 (25.52s). The final rearm callback is observed without opening a microphone.
Real EN/TR native output passed 2/18.12s on Oct16. This does not establish user-microphone
recognition accuracy or a new user confirmation of hearing normal replies.

Discovery distinguishes mandatory saved filename words (find_files.name_is_constraint) from
model-inferred topics/types. A failed name hypothesis permits one bounded metadata alternative
query only in the same verified folder, preserving other filters/exclusions. Alternatives are
explicitly not name/content/ownership matches. Missing folder spelling can return trusted root
labels through file_catalog_status; no global fallback. Inline name enumerations now obey the
existing single-suggestion contract. No sentence/document-specific production branches.

IMPORTANT: semantic acceptance still FAILS. Final synthetic unknown-name suite: 5 passed /1
failed (90.11s). The user's exact Turkish note sentence still omits Desktop scope and searches
literal not globally; English counterpart, photo, Turkish spreadsheet, mandatory-name negative
and empty-folder controls passed. Preserve the failing opt-in test. Interim 6/6 is NOT acceptance.
General English earlier run: 51/56 (419.83s); final focused 16: 12 passed /4 failed (168.55s).
One of those four was an overstrict test expecting a full filename query rather than equivalent
stem+extension; corrected, and that control passed in the final six. Real unresolved issues:
Turkish scope omission, inferred Excel on default XLSX opening, and authorizer accepting an
unrequested application parameter. Do not hide these failures or claim full-suite acceptance.

Diagnostic native-thinking comparison used the same local weights and fake Core only: English
passed in both modes; Turkish preserved scope on its first thinking step but later emitted an
unclosed reasoning/tool response and stopped. No raw reasoning logged or used as an action.
Production remains non-thinking; this does not prove model capacity is the sole cause.
See [VOICE_AND_DISCOVERY_FOLLOWUP.md](../docs/brain/VOICE_AND_DISCOVERY_FOLLOWUP.md) for logs,
exact validation commands and limits. Core rebuilt/started hidden as path-verified PID25816 on
Oct18; reopen desktop with jarvis -Desktop. No commit/push; inherited uncommitted work preserved.

Previous voice handoff (historical results):

Latest voice reliability follow-up (2026-10-16): user saw text but heard no answer, and reported
misrecognition. QML startup was forcing English ASR; this was removed and Listen now binds to
the controller's Auto default. Explicit en/tr remains available; final recognition returns its
detected language. Rust now discovers installed OneCore voices alongside SAPI without registry
changes (this host: Tolga tr, Zira en), selects pronunciation per request and supports bounded
speech-output device selection. Qt adds Output, Voice, Test voice and actual route feedback.
Recognition selection and pronunciation are separate; English agent text behavior is preserved.
User subsequently confirmed hearing BOTH live English/Turkish test sentences. This verifies
audible output for the tested Qt -> Core -> Realtek route; personal-microphone recognition
accuracy still requires separate evaluation. OMEN is also selectable.

Checks: 511 ordinary Brain/Qt passed /166 skipped (2.44s); 89 Rust ordinary passed /3 ignored.
Actual Qt -> Named Pipe -> Rust -> SAPI English/Turkish output: 2 passed /17.73s, start and
completion observed. Six synthetic installed-voice sentences, each explicit and Auto language,
passed 12 Whisper decodes /76.30s including negations. These clean synthetic fixtures do not
establish personal-microphone accuracy. Existing Whisper small model/decoder is unchanged.
Ruff, Rust fmt/Clippy and native build passed. Core was rebuilt and restarted hidden as PID26152;
reopen the desktop to load UI changes. No commit/push; prior uncommitted work preserved.
See [DESKTOP_VOICE.md](../docs/brain/DESKTOP_VOICE.md) for current evidence and exact commands.

Latest progressive recommendation follow-up (2026-10-16): the model chooses one best verified
file/folder/application candidate through suggest_result; CLI, Qt cards and voice present that
candidate only. Rejection removes only the proposed private identity, preserves alternatives
and carries exclusions into subsequent searches. Explicit list requests use show_results.
Identity confirmation alone does not authorize opening; an existing pending app-opening request
can complete after selection under the unchanged permission check and fresh Core resolution.
Bindings/rejections retain their original expiry; no new OS access or Rust changes in this follow-up.

Current checks: 508 Brain/Qt ordinary passed / 164 opt-in skipped (3.56s); six real Qwen9B
recommendation scenarios passed (179.76s), using synthetic metadata and a fake Core only.
The last full general English acceptance run was 55/56 (489.40s). Its remaining rejection →
unknown-filename case passed in a focused rerun (35.33s) after an exhausted-page observation
clarified that rejecting a suggestion is not a fresh search. The complete 56-case suite was
not rerun after that correction; do not describe this as a measured full-suite 56/56 pass.
Scope correction and default PDF opening passed in the full run. See
[RECOMMENDATIONS.md](../docs/brain/RECOMMENDATIONS.md) for exact commands and evidence.
Restart the Brain/desktop session to load Python/UI changes; no additional Core rebuild needed.
No commit/push. Earlier voice/desktop changes remain uncommitted alongside this follow-up.

Previous voice handoff (results below are historical):

Latest voice follow-up (2026-10-16): the hold-to-talk buffer error was a CPAL Xrun notification
being treated as fatal. Typed transient/fatal handling and bounded nonblocking callback delivery
replace that path. Real 12.05s microphone capture/finish passed with one Xrun on this host.
Opt-in Auto conversation uses local Silero v6.2.0 GGML CPU VAD (no ONNX), 200ms onset, 800ms
preroll and 900ms silence endpointing. It defaults off. Qt has waiting/listening/speaking
animations plus processing; actual SAPI completion controls rearm. Capture pauses for ASR,
agent reasoning and output. Six-second client lease discards pending PCM, including completed
turns. Manual/automatic maximum length rejects incomplete commands; cancellation drops late
transcripts. Voice controls are serialized; stale capture/output replies cannot revive a turn.

Current checks: 88 Rust ordinary passed / 2 opt-in skipped; actual VAD+ASR public fixture passed
in 19.21s; 17 Qt tests including real Qwen/Named Pipe passed in 14.37s; four actual device tests
passed in 49.88s. Combined Qt ordinary + Brain: 474 passed / 158 skipped (=458 Brain +16 Qt;
real Qt worker separately enabled). Ruff, Rust fmt/Clippy and debug build passed. An initial
pytest temporary-directory access issue was resolved with a fresh project-local --basetemp,
without ACL/security changes. Current project Core PID 49856 is the rebuilt serve process.
See [DESKTOP_VOICE.md](../docs/brain/DESKTOP_VOICE.md) for exact checks and historical first delivery.
No wake word, full duplex, saved recordings or Kokoro. This does not change the agent's semantic
acceptance (53/56 remains failed). No commit/push; earlier desktop work was already uncommitted.

Previous agent-loop handoff:

M001/M002/M003 and the application catalog refresh follow-up are implemented.
Latest work (2026-10-16): capability/result-feedback agent replaces production intent/TurnPlan
classification. Native provider templates, extensible capability/context/reference registration,
private bindings and current-effect assessment retain the Rust execution boundary. ONNX disabled.
The local development default is pinned Qwen3.5-9B GGUF; general assistant acceptance is NOT passed.
Latest user steering: JARVIS interaction is English; contributor communication remains Turkish.
Unicode filenames remain supported. English acceptance is separate from retained Turkish failures.
English final model acceptance: 53/56 passed (302.48s); general acceptance still fails.
Remaining: irrelevant name filter after direct-child scope correction; rejected results reappear;
pronoun/default PDF opening invents Adobe and is refused before any Core launch. See AGENT_LOOP.
Ordinary Brain checks: 452 passed / 157 opt-in skipped (includes archived tests, not model quality).
Rust: 79 test entries, fmt, Clippy -D warnings and debug build passed; use -j 1 if linking collides.
Actual new agent + Named Pipe live fixture: 1 passed / 24.33s, explicit process exit code 0;
Unicode TXT default opening and
explicit PDF/Chrome opening audited Source Brain, Allow, Success. No post-launch verification.
All fixture Core processes are owned/cleaned by the controller; no personal documents opened.
Restart the Brain session and Core after updating. No commit/push; inherited ahead-1 is preexisting.
See ../docs/brain/AGENT_LOOP.md for the current implementation, measured failures and handoff.
Older dated reports below describe their earlier code, not acceptance of this new loop.
Root AGENTS.md is only the automatic-discovery entry point; .codex remains tool configuration.

Historical implementation notes:
ConversationMemory + IntentContext.history integrated into Brain and both model prompts.
CLI /reset clears context. REPL retains memory; separate ask processes do not share memory.
User wants session-only memory. General chat remains outside the four-intent contract.
Engineering rules, architecture, tasks and working handoff are now canonical in this folder.
Validation results and limitations: ../docs/brain/SESSION_CONTEXT.md.

Validated: 131 ordinary tests, lint/format, real GGUF session correction. Both adapters pass
English contextual reference smoke. Known failure retained: ONNX 0.6B Turkish correction
returns clarify (opt-in diagnostic fails). General conversation quality is not accepted.
Use GGUF interactive session to try the working correction. See validation document for commands.

2026-10-06: user observed command-only behaviour and buried action notifications.
Readable ask/repl output now defaults to response.message; --json retains diagnostics.
Application success message shortened, still only after Core success. 132 ordinary tests pass.
General chat decision is pending user preference; do not misuse clarify for chat or change
closed intent enum without a documented, user-authorized task/architecture revision.
Checks for this follow-up: Ruff check/format, pytest services/brain/tests, git diff --check.

2026-10-06 reasoning follow-up: no new tools/intent. GGUF-only decision prompt; ONNX compact
prompt preserved after shared-prompt regression. 133 ordinary tests; GGUF diagnostic 17/18
(12 exposed regression + 5/6 additional diagnostics). Recall question still unnecessarily
clarifies; natural recall answer is not implemented. User preference for non-action respond
was asked, but no answer received. docs/brain/REASONING_DIAGNOSTIC.md owns details and checks.

User clarified actual goal: distinguish conversation from tasks before any tool dispatch.
Implemented request_routing.py and classifier/respond methods behind the model interface.
Conversation bypasses task decoder/legacy fast router/orchestrator; task parser still accepts
only four action intents. GGUF supports replies; ONNX conversational generation fails closed
after an observed fabricated action claim. Explicit selections remain deterministic safe tasks.
Current evidence and exact checks: ../docs/brain/REQUEST_ROUTING.md. No new OS tools.
During validation venv python.exe disappeared and restoration was denied; launcher now uses its
existing recorded base interpreter and packages when needed, without changing security settings.

Final request-routing validation: 156 ordinary tests / six opt-in skipped; two real-provider
routing safety tests passed. GGUF chat/recall and explicit task calls validated with mock Core.
ONNX chat deliberately raises typed ModelInferenceError; its task probes passed. All checks
used the existing base Python with current Brain source + venv site-packages in PYTHONPATH.
jarvis.ps1 has a parsed metadata-based fallback; original venv python.exe restoration remains
OS-denied, with no security settings modified. Latest feature contract: REQUEST_ROUTING.md.

Latest user transcript reproduced false capability denials and Turkish polite-action misrouting
even without history. Fixed admission examples and factual product capabilities in reply prompt.
Opt-in fixed-transcript recording uses mocked Core only, not automatic conversation persistence.
Evidence and exact checks: ../docs/brain/CONVERSATION_DIAGNOSIS.md. Regression integration now
covers Turkish greeting -> capability question -> two Chrome actions -> system inspection.

2026-10-07 user authorized terminal stress probes. Real GGUF + live Rust resolve_app:
Antigravity resolves but "idle" qualifier is unsupported; ChatGPT desktop wording unsupported
while shorter wording predicts open_application; ChatGPT/OMEN not found in live catalog;
Steam ambiguous. Critical exposed regression: "Steam'i açma" predicts task/open_application.
No apps launched and no production fix made. Evidence/commands: ../docs/brain/APP_REQUEST_PROBE.md.

2026-10-08 user authorized Windows packaged app discovery. Rust AppsFolder COM enumeration,
validated internal AUMID launch target, native activation after unchanged policy. Normal-user
live test enumerated 64 packages and real resolve_app found ChatGPT and OMEN Gaming Hub.
Restricted execution initially failed; successful explicit escalation distinguishes environment
access from implementation failures. No real app launched. docs/brain/WINDOWS_PACKAGED_APPS.md
owns evidence/commands/limitations; original model negation and qualifier failures remain.

Packaged discovery final: 65 Rust test entries, isolated live test (64 apps), Clippy/format/diff
clean. Rebuilt normal target/debug Core and reloaded only path-verified project process; final
Brain Named Pipe ping and ChatGPT/OMEN resolution succeeded. No real GUI launch performed.
Degraded discovery now warns and retains shortcuts; 60s check between COM calls, 10k item bound.

User requested contextual catalog refresh and declined post-launch verification. Implemented
registered Rust refresh_app_catalog + bounded next-turn Brain recovery after actual not-found;
120s one query, consumed once, reset/cancel/other-turn clear; fresh resolve and policy launch.
Standalone explicit commands refresh only. No model enum expansion. Live Named Pipe refresh and
missing follow-up passed without restarting Core (PID5740); no apps opened by live check.
174 ordinary Brain tests and 66 Rust test entries passed. docs/brain/CATALOG_REFRESH.md owns details.

2026-10-12: user authorized file-skills roadmap; first delivery implemented scoped Rust metadata
catalog/search/list and catalog-backed document/directory/containing-folder opening. Brain adds six
strict semantic intents, bounded file-result selection/pagination, and metadata inventory replies.
Defaults: native Windows Desktop/Documents/Downloads, optional local JARVIS_FILES_CONFIG TOML.
All machine actions retain Named Pipe -> registry -> validation -> policy -> executor -> audit.
No content reads, file modifications or post-launch verification. TASK_004.md defines the scope.
189 ordinary Brain tests, 74 Rust entries, two real GGUF safety/routing tests, one real ONNX baseline
test and one normal-user live read-only file catalog test passed. Ruff/Clippy checked. Existing test
EXE relinking intermittently failed with LNK1104; fresh target/file-skills-check completed the suite.
Evidence/commands/limits: ../docs/brain/FILE_SKILLS.md. Broader application negation remains open.
Natural date/folder filters in Brain, content understanding, watching/index persistence and file
mutations remain roadmap items. No commit or push was performed; inspect Git before continuing.

2026-10-12 launcher follow-up: user requested a global jarvis terminal command. Added bin/jarvis.cmd
and scripts/shell/install-jarvis-command.ps1; installer appends only this repository's bin to the
normal Windows user's PATH and broadcasts the environment change. No machine PATH or execution
policy changes. Command defaults to GGUF unless an existing backend environment value is set;
explicit launcher flags are forwarded. Installed for the current user. Repeated installation left
PATH unchanged. Verified Get-Command/where outside the repo without a PowerShell profile, and
launched the real REPL with exit piped in: GGUF selected, exit code 0, own Core stopped via
-StopCoreOnExit. Open a fresh terminal after installation. README documents registration.

2026-10-12 launcher correction: user reported GGUF was not selected. Centralized the default in
jarvis.ps1 (Model = gguf); inherited backend values no longer override the launcher default.
bin/jarvis.cmd only forwards arguments; the PowerShell profile helper no longer inserts a second
-Model argument, so explicit model selection works consistently. Normal-user verification loaded
scripts/shell/jarvis-profile.ps1 and ran 'exit' | jarvis -Model gguf -StopCoreOnExit, then ran
'exit' | bin/jarvis.cmd -StopCoreOnExit from TEMP with JARVIS_MODEL_BACKEND=onnx inherited.
Both reported QwenGgufIntentModel; the CMD launcher exited 0. git diff --check passed. Existing
terminal profile functions require reload or a new terminal. No execution policy changes.

2026-10-12 file-context correction: user transcript exposed global instead of relative searches,
strict name selection, lost browser clarification and unsupported application-qualified opening.
Delivered active folder context (120s), scoped relative searches, natural displayed-name selection,
concrete Google/local-Chrome clarification across evet, ambiguity/cancellation/expiry/changed-target
guards and a registered Rust open_file_with_app. Local PDF adapters support Chrome/Edge only;
Google Docs upload remains unsupported. Core natural-name search tolerates word separators.
202 ordinary Brain tests and 77 Rust entries passed; Ruff/Clippy passed. Real GGUF CV transcript
and normal-user live GGUF -> Named Pipe -> policy -> Windows synthetic PDF/Chrome launch passed.
Only synthetic PDFs were opened; no personal content reading or post-launch verification. Updated
normal Core was rebuilt/reloaded; ping and new-tool listing succeeded. Restart the Brain session
with exit then jarvis to load new Python code. Evidence/commands: ../docs/brain/FILE_SKILLS.md.
Changes remain uncommitted; no push. General model-question confirmation and other file-app/content
adapters remain later work; original broad application negation/qualifier issues are unchanged.
Final combined real-model run: five passed (three GGUF, two ONNX), including the exact CV transcript,
existing conversation/task safety and ONNX baseline. Ruff format, cargo fmt and diff checks passed.

2026-10-12 semantic file planning: reproduced user's “tr olan benimkisi onu açar mısın” refusal
with real GGUF and a previous false assistant capability claim. Model now receives bounded
displayed names/kinds, while IDs/locations stay private. Active file planning excludes free-form
assistant replies and keeps bounded user references; chat/recall memory is unchanged. Optional
open_file.application selects an explicit adapter; omitted/empty uses ordinary Windows association.
Semantic model target choices are strictly validated and bound to unique current Core candidates.
No phrase-specific patch or model training/artifact modification was needed. Relative searches
omit preceding candidates to avoid copying the previous folder kind into a file search.
218 ordinary Brain tests and four real GGUF integration entries passed; the normal-user live
synthetic-PDF test verified both default open_file and explicit Chrome opening. Ruff/diff checks
passed. Rust source unchanged; prior Rust test counts are historical. Normal Core restored.
Evidence/commands/limits: ../docs/brain/FILE_REASONING.md. Restart Brain to load new source.
Additional regression checks: existing GGUF conversation safety and ONNX smoke passed. ONNX
conversation/task safety initially failed with expanded prompts; kept new reasoning/admission
guidance on GGUF and restored compact ONNX prompts. Targeted ONNX conversation rerun passed.
Final Ruff check/format and ordinary suite passed; no claim of generalized ONNX file quality.

2026-10-14: user reported seven CV results -> “2. olanı açar mısın” -> global image search.
Added a separate select_file semantic contract (number/action/application), stable original UI
numbers in candidate context, a compact GGUF file planner and explicit current-page binding.
Selection cannot search for filenames. Numeric list notation constrains the target after admission;
wrong model search/row plans, invalid or expired pages clarify without machine queries. Default
association and explicit supported application choices are independent; consume before IPC.
258 ordinary Brain tests passed (14 opt-in skipped), three targeted real GGUF entries passed,
including six seven-result selection variants, four-type default opening and explicit semantic Edge.
The updated normal-user live seven-PDF fixture passed: exact “2. olanı açar mısın” selected the TR
PDF through open_file without another search; explicit Chrome also passed. Personal CVs were not
opened/read; no post-launch verification or model training. Fixture Core stopped, normal Core
restored. Rust source unchanged in this follow-up. Evidence: ../docs/brain/FILE_SELECTION.md.
Restart Brain to load new code; changes remain uncommitted, no push.
Final additional real-model regression run: three passed (GGUF conversation safety, ONNX
conversation safety, ONNX command/context smoke). Six final real-model entries total across
targeted/regression runs. Normal-user restored-Core ping returned ok; final Ruff/format/diff clean.

2026-10-14, natural file-goal follow-up: user reported ordinary lost-CV requests being refused.
Reproduced failed admission before Core. GGUF now classifies closed communicative purposes;
locate_file is retained in validated routing and directly selects a constrained metadata-search
planner through IntentContext.locating_file. Search planning identifies the wanted object before
extracting query/filters; its bounded description is discarded. Existing results cannot turn
another finding request into opening/listing. Other action/selection planners and ONNX admission
retain their separate contracts. Chat replies and unsupported claims are excluded from planning
history but preserved for conversation/recall. No sentence-specific router, training, model change,
new Core tool or OS bypass was added.
Final checks: 289 ordinary Brain tests passed (18 opt-in skipped), 12 real-model integration
entries passed (10 GGUF, 2 ONNX), Ruff check/format and git diff --check passed. Sixteen natural
file requests matched expected fixture names; six how-to/negative/hypothetical controls made
no machine calls. Tests also cover prior-denial recovery, repeated requests/topic changes,
folder/file scope, numbered selection, default/explicit opening and conversation safety.
One real normal-user Windows fixture entry passed: the exact three user sentences returned CV
results, a lost-presentation request found TXT without an inferred PPTX filter, relative scope
and default/Chrome opening worked. Only synthetic fixtures were used; no post-launch verification.
Fixture Core stopped and normal Core restored. Cache-write warning did not affect assertions.
Rust source unchanged in this follow-up; earlier Rust test counts remain historical. Evidence,
exact commands and language/metadata/date limitations: ../docs/brain/NATURAL_FILE_GOALS.md.
Restart Brain by exiting/relaunching jarvis to load source. Changes remain uncommitted; no push.

2026-10-14, subsequent user transcript and analysis: prior test interpretation was too broad.
The unchanged cross-domain natural-file test passes a fake model returning query="*" for all
16 inputs. Target inclusion on a small fixture is insufficient evidence of understanding.
Real GGUF with synthetic-only metadata reproduced desktop-note unsupported, “neden?” replaying
the tournament search, location loss, rejected/unknown-name turns blocked by fixed confidence
handling, global desktop listing and scope corrections becoming wrong operations. The user's
happy-chat-triggered search was not reproduced in the synthetic sequence; language mixing was.
24 context probes, a 14-turn traced sequence, 8 richer-schema probes and 30 rendering probes
were recorded under ignored target/assistant-analysis. Same model/current-message-last fixed
one “neden?” routing case; other rendering/schema changes were mixed, not a production fix.
Production still lacks goal/constraint/rejection state and tool-result feedback. locate_file
forces search-only output, so targeted clarification is unavailable in that provider branch.
Rust already supports scoped search, immediate-child listing and modification-time bounds;
Brain does not expose/bind all of them. Current 4B Q4 behavior is fragile, but model size versus
quantization versus prompting has not been isolated against another model. Do not claim that
upgrading/training or adding another prompt sentence alone solves assistant quality.
Added three repeatable diagnostic scripts and a detailed report with an acceptance/architecture/
model-comparison plan. No production behavior changed, no live personal file access/Core restart,
no model download/training, no commit/push. Previous test pass counts remain historical; they
are not acceptance of the reported dialogue behavior. See ASSISTANT_BEHAVIOR_ANALYSIS.md.

2026-10-15, authorized stateful assistant implementation (verification in progress):
GGUF handle_text now uses strict TurnPlan and AssistantSession with bounded goal, pending slots,
scope, rejection identities and verified outcome feedback. Current target/operation/constraints
are extracted separately. Current-purpose admission excludes old commands and displayed names;
reference binding and conversational recall retain their own bounded context. Model target quotes
must occur in the current message. Existing displayed-result selection is reused for version,
number and containing-folder references. Generic capability questions cannot select a shown row.
Retained goals support missing-name/location questions, rejection, direct/recursive scope changes,
one bounded same-scope type recovery, and new targets. Chat/explanation do not replay execution.
Native search adds closed categories, recursive/direct search and bounded private exclude_ids.
All actions still use Core/Named Pipe/registry/validation/policy/executor; no OS bypass, content
reading, mutation, upload, arbitrary app automation, post-launch checking or training was added.
User-visible paths/rows are not retained as model outcome feedback.

Latest ordinary checks: 369 passed, 40 opt-in skipped; Rust 78 entries, fmt/clippy/build passed.
Real-model acceptance is being rerun after failures uncovered by stronger controls; do not infer
that the full model suite is green from these ordinary counts. Historical ONNX 0.6B Turkish
context correction still fails its separate opt-in regression; the production GGUF default stays.
An isolated same-4B Q4/Q8 raw diagnostic scored 22/28 for each (14 probes, two repeats), with the
same ownership/identity/scope errors. Q8 was explicitly downloaded to a verified temporary cache;
production model/checksum/defaults unchanged. See ASSISTANT_DIALOGUE.md for artifact and limits.
Working tree includes preserved earlier uncommitted file-skill/launcher work; no commit/push.

2026-10-16, user counterexample and reassessment:
The supplied session already ran GGUF, not ONNX. Correct certificate discovery worked, but a
single-result pronoun opening asked for clarification. Misspelling and short location/type
answers lost the subject. Recommendation requests elicited an invented capability prohibition.
User explicitly disabled ONNX: factory defaults GGUF, rejects ONNX, no fallback/import; launcher
accepts only GGUF; mandatory GenAI dependency/public model export removed. Historical source and
tests remain archival. No package/model deletion, training, download or production model change.

Fixed two concrete metadata omissions in runtime/reply-template rendering. A text reply receives
bounded current names/kinds/numbers, never IDs/paths; conversation preserves the current task/page
without renewing TTL or authorizing actions. Cancel/reset/expiry remain clearing operations.
Real reply-component checks passed for warranty, service invoice, school timetable and absent
metadata. This does not repair admission: a recommendation request can still become a new search.

Current ordinary Brain: 391 passed, 51 opt-in skipped. New real-model dialogue regressions:
4 passed, 3 FAILED (typo before search, singleton pronoun opening, metadata opinion routed to search).
Do not mark them xfail or claim the assistant is ready. Earlier named Edge selection also remains
unaccepted. Flat-contract ablation got only action labels 6/8; not a retrieval score. Free text
also made mistakes, so neither architecture nor capacity alone is established as the sole cause.
Two failed single-pass TurnPlan prototypes stayed in ignored target; not deployed. Current-only
query substring restriction and fragmented planning are documented, not silently fixed with more
sentence rules. Core untouched this turn; no live personal file access/restart or commit/push.
Exact tests, local artifacts and next acceptance design: ASSISTANT_REASSESSMENT.md.
