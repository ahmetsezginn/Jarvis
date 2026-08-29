use std::{collections::BTreeMap, fs, path::Path};

use serde::Deserialize;

use crate::core::JarvisError;

#[derive(Debug, Clone, Default, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApplicationPreferences {
    #[serde(default)]
    pub aliases: BTreeMap<String, String>,
    #[serde(default)]
    pub applications: ApplicationPolicyPreferences,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApplicationPolicyPreferences {
    #[serde(default)]
    pub exclude: Vec<String>,
}

impl ApplicationPreferences {
    pub fn load(path: &Path) -> Result<Self, JarvisError> {
        let source = fs::read_to_string(path).map_err(|error| JarvisError::ConfigurationError {
            message: format!("could not read {}: {error}", path.display()),
        })?;
        toml::from_str(&source).map_err(|error| JarvisError::ConfigurationError {
            message: format!("invalid application preferences: {error}"),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_optional_aliases_and_exclusions() {
        let preferences: ApplicationPreferences = toml::from_str(
            "[aliases]\ncode = 'Visual Studio Code'\n[applications]\nexclude = ['Blocked']\n",
        )
        .unwrap();

        assert_eq!(preferences.aliases["code"], "Visual Studio Code");
        assert_eq!(preferences.applications.exclude, ["Blocked"]);
    }
}
