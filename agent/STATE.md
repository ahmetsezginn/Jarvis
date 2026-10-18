# Handoff

Latest normal-answer voice/discovery follow-up (2026-10-18): user heard Test voice but normal
answers were silent; also reported a natural Turkish Desktop-note request failing. Audit found
speech_start approximately 0.6s after speech_speak. SAPI RunningState=0 means queued, not done.
Rust now keeps output busy until WaitUntilDone(0) completes the whole queue; speech_poll adds
output_phase queued/speaking/idle. Qt waits for completion before automatic microphone rearm.
No fixed speech-duration estimate, saved microphone audio or Python device bypass was added.

Fresh checks: 516 Brain/Qt ordinary passed /175 opt-in skipped (3.60s); 90 Rust ordinary passed
/3 ignored, fmt and debug build passed. Ruff check/format passed (117 files); unchanged native
source passed Clippy on Oct16. Actual QML Send -> separate real 9B agent worker -> normal reply ->
Named Pipe -> Rust SAPI -> completion -> automatic rearm callback passed on Oct18 (25.78s),
also on Oct16 (25.52s). The final rearm callback is observed without opening a microphone.
Real EN/TR native output passed 2/18.12s on Oct16. This does not establish user-microphone
recognition accuracy or a new user confirmation of hearing normal replies.

Discovery distinguishes mandatory saved filename words (find_files.name_is_constraint) from
model-inferred topics/types. A failed name hypothesis permits one bounded metadata alternative
query only in the same verified folder, preserving other filters/exclusions. Alternatives are
explicitly not name/content/ownership matches. Missing folder spelling can return trusted root
labels through file_catalog_status; no global fallback. Inline name enumerations now obey the
existing single-suggestion contract. No sentence/document-specific production branches.

IMPORTANT: semantic acceptance still FAILS. Final synthetic unknown-name suite: 5 passed /1
failed (90.11s). The user's exact Turkish note sentence still omits Desktop scope and searches
literal not globally; English counterpart, photo, Turkish spreadsheet, mandatory-name negative
and empty-folder controls passed. Preserve the failing opt-in test. Interim 6/6 is NOT acceptance.
General English earlier run: 51/56 (419.83s); final focused 16: 12 passed /4 failed (168.55s).
One of those four was an overstrict test expecting a full filename query rather than equivalent
stem+extension; corrected, and that control passed in the final six. Real unresolved issues:
Turkish scope omission, inferred Excel on default XLSX opening, and authorizer accepting an
unrequested application parameter. Do not hide these failures or claim full-suite acceptance.

Diagnostic native-thinking comparison used the same local weights and fake Core only: English
passed in both modes; Turkish preserved scope on its first thinking step but later emitted an
unclosed reasoning/tool response and stopped. No raw reasoning logged or used as an action.
Production remains non-thinking; this does not prove model capacity is the sole cause.
See [VOICE_AND_DISCOVERY_FOLLOWUP.md](../docs/brain/VOICE_AND_DISCOVERY_FOLLOWUP.md) for logs,
exact validation commands and limits. Core rebuilt/started hidden as path-verified PID25816 on
Oct18; reopen desktop with jarvis -Desktop. No commit/push; inherited uncommitted work preserved.

Previous voice handoff (historical results):

Latest voice reliability follow-up (2026-10-16): user saw text but heard no answer, and reported
misrecognition. QML startup was forcing English ASR; this was removed and Listen now binds to
the controller's Auto default. Explicit en/tr remains available; final recognition returns its
detected language. Rust now discovers installed OneCore voices alongside SAPI without registry
changes (this host: Tolga tr, Zira en), selects pronunciation per request and supports bounded
speech-output device selection. Qt adds Output, Voice, Test voice and actual route feedback.
Recognition selection and pronunciation are separate; English agent text behavior is preserved.
User subsequently confirmed hearing BOTH live English/Turkish test sentences. This verifies
audible output for the tested Qt -> Core -> Realtek route; personal-microphone recognition
accuracy still requires separate evaluation. OMEN is also selectable.

Checks: 511 ordinary Brain/Qt passed /166 skipped (2.44s); 89 Rust ordinary passed /3 ignored.
Actual Qt -> Named Pipe -> Rust -> SAPI English/Turkish output: 2 passed /17.73s, start and
completion observed. Six synthetic installed-voice sentences, each explicit and Auto language,
passed 12 Whisper decodes /76.30s including negations. These clean synthetic fixtures do not
establish personal-microphone accuracy. Existing Whisper small model/decoder is unchanged.
Ruff, Rust fmt/Clippy and native build passed. Core was rebuilt and restarted hidden as PID26152;
reopen the desktop to load UI changes. No commit/push; prior uncommitted work preserved.
See [DESKTOP_VOICE.md](../docs/brain/DESKTOP_VOICE.md) for current evidence and exact commands.

