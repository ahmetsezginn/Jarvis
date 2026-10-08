use crate::{
    apps::ApplicationCatalog,
    core::{JarvisError, RiskLevel},
    tools::{Tool, ToolContext, ToolOutput},
};
use serde::Deserialize;
use serde_json::{Value, json};
use std::sync::Arc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Arguments {}

pub struct RefreshAppCatalogTool {
    catalog: Arc<ApplicationCatalog>,
}
impl RefreshAppCatalogTool {
    pub fn new(catalog: Arc<ApplicationCatalog>) -> Self {
        Self { catalog }
    }
}
impl Tool for RefreshAppCatalogTool {
    fn name(&self) -> &'static str {
        "refresh_app_catalog"
    }
    fn risk_level(&self) -> RiskLevel {
        RiskLevel::ReadOnly
    }
    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        if !arguments.is_object() {
            return Err(JarvisError::InvalidArguments {
                message: "catalog refresh requires an empty JSON object".to_owned(),
            });
        }
        serde_json::from_value::<Arguments>(arguments.clone())
            .map(|_| ())
            .map_err(|error| JarvisError::InvalidArguments {
                message: error.to_string(),
            })
    }
    fn execute(&self, _: &ToolContext, arguments: &Value) -> Result<ToolOutput, JarvisError> {
        self.validate(arguments)?;
        let count = self.catalog.refresh()?;
        Ok(json!({"refreshed": true, "discovered": count}))
    }
}
