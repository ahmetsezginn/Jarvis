use super::failure;
use crate::core::JarvisError;
use sha2::{Digest, Sha256};
use std::{path::PathBuf, sync::Mutex};
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

static MODEL: Mutex<Option<(&'static str, WhisperContext)>> = Mutex::new(None);

pub struct ModelProfile {
    pub name: &'static str,
    file: &'static str,
    pub(super) size: usize,
    pub(super) sha256: &'static str,
}

const SMALL: ModelProfile = ModelProfile {
    name: "small",
    file: "ggml-small.bin",
    size: 487601967,
    sha256: "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
};
const TURBO: ModelProfile = ModelProfile {
    name: "large-v3-turbo",
    file: "ggml-large-v3-turbo.bin",
    size: 1624555275,
    sha256: "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
};
const TURBO_Q5: ModelProfile = ModelProfile {
    name: "large-v3-turbo-q5_0",
    file: "ggml-large-v3-turbo-q5_0.bin",
    size: 574041195,
    sha256: "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2",
};

pub fn profile() -> Result<&'static ModelProfile, JarvisError> {
    let default = if engine()? == "transcribe-cpp" {
        "large-v3-turbo-q5_0"
    } else {
        "small"
    };
    select_profile(&std::env::var("JARVIS_WHISPER_PROFILE").unwrap_or_else(|_| default.into()))
}

pub fn engine() -> Result<&'static str, JarvisError> {
    let default = if cfg!(windows) {
        "transcribe-cpp"
    } else {
        "whisper-cpp"
    };
    match std::env::var("JARVIS_SPEECH_ENGINE")
        .as_deref()
        .unwrap_or(default)
    {
        "transcribe-cpp" if cfg!(windows) => Ok("transcribe-cpp"),
        "whisper-cpp" => Ok("whisper-cpp"),
        _ => Err(failure("Unsupported local speech engine")),
    }
}

pub fn recognizer_label() -> Result<String, JarvisError> {
    let device = if engine()? == "transcribe-cpp" {
        #[cfg(windows)]
        {
            super::transcribe_cpp::device_label()?
        }
        #[cfg(not(windows))]
        {
            String::new()
        }
    } else {
        "CPU".into()
    };
    Ok(format!(
        "Whisper {} / {} / {}",
        profile()?.name,
        engine()?,
        device
    ))
}

fn select_profile(name: &str) -> Result<&'static ModelProfile, JarvisError> {
    match name {
        "small" => Ok(&SMALL),
        "large-v3-turbo" => Ok(&TURBO),
        "large-v3-turbo-q5_0" => Ok(&TURBO_Q5),
        _ => Err(failure("Unsupported speech model profile")),
    }
}

impl ModelProfile {
    pub fn path(&self) -> PathBuf {
        std::env::var_os("JARVIS_WHISPER_MODEL")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join(format!("../../models/whisper-{}", self.name))
                    .join(self.file)
            })
    }

    fn verify(&self, bytes: &[u8]) -> Result<(), JarvisError> {
        if bytes.len() != self.size || format!("{:x}", Sha256::digest(bytes)) != self.sha256 {
            return Err(failure(
                "Whisper artifact checksum/size mismatch; provision selected profile",
            ));
        }
        Ok(())
    }
}

pub fn decoder() -> Result<SamplingStrategy, JarvisError> {
    match std::env::var("JARVIS_WHISPER_DECODER")
        .as_deref()
        .unwrap_or("beam")
    {
        "beam" => Ok(SamplingStrategy::BeamSearch {
            beam_size: 5,
            patience: -1.0,
        }),
        "greedy" => Ok(SamplingStrategy::Greedy { best_of: 1 }),
        _ => Err(failure("Unsupported speech decoder")),
    }
}

/// Signal diagnostics only; not an ASR confidence score or a transcript correction.
pub fn signal_stats(samples: &[f32]) -> serde_json::Value {
    let mut power = 0.0_f64;
    let mut peak = 0.0_f64;
    let mut clipped = 0;
    for &value in samples {
        if !value.is_finite() {
            return serde_json::json!({"valid":false});
        }
        let value = f64::from(value).abs();
        power += value * value;
        peak = peak.max(value);
        clipped += usize::from(value >= 0.999);
    }
    let count = samples.len().max(1) as f64;
    serde_json::json!({"valid":true,
        "rms_dbfs":20.0*(power/count).sqrt().max(0.000001).log10(),
        "peak_dbfs":20.0*peak.max(0.000001).log10(),
        "clipped_fraction":clipped as f64/count})
}

pub fn resample(input: &[f32], rate: u32) -> Vec<f32> {
    if input.is_empty() || rate == 0 {
        return Vec::new();
    }
    let count = input.len() * 16000 / rate as usize;
    (0..count)
        .map(|i| {
            let position = i as f64 * rate as f64 / 16000.0;
            let left = position as usize;
            let fraction = (position - left as f64) as f32;
            let a = input[left.min(input.len() - 1)];
            let b = input[(left + 1).min(input.len() - 1)];
            a + (b - a) * fraction
        })
        .collect()
}

pub fn speech_present(samples: &[f32]) -> bool {
    samples.len() >= 4800
        && samples.iter().all(|x| x.is_finite())
        && samples
            .chunks(320)
            .filter(|chunk| {
                let power = chunk.iter().map(|x| x * x).sum::<f32>() / chunk.len() as f32;
                power > 0.000025
            })
            .count()
            >= 8
}

pub fn transcribe(samples: &[f32], language: &str) -> Result<String, JarvisError> {
    transcribe_with_vocabulary(samples, language, "")
}

pub fn transcribe_with_vocabulary(
    samples: &[f32],
    language: &str,
    vocabulary: &str,
) -> Result<String, JarvisError> {
    recognize(samples, language, vocabulary).map(|result| result.0)
}

