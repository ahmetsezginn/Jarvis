use crate::core::JarvisError;

use super::{
    ApplicationCandidate, ApplicationCatalog, DiscoveredApplication, ResolvedApplication,
    normalize_application_text,
};

pub trait ApplicationResolver: Send + Sync {
    fn resolve(
        &self,
        query: &str,
        catalog: &ApplicationCatalog,
    ) -> Result<ResolvedApplication, JarvisError>;
}

pub struct DeterministicApplicationResolver;

impl ApplicationResolver for DeterministicApplicationResolver {
    fn resolve(
        &self,
        query: &str,
        catalog: &ApplicationCatalog,
    ) -> Result<ResolvedApplication, JarvisError> {
        let normalized_query = normalize_application_text(query);
        if normalized_query.is_empty() {
            return Err(JarvisError::InvalidArguments {
                message: "application query must not be empty".to_owned(),
            });
        }

        let mut ranked: Vec<(u16, DiscoveredApplication)> = catalog
            .applications()
            .into_iter()
            .filter_map(|application| {
                match_score(&normalized_query, &application).map(|score| (score, application))
            })
            .collect();
        ranked.sort_by(|left, right| {
            right
                .0
                .cmp(&left.0)
                .then_with(|| left.1.canonical_name().cmp(right.1.canonical_name()))
                .then_with(|| left.1.app_id().cmp(right.1.app_id()))
        });

        let best_score = ranked.first().map(|(score, _)| *score).ok_or_else(|| {
            JarvisError::ApplicationNotFound {
                query: query.to_owned(),
            }
        })?;
        let best: Vec<DiscoveredApplication> = ranked
            .into_iter()
            .take_while(|(score, _)| *score == best_score)
            .map(|(_, application)| application)
            .collect();

        if best.len() > 1 {
            return Err(JarvisError::ApplicationAmbiguous {
                query: query.to_owned(),
                candidates: best.iter().map(ApplicationCandidate::from).collect(),
            });
        }

        best.into_iter()
            .next()
            .map(ResolvedApplication::new)
            .ok_or_else(|| JarvisError::Internal {
                message: "resolver lost its selected application".to_owned(),
            })
    }
}

fn match_score(query: &str, application: &DiscoveredApplication) -> Option<u16> {
    let canonical = normalize_application_text(application.canonical_name());
    if canonical == query {
        return Some(300);
    }
    if application
        .aliases()
        .iter()
        .any(|alias| normalize_application_text(alias) == query)
    {
        return Some(250);
    }

    let mut best = fuzzy_score(query, &canonical);
    for alias in application.aliases() {
        best = best.max(fuzzy_score(query, &normalize_application_text(alias)));
    }
    best
}

fn fuzzy_score(query: &str, candidate: &str) -> Option<u16> {
    let query_compact = compact(query);
    let candidate_compact = compact(candidate);
    if query_compact.len() < 2 || candidate_compact.len() < 2 {
        return None;
    }

    if candidate.split_whitespace().any(|token| token == query)
        || candidate.contains(query)
        || candidate_compact.starts_with(&query_compact)
    {
        return Some(180);
    }

    let distance = levenshtein(&query_compact, &candidate_compact);
    let threshold = if query_compact.len() <= 4 { 1 } else { 2 };
    (distance <= threshold).then_some(120_u16.saturating_sub(distance as u16))
}

fn compact(value: &str) -> String {
    value
        .chars()
        .filter(|character| character.is_alphanumeric())
        .collect()
}

fn levenshtein(left: &str, right: &str) -> usize {
    let right: Vec<char> = right.chars().collect();
    let mut previous: Vec<usize> = (0..=right.len()).collect();
    for (left_index, left_character) in left.chars().enumerate() {
        let mut current = Vec::with_capacity(right.len() + 1);
        current.push(left_index + 1);
        for (right_index, right_character) in right.iter().enumerate() {
            let substitution =
                previous[right_index] + usize::from(left_character != *right_character);
            current.push(
                (current[right_index] + 1)
                    .min(previous[right_index + 1] + 1)
                    .min(substitution),
            );
        }
        previous = current;
    }
    previous[right.len()]
}

