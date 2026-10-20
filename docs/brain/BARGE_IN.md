# Native voice interruption — 20 October 2026

The user requested speaking over JARVIS's normal spoken replies, without pressing a button,
then continuing with a new request in the same conversation. Auto conversation now arms
echo-cancelled microphone capture before queueing reply speech. Confirmed speech onset
purges the current native speech queue; the same capture keeps the user's beginning, ends
on silence and supplies its final transcript through the normal Brain path. The old reading
does not resume. This interrupts speech presentation, not an already completed machine action.

## Execution and audio boundary

The existing registered `speech_start` accepts `barge_in: true` only with `automatic: true`,
plus optional bounded input/output indices. All parameters still pass registry validation,
policy and executor. No new tools or model capabilities are added (30 native tools remain).
Manual/ordinary capture keeps its earlier half-duplex behavior.

Rust uses Microsoft's built-in Voice Capture DSP (`CWMAudioAEC`) in source mode. Exact native
CPAL microphone identity and the SAPI output token's `DeviceId` bind active IMMDevice indices;
there is no caller/model-supplied endpoint ID or display-name guess. The DSP owns microphone
and render synchronization and produces 16kHz mono clean PCM. An all-zero shared render stream
keeps that same endpoint active before/after SAPI speech, as source mode requires an active
render stream. It changes no mixer settings. COM objects stay on their owning threads.

The existing pinned CPU Silero GGML model and TurnDetector inspect cleaned PCM, not raw
amplitude or recognized keywords. The 800ms preroll retains onset; two positive 100ms frames
start a turn. Native onset purges only this AudioService's SAPI queue before the next UI poll.
`speech_poll` returns an `interrupted` flag, phase, level and typed failure metadata; no PCM
or private endpoint identity leaves Rust. The same six-second client lease, 30-second
utterance bound, 900ms silence endpoint and final native speech-presence check still apply.

The UI invalidates old speech acknowledgements, keeps capture while the reply completes or
is interrupted, and sends a completed transcript once through the existing session. Cancel,
close, late callbacks, microphone changes and render-route failures cannot submit partial
audio or revive old speech. Error/expiry teardown also purges the associated output queue.
Recognition and agent reasoning remain sequential; there is no concurrent LLM inference or
streaming-token cancellation. This runtime finishes generating a reply before speaking it.

The startup countdown and welcome retain the user's earlier requirement: microphone closed
until actual model readiness and completed welcome output. If AEC opening fails for chosen
devices, an explicit UI message reports interruption unavailable and retains turn-by-turn
voice for that session. It never silently enables raw simultaneous playback/capture.

No cloud/API, ONNX, microphone recording, new model/runtime download, audio driver,
virtual device or wake-service change is involved. `windows-core` was already transitive;
it is now direct for the existing Windows COM implementation macro.

References used for the implementation:

- [Microsoft Voice Capture DSP](https://learn.microsoft.com/en-us/windows/win32/medfound/voicecapturedmo)
- [Native device-index binding and render-stream requirement](https://learn.microsoft.com/en-us/windows/win32/medfound/mfpkey-wmaaecma-device-indexesproperty)
- SDK `wmcodecdsp.h`: property GUID/PID constants and AEC-only mode.

## Validation

| Check | Result |
|---|---|
| Full ordinary Rust workspace | 136 passed / 9 opt-in ignored |
| Full ordinary Brain/Qt | 608 passed / 205 opt-in skipped |
| Workspace all-target Clippy, warnings denied | Passed |
| Rust formatting and Ruff | Passed |
| Native source + actual default mic/SAPI, no agent | Passed: 90 polls/9s, waiting throughout, no self-interruption |
| Actual Windows AEC filter + synthetic double talk + Silero | Passed: echo residual energy ratio below 0.15; speech retained |
| Actual Qt/QML + deployed Core + default mic/SAPI | Passed: speaking to waiting, AEC capture retained, no self-trigger |

The synthetic filter fixture combines a delayed English playback reference with a different
Turkish near-end sentence. It runs the actual Windows DSP in **filter mode**, then the actual
Silero/TurnDetector pipeline; no device or agent is used. Near-end speech starts at 6000ms and
was detected at 6300ms in this sample. This is one controlled latency sample, not a hardware
or microphone response-time guarantee. The production source-mode test separately uses the
real microphone and SAPI output. The real Qt test enters the normal response handler with a
fixture reply and actual Core/audio/QML; it does not pretend that a new 9B inference ran.

Fifteen added ordinary Qt cases cover pre-arming, continuous waiting, interruption before or
after speech acknowledgement, no reply resurrection, complete-turn-only submission, late
start after stop/close, explicit fallback, missing AEC confirmation, input/output changes and
late transcription cancellation. Native tests retain invalid-argument/zero-dispatch checks,
test denied/allowed duplex device binding, and reject COM-buffer overflow.

Initial failures were corrected rather than hidden: CPAL discovery had already initialized
the capture thread's STA apartment, so requesting MTA failed with RPC_E_CHANGED_MODE. The AEC
component now uses that same STA. The first Qt live test stopped at a fixed 12 seconds while
the Turkish sentence was still speaking; it now awaits actual speaking-to-waiting completion
with a 35-second deadline, and passed in 19.81s. This changed the test deadline, not speech
completion logic. A OneDrive-hosted stale test EXE caused a linker overwrite failure; only
the verified target output was renamed, without changing security settings or running apps.

Commands use the existing documented native build environment, Python package paths and
offscreen Qt. Pause the original running wake listener around direct microphone tests and
restore its original state in `finally`; do not test beside another active desktop.

```powershell
cargo test --workspace --locked --target-dir target/organizer-validation -j2
cargo clippy --workspace --all-targets --locked --target-dir target/organizer-validation -j2 -- -D warnings
cargo fmt --all --check
cargo test -p jarvis-core --lib --locked --target-dir target/organizer-validation real_filter_removes_echo_but_preserves_double_talk -- --ignored --nocapture
cargo test -p jarvis-core --test audio_pipeline --locked --target-dir target/organizer-validation real_echo_source_keeps_own_speech_out_of_a_turn -- --ignored --nocapture
python -m pytest -o addopts='' -p no:cacheprovider --basetemp <fresh-target-dir> services/brain/tests scripts/tests/test_desktop_qt.py -q
python -m ruff check services/brain services/desktop/main.py scripts
python -m ruff format --check services/brain services/desktop/main.py scripts
# Actual Core running; pause wake around this explicit test:
$env:JARVIS_RUN_BARGE_LIVE = '1'
python -m pytest -o addopts='' scripts/tests/test_desktop_qt.py -k real_qml_reply_arms_aec -q -s
```

Local evidence: `target/barge-rust-final.log`, `target/barge-python-final.log`,
`target/barge-clippy.log`, `target/barge-source-live.log`, `target/barge-filter-live.log`,
`target/barge-qml-live.log`. No personal task/file data was used or modified.

## Remaining validation

The user's own simultaneous speech, far-field distance, loud speakers, music, Bluetooth,
different microphones and room echoes have not been accepted by these bounded tests. The
feature does not improve or train Whisper; prior ASR errors remain possible. AEC can suppress
quiet near-end speech or leave residual echo in difficult acoustics. Source/filter fixture
success is not general acoustic acceptance. Retest with the user's real voice in the normal
desktop before claiming that quality. Wake and older organizer/model limitations remain open.

For a personal test, reopen `jarvis -Desktop`, keep Auto conversation enabled, ask for an
explanation, then speak a different request while JARVIS is talking. Its voice should stop,
the orb should show listening, and the new completed request should enter the same session.
