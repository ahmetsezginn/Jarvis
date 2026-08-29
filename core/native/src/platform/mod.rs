mod desktop;
pub mod fake;

#[cfg(windows)]
pub mod windows;

use std::sync::Arc;

pub use desktop::{DesktopPlatform, DiskStatus, MemoryStatus, SystemStatus};

#[cfg(not(windows))]
use crate::core::JarvisError;

#[cfg(windows)]
#[must_use]
pub fn current_desktop_platform() -> Arc<dyn DesktopPlatform> {
    Arc::new(windows::WindowsDesktopPlatform::new())
}

#[cfg(not(windows))]
#[must_use]
pub fn current_desktop_platform() -> Arc<dyn DesktopPlatform> {
    Arc::new(UnsupportedDesktopPlatform)
}

#[cfg(not(windows))]
struct UnsupportedDesktopPlatform;

#[cfg(not(windows))]
impl DesktopPlatform for UnsupportedDesktopPlatform {
    fn open_application(
        &self,
        _application: &crate::apps::DiscoveredApplication,
    ) -> Result<(), JarvisError> {
        Err(unsupported_platform_error())
    }

    fn open_folder(&self, _path: &std::path::Path) -> Result<(), JarvisError> {
        Err(unsupported_platform_error())
    }

    fn system_status(&self) -> Result<SystemStatus, JarvisError> {
        Err(unsupported_platform_error())
    }
}

#[cfg(not(windows))]
fn unsupported_platform_error() -> JarvisError {
    JarvisError::PlatformUnsupported {
        platform: std::env::consts::OS.to_owned(),
    }
}
