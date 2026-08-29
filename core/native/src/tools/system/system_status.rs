use serde_json::Value;

use crate::{
    core::{JarvisError, RiskLevel},
    tools::{Tool, ToolContext, ToolOutput},
};

pub struct SystemStatusTool;

impl Default for SystemStatusTool {
    fn default() -> Self {
        Self::new()
    }
}

impl SystemStatusTool {
    #[must_use]
    pub const fn new() -> Self {
        Self
    }
}

impl Tool for SystemStatusTool {
    fn name(&self) -> &'static str {
        "system_status"
    }

    fn risk_level(&self) -> RiskLevel {
        RiskLevel::ReadOnly
    }

    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        match arguments.as_object() {
            Some(map) if map.is_empty() => Ok(()),
            _ => Err(JarvisError::InvalidArguments {
                message: "system_status expects an empty JSON object".to_owned(),
            }),
        }
    }

    fn execute(
        &self,
        context: &ToolContext,
        _arguments: &Value,
    ) -> Result<ToolOutput, JarvisError> {
        let status = context.platform().system_status()?;
        serde_json::to_value(status).map_err(|error| JarvisError::Internal {
            message: format!("could not serialize system status: {error}"),
        })
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use serde_json::json;

    use super::*;
    use crate::platform::fake::FakeDesktopPlatform;

    #[test]
    fn produces_typed_serializable_result() {
        let platform = Arc::new(FakeDesktopPlatform::default());
        let context = ToolContext::new(platform.clone());
        let output = SystemStatusTool::new()
            .execute(&context, &json!({}))
            .expect("fake status should serialize");

        assert_eq!(output["cpu_usage_percent"], 10.0);
        assert_eq!(output["memory"]["total_bytes"], 100);
        assert_eq!(platform.calls().system_status_count, 1);
        serde_json::to_string(&output).expect("tool output should serialize");
    }
}
