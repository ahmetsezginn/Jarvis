use std::sync::Arc;

use serde::Serialize;
use serde_json::Value;

use crate::{
    core::{JarvisError, RiskLevel},
    platform::DesktopPlatform,
};

pub type ToolOutput = Value;

pub struct ToolContext {
    platform: Arc<dyn DesktopPlatform>,
}

impl ToolContext {
    #[must_use]
    pub fn new(platform: Arc<dyn DesktopPlatform>) -> Self {
        Self { platform }
    }

    #[must_use]
    pub fn platform(&self) -> &dyn DesktopPlatform {
        self.platform.as_ref()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct ToolMetadata {
    pub name: &'static str,
    pub risk_level: RiskLevel,
}

pub trait Tool: Send + Sync {
    fn name(&self) -> &'static str;
    fn risk_level(&self) -> RiskLevel;
    fn validate(&self, arguments: &Value) -> Result<(), JarvisError>;
    fn execute(&self, context: &ToolContext, arguments: &Value) -> Result<ToolOutput, JarvisError>;

    fn metadata(&self) -> ToolMetadata {
        ToolMetadata {
            name: self.name(),
            risk_level: self.risk_level(),
        }
    }
}
