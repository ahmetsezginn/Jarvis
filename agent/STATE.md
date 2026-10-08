# Handoff

M001/M002/M003 and the application catalog refresh follow-up are implemented.
Latest work: consolidated engineering documents in this folder. See README.md for the index.
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
