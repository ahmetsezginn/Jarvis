# Catalog refresh — 2026-10-08

User requested refresh on explicit instruction or a newly-installed follow-up to a missing
application, and explicitly declined additional post-launch verification.

Example: “Example uygulamasını aç” -> Rust application_not_found -> “ben daha yeni yükledim”
-> refresh_app_catalog -> fresh resolve_app -> open_app if uniquely resolved. Brain reports
“Katalog yenilendi. Example açıldı.” No post-launch check occurs. Ambiguous results display the
existing candidate selection; still-missing results report failure without looping.

Standalone “uygulama listesini yenile”, “kataloğu yenile”, “uygulama listesini güncelle” and
“uygulamaları yeniden tara” refresh only. A leading “Jarvis” is accepted. Supported installation
follow-ups include “ben daha yeni yükledim”, “az önce kurdum”, “bunu yeni yükledim, tekrar bak”,
“demin yükledim” and “ben daha yeni yükledim bunu”. Whole-turn matching is deliberately bounded;
arbitrary paraphrases are not guaranteed. Quotes, negations, questions and embedded commands
do not activate this recovery path. These checks do not solve the older model negation bug.

Recovery uses one actual failed opening target, not assistant prose or model-generated failure
claims. It retains only a validated human query for at most 120 seconds. The next unrelated turn,
cancellation, /reset, expiry or consumed attempt clears it. Repeated recovery requires a new
opening request. No conversation persistence or training was introduced. Model parsing retains
the four-intent enum; these explicit session actions resemble existing numbered selections and
are separate from ordinary conversation and the diagnostic Fast Router.

Rust owns discovery. The new refresh_app_catalog tool requires exactly an empty JSON object,
uses ReadOnly risk metadata, and traverses registry/validation/policy/executor/audit. It returns
refreshed/discovered, no launch identities. Full discovery failure preserves the previous catalog
and returns the existing typed error; degraded AppsFolder discovery retains the previously
documented shortcut fallback. A recovery opening uses only the fresh Rust-returned trusted ID.

Changes: Rust refresh tool, registry/export wiring and registry contract expectations; Brain
catalog_session.py, runtime recovery and the orchestrator's fixed refresh call; Rust validation,
atomicity/policy tests, Brain recovery tests, and an opt-in live Named Pipe test. Documentation
and agent state record the new behavior. No provider, model prompt, dependency or IPC envelope
change is required. No post-launch verification was added.

Validation: 174 ordinary Brain tests passed (seven opt-in tests skipped in the final run); all 66 Rust
test entries passed, and Clippy, Ruff and formatting checks passed. The added live integration
test passed in 1.43 seconds: refreshed real Windows metadata over one persistent Core connection,
then exercised missing-app -> newly-installed -> refresh -> still-missing. Its wrapper prohibits
open_app. Core PID remained 5740 during refresh. New installation appearance is simulated in
Rust unit tests; no software was installed for the live check. Mock tests verify successful
retry opens, failed/ambiguous refresh never opens, trusted ID use, expiry, cancellation/reset,
negations and unrelated turns. Core was rebuilt/reloaded once to install this new registered
tool; later refresh requests do not restart it.

Validation commands from repo root, normal Windows user context:

```powershell
$env:PYTHONPATH = ((Join-Path (Get-Location) 'services/brain/src'), (Join-Path (Get-Location) 'services/brain/.venv/Lib/site-packages')) -join ';'
$checkPython = 'C:\Users\szgnm\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$catalogTestTemp = Join-Path (Get-Location) ('target/pytest-catalog-' + [guid]::NewGuid().ToString('N'))
& $checkPython -m pytest services/brain/tests --basetemp $catalogTestTemp -o addopts='-q -p no:cacheprovider'
& $checkPython -m ruff check services/brain scripts
& $checkPython -m ruff format --check services/brain
cargo fmt --all -- --check
cargo test --offline --manifest-path core/native/Cargo.toml --target-dir target/apps-folder-live
cargo clippy --offline --manifest-path core/native/Cargo.toml --target-dir target/apps-folder-live --all-targets -- -D warnings
$env:JARVIS_RUN_CORE_REFRESH_TESTS = '1'
& $checkPython -m pytest services/brain/tests/integration/test_live_catalog_refresh.py -o addopts='-q -p no:cacheprovider'
$env:JARVIS_RUN_GGUF_TESTS = '1'
$env:JARVIS_RUN_MODEL_TESTS = '1'
& $checkPython -m pytest services/brain/tests/integration/test_real_conversation_routing.py -o addopts='-q -p no:cacheprovider'
git diff --check
```

The fresh workspace test directory avoids a preexisting Windows temp directory access denial,
without changing permissions or security settings. Existing terminal sessions may need reopening
after installing the updated Core. Startup command remains `.\jarvis.ps1 -Model gguf`.

Final opt-in real-provider regression: both GGUF and ONNX conversation/task routing tests
passed in 60.57s using mocked Core and offline inference. These retain their existing provider
limitations; the new refresh recovery itself is deterministic and does not invoke either model.
