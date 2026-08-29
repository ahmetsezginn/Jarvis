use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use thiserror::Error;

use crate::apps::ApplicationCandidate;

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum JarvisError {
    #[error("unknown tool: {name}")]
    UnknownTool { name: String },

    #[error("tool is already registered: {name}")]
    DuplicateTool { name: String },

    #[error("invalid arguments: {message}")]
    InvalidArguments { message: String },

    #[error("policy denied the request: {reason}")]
    PolicyDenied { reason: String },

    #[error("confirmation is required: {reason}")]
    ConfirmationRequired { reason: String },

    #[error("platform is not supported: {platform}")]
    PlatformUnsupported { platform: String },

    #[error("application discovery failed: {message}")]
    ApplicationDiscoveryFailed { message: String },

    #[error("application was not found: {query}")]
    ApplicationNotFound { query: String },

    #[error("application query is ambiguous: {query}")]
    ApplicationAmbiguous {
        query: String,
        candidates: Vec<ApplicationCandidate>,
    },

    #[error("invalid application ID: {app_id}")]
    InvalidApplicationId { app_id: String },

    #[error("application launch failed for {app_id}: {message}")]
    ApplicationLaunchFailed { app_id: String, message: String },

    #[error("folder was not found: {path}")]
    FolderNotFound { path: String },

    #[error("path is not a directory: {path}")]
    NotADirectory { path: String },

    #[error("execution failed: {message}")]
    ExecutionFailed { message: String },

    #[error("system information is unavailable: {message}")]
    SystemInformationUnavailable { message: String },

    #[error("configuration error: {message}")]
    ConfigurationError { message: String },

    #[error("IPC is unavailable: {message}")]
    IpcUnavailable { message: String },

    #[error("internal error: {message}")]
    Internal { message: String },
}

impl JarvisError {
    #[must_use]
    pub const fn code(&self) -> &'static str {
        match self {
            Self::UnknownTool { .. } => "unknown_tool",
            Self::DuplicateTool { .. } => "duplicate_tool",
            Self::InvalidArguments { .. } => "invalid_arguments",
            Self::PolicyDenied { .. } => "policy_denied",
            Self::ConfirmationRequired { .. } => "confirmation_required",
            Self::PlatformUnsupported { .. } => "platform_unsupported",
            Self::ApplicationDiscoveryFailed { .. } => "application_discovery_failed",
            Self::ApplicationNotFound { .. } => "application_not_found",
            Self::ApplicationAmbiguous { .. } => "application_ambiguous",
            Self::InvalidApplicationId { .. } => "invalid_application_id",
            Self::ApplicationLaunchFailed { .. } => "application_launch_failed",
            Self::FolderNotFound { .. } => "folder_not_found",
            Self::NotADirectory { .. } => "not_a_directory",
            Self::ExecutionFailed { .. } => "execution_failed",
            Self::SystemInformationUnavailable { .. } => "system_information_unavailable",
            Self::ConfigurationError { .. } => "configuration_error",
            Self::IpcUnavailable { .. } => "ipc_unavailable",
            Self::Internal { .. } => "internal",
        }
    }

    #[must_use]
    pub fn detail(&self) -> ErrorDetail {
        ErrorDetail {
            code: self.code().to_owned(),
            message: self.to_string(),
            details: match self {
                Self::ApplicationAmbiguous { candidates, .. } => {
                    Some(json!({ "candidates": candidates }))
                }
                _ => None,
            },
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ErrorDetail {
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<Value>,
}