Latest progressive recommendation follow-up (2026-10-16): the model chooses one best verified
file/folder/application candidate through suggest_result; CLI, Qt cards and voice present that
candidate only. Rejection removes only the proposed private identity, preserves alternatives
and carries exclusions into subsequent searches. Explicit list requests use show_results.
Identity confirmation alone does not authorize opening; an existing pending app-opening request
can complete after selection under the unchanged permission check and fresh Core resolution.
Bindings/rejections retain their original expiry; no new OS access or Rust changes in this follow-up.

Current checks: 508 Brain/Qt ordinary passed / 164 opt-in skipped (3.56s); six real Qwen9B
recommendation scenarios passed (179.76s), using synthetic metadata and a fake Core only.
The last full general English acceptance run was 55/56 (489.40s). Its remaining rejection →
unknown-filename case passed in a focused rerun (35.33s) after an exhausted-page observation
clarified that rejecting a suggestion is not a fresh search. The complete 56-case suite was
not rerun after that correction; do not describe this as a measured full-suite 56/56 pass.
Scope correction and default PDF opening passed in the full run. See
[RECOMMENDATIONS.md](../docs/brain/RECOMMENDATIONS.md) for exact commands and evidence.
Restart the Brain/desktop session to load Python/UI changes; no additional Core rebuild needed.
No commit/push. Earlier voice/desktop changes remain uncommitted alongside this follow-up.

Previous voice handoff (results below are historical):

Latest voice follow-up (2026-10-16): the hold-to-talk buffer error was a CPAL Xrun notification
being treated as fatal. Typed transient/fatal handling and bounded nonblocking callback delivery
replace that path. Real 12.05s microphone capture/finish passed with one Xrun on this host.
Opt-in Auto conversation uses local Silero v6.2.0 GGML CPU VAD (no ONNX), 200ms onset, 800ms
preroll and 900ms silence endpointing. It defaults off. Qt has waiting/listening/speaking
animations plus processing; actual SAPI completion controls rearm. Capture pauses for ASR,
agent reasoning and output. Six-second client lease discards pending PCM, including completed
turns. Manual/automatic maximum length rejects incomplete commands; cancellation drops late
transcripts. Voice controls are serialized; stale capture/output replies cannot revive a turn.

Current checks: 88 Rust ordinary passed / 2 opt-in skipped; actual VAD+ASR public fixture passed
in 19.21s; 17 Qt tests including real Qwen/Named Pipe passed in 14.37s; four actual device tests
passed in 49.88s. Combined Qt ordinary + Brain: 474 passed / 158 skipped (=458 Brain +16 Qt;
real Qt worker separately enabled). Ruff, Rust fmt/Clippy and debug build passed. An initial
pytest temporary-directory access issue was resolved with a fresh project-local --basetemp,
without ACL/security changes. Current project Core PID 49856 is the rebuilt serve process.
See [DESKTOP_VOICE.md](../docs/brain/DESKTOP_VOICE.md) for exact checks and historical first delivery.
No wake word, full duplex, saved recordings or Kokoro. This does not change the agent's semantic
acceptance (53/56 remains failed). No commit/push; earlier desktop work was already uncommitted.

Previous agent-loop handoff:

M001/M002/M003 and the application catalog refresh follow-up are implemented.
Latest work (2026-10-16): capability/result-feedback agent replaces production intent/TurnPlan
classification. Native provider templates, extensible capability/context/reference registration,
private bindings and current-effect assessment retain the Rust execution boundary. ONNX disabled.
The local development default is pinned Qwen3.5-9B GGUF; general assistant acceptance is NOT passed.
Latest user steering: JARVIS interaction is English; contributor communication remains Turkish.
Unicode filenames remain supported. English acceptance is separate from retained Turkish failures.
English final model acceptance: 53/56 passed (302.48s); general acceptance still fails.
Remaining: irrelevant name filter after direct-child scope correction; rejected results reappear;
pronoun/default PDF opening invents Adobe and is refused before any Core launch. See AGENT_LOOP.
Ordinary Brain checks: 452 passed / 157 opt-in skipped (includes archived tests, not model quality).
Rust: 79 test entries, fmt, Clippy -D warnings and debug build passed; use -j 1 if linking collides.
Actual new agent + Named Pipe live fixture: 1 passed / 24.33s, explicit process exit code 0;
Unicode TXT default opening and
explicit PDF/Chrome opening audited Source Brain, Allow, Success. No post-launch verification.
All fixture Core processes are owned/cleaned by the controller; no personal documents opened.
Restart the Brain session and Core after updating. No commit/push; inherited ahead-1 is preexisting.
See ../docs/brain/AGENT_LOOP.md for the current implementation, measured failures and handoff.
Older dated reports below describe their earlier code, not acceptance of this new loop.
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

