use std::{fs, path::PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    core::{JarvisError, RiskLevel},
    tools::{Tool, ToolContext, ToolOutput},
};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct OpenFolderArguments {
    path: PathBuf,
}

#[derive(Debug, Serialize)]
struct OpenFolderOutput {
    opened: bool,
    path: PathBuf,
}

pub struct OpenFolderTool;

impl Default for OpenFolderTool {
    fn default() -> Self {
        Self::new()
    }
}

impl OpenFolderTool {
    #[must_use]
    pub const fn new() -> Self {
        Self
    }
}

impl Tool for OpenFolderTool {
    fn name(&self) -> &'static str {
        "open_folder"
    }

    fn risk_level(&self) -> RiskLevel {
        RiskLevel::Low
    }

    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        let arguments = parse_arguments(arguments)?;
        canonical_directory(arguments.path).map(|_path| ())
    }

    fn execute(&self, context: &ToolContext, arguments: &Value) -> Result<ToolOutput, JarvisError> {
        let arguments = parse_arguments(arguments)?;
        let path = canonical_directory(arguments.path)?;
        context.platform().open_folder(&path)?;
        serde_json::to_value(OpenFolderOutput { opened: true, path }).map_err(|error| {
            JarvisError::Internal {
                message: format!("could not serialize open_folder result: {error}"),
            }
        })
    }
}

fn parse_arguments(arguments: &Value) -> Result<OpenFolderArguments, JarvisError> {
    serde_json::from_value(arguments.clone()).map_err(|error| JarvisError::InvalidArguments {
        message: error.to_string(),
    })
}

fn canonical_directory(path: PathBuf) -> Result<PathBuf, JarvisError> {
    if path.as_os_str().is_empty() {
        return Err(JarvisError::InvalidArguments {
            message: "path must not be empty".to_owned(),
        });
    }

    let metadata = fs::metadata(&path).map_err(|error| {
        if error.kind() == std::io::ErrorKind::NotFound {
            JarvisError::FolderNotFound {
                path: path.display().to_string(),
            }
        } else {
            JarvisError::ExecutionFailed {
                message: format!("could not inspect '{}': {error}", path.display()),
            }
        }
    })?;

    if !metadata.is_dir() {
        return Err(JarvisError::NotADirectory {
            path: path.display().to_string(),
        });
    }

    path.canonicalize()
        .map_err(|error| JarvisError::ExecutionFailed {
            message: format!("could not normalize '{}': {error}", path.display()),
        })
}

#[cfg(test)]
mod tests {
    use std::{fs, sync::Arc};

    use serde_json::json;
    use tempfile::tempdir;

    use super::*;
    use crate::platform::fake::FakeDesktopPlatform;

    #[test]
    fn rejects_missing_path() {
        let error = OpenFolderTool::new()
            .validate(&json!({}))
            .expect_err("missing path should fail");
        assert!(matches!(error, JarvisError::InvalidArguments { .. }));
    }

    #[test]
    fn rejects_nonexistent_path() {
        let directory = tempdir().unwrap();
        let missing = directory.path().join("missing");
        let error = OpenFolderTool::new()
            .validate(&json!({ "path": missing }))
            .expect_err("missing folder should fail");
        assert!(matches!(error, JarvisError::FolderNotFound { .. }));
    }

    #[test]
    fn rejects_file_path() {
        let directory = tempdir().unwrap();
        let file = directory.path().join("file.txt");
        fs::write(&file, b"data").unwrap();
        let error = OpenFolderTool::new()
            .validate(&json!({ "path": file }))
            .expect_err("file should fail");
        assert!(matches!(error, JarvisError::NotADirectory { .. }));
    }

    #[test]
    fn accepts_and_opens_valid_directory() {
        let directory = tempdir().unwrap();
        let platform = Arc::new(FakeDesktopPlatform::default());
        let context = ToolContext::new(platform.clone());
        let arguments = json!({ "path": directory.path() });

        OpenFolderTool::new().validate(&arguments).unwrap();
        let output = OpenFolderTool::new()
            .execute(&context, &arguments)
            .expect("valid directory should open on fake platform");

        assert_eq!(output["opened"], true);
        assert_eq!(platform.calls().opened_folders.len(), 1);
    }
}
