mod catalog;
mod discovery;
pub mod fake;
mod model;
mod resolver;

#[cfg(windows)]
pub mod windows;

use std::sync::Arc;

pub use catalog::ApplicationCatalog;
pub use discovery::ApplicationDiscovery;
pub use model::{
    ApplicationCandidate, ApplicationId, ApplicationSource, DiscoveredApplication,
    ResolvedApplication, TrustedLaunchTarget,
};
pub use resolver::{ApplicationResolver, DeterministicApplicationResolver};

use crate::core::JarvisError;

#[cfg(windows)]
pub fn current_application_discovery() -> Result<Arc<dyn ApplicationDiscovery>, JarvisError> {
    Ok(Arc::new(
        windows::WindowsApplicationDiscovery::from_environment()?,
    ))
}

#[cfg(not(windows))]
pub fn current_application_discovery() -> Result<Arc<dyn ApplicationDiscovery>, JarvisError> {
    Err(JarvisError::PlatformUnsupported {
        platform: std::env::consts::OS.to_owned(),
    })
}

#[must_use]
pub(crate) fn normalize_application_text(value: &str) -> String {
    value
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
}
