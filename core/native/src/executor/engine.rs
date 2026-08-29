use std::{sync::Arc, time::Instant};

use crate::{
    audit::{AuditDecision, AuditEvent, AuditSink},
    core::{JarvisError, ToolRequest, ToolResult, ToolStatus},
    platform::DesktopPlatform,
    policy::{PolicyDecision, PolicyEngine},
    tools::{ToolContext, ToolMetadata, ToolRegistry},
};

pub struct Executor {
    registry: ToolRegistry,
    policy: Arc<dyn PolicyEngine>,
    audit: Arc<dyn AuditSink>,
    context: ToolContext,
}

impl Executor {
    #[must_use]
    pub fn new(
        registry: ToolRegistry,
        policy: Arc<dyn PolicyEngine>,
        audit: Arc<dyn AuditSink>,
        platform: Arc<dyn DesktopPlatform>,
    ) -> Self {
        Self {
            registry,
            policy,
            audit,
            context: ToolContext::new(platform),
        }
    }

    #[must_use]
    pub fn list_tools(&self) -> Vec<ToolMetadata> {
        self.registry.list()
    }

    #[must_use]
    pub fn execute(&self, request: ToolRequest) -> ToolResult {
        let started = Instant::now();
        let tool = match self.registry.get(request.tool.as_str()) {
            Ok(tool) => tool,
            Err(error) => {
                return self.finish_failure(
                    &request,
                    ToolStatus::Failed,
                    &error,
                    AuditDecision::UnknownTool,
                    started,
                );
            }
        };

        if let Err(error) = tool.validate(&request.arguments) {
            return self.finish_failure(
                &request,
                ToolStatus::Failed,
                &error,
                AuditDecision::ValidationFailed,
                started,
            );
        }

        let metadata = tool.metadata();
        match self.policy.evaluate(&request, &metadata) {
            PolicyDecision::Deny { reason } => {
                let error = JarvisError::PolicyDenied { reason };
                self.finish_failure(
                    &request,
                    ToolStatus::Denied,
                    &error,
                    AuditDecision::Deny,
                    started,
                )
            }
            PolicyDecision::RequireConfirmation { reason } => {
                let error = JarvisError::ConfirmationRequired { reason };
                self.finish_failure(
                    &request,
                    ToolStatus::ConfirmationRequired,
                    &error,
                    AuditDecision::RequireConfirmation,
                    started,
                )
            }
            PolicyDecision::Allow => match tool.execute(&self.context, &request.arguments) {
                Ok(data) => {
                    let result =
                        ToolResult::success(request.request_id, request.tool.clone(), data);
                    self.emit_audit(&request, &result, AuditDecision::Allow, started);
                    result
                }
                Err(error) => self.finish_failure(
                    &request,
                    ToolStatus::Failed,
                    &error,
                    AuditDecision::Allow,
                    started,
                ),
            },
        }
    }

    fn finish_failure(
        &self,
        request: &ToolRequest,
        status: ToolStatus,
        error: &JarvisError,
        decision: AuditDecision,
        started: Instant,
    ) -> ToolResult {
        let result = ToolResult::failure(request.request_id, request.tool.clone(), status, error);
        self.emit_audit(request, &result, decision, started);
        result
    }

    fn emit_audit(
        &self,
        request: &ToolRequest,
        result: &ToolResult,
        decision: AuditDecision,
        started: Instant,
    ) {
        self.audit.emit(&AuditEvent::from_result(
            request,
            result,
            decision,
            started.elapsed(),
        ));
    }
}
