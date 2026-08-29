use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use uuid::Uuid;

use crate::core::{RequestSource, ToolRequest, ToolResult, ToolStatus};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuditDecision {
    UnknownTool,
    ValidationFailed,
    Allow,
    Deny,
    RequireConfirmation,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct AuditEvent {
    pub event_id: Uuid,
    pub request_id: String,
    pub timestamp_unix_ms: Option<u64>,
    pub tool: String,
    pub source: RequestSource,
    pub decision: AuditDecision,
    pub status: ToolStatus,
    pub success: bool,
    pub error_code: Option<String>,
    pub duration_ms: u64,
}

impl AuditEvent {
    #[must_use]
    pub fn from_result(
        request: &ToolRequest,
        result: &ToolResult,
        decision: AuditDecision,
        duration: Duration,
    ) -> Self {
        Self {
            event_id: Uuid::new_v4(),
            request_id: request.request_id.to_string(),
            timestamp_unix_ms: current_unix_milliseconds(),
            tool: request.tool.to_string(),
            source: request.source,
            decision,
            status: result.status,
            success: result.status == ToolStatus::Success,
            error_code: result.error.as_ref().map(|error| error.code.clone()),
            duration_ms: u64::try_from(duration.as_millis()).unwrap_or(u64::MAX),
        }
    }
}

fn current_unix_milliseconds() -> Option<u64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()
        .and_then(|duration| u64::try_from(duration.as_millis()).ok())
}
