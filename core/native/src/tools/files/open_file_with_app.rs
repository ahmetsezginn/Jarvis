use crate::{
    apps::{ApplicationCatalog, ApplicationId},
    core::{JarvisError, RiskLevel},
    files::FileCatalog,
    tools::{Tool, ToolContext, ToolOutput},
};
use serde::Deserialize;
use serde_json::Value;
use std::sync::Arc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Arguments {
    entry_id: String,
    app_id: String,
}

pub struct OpenFileWithAppTool {
    files: Arc<FileCatalog>,
    apps: Arc<ApplicationCatalog>,
}
impl OpenFileWithAppTool {
    pub fn new(files: Arc<FileCatalog>, apps: Arc<ApplicationCatalog>) -> Self {
        Self { files, apps }
    }
    fn parse(
        &self,
        value: &Value,
    ) -> Result<(String, crate::apps::DiscoveredApplication), JarvisError> {
        let args: Arguments =
            serde_json::from_value(value.clone()).map_err(|e| JarvisError::InvalidArguments {
                message: e.to_string(),
            })?;
        self.files.checked_entry(&args.entry_id)?;
        let app = self
            .apps
            .get(&ApplicationId::parse(&args.app_id)?)
            .ok_or(JarvisError::ApplicationNotFound { query: args.app_id })?;
        Ok((args.entry_id, app))
    }
}
impl Tool for OpenFileWithAppTool {
    fn name(&self) -> &'static str {
        "open_file_with_app"
    }
    fn risk_level(&self) -> RiskLevel {
        RiskLevel::Low
    }
    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        self.parse(arguments).map(|_| ())
    }
    fn execute(&self, context: &ToolContext, arguments: &Value) -> Result<ToolOutput, JarvisError> {
        let (id, app) = self.parse(arguments)?;
        self.files.open_with_app(&id, &app, context.platform())
    }
}
