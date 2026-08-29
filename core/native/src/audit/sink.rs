use std::sync::Mutex;

use super::AuditEvent;

pub trait AuditSink: Send + Sync {
    fn emit(&self, event: &AuditEvent);
}

pub struct TracingAuditSink;

impl AuditSink for TracingAuditSink {
    fn emit(&self, event: &AuditEvent) {
        tracing::info!(
            target: "jarvis.audit",
            event_id = %event.event_id,
            request_id = %event.request_id,
            timestamp_unix_ms = event.timestamp_unix_ms,
            tool = %event.tool,
            source = ?event.source,
            decision = ?event.decision,
            status = ?event.status,
            success = event.success,
            error_code = event.error_code.as_deref(),
            duration_ms = event.duration_ms,
            "tool request audited"
        );
    }
}

#[derive(Default)]
pub struct MemoryAuditSink {
    events: Mutex<Vec<AuditEvent>>,
}

impl MemoryAuditSink {
    #[must_use]
    pub fn events(&self) -> Vec<AuditEvent> {
        self.events
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }
}

impl AuditSink for MemoryAuditSink {
    fn emit(&self, event: &AuditEvent) {
        self.events
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(event.clone());
    }
}
