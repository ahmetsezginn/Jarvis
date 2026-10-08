# Session conversation context

User authorization: 2026-10-05, session-only memory is sufficient.
Scope: retain recent user/assistant pairs in one JarvisBrain; send to both local adapters.
Limits: six complete pairs, 2400 characters, existing 2048/128 token caps.
No persistence, training, new tools, cloud inference or generic chat intent.
/reset clears conversation and pending selection; cancellation clears earlier conversation.
With history, bypass legacy Fast Router to avoid interpreting corrections out of context.
Checks: fake-model context delivery, isolation, reset/cancel, bounds, prompt escaping,
strict output safety, real ONNX/GGUF inference without machine actions.
