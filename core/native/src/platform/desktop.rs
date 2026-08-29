use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::{apps::DiscoveredApplication, core::JarvisError};

pub trait DesktopPlatform: Send + Sync {
    fn open_application(&self, application: &DiscoveredApplication) -> Result<(), JarvisError>;
    fn open_folder(&self, path: &Path) -> Result<(), JarvisError>;
    fn system_status(&self) -> Result<SystemStatus, JarvisError>;
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SystemStatus {
    pub cpu_usage_percent: f32,
    pub memory: MemoryStatus,
    pub disks: Vec<DiskStatus>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MemoryStatus {
    pub used_bytes: u64,
    pub total_bytes: u64,
    pub usage_percent: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DiskStatus {
    pub name: String,
    pub used_bytes: u64,
    pub total_bytes: u64,
    pub usage_percent: f64,
}
