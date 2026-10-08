# Terminal application probes — 2026-10-07

User requested hands-on terminal stress testing after Antigravity/OMEN/ChatGPT failures.
Ran the real GGUF model and the project's real Rust Named Pipe Core. Only resolve_app was
executed; no application launch occurred. The diagnostic invokes task prediction even for
conversation to inspect it, but never dispatches those predictions. This is not production routing.

Evidence: artifacts/diagnostics/app_requests.json. Ten phrases, each in empty context and
after one previous false capability refusal: 20 admission and 20 task predictions. Eight direct
catalog queries, independent of model interpretation. This exposed fixture is not a benchmark.

| Request | Model result | Real catalog result |
| --- | --- | --- |
| antigravity idle | unsupported fresh; clarify after refusal | Antigravity resolves |
| Antigravity application | open_application both contexts | Antigravity resolves |
| Antigravity IDE | open_application fresh; unrelated clarification after refusal | probe queried Antigravity, not Antigravity IDE |
| Omen Gaming Hub, two phrasings | open_application both contexts | full name and OMEN not found |
| chat gpt masa üstü application | unsupported both contexts | ChatGPT not found |
| ChatGPT application | open_application both contexts | ChatGPT not found |
| Steam application | open_application both contexts | application_ambiguous |
| Chrome nedir? | conversation both contexts | no Core call |
| Steam'i açma | INCORRECT task/open_application both contexts | no Core call |

PowerShell metadata inspection found two differently named Antigravity shortcuts and two Steam
shortcuts across scoped Start Menu roots. Get-StartApps/Get-AppxPackage filters returned no
OMEN/ChatGPT entries in this process context; this does not prove the applications are uninstalled.
The implementation scans only scoped Start Menu shortcuts, so coverage is still incomplete.

Findings: semantic interpretation changes with qualifiers and previous refusals. The model is
not learning repeated app names during these runs. Rust really searches its catalog when called.
Do not claim the negation case is safe: both admission and task prediction failed on this phrase.
No production correction was made by this diagnostic change. Next fixes need general target
extraction, negation regressions, and broader trusted platform discovery, rather than per-app
whitelists. Existing strict schemas and Rust policy cannot detect a semantically reversed user
request on their own.

Commands from repository root:

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$env:JARVIS_MODEL_BACKEND = 'gguf'
$probePython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $probePython scripts/evaluation/probe_app_requests.py --output artifacts/diagnostics/app_requests.json
& $probePython -m ruff check scripts/evaluation/probe_app_requests.py
& $probePython -m ruff format --check scripts/evaluation/probe_app_requests.py
git diff --check
```

The initial ping timed out; started target/debug/jarvis-core.exe serve in a hidden process.
Subsequent real resolution and tool-list requests succeeded. The diagnostic saves only fixed
test phrases, validated predictions, canonical names and typed errors; no trusted IDs/raw payloads.
It does not record live user sessions or train a model. Changed files: the opt-in probe script,
this report and agent/STATE.md. No dependencies, executable intents or OS execution paths added.
