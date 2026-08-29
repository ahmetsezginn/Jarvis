use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::core::ErrorDetail;

pub const CONTROL_PROTOCOL_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RequestEnvelope {
    pub protocol_version: u32,
    pub request_id: String,
    pub message_type: String,
    pub payload: Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ResponseEnvelope {
    pub protocol_version: u32,
    pub request_id: String,
    pub message_type: String,
    pub ok: bool,
    pub payload: Option<Value>,
    pub error: Option<ErrorDetail>,
}

#[must_use]
pub fn success_response(
    request_id: impl Into<String>,
    message_type: impl Into<String>,
    payload: Value,
) -> ResponseEnvelope {
    ResponseEnvelope {
        protocol_version: CONTROL_PROTOCOL_VERSION,
        request_id: request_id.into(),
        message_type: message_type.into(),
        ok: true,
        payload: Some(payload),
        error: None,
    }
}

#[must_use]
pub fn error_response(
    request_id: impl Into<String>,
    code: impl Into<String>,
    message: impl Into<String>,
) -> ResponseEnvelope {
    ResponseEnvelope {
        protocol_version: CONTROL_PROTOCOL_VERSION,
        request_id: request_id.into(),
        message_type: "error".to_owned(),
        ok: false,
        payload: None,
        error: Some(ErrorDetail {
            code: code.into(),
            message: message.into(),
            details: None,
        }),
    }
}
