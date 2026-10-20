use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub schema: u32,
    pub owner_account: String,
    pub owner_sid: String,
    pub repository: PathBuf,
    pub powershell: PathBuf,
    #[serde(default)]
    pub microphone: Option<String>,
}
impl Config {
    pub fn validate(&self) -> Result<(), String> {
        let sid: Vec<_> = self.owner_sid.split('-').collect();
        if self.schema != 1
            || sid.len() != 8
            || sid[..4] != ["S", "1", "5", "21"]
            || sid[4..]
                .iter()
                .any(|part| part.is_empty() || part.parse::<u32>().is_err())
            || self.owner_account.is_empty()
            || self.owner_account.len() > 180
            || self.owner_account.chars().any(char::is_control)
            || self.microphone.as_ref().is_some_and(|name| {
                name.is_empty() || name.len() > 240 || name.chars().any(char::is_control)
            })
            || !self.repository.is_absolute()
            || !self.powershell.is_absolute()
            || self
                .powershell
                .file_name()
                .is_none_or(|s| !s.eq_ignore_ascii_case("powershell.exe"))
        {
            return Err("Invalid installed wake configuration".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn configuration_is_exact_and_never_accepts_arbitrary_launch_fields() {
        let source = r#"{"schema":1,"owner_account":"PC\\user","owner_sid":"S-1-5-21-1-2-3-1001","repository":"C:\\JARVIS","powershell":"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"}"#;
        let config: Config = serde_json::from_str(source).unwrap();
        #[cfg(windows)]
        assert!(config.validate().is_ok());
        assert!(
            serde_json::from_str::<Config>(
                &source.replace("\"schema\":1", "\"command\":\"shell\",\"schema\":1")
            )
            .is_err()
        );
        let mut bad = config;
        bad.owner_sid = "untrusted".into();
        assert!(bad.validate().is_err());
    }
}
