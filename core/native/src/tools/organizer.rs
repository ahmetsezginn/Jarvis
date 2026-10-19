use crate::{
    core::{JarvisError, RiskLevel},
    organizer::{AddItem, ListItems, Organizer, UpdateItem, local_clock},
    tools::{Tool, ToolContext, ToolOutput},
};
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::sync::Arc;

pub struct OrganizerTool {
    operation: &'static str,
    store: Arc<Organizer>,
}
fn parse<T: DeserializeOwned>(args: &Value) -> Result<T, JarvisError> {
    serde_json::from_value(args.clone()).map_err(|_| JarvisError::InvalidArguments {
        message: "invalid personal organizer arguments".into(),
    })
}
impl OrganizerTool {
    pub fn all(store: Arc<Organizer>) -> Vec<Arc<dyn Tool>> {
        [
            "organizer_clock",
            "organizer_list",
            "organizer_add",
            "organizer_update",
        ]
        .into_iter()
        .map(|operation| {
            Arc::new(Self {
                operation,
                store: store.clone(),
            }) as Arc<dyn Tool>
        })
        .collect()
    }
}
impl Tool for OrganizerTool {
    fn name(&self) -> &'static str {
        self.operation
    }
    fn risk_level(&self) -> RiskLevel {
        if ["organizer_add", "organizer_update"].contains(&self.operation) {
            RiskLevel::Low
        } else {
            RiskLevel::ReadOnly
        }
    }
    fn validate(&self, args: &Value) -> Result<(), JarvisError> {
        match self.operation {
            "organizer_add" => parse::<AddItem>(args)?.validate(),
            "organizer_list" => parse::<ListItems>(args)?.validate(),
            "organizer_update" => parse::<UpdateItem>(args)?.validate(),
            _ if args.as_object().is_some_and(|m| m.is_empty()) => Ok(()),
            _ => Err(JarvisError::InvalidArguments {
                message: "clock expects empty arguments".into(),
            }),
        }
    }
    fn execute(&self, _: &ToolContext, args: &Value) -> Result<ToolOutput, JarvisError> {
        self.validate(args)?;
        Ok(match self.operation {
            "organizer_add" => json!({"saved": true, "item": self.store.add(&parse(args)?)?}),
            "organizer_list" => json!(self.store.list(&parse(args)?)?),
            "organizer_update" => json!({"saved": true, "item": self.store.update(&parse(args)?)?}),
            _ => local_clock(),
        })
    }
}
