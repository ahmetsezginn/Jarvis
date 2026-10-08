# Conversation/task admission

Authorized by user's explicit correction: ordinary questions must not activate Rust tools.
Separate typed read-only request classification, read-only reply generation, and task execution.
Task enum/IPC/Rust policy remain unchanged; respond is a response-only event. Strictly validate
both new schemas; no string-to-tool path. Session-only history, bounded inference, no new tools.
Real tests: greetings, conceptual question, how-to question, unsupported folder request, recall,
then explicit app launch and live system inspection, with a mock Core recording exact calls.
GGUF is the conversational provider; ONNX refuses unvalidated reply generation. Do not claim
zero population routing error from these small tests. docs/brain/REQUEST_ROUTING.md owns results.
