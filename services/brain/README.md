# JARVIS Brain development client

This Python 3.12+ package is the non-AI TASK-002 client for the trusted Rust Core. It contains
only the local Windows Named Pipe transport, protocol models, a high-level Core client, and a
development CLI. It does not discover or launch applications, inspect system state, or implement
Rust tools.

Create an isolated environment and install the package with its development checks:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

With `jarvis-core serve` running, use:

```powershell
.\.venv\Scripts\python.exe -m jarvis_brain.cli ping
.\.venv\Scripts\python.exe -m jarvis_brain.cli tools
.\.venv\Scripts\python.exe -m jarvis_brain.cli status
.\.venv\Scripts\python.exe -m jarvis_brain.cli open-app "Google Chrome"
```
