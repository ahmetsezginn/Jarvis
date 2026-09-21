# Brain requirements and evaluation v1

Date: 2026-09-15. Status: requirements and diagnostic evaluation prepared; conversational
runtime, new model selection, training and new Core tools are NOT implemented by this work.

## Product outcome

JARVIS should understand everyday Turkish and English, preserve the meaning of corrections,
ask useful questions, and act only on a sufficiently identified supported request. Success is
measured by observable decisions, not by how much reasoning text a model produces.

Example acceptance conversation:

1. User: "VS aç."
2. Core evidence contains Visual Studio and Visual Studio Code. Brain asks which one.
3. User: "Code olan değil."
4. Brain selects the human name Visual Studio, resolves it again in Rust, and only then may open it.

If Visual Studio is absent, Brain must say it could not find it or request more information.
It must not choose Code, install software, or invent a launch target.

## Evidence and current gaps

- `jarvis.ps1` runs a separate `cli ask` Python process for each line.
- `build_non_thinking_prompt` includes the current message but no previous messages or candidates.
- `IntentContext` currently contains token budgets, not conversation history.
- The four-intent contract is appropriate for M003 but cannot represent general conversation,
  cancellation state, or a capability explanation distinctly.
- Fast Router can absorb negation and relational requests into an application query.
- Machine-specific aliases solve individual names, not general language understanding.
- Qwen3-0.6B is already pretrained and post-trained; it has no JARVIS-specific fine-tuning.
- The old 20-case benchmark includes examples exposed in prompts and fixes. Its reported 90%
  is historical diagnostic evidence, not an independent estimate of conversational ability.
- Model confidence is self-reported, not a calibrated probability of correctness.

## Requirements and acceptance evidence

| ID | Requirement | Evidence required before accepting implementation |
| --- | --- | --- |
| BR-01 | Extract the requested human app name without politeness, suffixes or negation clauses | Single-turn extraction and negative examples; paired TR/EN results |
| BR-02 | Maintain bounded session state | Corrections after 1, 3 and 6 turns; reset/restart removes pending selection |
| BR-03 | Use current Core evidence for installed-app claims | Same utterance under present, ambiguous, absent and stale catalog fixtures |
| BR-04 | Ask a discriminating question when evidence is insufficient | Question distinguishes candidates; no action before clarification |
| BR-05 | Respect exclusion and cancellation | "not Code", "neither", "cancel", topic change; zero unwanted action proposals |
| BR-06 | Distinguish app launch from actions inside an app | Browser-site, game mode, file editing and multi-action requests do not become a partial app launch |
| BR-07 | Route only unambiguous commands deterministically | Router precision measured separately from coverage; corrections fall back to contextual handling |
| BR-08 | Preserve Rust authority | All proposed app names resolve in Rust; model never provides ID/path/tool name or grants permission |
| BR-09 | Return concise truthful messages | "opened" only after Core success; policy denial and unavailable Core remain distinct from language failure |
| BR-10 | Run explicitly provisioned inference locally | No runtime downloads; missing artifact fails clearly; production requires no Torch/Transformers |
| BR-11 | Bound resource use | Session history, candidate count, input/output tokens, inference deadline, RAM and latency measured |
| BR-12 | Measure before tuning | Frozen versioned cases; separate router, model-only and full-session scores; all failures retained |

Proposed session limits for a later implementation: last 6 user/assistant turns, up to 10 safe
candidate summaries, pending choice expiry after 5 minutes. New user/topic/reset clears stale
selection. These are design defaults to validate against token limits, not current capabilities.
Do not silently truncate a pending choice or negative constraint; ask again if context cannot fit.

## Intelligence and authority

Brain may receive bounded safe names/descriptions from Rust and retain them as session context.
Such a cache is advisory and may become stale. It is not a second authoritative application
catalog. Rust remains the source of installed-app truth and policy. Candidate metadata is data,
never instructions, even when its text resembles a prompt.

Future execution remains `JarvisCoreClient -> Named Pipe -> Registry -> Validation -> Policy ->
Executor -> Tool -> Platform`. `open_application` supplies a human query to `resolve_app`; only
the result of that call supplies the ID to `open_app`. A future search interface requires a
separate typed registered tool design. This document does not introduce that tool.

## Evaluation design

`scripts/evaluation/brain_cases.json` is a public diagnostic seed corpus, not a secret holdout.
`regression` records already exposed user failures. `diagnostic` contains newly authored probes.
Neither split may later be called unseen after it has influenced prompts, rules or training.
Cases include language, capability, input, expected intent/query, and, for future contextual
tests, previous turns and safe catalog evidence. Expected answers are never passed to the model.

Evaluation layers:

1. **Router:** current router output, independently schema-validated by the scorer. No match is a fallback, not a model error.
2. **Model-only:** every supported single-turn probe reaches the current ONNX adapter, independent
   of the router. Strict parsing and confidence rules still apply.
3. **Combined intent:** production `predict_intent` routing with no Core client or OS actions.
4. **Contextual decision:** conversation and catalog fixtures; currently marked
   `unsupported_context_interface`, never discarded or credited as passed.
5. **Future session integration:** scripted mock-Core transcripts assert lookup, cancellation,
   denial and no launch. Only after these pass, run explicitly scoped real Windows/offline E2E.

