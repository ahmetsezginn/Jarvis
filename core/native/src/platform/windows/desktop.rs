use std::{path::Path, path::PathBuf, process::Command};

use sysinfo::{Disks, System};

use crate::{
    apps::{DiscoveredApplication, TrustedLaunchTarget},
    core::JarvisError,
    platform::{DesktopPlatform, DiskStatus, MemoryStatus, SystemStatus},
};

pub struct WindowsDesktopPlatform;

impl Default for WindowsDesktopPlatform {
    fn default() -> Self {
        Self::new()
    }
}

impl WindowsDesktopPlatform {
    #[must_use]
    pub const fn new() -> Self {
        Self
    }
}

impl DesktopPlatform for WindowsDesktopPlatform {
    fn open_application(&self, application: &DiscoveredApplication) -> Result<(), JarvisError> {
        let target = application.launch();
        let path = target.path();
        if !path.is_file() {
            return Err(JarvisError::ApplicationLaunchFailed {
                app_id: application.app_id().to_string(),
                message: "trusted launch target no longer exists".to_owned(),
            });
        }
        let canonical_path =
            path.canonicalize()
                .map_err(|error| JarvisError::ApplicationLaunchFailed {
                    app_id: application.app_id().to_string(),
                    message: format!("could not normalize trusted launch target: {error}"),
                })?;
        let launch_result = match target {
            TrustedLaunchTarget::Shortcut(_) => Command::new(trusted_explorer_path()?)
                .arg(canonical_path)
                .spawn(),
            TrustedLaunchTarget::Executable { arguments, .. } => {
                Command::new(canonical_path).args(arguments).spawn()
            }
        };
        launch_result
            .map(|_child| ())
            .map_err(|error| JarvisError::ApplicationLaunchFailed {
                app_id: application.app_id().to_string(),
                message: error.to_string(),
            })
    }

    fn open_folder(&self, path: &Path) -> Result<(), JarvisError> {
        Command::new(trusted_explorer_path()?)
            .arg(path)
            .spawn()
            .map(|_child| ())
            .map_err(|error| JarvisError::ExecutionFailed {
                message: format!("could not open folder '{}': {error}", path.display()),
            })
    }

    fn system_status(&self) -> Result<SystemStatus, JarvisError> {
        let mut system = System::new_all();
        system.refresh_cpu_usage();
        system.refresh_memory();

        let total_memory = system.total_memory();
        let used_memory = system.used_memory();
        let disks = Disks::new_with_refreshed_list()
            .iter()
            .map(|disk| {
                let total = disk.total_space();
                let used = total.saturating_sub(disk.available_space());
                DiskStatus {
                    name: disk.mount_point().display().to_string(),
                    used_bytes: used,
                    total_bytes: total,
                    usage_percent: percentage(used, total),
                }
            })
            .collect();

        Ok(SystemStatus {
            cpu_usage_percent: system.global_cpu_usage(),
            memory: MemoryStatus {
                used_bytes: used_memory,
                total_bytes: total_memory,
                usage_percent: percentage(used_memory, total_memory),
            },
            disks,
        })
    }
}

fn trusted_explorer_path() -> Result<PathBuf, JarvisError> {
    let system_root =
        std::env::var_os("SystemRoot").ok_or_else(|| JarvisError::ExecutionFailed {
            message: "SystemRoot is unavailable; cannot resolve Windows Explorer".to_owned(),
        })?;
    let explorer = PathBuf::from(system_root).join("explorer.exe");
    if !explorer.is_file() {
        return Err(JarvisError::ExecutionFailed {
            message: format!(
                "trusted Windows Explorer was not found at '{}'",
                explorer.display()
            ),
        });
    }
    explorer
        .canonicalize()
        .map_err(|error| JarvisError::ExecutionFailed {
            message: format!(
                "could not normalize trusted Windows Explorer path '{}': {error}",
                explorer.display()
            ),
        })
}

fn percentage(used: u64, total: u64) -> f64 {
    if total == 0 {
        0.0
    } else {
        (used as f64 / total as f64) * 100.0
    }
}
