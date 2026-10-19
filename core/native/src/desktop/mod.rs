//! Registered desktop shutdown requests. No background listener, audio or worker thread.
use crate::{audio::failure, core::JarvisError};
use serde_json::{Value, json};
use std::{
    sync::Mutex,
    time::{Duration, Instant},
};

pub enum Command {
    Attach,
    Poll(String),
    Close,
    Detach(String),
}
pub struct DesktopService {
    state: Mutex<State>,
    lease: Duration,
}
impl Default for DesktopService {
    fn default() -> Self {
        Self::with_lease(Duration::from_secs(8))
    }
}
impl DesktopService {
    pub fn with_lease(lease: Duration) -> Self {
        Self {
            state: Mutex::new(State::default()),
            lease,
        }
    }
    pub fn request(&self, command: Command) -> Result<Value, JarvisError> {
        let mut state = self.state.lock().map_err(failure)?;
        if state.heartbeat.is_some_and(|at| at.elapsed() >= self.lease) {
            state.session = None;
            state.heartbeat = None;
        }
        match command {
            Command::Attach => {
                if state.session.is_some() {
                    return Err(failure("A JARVIS desktop is already active"));
                }
                let id = uuid::Uuid::new_v4().to_string();
                state.session = Some(id.clone());
                state.heartbeat = Some(Instant::now());
                state.closing = false;
                state.revision += 1;
                let mut result = state.snapshot();
                result["session"] = json!(id);
                Ok(result)
            }
            Command::Poll(id) => {
                state.check(&id)?;
                Ok(state.snapshot())
            }
            Command::Close => {
                if state.session.is_none() {
                    return Err(failure("No active JARVIS desktop"));
                }
                state.closing = true;
                state.revision += 1;
                Ok(state.snapshot())
            }
            Command::Detach(id) => {
                state.check(&id)?;
                state.session = None;
                state.heartbeat = None;
                Ok(json!({"detached":true}))
            }
        }
    }
}
#[derive(Default)]
struct State {
    session: Option<String>,
    heartbeat: Option<Instant>,
    closing: bool,
    revision: u64,
}
impl State {
    fn check(&mut self, id: &str) -> Result<(), JarvisError> {
        if self.session.as_deref() != Some(id) {
            return Err(failure("Desktop session expired; reopen JARVIS"));
        }
        self.heartbeat = Some(Instant::now());
        Ok(())
    }
    fn snapshot(&self) -> Value {
        json!({"closing":self.closing,"revision":self.revision})
    }
}
