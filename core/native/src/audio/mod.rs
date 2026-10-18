//! Device access and bounded local speech. PCM never enters the JSON control protocol.
use crate::core::JarvisError;
use serde_json::Value;
use std::sync::Arc;

#[cfg(windows)]
mod sapi;
mod transcribe;
mod turn;
mod vad;
#[cfg(windows)]
mod windows;
pub use transcribe::{resample, speech_present, transcribe};

pub trait AudioService: Send + Sync {
    fn status(&self) -> Result<Value, JarvisError>;
    fn start(&self, device: Option<usize>, automatic: bool) -> Result<Value, JarvisError>;
    fn poll(&self, id: Option<&str>) -> Result<Value, JarvisError>;
    fn finish(&self, id: &str, language: &str) -> Result<Value, JarvisError>;
    fn cancel(&self, id: &str) -> Result<Value, JarvisError>;
    fn speak(
        &self,
        text: &str,
        language: &str,
        output: Option<usize>,
    ) -> Result<Value, JarvisError>;
    fn stop(&self) -> Result<Value, JarvisError>;
}

pub fn current_service() -> Arc<dyn AudioService> {
    #[cfg(windows)]
    {
        Arc::new(windows::WindowsAudio::default())
    }
    #[cfg(not(windows))]
    {
        Arc::new(Unsupported)
    }
}

pub fn failure(message: impl ToString) -> JarvisError {
    JarvisError::ExecutionFailed {
        message: message.to_string(),
    }
}

#[cfg(not(windows))]
struct Unsupported;
#[cfg(not(windows))]
impl AudioService for Unsupported {
    fn status(&self) -> Result<Value, JarvisError> {
        Err(failure("Voice requires Windows"))
    }
    fn start(&self, _: Option<usize>, _: bool) -> Result<Value, JarvisError> {
        self.status()
    }
    fn poll(&self, _: Option<&str>) -> Result<Value, JarvisError> {
        self.status()
    }
    fn finish(&self, _: &str, _: &str) -> Result<Value, JarvisError> {
        self.status()
    }
    fn cancel(&self, _: &str) -> Result<Value, JarvisError> {
        self.status()
    }
    fn speak(&self, _: &str, _: &str, _: Option<usize>) -> Result<Value, JarvisError> {
        self.status()
    }
    fn stop(&self) -> Result<Value, JarvisError> {
        self.status()
    }
}