2026-10-12: user authorized file-skills roadmap; first delivery implemented scoped Rust metadata
catalog/search/list and catalog-backed document/directory/containing-folder opening. Brain adds six
strict semantic intents, bounded file-result selection/pagination, and metadata inventory replies.
Defaults: native Windows Desktop/Documents/Downloads, optional local JARVIS_FILES_CONFIG TOML.
All machine actions retain Named Pipe -> registry -> validation -> policy -> executor -> audit.
No content reads, file modifications or post-launch verification. TASK_004.md defines the scope.
189 ordinary Brain tests, 74 Rust entries, two real GGUF safety/routing tests, one real ONNX baseline
test and one normal-user live read-only file catalog test passed. Ruff/Clippy checked. Existing test
EXE relinking intermittently failed with LNK1104; fresh target/file-skills-check completed the suite.
Evidence/commands/limits: ../docs/brain/FILE_SKILLS.md. Broader application negation remains open.
Natural date/folder filters in Brain, content understanding, watching/index persistence and file
mutations remain roadmap items. No commit or push was performed; inspect Git before continuing.

2026-10-12 launcher follow-up: user requested a global jarvis terminal command. Added bin/jarvis.cmd
and scripts/shell/install-jarvis-command.ps1; installer appends only this repository's bin to the
normal Windows user's PATH and broadcasts the environment change. No machine PATH or execution
policy changes. Command defaults to GGUF unless an existing backend environment value is set;
explicit launcher flags are forwarded. Installed for the current user. Repeated installation left
PATH unchanged. Verified Get-Command/where outside the repo without a PowerShell profile, and
launched the real REPL with exit piped in: GGUF selected, exit code 0, own Core stopped via
-StopCoreOnExit. Open a fresh terminal after installation. README documents registration.

2026-10-12 launcher correction: user reported GGUF was not selected. Centralized the default in
jarvis.ps1 (Model = gguf); inherited backend values no longer override the launcher default.
bin/jarvis.cmd only forwards arguments; the PowerShell profile helper no longer inserts a second
-Model argument, so explicit model selection works consistently. Normal-user verification loaded
scripts/shell/jarvis-profile.ps1 and ran 'exit' | jarvis -Model gguf -StopCoreOnExit, then ran
'exit' | bin/jarvis.cmd -StopCoreOnExit from TEMP with JARVIS_MODEL_BACKEND=onnx inherited.
Both reported QwenGgufIntentModel; the CMD launcher exited 0. git diff --check passed. Existing
terminal profile functions require reload or a new terminal. No execution policy changes.

2026-10-12 file-context correction: user transcript exposed global instead of relative searches,
strict name selection, lost browser clarification and unsupported application-qualified opening.
Delivered active folder context (120s), scoped relative searches, natural displayed-name selection,
concrete Google/local-Chrome clarification across evet, ambiguity/cancellation/expiry/changed-target
guards and a registered Rust open_file_with_app. Local PDF adapters support Chrome/Edge only;
Google Docs upload remains unsupported. Core natural-name search tolerates word separators.
202 ordinary Brain tests and 77 Rust entries passed; Ruff/Clippy passed. Real GGUF CV transcript
and normal-user live GGUF -> Named Pipe -> policy -> Windows synthetic PDF/Chrome launch passed.
Only synthetic PDFs were opened; no personal content reading or post-launch verification. Updated
normal Core was rebuilt/reloaded; ping and new-tool listing succeeded. Restart the Brain session
with exit then jarvis to load new Python code. Evidence/commands: ../docs/brain/FILE_SKILLS.md.
Changes remain uncommitted; no push. General model-question confirmation and other file-app/content
adapters remain later work; original broad application negation/qualifier issues are unchanged.
Final combined real-model run: five passed (three GGUF, two ONNX), including the exact CV transcript,
existing conversation/task safety and ONNX baseline. Ruff format, cargo fmt and diff checks passed.