pub fn recognize(
    samples: &[f32],
    language: &str,
    vocabulary: &str,
) -> Result<(String, Option<String>), JarvisError> {
    if vocabulary.chars().count() > 512 || vocabulary.chars().any(char::is_control) {
        return Err(failure("Invalid speech spelling context"));
    }
    if !["en", "tr", "auto"].contains(&language) {
        return Err(failure("Unsupported recognition language"));
    }
    if samples.len() > 16000 * 30 {
        return Err(failure("Recording exceeds 30 seconds"));
    }
    let selected = profile()?;
    // Native debug decoders can print recognized words even with realtime output off.
    // Disable provider diagnostics; typed Result errors and Core audit remain enabled.
    whisper_rs::install_logging_hooks();
    if !speech_present(samples) {
        return Ok((String::new(), None));
    }
    if !super::vad::contains_speech(samples)? {
        return Ok((String::new(), None));
    }
    #[cfg(windows)]
    if engine()? == "transcribe-cpp" {
        let result = super::transcribe_cpp::recognize(samples, language, vocabulary, selected)?;
        validate_transcript(&result.0)?;
        return Ok(result);
    }
    let strategy = decoder()?;
    let mut model = MODEL
        .try_lock()
        .map_err(|_| failure("Speech recognition is busy"))?;
    if model
        .as_ref()
        .is_none_or(|(name, _)| *name != selected.name)
    {
        // Never retain both model weights when a developer explicitly changes profiles.
        *model = None;
        let path = selected.path();
        if !path.is_file() {
            return Err(failure(
                "Local Whisper model is missing; run speech provisioning",
            ));
        }
        let mut options = WhisperContextParameters::default();
        options.use_gpu(false);
        // Load from verified in-memory bytes: also supports Unicode Windows repository paths.
        let bytes = std::fs::read(path).map_err(failure)?;
        selected.verify(&bytes)?;
        *model = Some((
            selected.name,
            WhisperContext::new_from_buffer_with_params(&bytes, options).map_err(failure)?,
        ));
    }
    let mut state = model.as_ref().unwrap().1.create_state().map_err(failure)?;
    let mut params = FullParams::new(strategy);
    params.set_n_threads(std::thread::available_parallelism().map_or(4, |n| n.get().min(6)) as i32);
    params.set_language(if language == "auto" {
        None
    } else {
        Some(language)
    });
    params.set_translate(false);
    if !vocabulary.is_empty() {
        params.set_initial_prompt(vocabulary);
    }
    params.set_no_context(true);
    params.set_no_timestamps(true);
    params.set_print_special(false);
    params.set_print_progress(false);
    params.set_print_realtime(false);
    params.set_print_timestamps(false);
    state.full(params, samples).map_err(failure)?;
    let mut parts = Vec::new();
    for segment in state.as_iter() {
        if segment.no_speech_probability() <= 0.6 {
            parts.push(segment.to_str_lossy().map_err(failure)?.trim().to_owned());
        }
    }
    let text = parts.join(" ");
    validate_transcript(&text)?;
    let detected = whisper_rs::get_lang_str(state.full_lang_id_from_state()).map(str::to_owned);
    Ok((text, detected))
}

fn validate_transcript(text: &str) -> Result<(), JarvisError> {
    if text.chars().count() > 2000 || text.chars().any(|c| c.is_control() && !c.is_whitespace()) {
        return Err(failure("Speech transcript is invalid or too long"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn speech_contract_rejects_oversize_language_and_control_output() {
        assert!(recognize(&vec![0.0; 480001], "en", "").is_err());
        assert!(recognize(&[], "invented-language", "").is_err());
        assert!(recognize(&[], "tr", "bad\ncontext").is_err());
        assert!(validate_transcript("bad\0output").is_err());
        assert!(validate_transcript(&"a".repeat(2001)).is_err());
        assert!(validate_transcript("Türkçe and English.").is_ok());
    }
    #[test]
    fn profiles_reject_unknown_names_and_unverified_weights() {
        assert!(select_profile("download-from-url").is_err());
        for name in ["small", "large-v3-turbo", "large-v3-turbo-q5_0"] {
            assert!(
                select_profile(name)
                    .unwrap()
                    .verify(b"not model weights")
                    .is_err()
            );
        }
        assert!(transcribe_with_vocabulary(&[0.0; 16000], "en", &"x".repeat(513)).is_err());
    }
    #[test]
    fn signal_diagnostics_distinguish_quiet_clipped_and_invalid_input() {
        let quiet = signal_stats(&[0.01; 160]);
        assert!((quiet["rms_dbfs"].as_f64().unwrap() + 40.0).abs() < 0.01);
        assert_eq!(signal_stats(&[1.0, -1.0])["clipped_fraction"], 1.0);
        assert_eq!(signal_stats(&[0.0; 160])["rms_dbfs"], -120.0);
        assert_eq!(signal_stats(&[f32::NAN])["valid"], false);
    }
    #[test]
    fn silence_short_and_nonfinite_audio_never_reach_whisper() {
        assert!(!speech_present(&vec![0.; 16000]));
        assert!(!speech_present(&vec![0.1; 1000]));
        assert!(!speech_present(&vec![f32::NAN; 16000]));
        assert_eq!(transcribe(&vec![0.; 16000], "en").unwrap(), "");
        assert!(speech_present(&vec![0.1; 16000]));
    }
    #[test]
    fn native_pcm_is_resampled_to_whisper_rate() {
        let result = resample(&vec![0.25; 48000], 48000);
        assert_eq!(result.len(), 16000);
        assert!(result.iter().all(|x| (*x - 0.25).abs() < 0.0001));
        assert!(resample(&[], 48000).is_empty());
    }
}
