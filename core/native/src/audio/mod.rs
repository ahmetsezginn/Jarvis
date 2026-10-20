//! Device access and bounded local speech. PCM never enters the JSON control protocol.
use crate::core::JarvisError;
use serde_json::Value;
use std::sync::Arc;

#[cfg(windows)]
mod echo;
#[cfg(windows)]
mod sapi;
mod transcribe;
#[cfg(windows)]
mod transcribe_cpp;
mod turn;
mod vad;
#[cfg(windows)]
mod windows;
pub use transcribe::{
    recognizer_label, resample, speech_present, transcribe, transcribe_with_vocabulary,
};

fn models_directory() -> std::path::PathBuf {
    if let Some(path) = std::env::var_os("JARVIS_MODELS_DIR") {
        return path.into();
    }
    // Installed layout: <app>/bin/jarvis-core.exe plus a fixed runtime marker.
    if let Ok(executable) = std::env::current_exe()
        && let Some(root) = executable.parent().and_then(std::path::Path::parent)
        && root.join("jarvis-runtime.json").is_file()
    {
        return root.join("models");
    }
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../models")
}

/// Neutral spelling context from native catalog display names, never actions or launch targets.
pub fn recognition_vocabulary(names: impl IntoIterator<Item = String>) -> String {
    let mut names: Vec<_> = names
        .into_iter()
        .filter(|name| {
            (1..=48).contains(&name.chars().count())
                && name
                    .chars()
                    .all(|c| c.is_alphanumeric() || " -_.'&+".contains(c))
        })
        .collect();
    names.sort_by_key(|name| (name.chars().count(), name.to_lowercase()));
    names.dedup();
    let mut vocabulary = String::from("JARVIS");
    for name in names.into_iter().take(64) {
        if vocabulary.chars().count() + name.chars().count() + 2 > 512 {
            break;
        }
        vocabulary.push_str(", ");
        vocabulary.push_str(&name);
    }
    vocabulary
}

pub trait AudioService: Send + Sync {
    fn status(&self) -> Result<Value, JarvisError>;
    fn start(&self, device: Option<usize>, automatic: bool) -> Result<Value, JarvisError>;
    fn start_interruptible(
        &self,
        _device: Option<usize>,
        _output: Option<usize>,
    ) -> Result<Value, JarvisError> {
        Err(failure(
            "Echo-cancelled listening is unavailable on this platform",
        ))
    }
    fn poll(&self, id: Option<&str>) -> Result<Value, JarvisError>;
    fn finish(&self, id: &str, language: &str, vocabulary: &str) -> Result<Value, JarvisError>;
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
    fn finish(&self, _: &str, _: &str, _: &str) -> Result<Value, JarvisError> {
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

#[cfg(test)]
mod vocabulary_tests {
    use super::*;
    #[test]
    fn catalog_spelling_hints_are_bounded_and_never_contain_paths_or_instructions() {
        let hints = recognition_vocabulary(
            [
                "Nebula Painter",
                "Çizim",
                "C:\\run.exe",
                "<tool_call>",
                "bad\nname",
            ]
            .map(str::to_owned),
        );
        assert!(hints.contains("Nebula Painter") && hints.contains("Çizim"));
        assert!(!hints.contains("run.exe") && !hints.contains('<') && !hints.contains('\n'));
        let many = recognition_vocabulary((0..500).map(|i| format!("Application {i:03}")));
        assert!(many.chars().count() <= 512);
    }
}