2026-10-12 semantic file planning: reproduced user's “tr olan benimkisi onu açar mısın” refusal
with real GGUF and a previous false assistant capability claim. Model now receives bounded
displayed names/kinds, while IDs/locations stay private. Active file planning excludes free-form
assistant replies and keeps bounded user references; chat/recall memory is unchanged. Optional
open_file.application selects an explicit adapter; omitted/empty uses ordinary Windows association.
Semantic model target choices are strictly validated and bound to unique current Core candidates.
No phrase-specific patch or model training/artifact modification was needed. Relative searches
omit preceding candidates to avoid copying the previous folder kind into a file search.
218 ordinary Brain tests and four real GGUF integration entries passed; the normal-user live
synthetic-PDF test verified both default open_file and explicit Chrome opening. Ruff/diff checks
passed. Rust source unchanged; prior Rust test counts are historical. Normal Core restored.
Evidence/commands/limits: ../docs/brain/FILE_REASONING.md. Restart Brain to load new source.
Additional regression checks: existing GGUF conversation safety and ONNX smoke passed. ONNX
conversation/task safety initially failed with expanded prompts; kept new reasoning/admission
guidance on GGUF and restored compact ONNX prompts. Targeted ONNX conversation rerun passed.
Final Ruff check/format and ordinary suite passed; no claim of generalized ONNX file quality.

2026-10-14: user reported seven CV results -> “2. olanı açar mısın” -> global image search.
Added a separate select_file semantic contract (number/action/application), stable original UI
numbers in candidate context, a compact GGUF file planner and explicit current-page binding.
Selection cannot search for filenames. Numeric list notation constrains the target after admission;
wrong model search/row plans, invalid or expired pages clarify without machine queries. Default
association and explicit supported application choices are independent; consume before IPC.
258 ordinary Brain tests passed (14 opt-in skipped), three targeted real GGUF entries passed,
including six seven-result selection variants, four-type default opening and explicit semantic Edge.
The updated normal-user live seven-PDF fixture passed: exact “2. olanı açar mısın” selected the TR
PDF through open_file without another search; explicit Chrome also passed. Personal CVs were not
opened/read; no post-launch verification or model training. Fixture Core stopped, normal Core
restored. Rust source unchanged in this follow-up. Evidence: ../docs/brain/FILE_SELECTION.md.
Restart Brain to load new code; changes remain uncommitted, no push.
Final additional real-model regression run: three passed (GGUF conversation safety, ONNX
conversation safety, ONNX command/context smoke). Six final real-model entries total across
targeted/regression runs. Normal-user restored-Core ping returned ok; final Ruff/format/diff clean.

2026-10-14, natural file-goal follow-up: user reported ordinary lost-CV requests being refused.
Reproduced failed admission before Core. GGUF now classifies closed communicative purposes;
locate_file is retained in validated routing and directly selects a constrained metadata-search
planner through IntentContext.locating_file. Search planning identifies the wanted object before
extracting query/filters; its bounded description is discarded. Existing results cannot turn
another finding request into opening/listing. Other action/selection planners and ONNX admission
retain their separate contracts. Chat replies and unsupported claims are excluded from planning
history but preserved for conversation/recall. No sentence-specific router, training, model change,
new Core tool or OS bypass was added.
Final checks: 289 ordinary Brain tests passed (18 opt-in skipped), 12 real-model integration
entries passed (10 GGUF, 2 ONNX), Ruff check/format and git diff --check passed. Sixteen natural
file requests matched expected fixture names; six how-to/negative/hypothetical controls made
no machine calls. Tests also cover prior-denial recovery, repeated requests/topic changes,
folder/file scope, numbered selection, default/explicit opening and conversation safety.
One real normal-user Windows fixture entry passed: the exact three user sentences returned CV
results, a lost-presentation request found TXT without an inferred PPTX filter, relative scope
and default/Chrome opening worked. Only synthetic fixtures were used; no post-launch verification.
Fixture Core stopped and normal Core restored. Cache-write warning did not affect assertions.
Rust source unchanged in this follow-up; earlier Rust test counts remain historical. Evidence,
exact commands and language/metadata/date limitations: ../docs/brain/NATURAL_FILE_GOALS.md.
Restart Brain by exiting/relaunching jarvis to load source. Changes remain uncommitted; no push.

