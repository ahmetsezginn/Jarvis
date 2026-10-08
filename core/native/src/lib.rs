pub mod apps;
pub mod audit;
pub mod config;
pub mod core;
pub mod executor;
pub mod ipc;
pub mod platform;
pub mod policy;
pub mod tools;

use std::sync::Arc;

use apps::{ApplicationCatalog, DeterministicApplicationResolver};
use audit::AuditSink;
use core::JarvisError;
use executor::Executor;
use platform::DesktopPlatform;
use policy::DefaultPolicyEngine;
use tools::{
    OpenAppTool, OpenFolderTool, RefreshAppCatalogTool, ResolveAppTool, SystemStatusTool,
    ToolRegistry,
};

/// Builds the single trusted execution pipeline used by every TASK-001 client.
pub fn build_executor(
    platform: Arc<dyn DesktopPlatform>,
    catalog: Arc<ApplicationCatalog>,
    audit: Arc<dyn AuditSink>,
) -> Result<Executor, JarvisError> {
    let mut registry = ToolRegistry::new();
    registry.register(Arc::new(SystemStatusTool::new()))?;
    registry.register(Arc::new(OpenFolderTool::new()))?;
    registry.register(Arc::new(ResolveAppTool::new(
        catalog.clone(),
        Arc::new(DeterministicApplicationResolver),
    )))?;
    registry.register(Arc::new(RefreshAppCatalogTool::new(catalog.clone())))?;
    registry.register(Arc::new(OpenAppTool::new(catalog)))?;

    Ok(Executor::new(
        registry,
        Arc::new(DefaultPolicyEngine),
        audit,
        platform,
    ))
}
