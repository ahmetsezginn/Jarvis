//! CPU Silero GGML, through the already linked whisper.cpp runtime; no ONNX.
use super::failure;
use crate::core::JarvisError;
use sha2::{Digest, Sha256};
use std::path::PathBuf;
use whisper_rs::{WhisperVadContext, WhisperVadContextParams};

pub fn model_path() -> PathBuf {
    super::models_directory().join("whisper-vad/ggml-silero-v6.2.0.bin")
}

pub fn load() -> Result<WhisperVadContext, JarvisError> {
    whisper_rs::install_logging_hooks();
    let path = model_path();
    let bytes =
        std::fs::read(&path).map_err(|_| failure("Provision the local Silero VAD model first"))?;
    if format!("{:x}", Sha256::digest(&bytes))
        != "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987"
    {
        return Err(failure("VAD artifact checksum mismatch"));
    }
    let mut params = WhisperVadContextParams::default();
    params.set_n_threads(2);
    params.set_use_gpu(false);
    WhisperVadContext::new(
        path.to_str().ok_or_else(|| failure("Invalid VAD path"))?,
        params,
    )
    .map_err(failure)
}

pub fn probability(model: &mut WhisperVadContext, window: &[f32]) -> Result<f32, JarvisError> {
    model.detect_speech(window).map_err(failure)?;
    let tail: Vec<_> = model
        .probabilities()
        .iter()
        .rev()
        .take(3)
        .copied()
        .collect();
    Ok(tail.iter().sum::<f32>() / tail.len().max(1) as f32)
}

