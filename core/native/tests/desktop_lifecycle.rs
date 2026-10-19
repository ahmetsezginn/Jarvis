use jarvis_core::{
    audit::MemoryAuditSink,
    core::{RequestSource, ToolRequest, ToolStatus},
    desktop::{Command, DesktopService},
    executor::Executor,
    platform::fake::FakeDesktopPlatform,
    policy::{DefaultPolicyEngine, PolicyDecision, PolicyEngine},
    tools::{ToolMetadata, ToolRegistry, desktop::DesktopTool},
};
use serde_json::{Value, json};
use std::{sync::Arc, time::Duration};
fn engine(service: Arc<DesktopService>, policy: Arc<dyn PolicyEngine>) -> Executor {
    let mut registry = ToolRegistry::new();
    for tool in DesktopTool::all(service) {
        registry.register(tool).unwrap();
    }
    Executor::new(
        registry,
        policy,
        Arc::new(MemoryAuditSink::default()),
        Arc::new(FakeDesktopPlatform::default()),
    )
}
fn call(engine: &Executor, tool: &str, args: Value) -> Value {
    let result = engine.execute(ToolRequest::new(tool, args, RequestSource::Brain));
    assert_eq!(result.status, ToolStatus::Success, "{result:?}");
    result.data
}
#[test]
fn registered_close_request_is_visible_only_to_current_private_desktop_session() {
    let service = Arc::new(DesktopService::default());
    let engine = engine(service, Arc::new(DefaultPolicyEngine));
    let attached = call(&engine, "desktop_attach", json!({}));
    let id = attached["session"].as_str().unwrap();
    let closed = call(&engine, "desktop_close", json!({}));
    assert_eq!(closed["closing"], true);
    assert!(closed["revision"].as_u64().unwrap() > attached["revision"].as_u64().unwrap());
    assert!(closed.get("session").is_none());
    assert_eq!(
        call(&engine, "desktop_poll", json!({"session":id}))["closing"],
        true
    );
    call(&engine, "desktop_detach", json!({"session":id}));
    assert!(
        engine
            .execute(ToolRequest::new(
                "desktop_close",
                json!({}),
                RequestSource::Brain
            ))
            .error
            .is_some()
    );
    assert_eq!(call(&engine, "desktop_attach", json!({}))["closing"], false);
}
#[test]
fn stale_or_second_client_cannot_take_over_or_close_a_new_session() {
    let service = DesktopService::with_lease(Duration::from_millis(30));
    let id = service.request(Command::Attach).unwrap()["session"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(service.request(Command::Attach).is_err());
    assert!(
        service
            .request(Command::Poll(uuid::Uuid::new_v4().to_string()))
            .is_err()
    );
    std::thread::sleep(Duration::from_millis(60));
    assert!(service.request(Command::Close).is_err());
    service.request(Command::Attach).unwrap();
    assert!(service.request(Command::Detach(id)).is_err());
}
struct Deny;
impl PolicyEngine for Deny {
    fn evaluate(&self, _: &ToolRequest, _: &ToolMetadata) -> PolicyDecision {
        PolicyDecision::Deny {
            reason: "test".into(),
        }
    }
}
#[test]
fn policy_and_strict_schemas_prevent_unapproved_shutdown() {
    let service = Arc::new(DesktopService::default());
    let allowed = engine(service.clone(), Arc::new(DefaultPolicyEngine));
    for (name, args) in [
        ("desktop_attach", json!({"command":"shell"})),
        ("desktop_close", json!({"wake_enabled":true})),
        ("desktop_close", json!(null)),
        ("desktop_poll", json!({"session":"made-up"})),
        ("desktop_detach", json!({"session":null})),
    ] {
        assert!(
            allowed
                .execute(ToolRequest::new(name, args, RequestSource::Brain))
                .error
                .is_some()
        );
    }
    let id = call(&allowed, "desktop_attach", json!({}))["session"]
        .as_str()
        .unwrap()
        .to_owned();
    let denied = engine(service, Arc::new(Deny));
    assert!(
        denied
            .execute(ToolRequest::new(
                "desktop_close",
                json!({}),
                RequestSource::Brain
            ))
            .error
            .is_some()
    );
    assert_eq!(
        call(&allowed, "desktop_poll", json!({"session":id}))["closing"],
        false
    );
}
