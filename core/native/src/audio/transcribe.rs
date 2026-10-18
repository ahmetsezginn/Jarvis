use super::failure;
use crate::core::JarvisError;
use sha2::{Digest, Sha256};
use std::{path::PathBuf, sync::Mutex};
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

static MODEL: Mutex<Option<WhisperContext>> = Mutex::new(None);

pub fn model_path() -> PathBuf {
    std::env::var_os("JARVIS_WHISPER_MODEL")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../models/whisper-small/ggml-small.bin")
        })
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
    recognize(samples, language).map(|result| result.0)
}

pub fn recognize(samples: &[f32], language: &str) -> Result<(String, Option<String>), JarvisError> {
    if !["en", "tr", "auto"].contains(&language) {
        return Err(failure("Unsupported recognition language"));
    }
    // Native debug decoders can print recognized words even with realtime output off.
    // Disable provider diagnostics; typed Result errors and Core audit remain enabled.
    whisper_rs::install_logging_hooks();
    if !speech_present(samples) {
        return Ok((String::new(), None));
    }
    if samples.len() > 16000 * 30 {
        return Err(failure("Recording exceeds 30 seconds"));
    }
    let mut model = MODEL
        .try_lock()
        .map_err(|_| failure("Speech recognition is busy"))?;
    if model.is_none() {
        let path = model_path();
        if !path.is_file() {
            return Err(failure(
                "Local Whisper model is missing; run speech provisioning",
            ));
        }
        let mut options = WhisperContextParameters::default();
        options.use_gpu(false);
        // Load from verified in-memory bytes: also supports Unicode Windows repository paths.
        let bytes = std::fs::read(path).map_err(failure)?;
        if bytes.len() != 487601967
            || format!("{:x}", Sha256::digest(&bytes))
                != "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b"
        {
            return Err(failure(
                "Whisper artifact checksum/size mismatch; provision it again",
            ));
        }
        *model =
            Some(WhisperContext::new_from_buffer_with_params(&bytes, options).map_err(failure)?);
    }
    let mut state = model.as_ref().unwrap().create_state().map_err(failure)?;
    let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
    params.set_n_threads(std::thread::available_parallelism().map_or(4, |n| n.get().min(6)) as i32);
    params.set_language(if language == "auto" {
        None
    } else {
        Some(language)
    });
    params.set_translate(false);
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
    if text.chars().count() > 2000 || text.contains(['\0', '\x1b']) {
        return Err(failure("Speech transcript is invalid or too long"));
    }
    let detected = whisper_rs::get_lang_str(state.full_lang_id_from_state()).map(str::to_owned);
    Ok((text, detected))
}

#[cfg(test)]
mod tests {
    use super::*;
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
