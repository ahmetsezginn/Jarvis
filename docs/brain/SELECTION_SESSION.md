# Application selection session — 2026-09-17

Implemented scope: one pending Rust ambiguity list per interactive Brain instance, not general
conversation history or long-term memory. The Fast Router remains disabled in CLI by default.
Reply handling uses route `session` and does not call the model for ordinal selections.

Example: `Steam'i aç` -> `1. Steam / 2. Steam` -> `üstteki` -> fresh Rust resolution -> open_app.
Identical display names are supported: if resolution remains ambiguous, the selected ID must be
present with its name in the **fresh** Rust candidate list. New ordering never changes selection.
IDs are never supplied by the model or accepted as user selection text.

Supported selections: numbers (1-based), first/second/third, üstteki/ikinci/alttaki, exact unique
displayed names. No referent means `diğeri` asks for a number rather than guessing.
One list, 2–10 candidates, 120-second monotonic expiry. Cancellation/new topic/completion clear it;
the selection is consumed before IPC so transport/policy failures cannot leave a replayable choice.
No cross-process persistence. Expired/absent selections produce clarification without Core calls.

Changed files: `intelligence/session.py`, runtime, orchestrator, Core client's application helper,
session unit/E2E tests, offline test switches, AGENTS/ARCHITECTURE/Brain README/development process.
No Rust code, policy, protocol, model prompt or model semantic contract changed.

Validation commands (repository root; E2E needs a same-user Core and real local GGUF):

```powershell
cargo fmt --check
cargo build
cargo clippy --all-targets --all-features -- -D warnings
cargo test
.\services\brain\.venv\Scripts\python.exe -m ruff check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m ruff format --check services/brain scripts
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
.\services\brain\.venv\Scripts\python.exe -m pytest services/brain/tests/integration
.\services\brain\.venv\Scripts\python.exe -m scripts.tests.session_e2e
.\scripts\tests\run_offline_e2e.ps1 -ProcessGuardOnly -Session
```

Offline process guard blocks Python network APIs, not native DLL networking or OS-wide traffic;
it must not be reported as firewall isolation. Test Core processes are stopped after verification;
Steam opened by the smoke test is left running. The existing stateless benchmark is unchanged;
it does not establish general multi-turn reasoning quality.
