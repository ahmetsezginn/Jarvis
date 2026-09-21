# JARVIS — Development Process

This document tracks the technical development sequence of JARVIS.

`README.md` is reserved for introducing the project: what JARVIS is, why it exists, its product vision, and how the overall system is positioned.

This file is the engineering process / milestone document.

---

## Development Rule

JARVIS is developed milestone by milestone.

A milestone is considered complete only after:

1. implementation is complete,
2. automated tests pass,
3. real Windows smoke tests pass where applicable,
4. security boundaries are verified,
5. documentation is updated,
6. the next milestone does not silently change completed architecture.

Completed milestones should be treated as stable foundations. New features belong in later tasks unless they fix an actual defect.

---

# Architecture Direction

JARVIS is intentionally multi-language.

```text
Rust
    Native Core
    OS integration
    Security
    Policy
    Tool execution
    IPC server

Python
    Brain
    Local AI
    Intent understanding
    Planning
    Orchestration
    Model experimentation

TypeScript / Tauri
    Future desktop UI
```

The permanent trust boundary is:

```text
User / Voice / UI
        |
        v
Brain / Intelligence
        |
        v
Validated semantic request
        |
        v
JarvisCoreClient
        |
        v
Local IPC
        |
        v
Rust Core
        |
        v
Registry
        |
        v
Validation
        |
        v
Policy
        |
        v
Executor
        |
        v
Tool
        |
        v
Operating System
```

The AI never becomes the operating-system authority.

---

# Milestone Status

## M001 — Trusted Execution Core

**Status: COMPLETE**

Implemented in Rust.

Delivered:

- Native Core
- Tool Registry
- typed ToolRequest / ToolResult
- validation
- Policy Engine
- Executor
- audit
- Windows platform abstraction
- dynamic application discovery
- trusted application catalog
- deterministic app resolver
- trusted `app_id`
- `system_status`
- `open_folder`
- `resolve_app`
- `open_app`

Security verified:

- caller-provided executable paths rejected
- no generic shell tool
- unknown tools rejected
- app launch requires a catalog-backed `app_id`
- tool execution passes through policy and executor

Real Windows smoke tests passed.

---

## M002 — Brain ↔ Core Bridge

**Status: COMPLETE**

Delivered:

- long-running `jarvis-core serve`
- Windows Named Pipe control transport
- current-user SID-based endpoint
- protected pipe ACL
- remote clients rejected
- 4-byte big-endian framing
- UTF-8 JSON control messages
- protocol version 1
- 1 MiB frame limit
- `hello`
- `ping`
- `list_tools`
- `execute_tool`
- Python 3.12+ Brain package
- persistent Named Pipe client abstraction
- typed errors and timeouts
- `JarvisCoreClient`

Security verified:

- Brain tool requests use `RequestSource::Brain`
- IPC forwards to the existing executor
- Python does not duplicate native OS tools
- invalid executable path remains rejected
- malformed / oversized / unsupported-version traffic is rejected
- TCP/LAN interface is not exposed

Real Windows E2E passed:

```text
Python Brain
 -> Named Pipe
 -> Rust resolve_app
 -> trusted app_id
 -> Rust open_app
 -> Chrome
```

---

# M003 — Local Intelligence Runtime

**Status: COMPLETE**

Selected intelligence stack:

```text
Qwen3-0.6B
    +
ONNX Runtime GenAI
    +
INT4
    +
CPU-first
    +
offline-first
```

Primary goal:

```text
"Google Chrome'u aç"
        |
        v
Local intelligence
        |
        v
Validated semantic intent
        |
        v
Python orchestrator
        |
        v
Rust Core
        |
        v
Chrome opens
```

Delivered:

- Qwen3-0.6B INT4 CPU artifact built from pinned revision
- ONNX Runtime GenAI 0.15.2 production adapter
- lazy model states and missing-artifact failures
- 2,048-token context and 128-token output limits
- Qwen3 non-thinking prompt form
- constrained output plus independent strict parsing and validation
- closed semantic intent contract
- small deterministic Turkish/English Fast Router
- fixed semantic orchestrator
- `ask`, `model-info`, and developer-only `predict --force-model` CLI paths
- reproducible isolated model provisioning and full dependency lock
- repeatable Turkish/English benchmark
- real ONNX, Windows Named Pipe, and offline E2E tests

Security verified:

- model output cannot provide arbitrary Core tool names, paths, shell commands, or trusted app IDs
- `open_application` always uses Rust `resolve_app` before `open_app`
- invalid model output fails closed without Core execution
- Python does not implement application launch or system status
- production Brain has no PyTorch or Transformers dependency
- runtime inference performs no download or remote inference

Measured on `AMD64 Family 25 Model 116`, using the 20-case benchmark:

```text
artifact size:              405,479,870 bytes
idle Brain RSS:              29,204,480 bytes
RSS after model load:       710,340,608 bytes
peak RSS:                 1,183,186,944 bytes
cold model load:                  2,023 ms
first inference:                    630 ms
warm inference median:              633 ms
Fast Router hit rate:                70%
model fallback rate:                 30%
intent accuracy:                     90%
argument accuracy:                  100%
invalid model output rate:         33.3% of fallbacks
unsafe-field generation rate:         0%
```

The 0.80 action threshold is a conservative benchmark-selected cutoff, not a calibrated
probability claim. The observed invalid outputs were rejected without execution. Model weights are
not committed to Git; the verified local artifact manifest records per-file checksums and the
aggregate digest.

