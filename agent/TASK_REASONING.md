# Interpretation before capability expansion

User asked to focus on reasoning before extending features (2026-10-06).
First stage: existing-intent interpretation, app/folder separation, negation, corrections,
use conversation context, trustworthy notifications. Implemented and measured; see
../docs/brain/REASONING_DIAGNOSTIC.md. No fine-tuning or new tools/model.
Unresolved: ordinary replies and recall cannot be represented by current intent enum.
Proposed respond intent must carry only a bounded message, perform zero Core calls, retain
strict parsing and use session-only context. Await user's choice before implementation.
Broader quality requires independently authored conversations and reporting failures, not
more keyword rules or a claim that extra output tokens create reasoning ability.
