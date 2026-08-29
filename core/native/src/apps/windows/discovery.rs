use std::{env, fs, path::Path, path::PathBuf};

use crate::{
    apps::{ApplicationDiscovery, ApplicationSource, DiscoveredApplication, TrustedLaunchTarget},
    core::JarvisError,
};

const MAX_DISCOVERY_ENTRIES: usize = 10_000;
const MAX_DISCOVERY_DEPTH: usize = 16;

#[derive(Debug, Clone)]
struct DiscoveryRoot {
    path: PathBuf,
    source: ApplicationSource,
}

pub struct WindowsApplicationDiscovery {
    roots: Vec<DiscoveryRoot>,
}

impl WindowsApplicationDiscovery {
    pub fn from_environment() -> Result<Self, JarvisError> {
        let mut roots = Vec::new();
        if let Some(app_data) = env::var_os("APPDATA") {
            roots.push(DiscoveryRoot {
                path: PathBuf::from(app_data)
                    .join("Microsoft")
                    .join("Windows")
                    .join("Start Menu")
                    .join("Programs"),
                source: ApplicationSource::UserStartMenu,
            });
        }
        if let Some(program_data) = env::var_os("ProgramData") {
            roots.push(DiscoveryRoot {
                path: PathBuf::from(program_data)
                    .join("Microsoft")
                    .join("Windows")
                    .join("Start Menu")
                    .join("Programs"),
                source: ApplicationSource::MachineStartMenu,
            });
        }
        if roots.is_empty() {
            return Err(JarvisError::ApplicationDiscoveryFailed {
                message: "Windows Start Menu locations are unavailable".to_owned(),
            });
        }
        Ok(Self { roots })
    }

    #[must_use]
    pub fn from_roots(roots: Vec<(PathBuf, ApplicationSource)>) -> Self {
        Self {
            roots: roots
                .into_iter()
                .map(|(path, source)| DiscoveryRoot { path, source })
                .collect(),
        }
    }
}

impl ApplicationDiscovery for WindowsApplicationDiscovery {
    fn discover(&self) -> Result<Vec<DiscoveredApplication>, JarvisError> {
        let mut applications = Vec::new();
        let mut visited = 0;
        for root in &self.roots {
            if !root.path.exists() {
                continue;
            }
            let canonical_root = root.path.canonicalize().map_err(|error| {
                JarvisError::ApplicationDiscoveryFailed {
                    message: format!(
                        "could not normalize Start Menu root '{}': {error}",
                        root.path.display()
                    ),
                }
            })?;
            discover_root(
                &canonical_root,
                root.source,
                &mut applications,
                &mut visited,
            )?;
        }
        Ok(applications)
    }
}

fn discover_root(
    root: &Path,
    source: ApplicationSource,
    applications: &mut Vec<DiscoveredApplication>,
    visited: &mut usize,
) -> Result<(), JarvisError> {
    let mut pending = vec![(root.to_path_buf(), 0_usize)];
    while let Some((directory, depth)) = pending.pop() {
        let entries =
            fs::read_dir(&directory).map_err(|error| JarvisError::ApplicationDiscoveryFailed {
                message: format!(
                    "could not read Start Menu '{}': {error}",
                    directory.display()
                ),
            })?;
        for entry in entries {
            *visited += 1;
            if *visited > MAX_DISCOVERY_ENTRIES {
                return Err(JarvisError::ApplicationDiscoveryFailed {
                    message: format!(
                        "application discovery exceeded {MAX_DISCOVERY_ENTRIES} Start Menu entries"
                    ),
                });
            }
            let entry = entry.map_err(|error| JarvisError::ApplicationDiscoveryFailed {
                message: format!("could not read a Start Menu entry: {error}"),
            })?;
            let file_type =
                entry
                    .file_type()
                    .map_err(|error| JarvisError::ApplicationDiscoveryFailed {
                        message: format!(
                            "could not inspect Start Menu entry '{}': {error}",
                            entry.path().display()
                        ),
                    })?;
            if file_type.is_dir() && !file_type.is_symlink() {
                if depth < MAX_DISCOVERY_DEPTH {
                    pending.push((entry.path(), depth + 1));
                }
                continue;
            }
            if !file_type.is_file() || !has_shortcut_extension(&entry.path()) {
                continue;
            }

            let path = entry.path().canonicalize().map_err(|error| {
                JarvisError::ApplicationDiscoveryFailed {
                    message: format!(
                        "could not normalize Start Menu shortcut '{}': {error}",
                        entry.path().display()
                    ),
                }
            })?;
            if !path.starts_with(root) {
                continue;
            }
            let Some(name) = path
                .file_stem()
                .map(|value| value.to_string_lossy().trim().to_owned())
            else {
                continue;
            };
            if name.is_empty() || is_non_application_shortcut(&name) {
                continue;
            }
            let stable_identity = path.to_string_lossy().replace('\\', "/").to_lowercase();
            applications.push(DiscoveredApplication::new(
                source,
                stable_identity,
                name,
                Vec::new(),
                None,
                TrustedLaunchTarget::Shortcut(path),
            )?);
        }
    }
    Ok(())
}

fn has_shortcut_extension(path: &Path) -> bool {
    path.extension()
        .is_some_and(|extension| extension.eq_ignore_ascii_case("lnk"))
}

fn is_non_application_shortcut(name: &str) -> bool {
    let normalized = name.to_lowercase();
    normalized.starts_with("uninstall")
        || normalized.contains("command prompt")
        || normalized.contains("powershell")
        || normalized == "windows terminal"
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use super::*;

    #[test]
    fn discovers_only_scoped_user_facing_shortcuts() {
        let root = tempdir().unwrap();
        let nested = root.path().join("Productivity");
        fs::create_dir(&nested).unwrap();
        fs::write(nested.join("Visual Studio Code.lnk"), b"shortcut").unwrap();
        fs::write(nested.join("notes.txt"), b"not an app").unwrap();
        fs::write(nested.join("Windows PowerShell.lnk"), b"shell").unwrap();
        let discovery = WindowsApplicationDiscovery::from_roots(vec![(
            root.path().to_path_buf(),
            ApplicationSource::UserStartMenu,
        )]);

        let first = discovery.discover().unwrap();
        let second = discovery.discover().unwrap();

        assert_eq!(first.len(), 1);
        assert_eq!(first[0].canonical_name(), "Visual Studio Code");
        assert_eq!(first[0].app_id(), second[0].app_id());
    }

    #[test]
    fn returns_typed_error_for_unreadable_root_shape() {
        let root = tempdir().unwrap();
        let file = root.path().join("not-a-directory");
        fs::write(&file, b"file").unwrap();
        let discovery = WindowsApplicationDiscovery::from_roots(vec![(
            file,
            ApplicationSource::MachineStartMenu,
        )]);

        let error = discovery.discover().expect_err("file root must fail");

        assert!(matches!(
            error,
            JarvisError::ApplicationDiscoveryFailed { .. }
        ));
    }
}