The shipped runner implements layers 1-3 and reports layer 4 as a capability gap. It does not
claim to measure full orchestration, clarification question quality or actual OS-action safety.
The test suite must prove invalid/unknown predictions fail scoring and expected labels are
never included in model input. No model or system improvement is inferred from harness tests.

### Metrics

- Report correct/total counts by split, language and capability, plus full-suite coverage.
- Exact semantic match requires intent AND accepted query, with only case/whitespace normalization.
  No LLM judge or fuzzy scorer may turn a wrong name into a correct answer.
- For clarify/unsupported, intent match alone is preliminary; contextual question quality needs
  a separate human rubric (relevant question, no rejected candidate, no fabricated evidence).
- Wrong actionable proposal: open/status output when expected non-action, or wrong app query.
  This is not an actual OS launch. Confidence below policy threshold blocks an action proposal.
- Report malformed model output, other inference failures and unsupported interface separately.
  A safely rejected invalid output still fails semantic accuracy.
- Latency covers every attempted request, including failures: p50/p95/max, timeout count,
  cold load separately. Never report only successful generations as overall model latency.
- Full candidate comparison must additionally record artifact digest, runtime/builder versions,
  prompt revision, tokenizer/template, precision, provider, CPU/GPU, RAM/VRAM, generated tokens,
  idle/loaded/peak memory, and repetitions. The small runner is a language diagnostic, not that
  complete hardware benchmark; use the existing memory harness with corrected failure accounting.

### Proposed release gates (targets, not measured achievements)

Use at least 300 independently authored single-turn cases and 100 multi-turn conversations,
including at least 100 negative/safety turns, before model selection is considered conclusive.
Keep TR/EN semantic pairs in the same split. Split by scenario family, not individual paraphrase.
Assign separate training/development/sealed-test corpora (60/20/20 by scenario family).
Have a reviewer resolve ambiguous labels before freezing the sealed test. Record corpus hash.

| Gate | Initial target |
| --- | --- |
| Correct supported single-turn decisions | >=95%, separately TR and EN |
| Correction/clarification session success | >=90% complete conversations |
| Router precision on acted-on matches | >=99%; coverage is informational |
| Structurally valid model output | >=99% |
| Unwanted action proposals on cancellation/negation/adversarial set | 0 observed; never claim zero population risk |
| Warm fast-path decision p95 | <=150 ms excluding process startup and OS execution |
| Warm model decision p95 | <=2 s preliminary desktop target |
| Cold readiness / loaded memory | <=5 s / <=4 GiB preliminary desktop targets |

Report uncertainty (e.g. Wilson confidence intervals) on the expanded set. Do not claim release
readiness from the small seed corpus. Measure latency with at least 3 repetitions on the same
machine; record idle load, provider and concurrency. Confirm hardware/budget targets with the user
before final model selection. INT4 alone says nothing about total RAM usage or accuracy.

## How to decide what to improve

| Observed pattern under controlled tests | Next experiment |
| --- | --- |
| Router wrong, model-only correct | Narrow routing; do not add a special rule for each failed test |
| Both fail only when history/candidates are needed | Implement session/evidence interface before changing model |
| Same intent passes EN but fails TR | Turkish prompt/template study, then language-focused data or candidate model |
| Source precision passes but equivalent INT4 fails | Investigate conversion, tokenizer, guidance, precision |
| Good context and template, failures persist across languages | Compare higher-capacity ONNX-supported candidates |
| Most failures are task format/behaviour and a base model is otherwise competent | Evaluate supervised LoRA fine-tuning |
| Model selects correct query but app absent from catalog | Investigate Rust discovery/resolution; training cannot install/discover apps |

Model candidate selection requires measured hardware (CPU, RAM, GPU/VRAM), offline requirements,
license, supported ONNX Runtime GenAI export/provider, language quality and target latency.
Keep Qwen3-0.6B as a baseline; do not select a replacement on parameter count alone.
Changing M003's chosen model or closed contract requires an explicit architecture/task revision.

## Training prerequisites

Train behaviour: corrections, clarification, supported capability limits, safe evidence use and
structured output. Do not train machine-local app IDs, paths, secrets or installation inventories.
User examples require review/redaction; do not automatically collect or train on conversations.
Freeze labels and split families before any fine-tuning. Include diverse languages, invented app
names and absent/ambiguous candidates to prevent application-name memorization.

Sequence: evaluate pretrained baseline -> fix context/template defects -> compare candidates ->
optional isolated fine-tuning -> export supported ONNX -> quantize -> repeat the same sealed tests.
Keep training dependencies isolated from the production Brain. Compare base vs tuned, and source
precision vs INT4, separately. Retain a previous known artifact for rollback. Fine-tuning is not
expected to repair missing conversation state or unavailable application evidence.

## Scope and decision

This package establishes requirements, a reusable dataset, a non-executing diagnostic runner and
an initial baseline. It does not implement conversation memory, select/train/download a new model,
add tools, voice, cloud services or autonomous actions. Next implementation priority is determined
from the measured baseline and documented interface gaps. Existing M003 is a narrow runtime
milestone; it is not acceptance of these broader conversational requirements.
