use std::{collections::BTreeMap, sync::Arc, sync::RwLock};

use crate::{config::ApplicationPreferences, core::JarvisError};

use super::{
    ApplicationCandidate, ApplicationDiscovery, ApplicationId, DiscoveredApplication,
    normalize_application_text,
};

pub struct ApplicationCatalog {
    discovery: Arc<dyn ApplicationDiscovery>,
    preferences: ApplicationPreferences,
    applications: RwLock<BTreeMap<ApplicationId, DiscoveredApplication>>,
}

impl ApplicationCatalog {
    #[must_use]
    pub fn new(
        discovery: Arc<dyn ApplicationDiscovery>,
        preferences: ApplicationPreferences,
    ) -> Self {
        Self {
            discovery,
            preferences,
            applications: RwLock::new(BTreeMap::new()),
        }
    }

    pub fn refresh(&self) -> Result<usize, JarvisError> {
        let mut discovered = self.discovery.discover()?;
        discovered.sort_by_key(DiscoveredApplication::deterministic_key);

        let exclusions: Vec<String> = self
            .preferences
            .applications
            .exclude
            .iter()
            .map(|name| normalize_application_text(name))
            .collect();
        let mut replacement = BTreeMap::new();
        for application in discovered {
            let normalized_name = normalize_application_text(application.canonical_name());
            if exclusions.contains(&normalized_name)
                || is_forbidden_shell_name(&normalized_name)
                || !application.launch().path().is_file()
            {
                continue;
            }
            replacement
                .entry(application.app_id().clone())
                .or_insert(application);
        }

        for (alias, target_name) in &self.preferences.aliases {
            let target_name = normalize_application_text(target_name);
            let matching_ids: Vec<ApplicationId> = replacement
                .values()
                .filter(|application| {
                    normalize_application_text(application.canonical_name()) == target_name
                })
                .map(|application| application.app_id().clone())
                .collect();
            for app_id in matching_ids {
                if let Some(application) = replacement.get_mut(&app_id) {
                    application.add_alias(alias.trim().to_owned());
                }
            }
        }

        let count = replacement.len();
        *self
            .applications
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = replacement;
        Ok(count)
    }

    #[must_use]
    pub fn get(&self, app_id: &ApplicationId) -> Option<DiscoveredApplication> {
        self.applications
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(app_id)
            .cloned()
    }

    #[must_use]
    pub fn applications(&self) -> Vec<DiscoveredApplication> {
        self.applications
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .values()
            .cloned()
            .collect()
    }

    #[must_use]
    pub fn search(&self, query: &str) -> Vec<ApplicationCandidate> {
        let query = normalize_application_text(query);
        if query.is_empty() {
            return Vec::new();
        }
        self.applications()
            .iter()
            .filter(|application| {
                normalize_application_text(application.canonical_name()).contains(&query)
                    || application
                        .aliases()
                        .iter()
                        .any(|alias| normalize_application_text(alias).contains(&query))
            })
            .map(ApplicationCandidate::from)
            .collect()
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.applications
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

fn is_forbidden_shell_name(normalized_name: &str) -> bool {
    [
        "command prompt",
        "cmd",
        "powershell",
        "powershell ise",
        "windows powershell",
        "windows terminal",
    ]
    .iter()
    .any(|forbidden| {
        normalized_name == *forbidden
            || normalized_name.starts_with(&format!("{forbidden} "))
            || normalized_name.contains(&format!(" {forbidden}"))
    })
}

#[cfg(test)]
mod tests {
    use std::{fs, sync::Arc};

    use tempfile::{TempDir, tempdir};

    use super::*;
    use crate::{
        apps::{ApplicationSource, TrustedLaunchTarget, fake::FakeApplicationDiscovery},
        config::ApplicationPreferences,
        core::JarvisError,
    };

    fn test_application(directory: &TempDir, identity: &str, name: &str) -> DiscoveredApplication {
        let executable = directory.path().join(format!("{identity}.exe"));
        fs::write(&executable, b"test").unwrap();
        DiscoveredApplication::new(
            ApplicationSource::AdministrativeOverride,
            identity,
            name,
            Vec::new(),
            None,
            TrustedLaunchTarget::Executable {
                path: executable,
                arguments: Vec::new(),
            },
        )
        .unwrap()
    }

    #[test]
    fn discovered_apps_populate_catalog() {
        let directory = tempdir().unwrap();
        let application = test_application(&directory, "one", "One");
        let catalog = ApplicationCatalog::new(
            Arc::new(FakeApplicationDiscovery::succeeding(vec![application])),
            ApplicationPreferences::default(),
        );

        assert_eq!(catalog.refresh().unwrap(), 1);
        assert_eq!(catalog.len(), 1);
    }

    #[test]
    fn duplicate_discoveries_are_deterministic() {
        let directory = tempdir().unwrap();
        let second = test_application(&directory, "same", "Zulu");
        let first = test_application(&directory, "same", "Alpha");
        let app_id = first.app_id().clone();
        let catalog = ApplicationCatalog::new(
            Arc::new(FakeApplicationDiscovery::succeeding(vec![second, first])),
            ApplicationPreferences::default(),
        );

        catalog.refresh().unwrap();

        assert_eq!(catalog.len(), 1);
        assert_eq!(catalog.get(&app_id).unwrap().canonical_name(), "Alpha");
    }

    #[test]
    fn refresh_replaces_catalog_atomically() {
        let directory = tempdir().unwrap();
        let first = test_application(&directory, "first", "First");
        let first_id = first.app_id().clone();
        let discovery = Arc::new(FakeApplicationDiscovery::succeeding(vec![first]));
        let catalog = ApplicationCatalog::new(discovery.clone(), ApplicationPreferences::default());
        catalog.refresh().unwrap();

        let second = test_application(&directory, "second", "Second");
        let second_id = second.app_id().clone();
        discovery.set_result(Ok(vec![second]));
        catalog.refresh().unwrap();

        assert!(catalog.get(&first_id).is_none());
        assert!(catalog.get(&second_id).is_some());
    }

    #[test]
    fn discovery_error_is_typed_and_preserves_previous_catalog() {
        let directory = tempdir().unwrap();
        let application = test_application(&directory, "one", "One");
        let discovery = Arc::new(FakeApplicationDiscovery::succeeding(vec![application]));
        let catalog = ApplicationCatalog::new(discovery.clone(), ApplicationPreferences::default());
        catalog.refresh().unwrap();
        discovery.set_result(Err(JarvisError::ApplicationDiscoveryFailed {
            message: "expected".to_owned(),
        }));

        let error = catalog.refresh().expect_err("refresh should fail");

        assert!(matches!(
            error,
            JarvisError::ApplicationDiscoveryFailed { .. }
        ));
        assert_eq!(catalog.len(), 1);
    }

    #[test]
    fn optional_preferences_add_aliases_and_exclusions() {
        let directory = tempdir().unwrap();
        let spotify = test_application(&directory, "spotify", "Spotify");
        let blocked = test_application(&directory, "blocked", "Blocked App");
        let mut preferences = ApplicationPreferences::default();
        preferences
            .aliases
            .insert("music".to_owned(), "Spotify".to_owned());
        preferences
            .applications
            .exclude
            .push("Blocked App".to_owned());
        let catalog = ApplicationCatalog::new(
            Arc::new(FakeApplicationDiscovery::succeeding(vec![spotify, blocked])),
            preferences,
        );

        catalog.refresh().unwrap();

        assert_eq!(catalog.len(), 1);
        assert_eq!(catalog.search("music")[0].name, "Spotify");
    }
}