Validation limitation: this host denied creation of a temporary Windows Firewall rule even when
the command was escalated. The offline E2E therefore passed with the Brain process's outbound
Python socket APIs denied, an explicit connection canary, offline environment flags, and the local
artifact. The stronger firewall-backed script path remains the default for an administrator-run
validation.

The local model remains untrusted and cannot directly execute tools or operating-system actions.

See:

```text
TASK_003.md
```

for the complete implementation contract.

---

# Planned Milestones

## Brain requirements and evaluation — 2026-09-15

Current priority before voice or new tool expansion: establish and run the Brain diagnostic
assessment in `docs/brain/REQUIREMENTS.md` and `scripts/evaluation`.
Deliverables: observable requirements, a 36-case public seed corpus, non-executing router/model/
combined evaluator, scorer tests and recorded baseline findings. The 8 contextual cases expose
an absent interface; they are not silently counted as passed. This assessment does not declare
conversational Brain ready and does not select or train a replacement model.

M003's earlier 20-case quality numbers are historical diagnostics with exposed examples, not
sealed-test evidence. Model changes/fine-tuning follow independent evaluation and a revised task
contract. Production M003 model and four-intent contract remain unchanged.

## M004 — Voice Input Pipeline

### Local-model comparison implementation (2026-09-15)

User-authorized scope: evaluate a stronger lightweight local model without requiring ONNX.
Qwen3-4B-Instruct-2507 Q4_K_M is provisioned with pinned revision/checksum and isolated CUDA
dependencies. An in-process GGUF adapter and explicit provider factory preserve the four-intent
contract and all Rust execution boundaries. The interactive CLI now reuses one model per session.
Comparison and integration validation passed; semantic acceptance did not. New model-only
accuracy is 19/28 versus the historical 2/28, but three wrong action proposals remain (eight with
the unchanged Fast Router). Keep GGUF opt-in, not promoted as a production-quality Brain.
See `docs/brain/LOCAL_MODEL_COMPARISON.md` for measurements and exact validation commands.
Historical ONNX remains available. No new native tools or voice features were added.

Planned, after the Brain assessment and resulting implementation decision. No M004 implementation
is included in M003.

Goals:

- microphone capture
- push-to-talk
- efficient local speech-to-text
- streaming-friendly design
- no change to Core security boundary

---

## M005 — Voice Output / JARVIS Interaction

Planned.

Goals:

- local or efficient TTS
- interruption / barge-in
- concise JARVIS responses
- audio device management

---

## M006 — Productivity Tools

Planned.

Possible capabilities:

- reminders
- workspaces
- focus mode
- file search
- folder analysis
- notifications

Each capability must be implemented as explicit Rust tools or trusted integrations.

---

## M007 — Company Integrations

Planned.

Possible integrations:

- calendars
- Teams / Slack
- company documents
- enterprise knowledge
- identity / policy systems

Company data permissions must remain separate from model intelligence.

---

# Engineering Backlog

These items are known but do not block M003.

## CORE-HARDENING-001

Named Pipe partial-frame read deadline.

Goals:

- header read timeout
- payload read timeout
- stalled client cancellation
- connection cleanup

---

## CORE-HARDENING-002

Graceful Core shutdown.

Goals:

```text
Ctrl+C / service stop
 -> stop accepting clients
 -> close pipe
 -> flush logs/audit
 -> exit cleanly
```

---

# Documentation Responsibilities

## README.md

Purpose:

- introduce JARVIS
- explain product vision
- explain the value proposition
- provide a high-level architecture overview
- explain who the product is for

Do not turn README into a milestone changelog.

## ARCHITECTURE.md

Purpose:

- define technical architecture
- define module boundaries
- define security boundaries
- define data/control flow
- document architectural decisions

## AGENTS.md

Purpose:

- rules for coding agents
- forbidden implementation shortcuts
- security requirements
- module ownership and boundaries
- test expectations

## DEVELOPMENT_PROCESS.md

Purpose:

- milestone order
- current development stage
- completed work
- backlog
- validation gates

## TASK_XXX.md

Purpose:

- exact implementation contract for a single development task

---

# Current Sequence

2026-09-17: bounded application clarification session implemented for the user's Steam/"üstteki"
case. One candidate list, numbered display, ordinal/name selection, 120-second expiry, cancellation,
new-topic clearing and fresh Rust ID comparison. No general conversation history, new tools or
model contract change. Dedicated session tests supplement the historical stateless benchmark.

Temporary routing diagnostic: user requested disabling Fast Router in terminal commands.
CLI ask/repl/predict now default to model-only; explicit opt-in restores the router. The launcher
accepts `-Model gguf` and displays selection. No model-quality fix or conversational capability
is claimed; validation and Rust authority are unchanged.

```text
M001 Trusted Execution Core
    COMPLETE
        |
        v
M002 Brain ↔ Core IPC
    COMPLETE
        |
        v
M003 Local Intelligence Runtime
    COMPLETE
        |
        v
Brain requirements + diagnostic assessment
    CURRENT PRIORITY (conversational implementation not yet accepted)
        |
        v
M004 Voice Input
    PLANNED
        |
        v
M005 Voice Output
        |
        v
M006 Productivity
        |
        v
M007 Enterprise Integrations
```