2026-10-14, subsequent user transcript and analysis: prior test interpretation was too broad.
The unchanged cross-domain natural-file test passes a fake model returning query="*" for all
16 inputs. Target inclusion on a small fixture is insufficient evidence of understanding.
Real GGUF with synthetic-only metadata reproduced desktop-note unsupported, “neden?” replaying
the tournament search, location loss, rejected/unknown-name turns blocked by fixed confidence
handling, global desktop listing and scope corrections becoming wrong operations. The user's
happy-chat-triggered search was not reproduced in the synthetic sequence; language mixing was.
24 context probes, a 14-turn traced sequence, 8 richer-schema probes and 30 rendering probes
were recorded under ignored target/assistant-analysis. Same model/current-message-last fixed
one “neden?” routing case; other rendering/schema changes were mixed, not a production fix.
Production still lacks goal/constraint/rejection state and tool-result feedback. locate_file
forces search-only output, so targeted clarification is unavailable in that provider branch.
Rust already supports scoped search, immediate-child listing and modification-time bounds;
Brain does not expose/bind all of them. Current 4B Q4 behavior is fragile, but model size versus
quantization versus prompting has not been isolated against another model. Do not claim that
upgrading/training or adding another prompt sentence alone solves assistant quality.
Added three repeatable diagnostic scripts and a detailed report with an acceptance/architecture/
model-comparison plan. No production behavior changed, no live personal file access/Core restart,
no model download/training, no commit/push. Previous test pass counts remain historical; they
are not acceptance of the reported dialogue behavior. See ASSISTANT_BEHAVIOR_ANALYSIS.md.

2026-10-15, authorized stateful assistant implementation (verification in progress):
GGUF handle_text now uses strict TurnPlan and AssistantSession with bounded goal, pending slots,
scope, rejection identities and verified outcome feedback. Current target/operation/constraints
are extracted separately. Current-purpose admission excludes old commands and displayed names;
reference binding and conversational recall retain their own bounded context. Model target quotes
must occur in the current message. Existing displayed-result selection is reused for version,
number and containing-folder references. Generic capability questions cannot select a shown row.
Retained goals support missing-name/location questions, rejection, direct/recursive scope changes,
one bounded same-scope type recovery, and new targets. Chat/explanation do not replay execution.
Native search adds closed categories, recursive/direct search and bounded private exclude_ids.
All actions still use Core/Named Pipe/registry/validation/policy/executor; no OS bypass, content
reading, mutation, upload, arbitrary app automation, post-launch checking or training was added.
User-visible paths/rows are not retained as model outcome feedback.

Latest ordinary checks: 369 passed, 40 opt-in skipped; Rust 78 entries, fmt/clippy/build passed.
Real-model acceptance is being rerun after failures uncovered by stronger controls; do not infer
that the full model suite is green from these ordinary counts. Historical ONNX 0.6B Turkish
context correction still fails its separate opt-in regression; the production GGUF default stays.
An isolated same-4B Q4/Q8 raw diagnostic scored 22/28 for each (14 probes, two repeats), with the
same ownership/identity/scope errors. Q8 was explicitly downloaded to a verified temporary cache;
production model/checksum/defaults unchanged. See ASSISTANT_DIALOGUE.md for artifact and limits.
Working tree includes preserved earlier uncommitted file-skill/launcher work; no commit/push.

2026-10-16, user counterexample and reassessment:
The supplied session already ran GGUF, not ONNX. Correct certificate discovery worked, but a
single-result pronoun opening asked for clarification. Misspelling and short location/type
answers lost the subject. Recommendation requests elicited an invented capability prohibition.
User explicitly disabled ONNX: factory defaults GGUF, rejects ONNX, no fallback/import; launcher
accepts only GGUF; mandatory GenAI dependency/public model export removed. Historical source and
tests remain archival. No package/model deletion, training, download or production model change.

Fixed two concrete metadata omissions in runtime/reply-template rendering. A text reply receives
bounded current names/kinds/numbers, never IDs/paths; conversation preserves the current task/page
without renewing TTL or authorizing actions. Cancel/reset/expiry remain clearing operations.
Real reply-component checks passed for warranty, service invoice, school timetable and absent
metadata. This does not repair admission: a recommendation request can still become a new search.

Current ordinary Brain: 391 passed, 51 opt-in skipped. New real-model dialogue regressions:
4 passed, 3 FAILED (typo before search, singleton pronoun opening, metadata opinion routed to search).
Do not mark them xfail or claim the assistant is ready. Earlier named Edge selection also remains
unaccepted. Flat-contract ablation got only action labels 6/8; not a retrieval score. Free text
also made mistakes, so neither architecture nor capacity alone is established as the sole cause.
Two failed single-pass TurnPlan prototypes stayed in ignored target; not deployed. Current-only
query substring restriction and fragmented planning are documented, not silently fixed with more
sentence rules. Core untouched this turn; no live personal file access/restart or commit/push.
Exact tests, local artifacts and next acceptance design: ASSISTANT_REASSESSMENT.md.
