//! Scoped metadata catalog. Paths and filesystem authority never originate in model output.
mod catalog;
mod shortcut;
#[cfg(windows)]
mod windows;

pub use catalog::{FileCatalog, FileEntry, FileKind, FileRoot, SearchArguments};
pub use shortcut::GameShortcutTarget;

pub fn configured_roots() -> Result<Vec<FileRoot>, crate::core::JarvisError> {
    if let Some(path) = std::env::var_os("JARVIS_FILES_CONFIG") {
        #[derive(serde::Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Config {
            roots: Vec<FileRoot>,
        }
        let text = std::fs::read_to_string(path).map_err(|error| {
            crate::core::JarvisError::ConfigurationError {
                message: error.to_string(),
            }
        })?;
        let config: Config = toml::from_str(&text).map_err(|error| {
            crate::core::JarvisError::ConfigurationError {
                message: error.to_string(),
            }
        })?;
        return Ok(config.roots);
    }
    #[cfg(windows)]
    {
        windows::known_roots()
    }
    #[cfg(not(windows))]
    {
        Ok(Vec::new())
    }
}
