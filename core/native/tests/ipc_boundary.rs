use std::sync::Arc;

use jarvis_core::{
    audit::{AuditDecision, MemoryAuditSink},
    core::{JarvisError, RequestSource, RiskLevel, ToolRequest},
    executor::Executor,
    ipc::{CONTROL_PROTOCOL_VERSION, ControlSession, RequestEnvelope},
    platform::fake::FakeDesktopPlatform,
    policy::{PolicyDecision, PolicyEngine},
    tools::{SystemStatusTool, ToolMetadata, ToolRegistry},
};
use serde_json::json;
use uuid::Uuid;

struct FixedPolicy(PolicyDecision);

impl PolicyEngine for FixedPolicy {
    fn evaluate(&self, _request: &ToolRequest, _metadata: &ToolMetadata) -> PolicyDecision {
        self.0.clone()
    }
}

fn request(message_type: &str, payload: serde_json::Value) -> RequestEnvelope {
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

fn session_with_policy(
    decision: PolicyDecision,
) -> (
    ControlSession,
    Arc<FakeDesktopPlatform>,
    Arc<MemoryAuditSink>,
) {
    let platform = Arc::new(FakeDesktopPlatform::default());
    let audit = Arc::new(MemoryAuditSink::default());
    let mut registry = ToolRegistry::new();
    registry
        .register(Arc::new(SystemStatusTool::new()))
        .unwrap();
    let executor = Arc::new(Executor::new(
        registry,
        Arc::new(FixedPolicy(decision)),
        audit.clone(),
        platform.clone(),
    ));
    let mut session = ControlSession::new(executor);
    handshake(&mut session);
    (session, platform, audit)
}

#[test]
fn ipc_policy_denial_never_reaches_platform() {
    let (mut session, platform, audit) = session_with_policy(PolicyDecision::Deny {
        reason: "IPC policy test".to_owned(),
    });
    let response = session.handle_request(request(
        "execute_tool",
        json!({ "tool": "system_status", "arguments": {} }),
    ));

    assert!(!response.ok);
    assert_eq!(response.error.unwrap().code, "policy_denied");
    assert_eq!(platform.calls().system_status_count, 0);
    assert_eq!(audit.events()[0].source, RequestSource::Brain);
    assert_eq!(audit.events()[0].decision, AuditDecision::Deny);
}

#[test]
fn ipc_unknown_tool_is_audited_and_never_reaches_platform() {
    let (mut session, platform, audit) = session_with_policy(PolicyDecision::Allow);
    let response = session.handle_request(request(
        "execute_tool",
        json!({ "tool": "missing", "arguments": {} }),
    ));

    assert!(!response.ok);
    assert_eq!(response.error.unwrap().code, "unknown_tool");
    assert_eq!(platform.calls().system_status_count, 0);
    assert_eq!(audit.events()[0].source, RequestSource::Brain);
    assert_eq!(audit.events()[0].decision, AuditDecision::UnknownTool);
}

#[test]
fn ipc_rejects_non_uuid_request_id_before_executor() {
    let (mut session, platform, audit) = session_with_policy(PolicyDecision::Allow);
    let mut invalid = request(
        "execute_tool",
        json!({ "tool": "system_status", "arguments": {} }),
    );
    invalid.request_id = "caller-controlled-text".to_owned();
    let response = session.handle_request(invalid);

    assert_eq!(response.error.unwrap().code, "invalid_message");
    assert_eq!(platform.calls().system_status_count, 0);
    assert!(audit.events().is_empty());
}

#[test]
fn ipc_invalid_app_id_error_remains_typed() -> Result<(), JarvisError> {
    let platform = Arc::new(FakeDesktopPlatform::default());
    let audit = Arc::new(MemoryAuditSink::default());
    let catalog = Arc::new(jarvis_core::apps::ApplicationCatalog::new(
        Arc::new(jarvis_core::apps::fake::FakeApplicationDiscovery::succeeding(Vec::new())),
        jarvis_core::config::ApplicationPreferences::default(),
    ));
    catalog.refresh()?;
    let executor = Arc::new(jarvis_core::build_executor(
        platform.clone(),
        catalog,
        audit,
    )?);
    let mut session = ControlSession::new(executor);
    handshake(&mut session);
    let response = session.handle_request(request(
        "execute_tool",
        json!({
            "tool": "open_app",
            "arguments": { "app_id": r"C:\Windows\System32\cmd.exe" }
        }),
    ));

    assert!(!response.ok);
    assert_eq!(response.error.unwrap().code, "invalid_application_id");
    assert!(platform.calls().opened_applications.is_empty());
    Ok(())
}

#[test]
fn risk_metadata_still_comes_from_registered_rust_tool() {
    let (mut session, _, _) = session_with_policy(PolicyDecision::Allow);
    let response = session.handle_request(request("list_tools", json!({})));
    let tool = &response.payload.unwrap()["tools"][0];
    assert_eq!(tool["name"], "system_status");
    assert_eq!(
        tool["risk_level"],
        serde_json::to_value(RiskLevel::ReadOnly).unwrap()
    );
}
