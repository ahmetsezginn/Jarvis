use std::{fs, sync::Arc};

use jarvis_core::{
    apps::{
        ApplicationCatalog, ApplicationId, ApplicationSource, DiscoveredApplication,
        TrustedLaunchTarget, fake::FakeApplicationDiscovery,
    },
    audit::{AuditDecision, MemoryAuditSink},
    config::ApplicationPreferences,
    core::{JarvisError, RequestSource, RiskLevel, ToolRequest, ToolStatus},
    executor::Executor,
    platform::fake::FakeDesktopPlatform,
    policy::{PolicyDecision, PolicyEngine},
    tools::{
        OpenAppTool, SystemStatusTool, Tool, ToolContext, ToolMetadata, ToolOutput, ToolRegistry,
    },
};
use serde_json::{Value, json};
use tempfile::TempDir;

struct FixedPolicy(PolicyDecision);

impl PolicyEngine for FixedPolicy {
    fn evaluate(&self, _request: &ToolRequest, _metadata: &ToolMetadata) -> PolicyDecision {
        self.0.clone()
    }
}

struct FailingTool;

impl Tool for FailingTool {
    fn name(&self) -> &'static str {
        "failing_tool"
    }

    fn risk_level(&self) -> RiskLevel {
        RiskLevel::Low
    }

    fn validate(&self, _arguments: &Value) -> Result<(), JarvisError> {
        Ok(())
    }

    fn execute(
        &self,
        _context: &ToolContext,
        _arguments: &Value,
    ) -> Result<ToolOutput, JarvisError> {
        Err(JarvisError::ExecutionFailed {
            message: "expected test failure".to_owned(),
        })
    }
}

fn executor_with_policy(
    decision: PolicyDecision,
) -> (Executor, Arc<FakeDesktopPlatform>, Arc<MemoryAuditSink>) {
    let platform = Arc::new(FakeDesktopPlatform::default());
    let audit = Arc::new(MemoryAuditSink::default());
    let mut registry = ToolRegistry::new();
    registry
        .register(Arc::new(SystemStatusTool::new()))
        .unwrap();
    let executor = Executor::new(
        registry,
        Arc::new(FixedPolicy(decision)),
        audit.clone(),
        platform.clone(),
    );
    (executor, platform, audit)
}

fn test_application(
    directory: &TempDir,
    identity: &str,
    name: &str,
    aliases: &[&str],
) -> DiscoveredApplication {
    let executable = directory.path().join(format!("{identity}.exe"));
    fs::write(&executable, b"test").unwrap();
    DiscoveredApplication::new(
        ApplicationSource::AdministrativeOverride,
        identity,
        name,
        aliases.iter().map(|alias| (*alias).to_owned()).collect(),
        None,
        TrustedLaunchTarget::Executable {
            path: executable,
            arguments: Vec::new(),
        },
    )
    .unwrap()
}

fn catalog(applications: Vec<DiscoveredApplication>) -> Arc<ApplicationCatalog> {
    let catalog = Arc::new(ApplicationCatalog::new(
        Arc::new(FakeApplicationDiscovery::succeeding(applications)),
        ApplicationPreferences::default(),
    ));
    catalog.refresh().unwrap();
    catalog
}

