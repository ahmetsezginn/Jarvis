use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    apps::{ApplicationCandidate, ApplicationCatalog, ApplicationResolver},
    core::{JarvisError, RiskLevel},
    tools::{Tool, ToolContext, ToolOutput},
};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ResolveAppArguments {
    query: String,
}

#[derive(Debug, Serialize)]
struct ResolveAppOutput {
    resolved: bool,
    app: ApplicationCandidate,
}

pub struct ResolveAppTool {
    catalog: Arc<ApplicationCatalog>,
    resolver: Arc<dyn ApplicationResolver>,
}

impl ResolveAppTool {
    #[must_use]
    pub fn new(catalog: Arc<ApplicationCatalog>, resolver: Arc<dyn ApplicationResolver>) -> Self {
        Self { catalog, resolver }
    }
}

impl Tool for ResolveAppTool {
    fn name(&self) -> &'static str {
        "resolve_app"
    }

    fn risk_level(&self) -> RiskLevel {
        RiskLevel::ReadOnly
    }

    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        let arguments = parse_arguments(arguments)?;
        let query = arguments.query.trim();
        if query.is_empty() || query.len() > 256 {
            return Err(JarvisError::InvalidArguments {
                message: "query must contain between 1 and 256 characters".to_owned(),
            });
        }
        Ok(())
    }

    fn execute(
        &self,
        _context: &ToolContext,
        arguments: &Value,
    ) -> Result<ToolOutput, JarvisError> {
        let arguments = parse_arguments(arguments)?;
        let resolved = self.resolver.resolve(&arguments.query, &self.catalog)?;
        serde_json::to_value(ResolveAppOutput {
            resolved: true,
            app: resolved.candidate(),
        })
        .map_err(|error| JarvisError::Internal {
            message: format!("could not serialize resolve_app result: {error}"),
        })
    }
}

fn parse_arguments(arguments: &Value) -> Result<ResolveAppArguments, JarvisError> {
    serde_json::from_value(arguments.clone()).map_err(|error| JarvisError::InvalidArguments {
        message: error.to_string(),
    })
}
