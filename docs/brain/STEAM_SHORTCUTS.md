# Steam game shortcut opening, 2026-10-19

The user's Desktop/games/Counter-Strike 2.url contained the standard local metadata target
`steam://rungameid/730`. Finding/selecting worked; the native document-extension allowlist then
rejected every shortcut with policy_denied. This was an absent native opening adapter, not a
new conversational failure. The same generic adapter now handles other Steam game numbers.

## Contract

Brain still uses only `open_file({entry_id})` through JarvisCoreClient, Named Pipe, registry,
validation, policy and executor. FileCatalog checks the selected file's scope, ancestry,
created/modified/size metadata and reparse/cloud exclusions. A `.url` is read only on opening,
as bounded shortcut metadata, not as document contents for the model. Windows read sharing
denies write/delete while the handle is retained; the final file is opened without following
a replaced reparse point. Handle metadata and catalog scope/staleness are checked again.

The parser accepts UTF-8/UTF-8 BOM or UTF-16LE BOM, at most16KiB, exactly one InternetShortcut
section/URL, and only `steam://rungameid/<positive-u32>`. It rebuilds that canonical URI from a
native-only typed target. No arguments, query, fragment, encoding escapes, install/other Steam
commands, arbitrary protocols or 64-bit non-Steam shortcut IDs are accepted. IconFile and other
metadata are ignored, never launched/read. General `.lnk`, programs and scripts stay excluded.

The Windows adapter initializes COM and uses fixed `open`, null parameters/directory and the
registered Steam protocol handler. It never opens the `.url` itself or accepts model-generated
paths, commands, IDs or executable names. This uses Microsoft's documented
[ShellExecuteW interface](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew).
Windows acceptance is the runtime success boundary; no post-launch verification was added.

## Verification

Fresh native tests: 62 library passed /2 ignored, 16 file-catalog integration passed. New cases
include two different games/names, UTF-8/BOM/UTF-16LE, metadata icon isolation, duplicate targets,
overflow/64-bit IDs, unsafe schemes/commands/arguments, oversized/stale/unknown files, injected
URI/ID fields, policy denial with zero dispatch, and the existing IPC contract through executor.
All-target Clippy with -D warnings and cargo fmt passed. No dependency, prompt or model changed.

Validated Core copied to this project's target/debug and restarted (PID36900 at update; verify
later). Live smoke found exactly the user's named shortcut in the specified Games folder and
opened its Core-returned entry_id through normal IPC/policy. The response reported opened=true;
development process inspection separately observed cs2 PID46088 starting. Game was left open.
This establishes process startup, not successful login/game readiness or a general game survey.
The existing wake service's prior Running state was preserved. No commit/push in this change.

With the existing CMAKE/LIBCLANG_PATH/CXXFLAGS voice build environment:

```powershell
cargo test -p jarvis-core --lib --test file_catalog --locked --target-dir target/organizer-validation -j 2
cargo clippy -p jarvis-core --all-targets --locked --target-dir target/organizer-validation -j 2 -- -D warnings
cargo fmt --all --check
# Normal documented Brain PYTHONPATH; --launch explicitly opens the game:
python scripts/tests/smoke_game_shortcut.py --name "Counter-Strike 2.url" --folder "$env:USERPROFILE\OneDrive\Desktop\games" --launch
```

Evidence: target/steam-shortcut-{tests-final,clippy,build,live}.log,
steam-shortcut-game-process.json and steam-shortcut-core.{stdout,stderr}.log. OneDrive's old
test-output lock was handled by renaming only verified individual target EXEs; no ACL/security
settings were changed. Older blanket-shortcut exclusions in historical milestone documents
remain historical; this narrow adapter supersedes them for validated Steam game metadata only.
