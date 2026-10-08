# Windows packaged applications — 2026-10-08

The native Rust catalog now includes packaged applications from Windows AppsFolder alongside
the current-user and shared Start Menu shortcuts. Native COM enumeration reads display names
and System.AppUserModel.ID. No PowerShell discovery script, recursive executable search or
per-application static whitelist was introduced.

Only validated packaged identities from the WindowsAppsFolder source are accepted. Stable
catalog IDs are derived from the source and identity. AUMIDs remain internal; resolve_app
returns app_id/name metadata and open_app accepts only app_id. Rust's existing registry,
validation, policy, executor and audit path still governs every launch. Activation uses
IApplicationActivationManager with no caller arguments. Filesystem existence checks continue
for shortcuts/executables, while packaged activation errors report application_launch_failed.

Implementation: apps/model.rs, apps/catalog.rs, apps/windows/discovery.rs, the new
apps/windows/packaged.rs, platform/windows/desktop.rs and Windows-only Cargo dependencies.
The existing windows-sys crate handles transport; windows supplies maintained typed Shell COM
interfaces needed here. No new Brain code, executable intent, tool or IPC schema was introduced.

Validation covers invalid identities/sources, packaged entries without filesystem paths,
catalog resolution without leaking launch identities, mocked platform launch and policy denial,
and degraded AppsFolder discovery preserving shortcuts. Existing IPC contract tests also run.
The live enumeration is opt-in; normal tests do not require installed packages.

Live evidence in the normal Windows user context: 64 packaged applications enumerated;
ChatGPT and OMEN Gaming Hub both resolved successfully via the real Rust executor and policy.
The restricted environment returned 0x80070490; normal-user rerun proved this was environment
access rather than absent installed applications. No application was launched in these checks.
Packaged activation is compiled and tested through a mock platform, not a real GUI launch.

Limitations: this adds packaged AppsFolder identities (family!application), not every arbitrary
desktop AUMID or portable executable. The AI may still misinterpret a command before resolution;
this change does not fix the separately documented semantic/negation failures. Duplicate names
remain a clarification case. Catalog refresh occurs at Core startup. Individual COM calls have
no hard timeout; enumeration checks 60 seconds between calls and at most 10,000 entries.

AppsFolder failures emit structured warnings if shortcuts are available, instead of preventing
all normal application use. If neither source is available, discovery fails with a typed error.
Windows metadata references: [System.AppUserModel.ID](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-id)
and [Shell item display strings](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/shobjidl_core/nf-shobjidl_core-ishellitem-getdisplayname.md).

Commands from the repository root in the normal Windows user environment:

```powershell
cargo fmt --all -- --check
cargo clippy --offline --manifest-path core/native/Cargo.toml --target-dir target/apps-folder-live --all-targets -- -D warnings
Remove-Item Env:JARVIS_RUN_WINDOWS_APPS_TESTS -ErrorAction SilentlyContinue
cargo test --offline --manifest-path core/native/Cargo.toml --target-dir target/apps-folder-live
$env:JARVIS_RUN_WINDOWS_APPS_TESTS = '1'
cargo test --offline --manifest-path core/native/Cargo.toml --target-dir target/apps-folder-live opt_in_live_apps_folder_enumeration -- --nocapture
& .\target\apps-folder-live\debug\jarvis-core.exe apps search 'ChatGPT'
& .\target\apps-folder-live\debug\jarvis-core.exe apps search 'OMEN Gaming Hub'
git diff --check
```

Separate build folders avoid overwriting active binaries and older test artifacts whose Windows
permissions prevented relinking. No security settings or directory permissions were changed.

Final validation: 65 Rust test entries passed (the opt-in entry returns without enumeration
in the ordinary run); the separate live test passed and enumerated 64 applications in 1.37s.
Clippy with -D warnings, formatting and git diff --check passed. The original 10s enumeration
check failed during a cold start under concurrent tests; it was raised to 60s with a timeout
HRESULT, then ordinary and live tests were run separately. Individual COM calls remain unbounded.

Normal launcher deployment: verified the active process path matched this repository's
target/debug/jarvis-core.exe, stopped that Core, ran `cargo build --offline --manifest-path
core/native/Cargo.toml`, then restarted `jarvis-core.exe serve` hidden. Build passed. Final real
JarvisCoreClient Named Pipe ping returned ok; Brain-source resolve_app calls returned ChatGPT
and OMEN Gaming Hub. Existing terminal clients may need to reconnect/restart after this reload.
