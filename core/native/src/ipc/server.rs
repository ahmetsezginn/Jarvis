use std::{io, sync::Arc};

use serde::Deserialize;
use serde_json::{Value, json};

use crate::{
    core::{RequestId, RequestSource, ToolName, ToolRequest, ToolStatus},
    executor::Executor,
};

use super::{
    CONTROL_PROTOCOL_VERSION, IpcListener, IpcStream, RequestEnvelope, ResponseEnvelope,
    error_response, read_frame, success_response, write_json_frame,
};

pub struct ControlServer {
    executor: Arc<Executor>,
}

impl ControlServer {
    #[must_use]
    pub fn new(executor: Arc<Executor>) -> Self {
        Self { executor }
    }

    pub fn serve(&self, listener: &dyn IpcListener) -> io::Result<()> {
        loop {
            let stream = listener.accept()?;
            let executor = self.executor.clone();
            let endpoint = listener.endpoint().to_owned();
            std::thread::Builder::new()
                .name("jarvis-ipc-client".to_owned())
                .spawn(move || {
                    tracing::info!(target: "jarvis.ipc", pipe_endpoint = %endpoint, "client connected");
                    if let Err(error) = Self::handle_connection(stream, executor) {
                        tracing::warn!(target: "jarvis.ipc", error = %error, "client connection rejected");
                    }
                    tracing::info!(target: "jarvis.ipc", pipe_endpoint = %endpoint, "client disconnected");
                })?;
        }
    }

    fn handle_connection(
        mut stream: Box<dyn IpcStream>,
        executor: Arc<Executor>,
    ) -> io::Result<()> {
        let mut session = ControlSession::new(executor);
        loop {
            let payload = match read_frame(&mut stream) {
                Ok(Some(payload)) => payload,
                Ok(None) => return Ok(()),
                Err(error) => {
                    let response = error_response("", error.code(), error.to_string());
                    let _ = write_json_frame(&mut stream, &response);
                    return Err(io::Error::new(io::ErrorKind::InvalidData, error));
                }
            };

            let response = session.handle_payload(&payload);
            let close_connection = response
                .error
                .as_ref()
                .is_some_and(|error| error.code == "unsupported_protocol_version");
            write_json_frame(&mut stream, &response)
                .map_err(|error| io::Error::other(error.to_string()))?;
            if close_connection {
                return Ok(());
            }
        }
    }
}

pub struct ControlSession {
    executor: Arc<Executor>,
    handshake_complete: bool,
}

impl ControlSession {
    #[must_use]
    pub fn new(executor: Arc<Executor>) -> Self {
        Self {
            executor,
            handshake_complete: false,
        }
    }

    #[must_use]
    pub fn handle_payload(&mut self, bytes: &[u8]) -> ResponseEnvelope {
        let request = match serde_json::from_slice::<RequestEnvelope>(bytes) {
            Ok(request) => request,
            Err(error) => {
                return error_response(
                    extract_request_id(bytes).unwrap_or_default(),
                    "invalid_message",
                    format!("request must be a valid UTF-8 JSON envelope: {error}"),
                );
            }
        };
        self.handle_request(request)
    }

    #[must_use]
    pub fn handle_request(&mut self, request: RequestEnvelope) -> ResponseEnvelope {
        if request.protocol_version != CONTROL_PROTOCOL_VERSION {
            tracing::warn!(
                target: "jarvis.ipc",
                request_id = %request.request_id,
                received_version = request.protocol_version,
                "unsupported control protocol version"
            );
            return error_response(
                request.request_id,
                "unsupported_protocol_version",
                format!(
                    "protocol version {} is unsupported; server requires {}",
                    request.protocol_version, CONTROL_PROTOCOL_VERSION
                ),
            );
        }

        let request_id = match RequestId::parse(&request.request_id) {
            Ok(request_id) => request_id,
            Err(error) => {
                return error_response(
                    request.request_id,
                    "invalid_message",
                    format!("request_id must be a UUID: {error}"),
                );
            }
        };

        if request.message_type == "hello" {
            return self.hello(request);
        }
        if !self.handshake_complete {
            return error_response(
                request.request_id,
                "handshake_required",
                "a successful hello handshake is required before this message",
            );
        }

        tracing::debug!(
            target: "jarvis.ipc",
            request_id = %request.request_id,
            message_type = %request.message_type,
            "control request received"
        );
        match request.message_type.as_str() {
            "ping" => self.ping(request),
            "list_tools" => self.list_tools(request),
            "execute_tool" => self.execute_tool(request, request_id),
            _ => error_response(
                request.request_id,
                "unknown_message_type",
                format!("unknown message type: {}", request.message_type),
            ),
        }
    }

