use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::{ErrorDetail, JarvisError, RequestId, ToolName};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ToolStatus {
    Success,
    Denied,
    ConfirmationRequired,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolResult {
    pub request_id: RequestId,
    pub tool: ToolName,
    pub status: ToolStatus,
    pub data: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ErrorDetail>,
}

impl ToolResult {
    #[must_use]
    pub fn success(request_id: RequestId, tool: ToolName, data: Value) -> Self {
        Self {
            request_id,
            tool,
            status: ToolStatus::Success,
            data,
            error: None,
        }
    }

    #[must_use]
    pub fn failure(
        request_id: RequestId,
        tool: ToolName,
        status: ToolStatus,
        error: &JarvisError,
    ) -> Self {
        Self {
            request_id,
            tool,
            status,
            data: Value::Null,
            error: Some(error.detail()),
        }
    }
}
