use std::time::{Duration, Instant};

/// Detection grants only one fixed user-context activation, never a command/transcript.
pub struct Gate {
    next_launch: Instant,
}
impl Gate {
    pub fn new(now: Instant) -> Self {
        Self { next_launch: now }
    }
    pub fn allow(
        &mut self,
        now: Instant,
        owner_active: bool,
        app_running: bool,
        detected: bool,
    ) -> bool {
        if !owner_active || app_running || !detected || now < self.next_launch {
            return false;
        }
        self.next_launch = now + Duration::from_secs(15);
        true
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_detection_in_owner_session_activates_once_without_restart_storms() {
        let now = Instant::now();
        let mut gate = Gate::new(now);
        assert!(!gate.allow(now, false, false, true));
        assert!(!gate.allow(now, true, true, true));
        assert!(!gate.allow(now, true, false, false));
        assert!(gate.allow(now, true, false, true));
        assert!(!gate.allow(now, true, false, true));
        assert!(gate.allow(now + Duration::from_secs(16), true, false, true));
    }
}
