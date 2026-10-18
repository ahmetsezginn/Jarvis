# JARVIS agent documents

Project documents have one canonical location in this folder. The root AGENTS.md is only an
automatic-discovery entry point. Commands and source paths in these documents are relative to
the repository root, unless explicitly stated otherwise.

Current desktop/voice milestone: [DESKTOP_VOICE.md](../docs/brain/DESKTOP_VOICE.md), with setup at
[services/desktop/README.md](../services/desktop/README.md). Launch with `jarvis -Desktop`.

Progressive suggestions and rejection dialogue: [RECOMMENDATIONS.md](../docs/brain/RECOMMENDATIONS.md).
Latest normal reply voice and unknown-filename discovery follow-up:
[VOICE_AND_DISCOVERY_FOLLOWUP.md](../docs/brain/VOICE_AND_DISCOVERY_FOLLOWUP.md).

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