/// Energy alone is not speech. Gate completed manual AND automatic utterances;
/// retain the original PCM, including pauses/negations, rather than trimming words.
pub fn contains_speech(samples: &[f32]) -> Result<bool, JarvisError> {
    let mut model = load()?;
    model.detect_speech(samples).map_err(failure)?;
    // Silero's 16 kHz frames contain 512 samples (32ms). Require at least 160ms
    // of model-detected speech across this bounded utterance.
    Ok(model
        .probabilities()
        .iter()
        .filter(|&&p| p >= 0.5)
        .take(5)
        .count()
        >= 5)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audio::turn::TurnDetector;
    use std::collections::VecDeque;

    #[test]
    #[ignore = "explicit synthetic short utterances through real Auto VAD and ASR; no device"]
    fn real_auto_turn_retains_short_utterances() {
        let root = std::path::PathBuf::from(
            std::env::var("JARVIS_ASR_EVAL").expect("Set quality fixture root"),
        );
        let cases: serde_json::Value =
            serde_json::from_slice(&std::fs::read(root.join("manifest.json")).unwrap()).unwrap();
        let vocabulary = crate::audio::recognition_vocabulary(
            [
                "Steam", "Firefox", "Notepad", "Obsidian", "Spotify", "Chrome",
            ]
            .map(str::to_owned),
        );
        let mut failures = Vec::new();
        for case in cases.as_array().unwrap().iter().take(3) {
            let wav = std::fs::read(root.join(case["file"].as_str().unwrap())).unwrap();
            let mut offset = 12;
            let mut original = Vec::new();
            while offset + 8 <= wav.len() {
                let length =
                    u32::from_le_bytes(wav[offset + 4..offset + 8].try_into().unwrap()) as usize;
                if &wav[offset..offset + 4] == b"data" {
                    original.extend(
                        wav[offset + 8..offset + 8 + length]
                            .chunks_exact(2)
                            .map(|x| i16::from_le_bytes([x[0], x[1]]) as f32 / 32768.),
                    );
                }
                offset += 8 + length + length % 2;
            }
            for noisy in [false, true] {
                let mut random = 1949_u32;
                let pcm: Vec<_> = original
                    .iter()
                    .map(|sample| {
                        if !noisy {
                            return *sample;
                        }
                        random = random.wrapping_mul(1664525).wrapping_add(1013904223);
                        sample * 0.12 + (random as f32 / u32::MAX as f32 * 2. - 1.) * 0.003
                    })
                    .collect();
                let mut model = load().unwrap();
                let mut window = VecDeque::new();
                let mut turn = TurnDetector::default();
                for chunk in pcm
                    .chunks(1600)
                    .chain(std::iter::repeat_n(&[0.; 1600][..], 20))
                {
                    let mut frame = [0.; 1600];
                    frame[..chunk.len()].copy_from_slice(chunk);
                    window.extend(frame);
                    while window.len() > 15360 {
                        window.pop_front();
                    }
                    let score = probability(&mut model, window.make_contiguous()).unwrap();
                    turn.push(&frame, score >= 0.5);
                    if turn.complete {
                        break;
                    }
                }
                assert!(turn.complete && !turn.truncated, "No completed Auto turn");
                let text =
                    crate::audio::transcribe_with_vocabulary(&turn.samples, "auto", &vocabulary)
                        .unwrap();
                let normalized = text.to_lowercase();
                let good = case["keywords"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .all(|word| normalized.contains(word.as_str().unwrap()));
                println!(
                    "Auto fixture {} noisy={noisy} duration_ms={} matched={good}: {text}",
                    case["file"],
                    turn.samples.len() * 1000 / 16000
                );
                if !good {
                    failures.push(format!("{} noisy={noisy}: {text}", case["file"]));
                }
            }
        }
        assert!(failures.is_empty(), "{}", failures.join("\n"));
    }

    #[test]
    #[ignore = "explicit pinned VAD inference on public speech and synthetic noise"]
    fn real_vad_rejects_silence_and_noise_then_endpoints_public_speech() {
        let mut model = load().unwrap();
        for amplitude in [0., 0.01, 0.1] {
            let mut window = VecDeque::new();
            let mut turn = TurnDetector::default();
            let mut random = 1234567_u32;
            for _ in 0..60 {
                let frame: Vec<_> = (0..1600)
                    .map(|_| {
                        random = random.wrapping_mul(1664525).wrapping_add(1013904223);
                        (random as f32 / u32::MAX as f32 * 2. - 1.) * amplitude
                    })
                    .collect();
                window.extend(frame.iter().copied());
                while window.len() > 15360 {
                    window.pop_front();
                }
                let score = probability(&mut model, window.make_contiguous()).unwrap();
                turn.push(&frame, score >= 0.5);
            }
            assert!(
                !turn.listening,
                "noise amplitude {amplitude} triggered a turn"
            );
        }
        let path = std::env::var("JARVIS_SPEECH_FIXTURE").expect("Set public WAV fixture");
        let wav = std::fs::read(path).unwrap();
        let mut offset = 12;
        let mut pcm = Vec::new();
        while offset + 8 <= wav.len() {
            let length =
                u32::from_le_bytes(wav[offset + 4..offset + 8].try_into().unwrap()) as usize;
            if &wav[offset..offset + 4] == b"data" {
                pcm.extend(
                    wav[offset + 8..offset + 8 + length]
                        .chunks_exact(2)
                        .map(|x| i16::from_le_bytes([x[0], x[1]]) as f32 / 32768.),
                );
            }
            offset += 8 + length + length % 2;
        }
        let mut window = VecDeque::new();
        let mut turn = TurnDetector::default();
        for frame in pcm
            .chunks(1600)
            .chain(std::iter::repeat_n(&[0.; 1600][..], 20))
        {
            window.extend(frame.iter().copied());
            while window.len() > 15360 {
                window.pop_front();
            }
            let score = probability(&mut model, window.make_contiguous()).unwrap();
            turn.push(frame, score >= 0.5);
            if turn.complete {
                break;
            }
        }
        assert!(turn.listening && turn.complete && !turn.truncated);
        assert!(turn.samples.len() > 16000);
        let text = crate::audio::transcribe(&turn.samples, "en").unwrap();
        assert!(text.to_lowercase().contains("fellow"), "{text}");
        println!(
            "Public VAD endpoint: {} ms; silence and noise rejected",
            turn.samples.len() * 1000 / 16000
        );
    }
}