    fn hello(&mut self, request: RequestEnvelope) -> ResponseEnvelope {
        let hello: HelloPayload = match serde_json::from_value(request.payload) {
            Ok(payload) => payload,
            Err(error) => {
                return error_response(
                    request.request_id,
                    "invalid_message",
                    format!("invalid hello payload: {error}"),
                );
            }
        };
        if hello.client.trim().is_empty() || hello.client_version.trim().is_empty() {
            return error_response(
                request.request_id,
                "invalid_message",
                "hello client and client_version must be non-empty strings",
            );
        }

        self.handshake_complete = true;
        tracing::info!(
            target: "jarvis.ipc",
            request_id = %request.request_id,
            client = %hello.client,
            client_version = %hello.client_version,
            "control handshake completed"
        );
        success_response(
            request.request_id,
            "hello_ack",
            json!({
                "core": "jarvis-core",
                "core_version": env!("CARGO_PKG_VERSION"),
                "protocol_version": CONTROL_PROTOCOL_VERSION,
            }),
        )
    }

    fn ping(&self, request: RequestEnvelope) -> ResponseEnvelope {
        if let Err(error) = validate_empty_payload(request.payload) {
            return error_response(request.request_id, "invalid_message", error);
        }
        success_response(request.request_id, "pong", json!({ "status": "ok" }))
    }

    fn list_tools(&self, request: RequestEnvelope) -> ResponseEnvelope {
        if let Err(error) = validate_empty_payload(request.payload) {
            return error_response(request.request_id, "invalid_message", error);
        }
        success_response(
            request.request_id,
            "tools",
            json!({ "tools": self.executor.list_tools() }),
        )
    }

