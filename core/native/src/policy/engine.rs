use crate::{
    core::{RiskLevel, ToolRequest},
    tools::ToolMetadata,
};

use super::PolicyDecision;

pub trait PolicyEngine: Send + Sync {
    fn evaluate(&self, request: &ToolRequest, metadata: &ToolMetadata) -> PolicyDecision;
}

pub struct DefaultPolicyEngine;

impl PolicyEngine for DefaultPolicyEngine {
    fn evaluate(&self, _request: &ToolRequest, metadata: &ToolMetadata) -> PolicyDecision {
        match metadata.risk_level {
            RiskLevel::ReadOnly | RiskLevel::Low => PolicyDecision::Allow,
            RiskLevel::Medium | RiskLevel::High => PolicyDecision::RequireConfirmation {
                reason: format!(
                    "tool '{}' has {:?} risk",
                    metadata.name, metadata.risk_level
                ),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;
    use crate::core::{RequestSource, ToolRequest};

    fn decision_for(risk_level: RiskLevel) -> PolicyDecision {
        DefaultPolicyEngine.evaluate(
            &ToolRequest::new("test", json!({}), RequestSource::Internal),
            &ToolMetadata {
                name: "test",
                risk_level,
            },
        )
    }

    #[test]
    fn allows_read_only_tool() {
        assert_eq!(decision_for(RiskLevel::ReadOnly), PolicyDecision::Allow);
    }

    #[test]
    fn allows_low_risk_tool() {
        assert_eq!(decision_for(RiskLevel::Low), PolicyDecision::Allow);
    }

    #[test]
    fn requires_confirmation_for_medium_risk_tool() {
        assert!(matches!(
            decision_for(RiskLevel::Medium),
            PolicyDecision::RequireConfirmation { .. }
        ));
    }

    #[test]
    fn requires_confirmation_for_high_risk_tool() {
        assert!(matches!(
            decision_for(RiskLevel::High),
            PolicyDecision::RequireConfirmation { .. }
        ));
    }
}
