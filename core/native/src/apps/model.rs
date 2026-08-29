use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::core::JarvisError;

const APPLICATION_ID_NAMESPACE: Uuid = Uuid::from_u128(0x3a18_58e5_f38b_52bc_a315_b6cd_3cc9_f808);

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ApplicationId(String);

impl ApplicationId {
    #[must_use]
    pub fn from_source(source: ApplicationSource, stable_identity: &str) -> Self {
        let identity = format!("{}\0{stable_identity}", source.stable_key());
        let uuid = Uuid::new_v5(&APPLICATION_ID_NAMESPACE, identity.as_bytes());
        Self(format!("app_{}", uuid.simple()))
    }

    pub fn parse(value: &str) -> Result<Self, JarvisError> {
        let suffix = value
            .strip_prefix("app_")
            .filter(|suffix| {
                suffix.len() == 32 && suffix.bytes().all(|byte| byte.is_ascii_hexdigit())
            })
            .ok_or_else(|| JarvisError::InvalidApplicationId {
                app_id: value.to_owned(),
            })?;
        Ok(Self(format!("app_{}", suffix.to_ascii_lowercase())))
    }

    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for ApplicationId {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.0.fmt(formatter)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ApplicationSource {
    UserStartMenu,
    MachineStartMenu,
    AdministrativeOverride,
}

impl ApplicationSource {
    const fn stable_key(self) -> &'static str {
        match self {
            Self::UserStartMenu => "user_start_menu",
            Self::MachineStartMenu => "machine_start_menu",
            Self::AdministrativeOverride => "administrative_override",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TrustedLaunchTarget {
    Shortcut(PathBuf),
    Executable {
        path: PathBuf,
        arguments: Vec<String>,
    },
}

impl TrustedLaunchTarget {
    #[must_use]
    pub fn path(&self) -> &Path {
        match self {
            Self::Shortcut(path) | Self::Executable { path, .. } => path,
        }
    }

    pub(crate) fn deterministic_key(&self) -> String {
        match self {
            Self::Shortcut(path) => format!("shortcut:{}", path.display()),
            Self::Executable { path, arguments } => {
                format!("executable:{}\0{}", path.display(), arguments.join("\0"))
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiscoveredApplication {
    app_id: ApplicationId,
    canonical_name: String,
    aliases: Vec<String>,
    publisher: Option<String>,
    source: ApplicationSource,
    launch: TrustedLaunchTarget,
}

impl DiscoveredApplication {
    pub fn new(
        source: ApplicationSource,
        stable_identity: impl AsRef<str>,
        canonical_name: impl Into<String>,
        aliases: Vec<String>,
        publisher: Option<String>,
        launch: TrustedLaunchTarget,
    ) -> Result<Self, JarvisError> {
        let canonical_name = canonical_name.into().trim().to_owned();
        if canonical_name.is_empty() {
            return Err(JarvisError::ApplicationDiscoveryFailed {
                message: "discovered application name must not be empty".to_owned(),
            });
        }
        if !launch.path().is_absolute() {
            return Err(JarvisError::ApplicationDiscoveryFailed {
                message: format!("launch target for '{canonical_name}' must be absolute"),
            });
        }

        let mut aliases: Vec<String> = aliases
            .into_iter()
            .map(|alias| alias.trim().to_owned())
            .filter(|alias| !alias.is_empty())
            .collect();
        aliases.sort_by_key(|alias| alias.to_lowercase());
        aliases.dedup_by(|left, right| left.eq_ignore_ascii_case(right));

        Ok(Self {
            app_id: ApplicationId::from_source(source, stable_identity.as_ref()),
            canonical_name,
            aliases,
            publisher: publisher.filter(|value| !value.trim().is_empty()),
            source,
            launch,
        })
    }

    #[must_use]
    pub fn app_id(&self) -> &ApplicationId {
        &self.app_id
    }

    #[must_use]
    pub fn canonical_name(&self) -> &str {
        &self.canonical_name
    }

    #[must_use]
    pub fn aliases(&self) -> &[String] {
        &self.aliases
    }

    #[must_use]
    pub fn publisher(&self) -> Option<&str> {
        self.publisher.as_deref()
    }

    #[must_use]
    pub const fn source(&self) -> ApplicationSource {
        self.source
    }

    #[must_use]
    pub(crate) fn launch(&self) -> &TrustedLaunchTarget {
        &self.launch
    }

    pub(crate) fn add_alias(&mut self, alias: String) {
        if !self
            .aliases
            .iter()
            .any(|existing| existing.eq_ignore_ascii_case(&alias))
        {
            self.aliases.push(alias);
            self.aliases.sort_by_key(|value| value.to_lowercase());
        }
    }

    pub(crate) fn deterministic_key(&self) -> String {
        format!(
            "{}\0{}\0{}",
            self.canonical_name.to_lowercase(),
            self.source.stable_key(),
            self.launch.deterministic_key()
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ApplicationCandidate {
    pub app_id: ApplicationId,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub publisher: Option<String>,
}

impl From<&DiscoveredApplication> for ApplicationCandidate {
    fn from(application: &DiscoveredApplication) -> Self {
        Self {
            app_id: application.app_id.clone(),
            name: application.canonical_name.clone(),
            publisher: application.publisher.clone(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedApplication {
    application: DiscoveredApplication,
}

impl ResolvedApplication {
    #[must_use]
    pub fn new(application: DiscoveredApplication) -> Self {
        Self { application }
    }

    #[must_use]
    pub fn application(&self) -> &DiscoveredApplication {
        &self.application
    }

    #[must_use]
    pub fn candidate(&self) -> ApplicationCandidate {
        ApplicationCandidate::from(&self.application)
    }
}
