use std::{collections::BTreeMap, sync::Arc};

use crate::core::JarvisError;

use super::{Tool, ToolMetadata};

#[derive(Default)]
pub struct ToolRegistry {
    tools: BTreeMap<&'static str, Arc<dyn Tool>>,
}

impl ToolRegistry {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, tool: Arc<dyn Tool>) -> Result<(), JarvisError> {
        let name = tool.name();
        if self.tools.contains_key(name) {
            return Err(JarvisError::DuplicateTool {
                name: name.to_owned(),
            });
        }
        self.tools.insert(name, tool);
        Ok(())
    }

    pub fn get(&self, name: &str) -> Result<Arc<dyn Tool>, JarvisError> {
        self.tools
            .get(name)
            .cloned()
            .ok_or_else(|| JarvisError::UnknownTool {
                name: name.to_owned(),
            })
    }

    #[must_use]
    pub fn list(&self) -> Vec<ToolMetadata> {
        self.tools.values().map(|tool| tool.metadata()).collect()
    }
}

#[cfg(test)]
mod tests {
    use serde_json::Value;

    use super::*;
    use crate::{
        core::RiskLevel,
        tools::{ToolContext, ToolOutput},
    };

    struct TestTool;

    impl Tool for TestTool {
        fn name(&self) -> &'static str {
            "test"
        }

        fn risk_level(&self) -> RiskLevel {
            RiskLevel::ReadOnly
        }

        fn validate(&self, _arguments: &Value) -> Result<(), JarvisError> {
            Ok(())
        }

        fn execute(
            &self,
            _context: &ToolContext,
            _arguments: &Value,
        ) -> Result<ToolOutput, JarvisError> {
            Ok(Value::Null)
        }
    }

    #[test]
    fn registers_and_resolves_tool() {
        let mut registry = ToolRegistry::new();
        registry
            .register(Arc::new(TestTool))
            .expect("first registration should succeed");

        let tool = registry.get("test").expect("tool should resolve");
        assert_eq!(tool.name(), "test");
        assert_eq!(registry.list().len(), 1);
    }

    #[test]
    fn rejects_duplicate_tool_name() {
        let mut registry = ToolRegistry::new();
        registry.register(Arc::new(TestTool)).unwrap();

        let error = registry
            .register(Arc::new(TestTool))
            .expect_err("duplicate should fail");
        assert_eq!(
            error,
            JarvisError::DuplicateTool {
                name: "test".to_owned()
            }
        );
    }

    #[test]
    fn returns_typed_error_for_unknown_tool() {
        let registry = ToolRegistry::new();
        let error = registry.get("missing").err().expect("lookup should fail");

        assert_eq!(
            error,
            JarvisError::UnknownTool {
                name: "missing".to_owned()
            }
        );
    }
}
