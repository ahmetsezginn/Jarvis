# JARVIS Windows wake service

This is an internal component of the same JARVIS product and Cargo workspace, not a second
application to install manually. Windows SCM runs the small native `JarvisWake` service under
LocalService. Qt, Python, the language model and ordinary speech recognizer need not remain open.
The acoustic detector is still being evaluated; **general wake acceptance is not complete**.
The first PocketSphinx detector failed the user's real voice test on 2026-10-19. The current
candidate uses openWakeWord's pinned TFLite graphs and Google's native LiteRT 2.3.0 CPU DLL,
called by Rust through the official C ABI. Only the standalone DLL is extracted from the
official distribution; no Python wheel/package is installed or imported by the service.
The published model also triggers on the synthetic name-only sample and misses the Turkish
synthetic sample. This is experimental infrastructure, not a claim of Siri-level wake quality.
After replacing that detector, the user confirmed a real microphone activation worked.
One confirmed live success is separate from the remaining false-wake/locale failures.

Run `install.cmd` in the repository after completing the existing Brain/Desktop prerequisites.
It registers the user command, explicitly provisions the small pinned wake assets, builds the
native executable and requests Windows UAC only for the protected installation/SCM/task step.
`install.cmd -SkipWakeService` installs only the command. `install.cmd -RemoveWakeService`
stops/removes the service and its fixed launch task; models, organizer data and Qt are retained.
This is the developer/local-host installer, not a bundled MSI with language-model downloads.
No machine/user execution-policy setting is changed; the setup cmd opts into its own PS process.

Installed binaries/configuration live in `%ProgramFiles%\JARVIS\Wake`, writable only by
Administrators/SYSTEM. Status lives in `%ProgramData%\JARVIS\Wake\status.json`; LocalService
can write only this status directory. The installed configuration binds one Windows account
and one fixed repository. Moving that repository requires rerunning installation.

The service never evaluates a transcript, arbitrary executable, shell command or agent output.
It can request only the fixed `\JARVIS\Launch` Windows task. That task uses the signed-in owner's
interactive token at limited privilege, without a saved password. Its protected native launcher
starts the existing fixed JARVIS bootstrap. The service itself never runs user-editable code
as LocalService/SYSTEM. All subsequent AI machine actions still use Core validation and policy.

`jarvis -Desktop` and microphone activation use the same service/task. Repeated activation does
not start another model. The service drops its microphone before launching; while the task is
running it remains paused internally. Normal window/chat close terminates Qt and its Brain
worker, and the listener rearms. The native parent owns a kill-on-close Windows job for its
new descendants; existing shared Core processes are not killed.

Only the installed owner in the unlocked active console session may trigger activation. This
first implementation supports one owner; remote-desktop/multiuser activation is not supported.
Windows Services can Pause/Resume/Stop `JARVIS Wake`. The installed owner has those rights but
cannot change its binary/configuration. The default desktop profile is GGUF qwen35-9b.
`install.cmd -WakeMicrophone "exact Windows device name"` selects a particular native input;
if it disappears, capture reports an error instead of switching silently. Otherwise Windows'
default input is used and followed when it changes. `install.cmd -DefaultWakeMicrophone`
clears a prior explicit pin; this is the current user's selected mode after removing the USB mic.
Old PCM/features are dropped before opening the new default. `input_name` shows the actual route.
The pretrained wake model is CC BY-NC-SA 4.0; this local personal prototype does not establish
commercial distribution rights. Runtime/code licenses are included in the installed package.
CLI sessions or directly launched development Python windows do not participate in the desktop
task's single-instance tracking; stop/pause the listener while using such diagnostic sessions.
There is no Qt tray resident, cloud speech, startup/runtime download, ONNX restoration or
microphone recording. Bounded PCM remains in native memory; status reports only signal level,
counters, phase, errors, memory and CPU time. Per the latest user preference, Qt starts Turkish
Auto conversation after real model readiness and completed Turkish welcome output. During load
it announces an estimated countdown with its microphone closed. Qt follows Windows' default
independently of any optional fixed wake pin. Native Core reports route changes so interrupted turns are
cancelled before reopening; a manual fixed-device choice never silently switches.

Validation and open acoustic limitations are recorded in
[WAKE_DAEMON_PLAN.md](../../docs/brain/WAKE_DAEMON_PLAN.md).
