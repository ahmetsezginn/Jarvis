# JARVIS desktop and local voice

Start from the registered command:

```powershell
jarvis -Desktop
```

`jarvis` without this switch keeps the existing terminal session. The desktop uses the same
Qwen3.5-9B agent and session bindings. The fixed worker is a separate process so Qt remains
responsive. No HTTP server, account or cloud speech service is required.

The worker starts loading the checked local model immediately on opening. The microphone stays
closed during preparation, in both automatic and manual modes. JARVIS announces activation and
an estimated remaining time; the UI countdown uses a monotonic clock. The current host default
is8 seconds, based on its measured7.9s 9B load, not an automatically learned history or exact
progress. If exceeded, the UI says preparation continues; only the actual model_ready event
ends activation. Once ready, stale preparation speech is cancelled, then JARVIS says
"Sistem aktif. Merhaba, nasıl yardımcı olabilirim?". Capture starts after actual native output
completion. Escape cancels automatic startup. Muted output still waits for model readiness.
The former early-audio/deferred-ASR flow has been removed. Typed-only/opt-out clients retain
their bounded worker input pipe. Closing ends the worker and releases the model; the small wake
service never retains it. Ordinary speech recognition and response generation still take time.

Ask JARVIS to close its own application or use the window X. Both end the desktop process;
the fixed Brain worker exits and the large language model is released. Session-only conversation
ends; saved personal tasks/notes remain in native storage. There is no tray-resident assistant
or embedded wake listener. An independent native Windows service is now part of the same product
and `install.cmd`; see [service setup and current acoustic limits](../wake/README.md).
Manual desktop opening remains `jarvis -Desktop` and uses the installed service's single task.
The desktop starts with Turkish recognition/voice and Auto conversation, including wake launches.
After device discovery and model activation, it waits for the welcome output to finish before
opening capture. Both wake and desktop follow the Windows default microphone. When that
default changes, the interrupted turn is discarded and automatic capture rearms on the new
default; it never joins speech from different microphones. Escape/End conversation stops listening.
An explicit device selected manually remains fixed; device errors do not silently change it.

Type and press Enter (Shift+Enter adds a line). Hold **Hold to talk** while speaking and release
to transcribe/send. Recognition uses multilingual Whisper Turbo Q5 through native transcribe.cpp with bounded
spelling context from installed application names. Recognized words are never replaced by
application-name rules. **Listen** starts at Türkçe;
choose Türkçe or English explicitly for short utterances when automatic language detection is
unreliable. The actual input-device name, last detected language and signal level appear below
the controls. Low level or clipping is shown there; these diagnostics are not a confidence score.
Choose an input device from the list, or leave the system default. A turn is limited to 30 seconds;
hitting the limit discards the unfinished turn instead of sending it. **Cancel recording** or
**Cancel transcription** discards that pending voice input. **Stop voice** stops output.
**Speak replies** mutes/unmutes spoken answers. These controls do not undo an already executed task.

**Auto conversation** starts on, so you can speak without holding a button. The waiting
orbit means the microphone is monitoring for speech; moving green bars mean speech was detected
(their height follows the actual input level); the flowing violet/cyan animation means JARVIS is
speaking. After about 900ms of silence, the completed utterance is transcribed and sent through
the same agent session. The processing state covers transcription and reasoning. After actual
speech output completion, JARVIS automatically returns to waiting. With **Speak replies** off,
it returns after the text reply. **End conversation** or Escape turns automatic listening off.
The microphone is paused while JARVIS processes or speaks; hold-to-talk can interrupt its voice.
A running decoder finishes in Rust, but cancelling transcription discards its late result and
never dispatches it. The UI itself has no wake-word detector; the independent service opens it.
Queued synthesis/device startup also keeps output busy; automatic listening waits for the
whole native speech queue to complete. Test voice alone does not exercise normal agent replies;
the live regression now includes the actual QML Send button and real agent worker.
When locating an item, JARVIS recommends one likely match first, using your goal and current
metadata. The same suggestion is spoken and shown as one card. Say it is not the right one to
move to another candidate; rejected items do not return during that binding's lifetime. A yes to
"could this be the one?" after locating a file confirms identity; ask to open it when that is
what you want. A pending app-opening request can complete after the intended app is identified;
this uses the original request, current selection assessment and fresh Core resolution. Ask for
all options to see the remaining page. Clicking a card is an explicit request to open that item.
Result cards open the bound current item; old page tokens and expired bindings cannot open
different items. **New session** clears conversation and private result bindings.

Current host profile: 32 GB system RAM and the existing 8 GB GPU/Qwen configuration. Whisper
Turbo Q5 runs on the dedicated Vulkan GPU with at most six CPU threads. Its weights are released
after recognition so the same GPU serves Qwen reasoning. The first speech request verifies the
model and can take longer. No startup download occurs. This is the first local
version: endpointing uses release in push-to-talk, or local CPU Silero GGML speech detection
and silence in Auto conversation. No ONNX package or cloud speech is involved. Wake-word
detection, full-duplex echo cancellation and neural Kokoro output are not included. TTS currently
uses installed English/Turkish Windows voices, including OneCore language-pack voices. Choose
the pronunciation language with **Voice**, the destination with **Output**, then use **Test voice**
to hear a fixed local sentence without sending anything to the agent. The selected voice and
actual output name appear below the controls. An unavailable language/device reports an error;
it does not silently use a different voice. Voice changes pronunciation, while response text
retains the existing English agent behavior. This does not change Windows registry settings,
system mixer volume, or other applications' audio preferences.

