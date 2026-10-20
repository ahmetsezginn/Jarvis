# JARVIS agent documents

Windows installer, explicit CPU/NVIDIA runtime, local model cleanup and distribution validation:
[DISTRIBUTION_2026-10-20.md](../docs/brain/DISTRIBUTION_2026-10-20.md).
Installer tooling and artifacts are deliberately local-only; source setup remains documented.

Native echo-cancelled voice interruption in Auto conversation:
[BARGE_IN.md](../docs/brain/BARGE_IN.md).

Project documents have one canonical location in this folder. The root AGENTS.md is only an
automatic-discovery entry point. Commands and source paths in these documents are relative to
the repository root, unless explicitly stated otherwise.

Windows wake service in the same product/workspace: [setup](../services/wake/README.md) and
[implementation/acceptance](../docs/brain/WAKE_DAEMON_PLAN.md). SCM/activation are implemented;
actual microphone accuracy is still under evaluation after a failed user test. The earlier
integrated Core/Qt wake was removed. Desktop close exits Qt/Brain:
[DESKTOP_WAKE.md](../docs/brain/DESKTOP_WAKE.md).

Current task/notes capability: [PERSONAL_ORGANIZER.md](../docs/brain/PERSONAL_ORGANIZER.md).
Persistent native storage, daily agendas/recurrence, day copying, completion/reopening,
rescheduling and note recall;
the same model-driven capability loop handles typed and spoken requests.
Day copying, daily persistence and atomic recurrence groups:
[TASK_ROUTINES_2026-10-20.md](../docs/brain/TASK_ROUTINES_2026-10-20.md).
Adversarial review supersedes the earlier bounded acceptance: [PERSONAL_ORGANIZER_STRESS_2026-10-18.md](../docs/brain/PERSONAL_ORGANIZER_STRESS_2026-10-18.md).
Actual wrong-target and wrong-date writes were reproduced; overall task acceptance is FAILED.

Current desktop/voice milestone: [DESKTOP_VOICE.md](../docs/brain/DESKTOP_VOICE.md), with setup at
[services/desktop/README.md](../services/desktop/README.md). Launch with `jarvis -Desktop`.

Catalog-backed `.url` Steam game opening: [STEAM_SHORTCUTS.md](../docs/brain/STEAM_SHORTCUTS.md).

Progressive suggestions and rejection dialogue: [RECOMMENDATIONS.md](../docs/brain/RECOMMENDATIONS.md).
Latest normal reply voice and unknown-filename discovery follow-up:
[VOICE_AND_DISCOVERY_FOLLOWUP.md](../docs/brain/VOICE_AND_DISCOVERY_FOLLOWUP.md).

Speech-input quality comparisons, failed personal retest, offline alternatives and signal diagnostics:
[ASR_QUALITY.md](../docs/brain/ASR_QUALITY.md).

Standalone Handy 0.9.8 trial, local-recording authorization and first performance evidence:
[HANDY_TRIAL.md](../docs/brain/HANDY_TRIAL.md).

Latest correction: Handy's native engine integrated directly into JARVIS Rust Core:
[NATIVE_SPEECH_PROVIDER.md](../docs/brain/NATIVE_SPEECH_PROVIDER.md).

Latest repository/file-operation review and publication checks:
[PRE_PUSH_REVIEW_2026-10-20.md](../docs/brain/PRE_PUSH_REVIEW_2026-10-20.md).
Earlier file-operation review:
[PRE_PUSH_REVIEW_2026-10-18.md](../docs/brain/PRE_PUSH_REVIEW_2026-10-18.md).

Current architecture revision: [AGENT_LOOP.md](../docs/brain/AGENT_LOOP.md). Production now uses
the capability/result feedback loop; older intent and TurnPlan reports are historical diagnostics.
The active product language is English; original filenames retain Unicode. Current real-model
checks are `services/brain/tests/integration/test_english_agent_acceptance.py`; the old Turkish
failures remain separately reproducible, rather than being removed to obtain a passing suite.

- [AGENTS.md](AGENTS.md): mandatory engineering rules.
- [ARCHITECTURE.md](ARCHITECTURE.md): system architecture.
- [STATE.md](STATE.md): current implementation state and handoff notes.
- [TASK_001.md](TASK_001.md): native Core milestone specification.
- [TASK_002.md](TASK_002.md): local IPC milestone specification.
- [TASK_003.md](TASK_003.md): local intelligence milestone specification.
- [TASK_004.md](TASK_004.md): scoped file/folder catalog, search, listing and opening.
- [TASK_CONTEXT.md](TASK_CONTEXT.md): session memory work.
- [TASK_REASONING.md](TASK_REASONING.md): interpretation diagnostics.
- [TASK_REQUEST_ROUTING.md](TASK_REQUEST_ROUTING.md): conversation/task separation.

Developer workflow remains in [DEVELOPMENT_PROCESS.md](../DEVELOPMENT_PROCESS.md); product setup
remains in [README.md](../README.md). Detailed Brain reports remain under [docs/brain](../docs/brain).
The .codex directory contains tool settings, not another copy of project documentation.

Latest natural-language file-goal diagnostics and reproduction:
[NATURAL_FILE_GOALS.md](../docs/brain/NATURAL_FILE_GOALS.md).

Latest quality assessment (previous natural-file acceptance is qualified):
[ASSISTANT_BEHAVIOR_ANALYSIS.md](../docs/brain/ASSISTANT_BEHAVIOR_ANALYSIS.md).

Follow-up implementation and historical verification:
[ASSISTANT_DIALOGUE.md](../docs/brain/ASSISTANT_DIALOGUE.md).

Earlier assessment, ONNX retirement and real-model regressions before the agent-loop redesign:
[ASSISTANT_REASSESSMENT.md](../docs/brain/ASSISTANT_REASSESSMENT.md).
