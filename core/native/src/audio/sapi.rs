//! Thread-confined, platform-owned SAPI tokens. No registry writes or caller-provided token IDs.
use super::failure;
use crate::core::JarvisError;
use serde_json::{Value, json};
use windows::{
    Win32::{
        Foundation::VARIANT_FALSE,
        Media::Speech::{
            ISpeechObjectToken, ISpeechObjectTokenCategory, ISpeechObjectTokens, ISpeechVoice,
            SpObjectTokenCategory, SpVoice, SpeechVoiceSpeakFlags,
        },
        System::Com::{CLSCTX_ALL, CoCreateInstance},
    },
    core::BSTR,
};

pub struct Speaker {
    voice: ISpeechVoice,
    voices: Vec<ISpeechObjectToken>,
    outputs: Vec<ISpeechObjectToken>,
    default_output: ISpeechObjectToken,
}

fn tokens(collection: ISpeechObjectTokens) -> Result<Vec<ISpeechObjectToken>, JarvisError> {
    let count = unsafe { collection.Count() }.map_err(failure)?.min(32);
    (0..count)
        .map(|i| unsafe { collection.Item(i) }.map_err(failure))
        .collect()
}

fn language_matches(attributes: &str, language: &str) -> bool {
    let primary = match language {
        "en" => 0x09,
        "tr" => 0x1f,
        _ => return false,
    };
    attributes.split(';').any(|value| {
        u32::from_str_radix(value.trim(), 16).is_ok_and(|lcid| lcid & 0x3ff == primary)
    })
}

impl Speaker {
    pub fn new() -> Result<Self, JarvisError> {
        let voice: ISpeechVoice =
            unsafe { CoCreateInstance(&SpVoice, None, CLSCTX_ALL) }.map_err(failure)?;
        let mut voices =
            tokens(unsafe { voice.GetVoices(&BSTR::new(), &BSTR::new()) }.map_err(failure)?)?;
        // Windows language packs can expose voices only through OneCore. Read the installed
        // category directly, never copy tokens into SAPI or modify Windows speech settings.
        let category: ISpeechObjectTokenCategory =
            unsafe { CoCreateInstance(&SpObjectTokenCategory, None, CLSCTX_ALL) }
                .map_err(failure)?;
        if unsafe {
            category.SetId(
                &BSTR::from("HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech_OneCore\\Voices"),
                VARIANT_FALSE,
            )
        }
        .is_ok()
        {
            let more = tokens(
                unsafe { category.EnumerateTokens(&BSTR::new(), &BSTR::new()) }.map_err(failure)?,
            )?;
            for token in more {
                let id = unsafe { token.Id() }.map_err(failure)?;
                if !voices
                    .iter()
                    .any(|existing| unsafe { existing.Id() }.is_ok_and(|value| value == id))
                    && voices.len() < 64
                {
                    voices.push(token);
                }
            }
        }
        let outputs =
            tokens(unsafe { voice.GetAudioOutputs(&BSTR::new(), &BSTR::new()) }.map_err(failure)?)?;
        let default_output = unsafe { voice.AudioOutput() }.map_err(failure)?;
        // This affects this voice instance only; system/application mixer volume is untouched.
        unsafe { voice.SetVolume(100) }.map_err(failure)?;
        Ok(Self {
            voice,
            voices,
            outputs,
            default_output,
        })
    }

    pub fn inventory(&self) -> Result<Value, JarvisError> {
        let mut voices = Vec::new();
        for token in &self.voices {
            let name = unsafe { token.GetDescription(0) }
                .map_err(failure)?
                .to_string();
            let attributes = unsafe { token.GetAttribute(&BSTR::from("Language")) }
                .map_err(failure)?
                .to_string();
            let languages: Vec<_> = ["en", "tr"]
                .into_iter()
                .filter(|lang| language_matches(&attributes, lang))
                .collect();
            voices.push(json!({"name":name, "languages":languages}));
        }
        let mut outputs = Vec::new();
        for (index, token) in self.outputs.iter().enumerate() {
            outputs.push(json!({"index":index,"name":unsafe { token.GetDescription(0) }.map_err(failure)?.to_string()}));
        }
        Ok(json!({"voices":voices,"output_devices":outputs,
            "default_output":unsafe { self.default_output.GetDescription(0) }.map_err(failure)?.to_string()}))
    }

