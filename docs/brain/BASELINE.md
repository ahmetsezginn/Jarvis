# Brain diagnostic baseline — 2026-09-15

## Scope and reproducibility

Measured the existing production intent adapter and router, without changing their prompts,
weights, extraction rules, aliases or settings. No Core client was constructed and no machine
actions were performed. One run per mode; these timings are diagnostic, not stable hardware
performance claims. Full JSON per-case results are printed by the commands below.

- Qwen/Qwen3-0.6B revision `c1899de289a04d12100db370d81485cdf75e47ca`
- ONNX Runtime GenAI `0.15.2`, existing INT4 CPU artifact, non-thinking
- Existing 2048 input / 128 output token caps and confidence threshold 0.80
- Dataset SHA-256: `e744fed53137e30e03b79e06aca743113f7d9f7ab2195d3eee1935298e119628`
- Prompt file SHA-256: `1982526046c4b34955138195b6ac85ca2618b31fb80c4b82731b19b05cbefb12`
- Public corpus: 36 cases, 5 exposed regressions + 31 diagnostic cases; not a sealed holdout
- 28 single-turn cases attempted; 8 context cases explicitly unsupported in every mode

## Results

| Measurement | Router only | Model forced | Combined intent pipeline |
| --- | ---: | ---: | ---: |
| Exact semantic match / 28 single turns | 11/28 | 2/28 | 11/28 |
| Full-suite requirements covered correctly / 36 | 11/36 | 2/36 | 11/36 |
| Wrong actionable query/intent proposals | 7 | 9 | 10 |
| ModelOutputInvalid | N/A | 14/28 | 5/10 model fallbacks |
| Router fallbacks | 10/28 | N/A | 10/28 |
| Request p50 (ms), includes failed requests | 0.020 | 3979.865 | 0.086 |
| Request p95 (ms), includes failed requests | 0.041 | 4204.851 | 4069.035 |
| Maximum request time (ms) | 0.179 | 5696.967 | 4396.547 |
| Model load (ms), excluded from request times | N/A | 4085.261 | 3432.388 |

Router matched 18 cases: 11 correct, 7 incorrect (61.1% matched-result precision). Its unmatched
cases are legitimate fallbacks, not evidence of a model defect. Combined mode still only got
11/28 exact decisions because none of the 10 fallbacks passed this seed set's full rubric.

Single-turn TR/EN denominators exclude context gaps:

| Mode | Turkish | English |
| --- | ---: | ---: |
| Router | 7/16 | 4/12 |
| Model | 1/16 | 1/12 |
| Combined | 7/16 | 4/12 |

An incorrect human query counts as a wrong action proposal, even if Rust would later reject it.
These are NOT observed unintended launches. The test does not measure final Rust resolver or
policy decisions. Invalid outputs are safely rejected but are not counted as semantic successes.

## Representative evidence

| Case | Observed behaviour | Implication |
| --- | --- | --- |
| d01: Hesap Makinesi'ni aç | Router retains `'ni`; model produces invalid output | Extraction and model output both need investigation |
| d02: Open Calculator | Router extracts Calculator; model query is Open Calculator | Model issue also exists in English |
| d12: Open Notepad, not Firefox | Router includes `not Firefox`; model correctly extracts Notepad | Router can suppress a correct model decision |
| d07/d08: RAM usage question | Model asks a clarification instead of system_status | Semantics fail in both languages |
| d13/d14: unspecified application | Action query invented from generic application phrase | Confidence 0.95-1.0 does not establish correctness |
| r04/d15/d16: open a site inside browser | Router produces app launch query | Capability boundaries need semantic handling |
| c01-c08 | Interface cannot accept history/evidence | Model-only replacement cannot supply missing state |

Model-correct IDs: d12, d23. Combined/router-correct IDs: r01, r02, r03, d02, d05, d18,
d19, d20, d21, d23, d24. This makes the summary auditable against a rerun without implying
that unlisted cases are all the same failure category.

## Decision

The current pipeline does not meet the proposed conversational requirements. This evidence
does not establish that the base Qwen family is incapable, nor isolate INT4 degradation.
No comparison against source precision, alternate prompting or larger models was performed.

Next bounded experiments, in priority order:

1. Diagnose the adapter output contract: compare official chat-template parity, generation
   stopping, guidance and precision in an isolated no-action harness. Keep strict validation.
2. Implement a bounded session/evidence interface, with mock-Core conversations, under a new
   task contract. Then evaluate c01-c08 and expand to longer conversations.
3. Narrow Fast Router eligibility for ambiguity/negation/relational requests, tested on fresh
   scenario families. Avoid tuning only to this now-exposed corpus.
4. Compare a few supported local candidates using the same context and budget after recording
   available CPU/RAM/GPU/VRAM. Do not prescribe a model before that comparison.
5. Consider fine-tuning only after architecture/configuration errors are isolated and a reviewed
   training/development/sealed-test split exists.

## Limits

This is an initial 36-case diagnostic, not a representative release evaluation. Context scenarios
are fixtures for future work, not executed conversations. No training, alternate model, new tools,
language translation pipeline or production behaviour changes were implemented.
No fresh hardware memory profile, conversion-quality comparison or repeated latency experiment
was run. The runner has no independent hard per-request deadline; a blocked native inference may
require cancelling the process. Deadline/cancellation measurement remains an explicit requirement
before broader candidate benchmarking. The native inference token cap is not a wall-clock timeout.
No Windows/offline E2E was repeated because this evaluator cannot execute Core actions.

## Exact validation commands

Run in repository root using the existing production Brain environment:

```powershell
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --validate-only
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --mode router
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --mode model
.\services\brain\.venv\Scripts\python.exe -m scripts.evaluation.evaluate_brain --mode combined
.\services\brain\.venv\Scripts\python.exe -m ruff format --check scripts\evaluation services\brain\tests\test_brain_evaluation.py
.\services\brain\.venv\Scripts\python.exe -m ruff check scripts\evaluation services\brain\tests\test_brain_evaluation.py
.\services\brain\.venv\Scripts\python.exe -m pytest services\brain\tests
git diff --check
```

Harness validation is separate from model quality: its tests must pass even when the model scores
poorly. The opt-in standalone ONNX integration test is skipped in the default unit test run;
the model/combined evaluations above actually exercised ONNX inference.
