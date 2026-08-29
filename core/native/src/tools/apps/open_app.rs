use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    apps::{ApplicationCatalog, ApplicationId},
    core::{JarvisError, RiskLevel},
    tools::{Tool, ToolContext, ToolOutput},
};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct OpenAppArguments {
    app_id: String,
}

#[derive(Debug, Serialize)]
struct OpenAppOutput {
    opened: bool,
    app_id: ApplicationId,
    name: String,
}

pub struct OpenAppTool {
    catalog: Arc<ApplicationCatalog>,
}

impl OpenAppTool {
    #[must_use]
    pub fn new(catalog: Arc<ApplicationCatalog>) -> Self {
        Self { catalog }
    }
}

impl Tool for OpenAppTool {
    fn name(&self) -> &'static str {
        "open_app"
    }

    fn risk_level(&self) -> RiskLevel {
        RiskLevel::Low
    }

    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        let arguments = parse_arguments(arguments)?;
        let app_id = ApplicationId::parse(&arguments.app_id)?;
        self.catalog
            .get(&app_id)
            .ok_or(JarvisError::ApplicationNotFound {
                query: arguments.app_id,
            })
            .map(|_application| ())
    }

    fn execute(&self, context: &ToolContext, arguments: &Value) -> Result<ToolOutput, JarvisError> {
        let arguments = parse_arguments(arguments)?;
        let app_id = ApplicationId::parse(&arguments.app_id)?;
        let application = self
            .catalog
            .get(&app_id)
            .ok_or(JarvisError::ApplicationNotFound {
                query: arguments.app_id,
            })?;
        context.platform().open_application(&application)?;
        serde_json::to_value(OpenAppOutput {
            opened: true,
            app_id: application.app_id().clone(),
            name: application.canonical_name().to_owned(),
        })
        .map_err(|error| JarvisError::Internal {
            message: format!("could not serialize open_app result: {error}"),
        })
    }
}

fn parse_arguments(arguments: &Value) -> Result<OpenAppArguments, JarvisError> {
    serde_json::from_value(arguments.clone()).map_err(|error| JarvisError::InvalidArguments {
        message: error.to_string(),
    })
}