    pub fn output_status(&self) -> Result<Value, JarvisError> {
        // RunningState == 0 means waiting to speak, NOT completion. In particular,
        // synthesis/device startup may still be pending after an asynchronous Speak.
        let running = unsafe { self.voice.Status().and_then(|status| status.RunningState()) }
            .map_err(failure)?
            .0;
        let done = unsafe { self.voice.WaitUntilDone(0) }
            .map_err(failure)?
            .as_bool();
        Ok(output_status(running, done))
    }

    pub fn speak(
        &self,
        text: &str,
        language: &str,
        output: Option<usize>,
    ) -> Result<Value, JarvisError> {
        let token = self
            .voices
            .iter()
            .find(|token| {
                unsafe { token.GetAttribute(&BSTR::from("Language")) }
                    .is_ok_and(|value| language_matches(&value.to_string(), language))
            })
            .ok_or_else(|| {
                failure(format!(
                    "No installed {language} speech voice; choose an available voice language"
                ))
            })?;
        let destination = match output {
            Some(index) => self
                .outputs
                .get(index)
                .ok_or_else(|| failure("Speech output device is unavailable; refresh devices"))?,
            None => &self.default_output,
        };
        // Validate/select before queueing any audio; unsupported languages never fall back silently.
        self.stop()?;
        unsafe {
            self.voice.putref_Voice(token).map_err(failure)?;
            self.voice
                .putref_AudioOutput(destination)
                .map_err(failure)?;
            self.voice
                .Speak(&BSTR::from(text), SpeechVoiceSpeakFlags(1 | 2 | 16))
                .map_err(failure)?;
        }
        Ok(
            json!({"queued":true,"engine":"windows-sapi","language":language,
            "voice":unsafe { token.GetDescription(0) }.map_err(failure)?.to_string(),
            "output_device":unsafe { destination.GetDescription(0) }.map_err(failure)?.to_string()}),
        )
    }

    pub fn stop(&self) -> Result<(), JarvisError> {
        unsafe {
            self.voice
                .Speak(&BSTR::new(), SpeechVoiceSpeakFlags(1 | 2 | 16))
        }
        .map(|_| ())
        .map_err(failure)
    }
}

fn output_status(running: i32, done: bool) -> Value {
    let phase = if done {
        "idle"
    } else if running == 2 {
        "speaking"
    } else {
        "queued"
    };
    // Keep the existing boolean conservative for clients predating output_phase.
    json!({"speaking":!done, "output_phase":phase})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn language_attributes_are_hex_lcids_with_optional_padding_and_multiple_locales() {
        assert!(language_matches("041f", "tr"));
        assert!(language_matches("41F", "tr"));
        assert!(language_matches("409;809", "en"));
        assert!(language_matches(" 0409 ", "en"));
        assert!(!language_matches("041f", "en"));
        assert!(!language_matches("not-a-language", "tr"));
        assert!(!language_matches("409", "auto"));
    }

    #[test]
    fn pending_synthesis_is_busy_until_the_entire_queue_completes() {
        assert_eq!(
            output_status(0, false),
            json!({"speaking":true,"output_phase":"queued"})
        );
        assert_eq!(
            output_status(2, false),
            json!({"speaking":true,"output_phase":"speaking"})
        );
        assert_eq!(
            output_status(1, true),
            json!({"speaking":false,"output_phase":"idle"})
        );
        assert_eq!(
            output_status(0, true),
            json!({"speaking":false,"output_phase":"idle"})
        );
    }
}
