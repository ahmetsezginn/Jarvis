use crate::{
    audio::AudioService,
    core::{JarvisError, RiskLevel},
    tools::{Tool, ToolContext, ToolOutput},
};
use serde::Deserialize;
use serde_json::{Value, json};
use std::sync::Arc;

#[derive(Deserialize, Default)]
#[serde(deny_unknown_fields)]
struct Arguments {
    device_index: Option<usize>,
    recording_id: Option<String>,
    language: Option<String>,
    text: Option<String>,
    automatic: Option<bool>,
    output_device_index: Option<usize>,
}

pub struct AudioTool {
    name: &'static str,
    audio: Arc<dyn AudioService>,
    catalog: Option<Arc<crate::apps::ApplicationCatalog>>,
}
impl AudioTool {
    pub fn all(
        audio: Arc<dyn AudioService>,
        catalog: Option<Arc<crate::apps::ApplicationCatalog>>,
    ) -> Vec<Arc<dyn Tool>> {
        [
            "speech_status",
            "speech_poll",
            "speech_start",
            "speech_finish",
            "speech_cancel",
            "speech_speak",
            "speech_stop",
        ]
        .into_iter()
        .map(|name| {
            Arc::new(Self {
                name,
                audio: audio.clone(),
                catalog: catalog.clone(),
            }) as Arc<dyn Tool>
        })
        .collect()
    }
    fn arguments(&self, value: &Value) -> Result<Arguments, JarvisError> {
        let invalid = || JarvisError::InvalidArguments {
            message: "Invalid speech arguments".into(),
        };
        let args: Arguments = serde_json::from_value(value.clone()).map_err(|_| invalid())?;
        let object = value.as_object().ok_or_else(invalid)?;
        let allowed: &[&str] = match self.name {
            "speech_start" => &["device_index", "automatic"],
            "speech_poll" => &["recording_id"],
            "speech_finish" => &["recording_id", "language"],
            "speech_cancel" => &["recording_id"],
            "speech_speak" => &["text", "language", "output_device_index"],
            _ => &[],
        };
        if object.keys().any(|key| !allowed.contains(&key.as_str())) {
            return Err(invalid());
        }
        if args.device_index.is_some_and(|x| x >= 32)
            || args.output_device_index.is_some_and(|x| x >= 32)
        {
            return Err(invalid());
        }
        if self.name == "speech_poll"
            && args
                .recording_id
                .as_ref()
                .is_some_and(|id| uuid::Uuid::parse_str(id).is_err())
        {
            return Err(invalid());
        }
        if matches!(self.name, "speech_finish" | "speech_cancel")
            && args
                .recording_id
                .as_ref()
                .is_none_or(|id| uuid::Uuid::parse_str(id).is_err())
        {
            return Err(invalid());
        }
        if args
            .language
            .as_ref()
            .is_some_and(|x| !["auto", "en", "tr"].contains(&x.as_str()))
        {
            return Err(invalid());
        }
        if self.name == "speech_speak" && args.language.as_deref() == Some("auto") {
            return Err(invalid());
        }
        if self.name == "speech_speak"
            && args.text.as_ref().is_none_or(|text| {
                text.trim().is_empty()
                    || text.chars().count() > 1024
                    || text.chars().any(|c| c.is_control() && c != '\n')
            })
        {
            return Err(invalid());
        }
        Ok(args)
    }
}
impl Tool for AudioTool {
    fn name(&self) -> &'static str {
        self.name
    }
    fn risk_level(&self) -> RiskLevel {
        if self.name == "speech_status" {
            RiskLevel::ReadOnly
        } else {
            RiskLevel::Low
        }
    }
    fn validate(&self, args: &Value) -> Result<(), JarvisError> {
        self.arguments(args).map(|_| ())
    }
    fn execute(&self, _: &ToolContext, value: &Value) -> Result<ToolOutput, JarvisError> {
        let args = self.arguments(value)?;
        match self.name {
            "speech_status" => self.audio.status(),
            "speech_start" => self
                .audio
                .start(args.device_index, args.automatic.unwrap_or(false)),
            "speech_poll" => self.audio.poll(args.recording_id.as_deref()),
            "speech_finish" => self.audio.finish(
                args.recording_id.as_deref().unwrap(),
                args.language.as_deref().unwrap_or("auto"),
                &crate::audio::recognition_vocabulary(self.catalog.as_ref().map_or_else(
                    Vec::new,
                    |catalog| {
                        catalog
                            .applications()
                            .iter()
                            .map(|app| app.canonical_name().to_owned())
                            .collect()
                    },
                )),
            ),
            "speech_cancel" => self.audio.cancel(args.recording_id.as_deref().unwrap()),
            "speech_speak" => self.audio.speak(
                args.text.as_deref().unwrap(),
                args.language.as_deref().unwrap_or("en"),
                args.output_device_index,
            ),
            "speech_stop" => self.audio.stop(),
            _ => Ok(json!({})),
        }
    }
}
