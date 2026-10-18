//! Handy's native recognition provider, in-process Rust; no GUI, network or recordings.
use super::{failure, transcribe::ModelProfile};
use crate::core::JarvisError;
use sha2::{Digest, Sha256};
use std::{
    fs::File,
    io::Read,
    path::PathBuf,
    sync::{Mutex, OnceLock},
};
use transcribe_cpp::{
    Backend, DeviceType, Model, ModelOptions, RunExtension, RunOptions, SessionOptions,
    TimestampKind, WhisperRunOptions,
};

// Retain only a verified read handle. GPU model/session weights are freed before Brain reasoning.
static VERIFIED: Mutex<Option<(PathBuf, &'static str, File)>> = Mutex::new(None);
static INITIALIZED: OnceLock<Result<(), String>> = OnceLock::new();

fn initialize() -> Result<(), JarvisError> {
    INITIALIZED
        .get_or_init(|| {
            transcribe_cpp::disable_logging();
            if transcribe_cpp::version() != "0.2.4" {
                return Err("Expected native transcribe.cpp 0.2.4".into());
            }
            let dir = std::env::current_exe()
                .map_err(|e| e.to_string())?
                .parent()
                .ok_or("Cannot locate native speech runtime")?
                .to_owned();
            // Never search CWD or PATH for compute modules.
            transcribe_cpp::init_backends(&dir).map_err(|e| e.to_string())
        })
        .as_ref()
        .map_err(failure)
        .copied()
}

fn requested_device() -> Result<&'static str, JarvisError> {
    match std::env::var("JARVIS_SPEECH_DEVICE")
        .as_deref()
        .unwrap_or("gpu")
    {
        "gpu" => Ok("gpu"),
        "cpu" => Ok("cpu"),
        _ => Err(failure("Speech device must be gpu or cpu")),
    }
}

fn device() -> Result<transcribe_cpp::Device, JarvisError> {
    initialize()?;
    let requested = requested_device()?;
    let devices = transcribe_cpp::devices();
    devices.into_iter().filter(|d| {
        if requested == "cpu" { d.device_type == DeviceType::Cpu }
        else { d.device_type == DeviceType::Gpu && d.kind == "vulkan" }
    }).max_by_key(|d| d.memory_total)
      .ok_or_else(|| failure("Requested speech compute device unavailable; CPU requires explicit JARVIS_SPEECH_DEVICE=cpu"))
}

pub fn device_label() -> Result<String, JarvisError> {
    let selected = device()?;
    Ok(format!("{} ({})", selected.description, selected.kind))
}

fn verify_file(path: &std::path::Path, size: u64, checksum: &str) -> Result<File, JarvisError> {
    use std::os::windows::fs::OpenOptionsExt;
    // Deny writes/deletes while verified: file-path loading cannot race a replacement.
    let mut file = std::fs::OpenOptions::new()
        .read(true)
        .share_mode(1)
        .open(path)
        .map_err(|_| failure("Provision the local speech model first"))?;
    if file.metadata().map_err(failure)?.len() != size {
        return Err(failure("Speech model size mismatch"));
    }
    let mut hash = Sha256::new();
    let mut chunk = vec![0; 1024 * 1024];
    loop {
        let count = file.read(&mut chunk).map_err(failure)?;
        if count == 0 {
            break;
        }
        hash.update(&chunk[..count]);
    }
    if format!("{:x}", hash.finalize()) != checksum {
        return Err(failure("Speech model checksum mismatch"));
    }
    Ok(file)
}

pub fn recognize(
    samples: &[f32],
    language: &str,
    vocabulary: &str,
    profile: &ModelProfile,
) -> Result<(String, Option<String>), JarvisError> {
    let mut verified = VERIFIED
        .try_lock()
        .map_err(|_| failure("Speech recognition is busy"))?;
    let path = profile.path();
    if verified
        .as_ref()
        .is_none_or(|(p, checksum, _)| *p != path || *checksum != profile.sha256)
    {
        *verified = None;
        *verified = Some((
            path.clone(),
            profile.sha256,
            verify_file(&path, profile.size as u64, profile.sha256)?,
        ));
    }
    let selected = device()?;
    if selected.device_type == DeviceType::Gpu
        && selected.memory_free != 0
        && selected.memory_free < profile.size as u64 + 384 * 1024 * 1024
    {
        return Err(failure(
            "Not enough free GPU memory for speech; release GPU memory or select CPU explicitly",
        ));
    }
    let model = Model::load_with(
        path,
        &ModelOptions {
            backend: if selected.device_type == DeviceType::Cpu {
                Backend::Cpu
            } else {
                Backend::Vulkan
            },
            device: Some(selected),
        },
    )
    .map_err(failure)?;
    let mut session = model
        .session_with(&SessionOptions {
            n_threads: 6,
            ..Default::default()
        })
        .map_err(failure)?;
    let result = session
        .run(
            samples,
            &RunOptions {
                language: (language != "auto").then(|| language.to_owned()),
                timestamps: TimestampKind::None,
                family: Some(RunExtension::Whisper(WhisperRunOptions {
                    initial_prompt: (!vocabulary.is_empty()).then(|| vocabulary.to_owned()),
                    condition_on_prev_tokens: Some(false),
                    ..Default::default()
                })),
                ..Default::default()
            },
        )
        .map_err(failure)?;
    // Session and model drop here even on error; no GPU weights retained between turns.
    let recognized_language = result
        .language
        .or_else(|| (language != "auto" && !result.text.is_empty()).then(|| language.to_owned()));
    Ok((result.text, recognized_language))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn verification_rejects_corruption_and_pins_file_against_writes() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("invalid.bin");
        std::fs::write(&path, b"bad").unwrap();
        let checksum = format!("{:x}", Sha256::digest(b"bad"));
        assert!(verify_file(&path, 4, &checksum).is_err());
        assert!(verify_file(&path, 3, &"0".repeat(64)).is_err());
        let guard = verify_file(&path, 3, &checksum).unwrap();
        assert!(std::fs::write(&path, b"new").is_err());
        drop(guard);
        std::fs::write(&path, b"new").unwrap();
        assert!(verify_file(&path, 3, &checksum).is_err());
    }
}
