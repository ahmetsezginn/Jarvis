use std::{
    path::{Path, PathBuf},
    sync::Mutex,
};

use crate::{apps::DiscoveredApplication, core::JarvisError};

use super::{DesktopPlatform, MemoryStatus, SystemStatus};

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct PlatformCalls {
    pub opened_applications: Vec<String>,
    pub opened_folders: Vec<PathBuf>,
    pub opened_files: Vec<PathBuf>,
    pub opened_steam_games: Vec<u32>,
    pub opened_files_with_apps: Vec<(PathBuf, String)>,
    pub system_status_count: usize,
}

pub struct FakeDesktopPlatform {
    calls: Mutex<PlatformCalls>,
    system_status: SystemStatus,
}

impl Default for FakeDesktopPlatform {
    fn default() -> Self {
        Self {
            calls: Mutex::new(PlatformCalls::default()),
            system_status: SystemStatus {
                cpu_usage_percent: 10.0,
                memory: MemoryStatus {
                    used_bytes: 25,
                    total_bytes: 100,
                    usage_percent: 25.0,
                },
                disks: Vec::new(),
            },
        }
    }
}

impl FakeDesktopPlatform {
    #[must_use]
    pub fn with_system_status(system_status: SystemStatus) -> Self {
        Self {
            calls: Mutex::new(PlatformCalls::default()),
            system_status,
        }
    }

    #[must_use]
    pub fn calls(&self) -> PlatformCalls {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }
}

impl DesktopPlatform for FakeDesktopPlatform {
    fn open_game_shortcut(
        &self,
        target: &crate::files::GameShortcutTarget,
    ) -> Result<(), JarvisError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .opened_steam_games
            .push(target.steam_app_id());
        Ok(())
    }
    fn open_file_with_app(
        &self,
        path: &Path,
        application: &DiscoveredApplication,
    ) -> Result<(), JarvisError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .opened_files_with_apps
            .push((path.to_path_buf(), application.app_id().to_string()));
        Ok(())
    }
    fn open_file(&self, path: &Path) -> Result<(), JarvisError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .opened_files
            .push(path.to_path_buf());
        Ok(())
    }
    fn open_application(&self, application: &DiscoveredApplication) -> Result<(), JarvisError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .opened_applications
            .push(application.app_id().to_string());
        Ok(())
    }

    fn open_folder(&self, path: &Path) -> Result<(), JarvisError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .opened_folders
            .push(path.to_path_buf());
        Ok(())
    }

    fn system_status(&self) -> Result<SystemStatus, JarvisError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .system_status_count += 1;
        Ok(self.system_status.clone())
    }
}
