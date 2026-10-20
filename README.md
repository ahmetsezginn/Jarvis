# JARVIS

A local AI assistant for Windows. Find files, open applications, manage tasks and notes,
and talk through a Qt desktop interface. AI reasoning runs locally; Rust validates and
executes computer actions.

## Install and start

The installer is distributed separately as **JarvisInstaller-0.3.0-preview.1.exe**.
Installer binaries, model weights and build tooling are deliberately excluded from Git.

1. Run the provided installer. Python and Rust are **not** required on the recipient's PC.
2. Choose **CPU** or **NVIDIA GPU**. CPU mode is slower; NVIDIA mode is intended for a
   compatible GPU with about 8 GB VRAM and a current driver.
3. Keep an internet connection for setup: approximately **6.3 GB of models** are downloaded
   from pinned sources and checked with SHA-256. Allow **20 GB free disk space** for setup.
4. Optionally enable **Hey Jarvis**. Installing its Windows service requires administrator
   approval. You can use the desktop without this service.
5. Open **JARVIS** from the Start menu or desktop shortcut.

Requirements: Windows 10/11 x64 and a recent 64-bit processor. **16 GB RAM is recommended;
32 GB gives more headroom.** CPU performance varies considerably between computers.
GPU mode does not silently fall back to CPU: select the appropriate mode during setup.

After provisioning, conversation and speech recognition run locally. Startup does not
fetch models or call a cloud inference API. Microphone recordings are not saved.

An optional offline setup can use a folder named `offline-models` beside the installer,
containing the three exact pinned model files. Incorrect hashes stop installation.
The installer and offline assets are shared separately, not through this repository.

## Everyday use

- Ask for help finding a document or opening an installed application.
- Add tasks, ask what is due today, complete a task, copy yesterday's agenda or make tasks
  repeat daily. Save and recall personal notes in the same conversation.
- In **Auto conversation**, speak over a normal reply to interrupt it and give a new request.
- Press **Escape** or **End conversation** to stop automatic listening. **Hold to talk**
  remains available for manual input.
- Closing the window or asking JARVIS to close exits the desktop and releases its model.
  The optional small wake service remains available independently.

The desktop starts with Turkish listening/voice. Its primary reasoning profile is English;
original Unicode filenames are preserved. During model preparation, the microphone stays
closed. Listening begins after actual readiness and the completed welcome.

If command registration was selected, open a new terminal and use:

```powershell
jarvis                      # Terminal conversation
jarvis -Desktop             # Desktop
jarvis "What is due today?"  # One request
```

Settings and installed files live separately from your saved notes/tasks. The installer
uses your Windows application directory; personal organizer data stays under
`%LOCALAPPDATA%\JARVIS`. `/reset` clears conversation context, not saved records.
Uninstall through **Windows Settings > Apps**; personal notes and tasks are retained.

## Current capabilities and limits

| Available | Scope |
|---|---|
| Application discovery and opening | Windows catalog-backed applications |
| File search, folder browsing and opening | Metadata in configured roots; Windows default opener |
| Explicit PDF opener | Existing Chrome/Edge adapters |
| Steam game shortcuts | Validated Steam targets only |
| Personal tasks and notes | Persistent local storage, daily recurrence and day copying |
| Local voice | Hold-to-talk, Auto conversation and echo-cancelled interruption |
| Hey Jarvis | Optional independent native Windows service |

This is an **experimental preview**. Speech recognition, wake accuracy and ambiguous
file/task/date interpretation still have documented failures. File scans can be partial;
searching metadata does not read document contents. File deletion, cloud sync, timed alarms
and downloaded executable skills are not implemented.

The pretrained wake models use **CC BY-NC-SA 4.0**. This preview is for personal/non-commercial
evaluation; see [wake notices](services/wake/resources/THIRD_PARTY.md). Other bundled components
retain their own licenses, included with the installer.

## Architecture

```text
Text / voice / Qt desktop
          |
Python Brain — local model + capability/result loop
          |
JarvisCoreClient -> Named Pipe
          |
Rust registry -> validation -> policy -> executor
          |
Windows / applications / local organizer
```

The default model is **Qwen3.5-9B Q4_K_M GGUF**. Native speech uses transcribe.cpp,
Whisper Turbo Q5, Silero VAD and Windows SAPI. ONNX is disabled. The model cannot supply
arbitrary shell commands, executable paths or trusted catalog IDs.

## Run from source

For contributors, provision the [Brain](services/brain/README.md#current-runtime-capability-agent-2026-10-16),
then follow [desktop/native speech setup](services/desktop/README.md#explicit-setup).
Choose the pinned CPU or CUDA requirements for your environment; do not install both
runtime variants into the same environment. The root `install.cmd` is a **developer checkout
setup helper**, not the distributable end-user installer.

```powershell
.\jarvis.ps1                 # Prepared source checkout: terminal
.\jarvis.ps1 -Desktop        # Prepared source checkout: desktop
```

- [Current state and validation](agent/STATE.md)
- [Architecture and engineering rules](agent/README.md)
- [Local organizer](docs/brain/PERSONAL_ORGANIZER.md)
- [Voice interruption and measured limits](docs/brain/BARGE_IN.md)
- [Installer validation and cleanup](docs/brain/DISTRIBUTION_2026-10-20.md)