#[test]
fn unknown_tool_never_reaches_platform_and_is_audited() {
    let (executor, platform, audit) = executor_with_policy(PolicyDecision::Allow);
    let result = executor.execute(ToolRequest::new(
        "missing",
        json!({}),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Failed);
    assert_eq!(result.error.unwrap().code, "unknown_tool");
    assert_eq!(platform.calls().system_status_count, 0);
    assert_eq!(audit.events().len(), 1);
    assert_eq!(audit.events()[0].decision, AuditDecision::UnknownTool);
}

#[test]
fn invalid_arguments_never_reach_platform() {
    let (executor, platform, audit) = executor_with_policy(PolicyDecision::Allow);
    let result = executor.execute(ToolRequest::new(
        "system_status",
        json!({ "unexpected": true }),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Failed);
    assert_eq!(platform.calls().system_status_count, 0);
    assert_eq!(audit.events()[0].decision, AuditDecision::ValidationFailed);
}

#[test]
fn denied_request_never_executes() {
    let (executor, platform, audit) = executor_with_policy(PolicyDecision::Deny {
        reason: "test denial".to_owned(),
    });
    let result = executor.execute(ToolRequest::new(
        "system_status",
        json!({}),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Denied);
    assert_eq!(platform.calls().system_status_count, 0);
    assert_eq!(audit.events()[0].decision, AuditDecision::Deny);
}

#[test]
fn confirmation_required_request_never_executes() {
    let (executor, platform, audit) = executor_with_policy(PolicyDecision::RequireConfirmation {
        reason: "test confirmation".to_owned(),
    });
    let result = executor.execute(ToolRequest::new(
        "system_status",
        json!({}),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::ConfirmationRequired);
    assert_eq!(platform.calls().system_status_count, 0);
    assert_eq!(
        audit.events()[0].decision,
        AuditDecision::RequireConfirmation
    );
}

#[test]
fn allowed_request_executes_exactly_once_and_emits_audit() {
    let (executor, platform, audit) = executor_with_policy(PolicyDecision::Allow);
    let result = executor.execute(ToolRequest::new(
        "system_status",
        json!({}),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Success);
    assert_eq!(platform.calls().system_status_count, 1);
    assert_eq!(audit.events().len(), 1);
    assert_eq!(audit.events()[0].decision, AuditDecision::Allow);
    assert!(audit.events()[0].success);
}

#[test]
fn failed_execution_is_returned_and_audited() {
    let platform = Arc::new(FakeDesktopPlatform::default());
    let audit = Arc::new(MemoryAuditSink::default());
    let mut registry = ToolRegistry::new();
    registry.register(Arc::new(FailingTool)).unwrap();
    let executor = Executor::new(
        registry,
        Arc::new(FixedPolicy(PolicyDecision::Allow)),
        audit.clone(),
        platform,
    );

    let result = executor.execute(ToolRequest::new(
        "failing_tool",
        json!({}),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Failed);
    assert_eq!(result.error.unwrap().code, "execution_failed");
    assert_eq!(audit.events()[0].decision, AuditDecision::Allow);
    assert!(!audit.events()[0].success);
}

#[test]
fn resolve_app_requires_query() {
    let executor = jarvis_core::build_executor(
        Arc::new(FakeDesktopPlatform::default()),
        catalog(Vec::new()),
        Arc::new(MemoryAuditSink::default()),
    )
    .unwrap();

    let result = executor.execute(ToolRequest::new(
        "resolve_app",
        json!({}),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Failed);
    assert_eq!(result.error.unwrap().code, "invalid_arguments");
}

#[test]
fn resolve_app_returns_metadata_without_launch_target() {
    let directory = tempfile::tempdir().unwrap();
    let application = test_application(&directory, "spotify", "Spotify", &["music"]);
    let executable_path = directory.path().join("spotify.exe").display().to_string();
    let executor = jarvis_core::build_executor(
        Arc::new(FakeDesktopPlatform::default()),
        catalog(vec![application]),
        Arc::new(MemoryAuditSink::default()),
    )
    .unwrap();

    let result = executor.execute(ToolRequest::new(
        "resolve_app",
        json!({ "query": "music" }),
        RequestSource::Internal,
    ));
    let serialized = serde_json::to_string(&result).unwrap();

    assert_eq!(result.status, ToolStatus::Success);
    assert_eq!(result.data["app"]["name"], "Spotify");
    assert!(!serialized.contains(&executable_path));
    assert!(!serialized.contains("executable"));
}

#[test]
fn ambiguity_is_typed_audited_and_contains_safe_candidates() {
    let directory = tempfile::tempdir().unwrap();
    let applications = vec![
        test_application(&directory, "vscode", "Visual Studio Code", &[]),
        test_application(&directory, "codeblocks", "CodeBlocks", &[]),
    ];
    let audit = Arc::new(MemoryAuditSink::default());
    let executor = jarvis_core::build_executor(
        Arc::new(FakeDesktopPlatform::default()),
        catalog(applications),
        audit.clone(),
    )
    .unwrap();

    let result = executor.execute(ToolRequest::new(
        "resolve_app",
        json!({ "query": "code" }),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Failed);
    let error = result.error.unwrap();
    assert_eq!(error.code, "application_ambiguous");
    assert_eq!(
        error.details.unwrap()["candidates"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(
        audit.events()[0].error_code.as_deref(),
        Some("application_ambiguous")
    );
}

#[test]
fn open_app_rejects_missing_id_raw_path_and_caller_executable() {
    let platform = Arc::new(FakeDesktopPlatform::default());
    let executor = jarvis_core::build_executor(
        platform.clone(),
        catalog(Vec::new()),
        Arc::new(MemoryAuditSink::default()),
    )
    .unwrap();

    for arguments in [
        json!({}),
        json!({ "app_id": r"C:\random\payload.exe" }),
        json!({ "path": r"C:\random\payload.exe" }),
        json!({ "executable": "powershell.exe" }),
    ] {
        let result = executor.execute(ToolRequest::new(
            "open_app",
            arguments,
            RequestSource::Internal,
        ));
        assert_eq!(result.status, ToolStatus::Failed);
    }
    assert!(platform.calls().opened_applications.is_empty());
}

#[test]
fn open_app_rejects_unknown_well_formed_id() {
    let platform = Arc::new(FakeDesktopPlatform::default());
    let executor = jarvis_core::build_executor(
        platform.clone(),
        catalog(Vec::new()),
        Arc::new(MemoryAuditSink::default()),
    )
    .unwrap();
    let unknown = ApplicationId::from_source(ApplicationSource::AdministrativeOverride, "unknown");

    let result = executor.execute(ToolRequest::new(
        "open_app",
        json!({ "app_id": unknown }),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Failed);
    assert_eq!(result.error.unwrap().code, "application_not_found");
    assert!(platform.calls().opened_applications.is_empty());
}

#[test]
fn valid_app_id_launches_only_catalog_backed_application() {
    let directory = tempfile::tempdir().unwrap();
    let application = test_application(&directory, "trusted", "Trusted App", &[]);
    let app_id = application.app_id().clone();
    let platform = Arc::new(FakeDesktopPlatform::default());
    let executor = jarvis_core::build_executor(
        platform.clone(),
        catalog(vec![application]),
        Arc::new(MemoryAuditSink::default()),
    )
    .unwrap();

    let result = executor.execute(ToolRequest::new(
        "open_app",
        json!({ "app_id": app_id.clone() }),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Success);
    assert_eq!(result.data["name"], "Trusted App");
    assert_eq!(platform.calls().opened_applications, [app_id.to_string()]);
}

#[test]
fn policy_denial_prevents_catalog_backed_application_launch() {
    let directory = tempfile::tempdir().unwrap();
    let application = test_application(&directory, "trusted", "Trusted App", &[]);
    let app_id = application.app_id().clone();
    let catalog = catalog(vec![application]);
    let platform = Arc::new(FakeDesktopPlatform::default());
    let mut registry = ToolRegistry::new();
    registry
        .register(Arc::new(OpenAppTool::new(catalog)))
        .unwrap();
    let executor = Executor::new(
        registry,
        Arc::new(FixedPolicy(PolicyDecision::Deny {
            reason: "blocked".to_owned(),
        })),
        Arc::new(MemoryAuditSink::default()),
        platform.clone(),
    );

    let result = executor.execute(ToolRequest::new(
        "open_app",
        json!({ "app_id": app_id }),
        RequestSource::Internal,
    ));

    assert_eq!(result.status, ToolStatus::Denied);
    assert!(platform.calls().opened_applications.is_empty());
}

#[test]
fn production_registry_contains_only_task_001_tools() {
    let executor = jarvis_core::build_executor(
        Arc::new(FakeDesktopPlatform::default()),
        catalog(Vec::new()),
        Arc::new(MemoryAuditSink::default()),
    )
    .expect("registry should build");
    let metadata = executor.list_tools();
    let names: Vec<_> = metadata.iter().map(|item| item.name).collect();

    assert_eq!(
        names,
        ["open_app", "open_folder", "resolve_app", "system_status"]
    );
    assert_eq!(metadata[0].risk_level, RiskLevel::Low);
    assert_eq!(metadata[1].risk_level, RiskLevel::Low);
    assert_eq!(metadata[2].risk_level, RiskLevel::ReadOnly);
    assert_eq!(metadata[3].risk_level, RiskLevel::ReadOnly);
}