ASR comparisons and remaining errors are recorded in [ASR_QUALITY.md](../../docs/brain/ASR_QUALITY.md).
The current host default is transcribe-cpp / large-v3-turbo-q5_0 / dedicated GPU. Set
`JARVIS_SPEECH_DEVICE=cpu` for explicit CPU use. For the historical small CPU provider set
`JARVIS_SPEECH_ENGINE=whisper-cpp` and `JARVIS_WHISPER_PROFILE=small` before starting Core.
`JARVIS_WHISPER_DECODER` applies only to that legacy provider. No silent fallback/download.
See [native integration](../../docs/brain/NATIVE_SPEECH_PROVIDER.md) for actual tests and limits.
Speech stops before recording begins to avoid feeding the assistant's voice into its own mic.

## Explicit setup

Use the existing Brain interpreter/environment. If its venv executable is missing on this host,
`jarvis.ps1` already reads its recorded base interpreter and retains installed Brain packages.
Install desktop packages separately; do not upgrade the Brain environment:

```powershell
python -m pip install --target services/desktop/.venv/Lib/site-packages -r services/desktop/requirements.txt
python -m pip install --target services/desktop/.venv/Lib/site-packages -r services/desktop/requirements-build.txt
python scripts/models/provision_speech.py
./scripts/models/provision_transcribe.ps1
./scripts/shell/build-voice.ps1
jarvis -Desktop
```

Run the two Qt packages together in the same installation. To repair an existing partial target,
add `--upgrade` to that desktop-only installation. Building requires MSVC and the build packages.
The pinned Whisper crate needs Windows-generated bindings: `LIBCLANG_PATH` points to
`services/desktop/.venv/Lib/site-packages/clang/native`; `CMAKE` points to its `cmake/data/bin/cmake.exe`.
The build script sets these temporarily and restores them. Stop an existing project Core before
rebuilding its executable, then restart it. Do not bypass PowerShell execution policy.

Python 3.12 and PySide6 Essentials/Addons 6.10.3 were verified on this host. Qt licensing is
provided by the distributions; no Qt source changes or private font redistribution are included.

## Boundaries and data

Qt requests microphone/speech operations only through `JarvisCoreClient`. Registered Rust tools
validate input and pass policy/audit before touching CPAL/WASAPI or Windows SAPI. The microphone
stream belongs to a Rust worker thread. Captured PCM remains in bounded Rust memory and never
enters the JSON control channel. Recognition happens natively through transcribe-cpp Rust bindings;
only final text crosses the pipe. The regular Python agent remains responsible for interpretation,
planning and all user-requested computer tasks. Speech tools are not advertised to the model.

Recordings and transcripts are not persisted by the voice layer. Native decoder diagnostic logs
are disabled to prevent recognized words from leaking into Core logs; typed failures and Core
audit events remain enabled. UI chat lives only in memory. Detailed file paths are displayed in
result cards, outside model history; speech uses a short result summary instead of reading paths.
Automatic listening follows the desktop startup preference and can be stopped in this window. A six-second
client heartbeat lease closes abandoned capture and discards pending PCM, including completed
turns. Default-input changes discard/rearm; other fatal device errors stop automatic mode. A transient driver buffer notice no longer fails
a whole healthy recording; sustained/internal audio loss is reported and never sent as a command.
No embedded wake detector, telemetry or microphone permission changes occur.

The Qt client may read its fixed QML/font resources and spawn only the fixed Python session worker.
It cannot execute model-provided commands or choose executable paths. The worker does not launch
Core; the existing trusted launcher handles that bootstrap.

## Checks

With repository root, Brain source/packages and desktop packages on `PYTHONPATH`:

```powershell
python -m pytest services/brain/tests -o 'addopts=' -q
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_QUICK_BACKEND = 'software'
python -m pytest scripts/tests/test_desktop_qt.py -o 'addopts=' -q
# Requires an already running current Core; actual local Qwen, no test file/app launch:
$env:JARVIS_RUN_DESKTOP_LIVE = '1'
python -m pytest scripts/tests/test_desktop_qt.py -o 'addopts=' -q -s
# Preload before any message and then answer using the ready model (pause wake service first):
$env:JARVIS_RUN_DESKTOP_PRELOAD_LIVE = '1'
python -m pytest scripts/tests/test_desktop_qt.py -k real_model_preloads -q -s
# Estimated activation -> real model readiness -> completed welcome -> microphone:
# No other desktop; pause wake service for this direct development test and restore afterward.
$env:JARVIS_RUN_DESKTOP_STARTUP_LIVE = '1'
python -m pytest scripts/tests/test_desktop_qt.py -k real_startup_worker -q -s
# Actual microphone/recognition and local speaker; transcripts are never dispatched or printed:
$env:JARVIS_RUN_VOICE_DEVICE_LIVE = '1'
python -m pytest scripts/tests/test_voice_device_live.py -o 'addopts=' -q -s
```

Qt tests use a local offscreen surface. Reset/remove those two Qt rendering environment variables
before opening the interactive application. Current evidence and exact native test commands:
[DESKTOP_VOICE.md](../../docs/brain/DESKTOP_VOICE.md).
