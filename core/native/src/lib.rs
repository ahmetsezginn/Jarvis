pub mod apps;
pub mod audio;
pub mod audit;
pub mod config;
pub mod core;
pub mod desktop;
pub mod executor;
pub mod files;
pub mod ipc;
pub mod organizer;
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
    build_executor_with_files(
        platform,
        catalog,
        audit,
        Arc::new(files::FileCatalog::new(Vec::new())?),
    )
}

pub fn build_executor_with_files(
    platform: Arc<dyn DesktopPlatform>,
    catalog: Arc<ApplicationCatalog>,
    audit: Arc<dyn AuditSink>,
    files: Arc<files::FileCatalog>,
) -> Result<Executor, JarvisError> {
    build_executor_with_organizer(
        platform,
        catalog,
        audit,
        files,
        Arc::new(organizer::Organizer::in_memory()),
    )
}

/// Production supplies the current user's persistent store; tests use isolated stores.
pub fn build_executor_with_organizer(
    platform: Arc<dyn DesktopPlatform>,
    catalog: Arc<ApplicationCatalog>,
    audit: Arc<dyn AuditSink>,
    files: Arc<files::FileCatalog>,
    organizer: Arc<organizer::Organizer>,
) -> Result<Executor, JarvisError> {
    let mut registry = ToolRegistry::new();
    let desktop = Arc::new(desktop::DesktopService::default());
    registry.register(Arc::new(SystemStatusTool::new()))?;
    registry.register(Arc::new(OpenFolderTool::new()))?;
    for tool in tools::desktop::DesktopTool::all(desktop.clone()) {
        registry.register(tool)?;
    }
    for tool in tools::organizer::OrganizerTool::all(organizer) {
        registry.register(tool)?;
    }
    registry.register(Arc::new(ResolveAppTool::new(
        catalog.clone(),
        Arc::new(DeterministicApplicationResolver),
    )))?;
    registry.register(Arc::new(RefreshAppCatalogTool::new(catalog.clone())))?;
    registry.register(Arc::new(OpenAppTool::new(catalog.clone())))?;
    registry.register(Arc::new(tools::files::OpenFileWithAppTool::new(
        files.clone(),
        catalog.clone(),
    )))?;
    for tool in tools::files::FileCatalogTool::all(files) {
        registry.register(tool)?;
    }
    for tool in tools::audio::AudioTool::all(audio::current_service(), Some(catalog)) {
        registry.register(tool)?;
    }

    Ok(Executor::new(
        registry,
        Arc::new(DefaultPolicyEngine),
        audit,
        platform,
    ))
}
