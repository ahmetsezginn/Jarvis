use crate::{
    core::{JarvisError, RiskLevel},
    desktop::{Command, DesktopService},
    tools::{Tool, ToolContext, ToolOutput},
};
use serde::Deserialize;
use serde_json::Value;
use std::sync::Arc;

pub struct DesktopTool {
    name: &'static str,
    service: Arc<DesktopService>,
}
#[derive(Deserialize, Default)]
#[serde(deny_unknown_fields)]
struct Arguments {
    session: Option<String>,
}
impl DesktopTool {
    pub fn all(service: Arc<DesktopService>) -> Vec<Arc<dyn Tool>> {
        [
            "desktop_attach",
            "desktop_close",
            "desktop_detach",
            "desktop_poll",
        ]
        .into_iter()
        .map(|name| {
            Arc::new(Self {
                name,
                service: service.clone(),
            }) as Arc<dyn Tool>
        })
        .collect()
    }
    fn arguments(&self, value: &Value) -> Result<Arguments, JarvisError> {
        let invalid = || JarvisError::InvalidArguments {
            message: "Invalid desktop arguments".into(),
        };
        let args: Arguments = serde_json::from_value(value.clone()).map_err(|_| invalid())?;
        let needs_session = matches!(self.name, "desktop_poll" | "desktop_detach");
        let object = value.as_object().ok_or_else(invalid)?;
        if (needs_session
            && (object.len() != 1
                || args
                    .session
                    .as_ref()
                    .is_none_or(|s| uuid::Uuid::parse_str(s).is_err())))
            || (!needs_session && !object.is_empty())
        {
            return Err(invalid());
        }
        Ok(args)
    }
}
impl Tool for DesktopTool {
    fn name(&self) -> &'static str {
        self.name
    }
    fn risk_level(&self) -> RiskLevel {
        RiskLevel::Low
    }
    fn validate(&self, value: &Value) -> Result<(), JarvisError> {
        self.arguments(value).map(|_| ())
    }
    fn execute(&self, _: &ToolContext, value: &Value) -> Result<ToolOutput, JarvisError> {
        let args = self.arguments(value)?;
        self.service.request(match self.name {
            "desktop_attach" => Command::Attach,
            "desktop_poll" => Command::Poll(args.session.unwrap()),
            "desktop_detach" => Command::Detach(args.session.unwrap()),
            _ => Command::Close,
        })
    }
}
