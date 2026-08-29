use std::{
    env,
    io::{self, Write},
    path::{Path, PathBuf},
    process::ExitCode,
    sync::Arc,
};

use jarvis_core::{
    apps::{ApplicationCatalog, current_application_discovery},
    audit::TracingAuditSink,
    build_executor,
    config::ApplicationPreferences,
    core::{JarvisError, RequestSource, ToolRequest, ToolStatus},
    executor::Executor,
    platform::current_desktop_platform,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tracing_subscriber::util::SubscriberInitExt;

fn main() -> ExitCode {
    if let Err(error) = initialize_logging() {
        write_error(&error);
        return ExitCode::from(1);
    }

    match run() {
        Ok(exit_code) => exit_code,
        Err(error) => {
            write_error(&error);
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<ExitCode, JarvisError> {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let preferences = match preferences_config_path()? {
        Some(path) => ApplicationPreferences::load(&path)?,
        None => ApplicationPreferences::default(),
    };
    let catalog = Arc::new(ApplicationCatalog::new(
        current_application_discovery()?,
        preferences,
    ));
    let discovered = catalog.refresh()?;
    let executor = Arc::new(build_executor(
        current_desktop_platform(),
        catalog.clone(),
        Arc::new(TracingAuditSink),
    )?);

    match arguments.as_slice() {
        [command] if command == "serve" => {
            jarvis_core::ipc::serve(executor)?;
            Ok(ExitCode::SUCCESS)
        }
        [group, command] if group == "tools" && command == "list" => {
            write_json(&executor.list_tools())?;
            Ok(ExitCode::SUCCESS)
        }
        [group, command] if group == "apps" && command == "refresh" => {
            write_json(&CatalogRefreshOutput { discovered })?;
            Ok(ExitCode::SUCCESS)
        }
        [group, command, query] if group == "apps" && command == "search" => {
            execute_and_write(&executor, "resolve_app", json!({ "query": query }))
        }
        [group, command, query] if group == "app" && command == "open" => {
            let resolution = executor.execute(ToolRequest::new(
                "resolve_app",
                json!({ "query": query }),
                RequestSource::Cli,
            ));
            if resolution.status != ToolStatus::Success {
                write_json(&resolution)?;
                return Ok(ExitCode::from(1));
            }
            let resolved: ResolveAppData = serde_json::from_value(resolution.data).map_err(|error| {
                JarvisError::Internal {
                    message: format!("could not read resolve_app output: {error}"),
                }
            })?;
            execute_and_write(
                &executor,
                "open_app",
                json!({ "app_id": resolved.app.app_id }),
            )
        }
        [command, tool, json_arguments] if command == "tool" => {
            let arguments: Value = serde_json::from_str(json_arguments).map_err(|error| {
                JarvisError::InvalidArguments {
                    message: format!("tool arguments must be valid JSON: {error}"),
                }
            })?;
            execute_and_write(&executor, tool, arguments)
        }
        _ => Err(JarvisError::InvalidArguments {
            message: "usage: jarvis-core serve | tools list | apps refresh | apps search <query> | app open <query> | tool <name> '<json>'".to_owned(),
        }),
    }
}

fn execute_and_write(
    executor: &Executor,
    tool: &str,
    arguments: Value,
) -> Result<ExitCode, JarvisError> {
    let result = executor.execute(ToolRequest::new(tool, arguments, RequestSource::Cli));
    write_json(&result)?;
    Ok(if result.status == ToolStatus::Success {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    })
}

fn preferences_config_path() -> Result<Option<PathBuf>, JarvisError> {
    if let Some(path) = env::var_os("JARVIS_PREFERENCES_CONFIG") {
        return Ok(Some(PathBuf::from(path)));
    }

    let current_directory =
        env::current_dir().map_err(|error| JarvisError::ConfigurationError {
            message: format!("could not determine current directory: {error}"),
        })?;
    Ok(find_preferences_in_ancestors(&current_directory))
}

fn find_preferences_in_ancestors(start: &Path) -> Option<PathBuf> {
    start.ancestors().find_map(|directory| {
        let candidate = directory.join("config").join("preferences.toml");
        candidate.is_file().then_some(candidate)
    })
}

#[derive(Serialize)]
struct CatalogRefreshOutput {
    discovered: usize,
}

#[derive(Deserialize)]
struct ResolveAppData {
    app: ResolveAppCandidate,
}

#[derive(Deserialize)]
struct ResolveAppCandidate {
    app_id: String,
}

fn initialize_logging() -> Result<(), JarvisError> {
    tracing_subscriber::fmt()
        .json()
        .with_writer(io::stderr)
        .with_target(true)
        .finish()
        .try_init()
        .map_err(|error| JarvisError::Internal {
            message: format!("could not initialize logging: {error}"),
        })
}

fn write_json(value: &impl Serialize) -> Result<(), JarvisError> {
    let stdout = io::stdout();
    let mut lock = stdout.lock();
    serde_json::to_writer_pretty(&mut lock, value).map_err(|error| JarvisError::Internal {
        message: format!("could not serialize CLI output: {error}"),
    })?;
    writeln!(lock).map_err(|error| JarvisError::Internal {
        message: format!("could not write CLI output: {error}"),
    })
}

fn write_error(error: &JarvisError) {
    let stderr = io::stderr();
    let mut lock = stderr.lock();
    if serde_json::to_writer(&mut lock, &error.detail()).is_ok() {
        let _write_result = writeln!(lock);
    }
}

#[cfg(test)]
mod tests {
    use tempfile::tempdir;

    use super::*;

    #[test]
    fn finds_optional_preferences_in_parent_directory() {
        let root = tempdir().unwrap();
        let config_directory = root.path().join("config");
        std::fs::create_dir(&config_directory).unwrap();
        std::fs::write(config_directory.join("preferences.toml"), "[aliases]").unwrap();
        let child = root.path().join("child");
        std::fs::create_dir(&child).unwrap();

        assert_eq!(
            find_preferences_in_ancestors(&child),
            Some(config_directory.join("preferences.toml"))
        );
    }
}