#[cfg(test)]
mod tests {
    use std::{fs, sync::Arc};

    use tempfile::{TempDir, tempdir};

    use super::*;
    use crate::{
        apps::{
            ApplicationSource, DiscoveredApplication, TrustedLaunchTarget,
            fake::FakeApplicationDiscovery,
        },
        config::ApplicationPreferences,
    };

    fn test_application(
        directory: &TempDir,
        identity: &str,
        name: &str,
        aliases: &[&str],
    ) -> DiscoveredApplication {
        let executable = directory.path().join(format!("{identity}.exe"));
        fs::write(&executable, b"test").unwrap();
        DiscoveredApplication::new(
            ApplicationSource::AdministrativeOverride,
            identity,
            name,
            aliases.iter().map(|alias| (*alias).to_owned()).collect(),
            None,
            TrustedLaunchTarget::Executable {
                path: executable,
                arguments: Vec::new(),
            },
        )
        .unwrap()
    }

    fn catalog(applications: Vec<DiscoveredApplication>) -> ApplicationCatalog {
        let catalog = ApplicationCatalog::new(
            Arc::new(FakeApplicationDiscovery::succeeding(applications)),
            ApplicationPreferences::default(),
        );
        catalog.refresh().unwrap();
        catalog
    }

    #[test]
    fn resolves_exact_case_insensitive_name() {
        let directory = tempdir().unwrap();
        let catalog = catalog(vec![test_application(
            &directory,
            "spotify",
            "Spotify",
            &[],
        )]);

        let resolved = DeterministicApplicationResolver
            .resolve("  SPOTIFY  ", &catalog)
            .unwrap();

        assert_eq!(resolved.application().canonical_name(), "Spotify");
    }

    #[test]
    fn resolves_exact_alias() {
        let directory = tempdir().unwrap();
        let catalog = catalog(vec![test_application(
            &directory,
            "vscode",
            "Visual Studio Code",
            &["code"],
        )]);

        let resolved = DeterministicApplicationResolver
            .resolve("CODE", &catalog)
            .unwrap();

        assert_eq!(
            resolved.application().canonical_name(),
            "Visual Studio Code"
        );
    }

    #[test]
    fn resolves_basic_typo_fuzzily() {
        let directory = tempdir().unwrap();
        let catalog = catalog(vec![test_application(
            &directory,
            "spotify",
            "Spotify",
            &[],
        )]);

        let resolved = DeterministicApplicationResolver
            .resolve("spotfy", &catalog)
            .unwrap();

        assert_eq!(resolved.application().canonical_name(), "Spotify");
    }

    #[test]
    fn returns_not_found_without_inventing_target() {
        let directory = tempdir().unwrap();
        let catalog = catalog(vec![test_application(
            &directory,
            "spotify",
            "Spotify",
            &[],
        )]);

        let error = DeterministicApplicationResolver
            .resolve("unrelated", &catalog)
            .expect_err("unknown query must fail");

        assert!(matches!(error, JarvisError::ApplicationNotFound { .. }));
    }

    #[test]
    fn returns_ambiguity_for_equally_plausible_candidates() {
        let directory = tempdir().unwrap();
        let catalog = catalog(vec![
            test_application(&directory, "vscode", "Visual Studio Code", &[]),
            test_application(&directory, "codeblocks", "CodeBlocks", &[]),
        ]);

        let error = DeterministicApplicationResolver
            .resolve("code", &catalog)
            .expect_err("ambiguous query must fail");

        match error {
            JarvisError::ApplicationAmbiguous { candidates, .. } => {
                assert_eq!(candidates.len(), 2);
            }
            other => panic!("unexpected error: {other}"),
        }
    }
}