    fn execute_tool(&self, request: RequestEnvelope, request_id: RequestId) -> ResponseEnvelope {
        let payload: ExecuteToolPayload = match serde_json::from_value(request.payload) {
            Ok(payload) => payload,
            Err(error) => {
                return error_response(
                    request.request_id,
                    "invalid_message",
                    format!("invalid execute_tool payload: {error}"),
                );
            }
        };
        if payload.tool.trim().is_empty() {
            return error_response(
                request.request_id,
                "invalid_message",
                "execute_tool tool must be a non-empty string",
            );
        }

        tracing::info!(
            target: "jarvis.ipc",
            request_id = %request.request_id,
            tool = %payload.tool,
            "forwarding Brain tool request to executor"
        );
        let tool_request = ToolRequest {
            request_id,
            tool: ToolName::new(payload.tool),
            arguments: payload.arguments,
            source: RequestSource::Brain,
        };
        let result = self.executor.execute(tool_request);
        let ok = result.status == ToolStatus::Success;
        let error = result.error.clone();
        let payload = match serde_json::to_value(&result) {
            Ok(payload) => payload,
            Err(serialization_error) => {
                return error_response(
                    request.request_id,
                    "internal_protocol_error",
                    format!("could not serialize tool result: {serialization_error}"),
                );
            }
        };
        ResponseEnvelope {
            protocol_version: CONTROL_PROTOCOL_VERSION,
            request_id: request.request_id,
            message_type: "tool_result".to_owned(),
            ok,
            payload: Some(payload),
            error,
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct HelloPayload {
    client: String,
    client_version: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ExecuteToolPayload {
    tool: String,
    arguments: Value,
}

fn validate_empty_payload(payload: Value) -> Result<(), String> {
    match payload {
        Value::Object(object) if object.is_empty() => Ok(()),
        _ => Err("payload must be an empty JSON object".to_owned()),
    }
}

fn extract_request_id(bytes: &[u8]) -> Option<String> {
    serde_json::from_slice::<Value>(bytes)
        .ok()?
        .get("request_id")?
        .as_str()
        .map(ToOwned::to_owned)
}

#[cfg(test)]
mod tests {
    use std::{
        io::{Cursor, Read, Write},
        sync::Arc,
    };

    use serde_json::json;
    use uuid::Uuid;

    use super::*;
    use crate::{
        apps::{ApplicationCatalog, fake::FakeApplicationDiscovery},
        audit::MemoryAuditSink,
        config::ApplicationPreferences,
        core::RequestSource,
        platform::fake::FakeDesktopPlatform,
    };

    fn test_runtime() -> (
        Arc<Executor>,
        Arc<FakeDesktopPlatform>,
        Arc<MemoryAuditSink>,
    ) {
        let platform = Arc::new(FakeDesktopPlatform::default());
        let audit = Arc::new(MemoryAuditSink::default());
        let catalog = Arc::new(ApplicationCatalog::new(
            Arc::new(FakeApplicationDiscovery::succeeding(Vec::new())),
            ApplicationPreferences::default(),
        ));
        catalog.refresh().unwrap();
        let executor =
            Arc::new(crate::build_executor(platform.clone(), catalog, audit.clone()).unwrap());
        (executor, platform, audit)
    }

    fn request(message_type: &str, payload: Value) -> RequestEnvelope {
        RequestEnvelope {
            protocol_version: CONTROL_PROTOCOL_VERSION,
            request_id: Uuid::new_v4().to_string(),
            message_type: message_type.to_owned(),
            payload,
        }
    }

    fn handshake(session: &mut ControlSession) {
        let response = session.handle_request(request(
            "hello",
            json!({ "client": "jarvis-brain", "client_version": "0.1.0" }),
        ));
        assert!(response.ok);
    }

    #[test]
    fn hello_and_ping_work_on_persistent_session() {
        let (executor, _, _) = test_runtime();
        let mut session = ControlSession::new(executor);
        handshake(&mut session);
        let response = session.handle_request(request("ping", json!({})));
        assert!(response.ok);
        assert_eq!(response.message_type, "pong");
        assert_eq!(response.payload.unwrap()["status"], "ok");
    }

    #[test]
    fn normal_messages_require_handshake() {
        let (executor, _, _) = test_runtime();
        let mut session = ControlSession::new(executor);
        let response = session.handle_request(request("ping", json!({})));
        assert_eq!(response.error.unwrap().code, "handshake_required");
    }

    #[test]
    fn unsupported_version_cannot_execute_tool() {
        let (executor, platform, audit) = test_runtime();
        let mut session = ControlSession::new(executor);
        let mut incompatible = request(
            "execute_tool",
            json!({ "tool": "system_status", "arguments": {} }),
        );
        incompatible.protocol_version = 99;
        let response = session.handle_request(incompatible);
        assert_eq!(response.error.unwrap().code, "unsupported_protocol_version");
        assert_eq!(platform.calls().system_status_count, 0);
        assert!(audit.events().is_empty());
    }

    #[test]
    fn list_tools_comes_from_production_registry() {
        let (executor, _, _) = test_runtime();
        let mut session = ControlSession::new(executor);
        handshake(&mut session);
        let response = session.handle_request(request("list_tools", json!({})));
        let tools = response.payload.unwrap()["tools"]
            .as_array()
            .unwrap()
            .clone();
        let names: Vec<_> = tools
            .iter()
            .map(|tool| tool["name"].as_str().unwrap())
            .collect();
        assert_eq!(
            names,
            [
                "open_app",
                "open_folder",
                "refresh_app_catalog",
                "resolve_app",
                "system_status"
            ]
        );
    }

    #[test]
    fn execute_tool_uses_brain_source_executor_and_audit() {
        let (executor, platform, audit) = test_runtime();
        let mut session = ControlSession::new(executor);
        handshake(&mut session);
        let response = session.handle_request(request(
            "execute_tool",
            json!({ "tool": "system_status", "arguments": {} }),
        ));
        assert!(response.ok);
        assert_eq!(platform.calls().system_status_count, 1);
        assert_eq!(audit.events().len(), 1);
        assert_eq!(audit.events()[0].source, RequestSource::Brain);
    }

    #[test]
    fn invalid_arguments_and_caller_paths_never_reach_platform() {
        let (executor, platform, audit) = test_runtime();
        let mut session = ControlSession::new(executor);
        handshake(&mut session);
        for arguments in [
            json!({ "app_id": r"C:\Windows\System32\cmd.exe" }),
            json!({ "path": r"C:\Windows\System32\cmd.exe" }),
            json!({ "executable": "cmd.exe" }),
        ] {
            let response = session.handle_request(request(
                "execute_tool",
                json!({ "tool": "open_app", "arguments": arguments }),
            ));
            assert!(!response.ok);
        }
        assert!(platform.calls().opened_applications.is_empty());
        assert_eq!(audit.events().len(), 3);
    }

    #[test]
    fn malformed_json_and_unknown_message_have_typed_errors() {
        let (executor, _, _) = test_runtime();
        let mut session = ControlSession::new(executor);
        let malformed = session.handle_payload(b"{not-json");
        assert_eq!(malformed.error.unwrap().code, "invalid_message");
        handshake(&mut session);
        let unknown = session.handle_request(request("future_message", json!({})));
        assert_eq!(unknown.error.unwrap().code, "unknown_message_type");
    }

    struct TestStream {
        input: Cursor<Vec<u8>>,
        output: Vec<u8>,
    }

    impl Read for TestStream {
        fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
            self.input.read(buffer)
        }
    }

    impl Write for TestStream {
        fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
            self.output.extend_from_slice(buffer);
            Ok(buffer.len())
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn malformed_connection_does_not_poison_a_subsequent_session() {
        let (executor, _, _) = test_runtime();
        let malformed = TestStream {
            input: Cursor::new(vec![0, 0]),
            output: Vec::new(),
        };
        assert!(ControlServer::handle_connection(Box::new(malformed), executor.clone()).is_err());

        let mut encoded = Vec::new();
        write_json_frame(
            &mut encoded,
            &request(
                "hello",
                json!({ "client": "jarvis-brain", "client_version": "0.1.0" }),
            ),
        )
        .unwrap();
        let valid = TestStream {
            input: Cursor::new(encoded),
            output: Vec::new(),
        };
        assert!(ControlServer::handle_connection(Box::new(valid), executor).is_ok());
    }
}
