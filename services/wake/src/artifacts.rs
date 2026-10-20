use sha2::{Digest, Sha256};
use std::path::Path;
pub const MODELS: [(&str, &str); 4] = [
    (
        "libLiteRt.dll",
        "445f51fed26967fc1112e0de9ddfef7d8497b24322bbfe18b556426a60000891",
    ),
    (
        "melspectrogram.tflite",
        "96fa0adccb6e8cf95cb14465409a1a2898ee4a96a85bb9ed3c7eb0e68bf163e8",
    ),
    (
        "embedding_model.tflite",
        "c0aea21eb84a4ce90a08c870da41b7a7173b45269e6a3207c71d67c40f3a59d8",
    ),
    (
        "hey_jarvis_v0.1.tflite",
        "14bff778604985e1b5c19f0f7bbe477a69cf281d8db34b232b3b972411f710e2",
    ),
];
pub fn verify(root: &Path) -> Result<(), String> {
    for (name, hash) in MODELS {
        let path = root.join(name);
        let metadata = std::fs::metadata(&path).map_err(|error| error.to_string())?;
        if !metadata.is_file() || metadata.len() > 8_000_000 {
            return Err("Invalid keyword artifact size".into());
        }
        let bytes = std::fs::read(path).map_err(|error| error.to_string())?;
        if format!("{:x}", Sha256::digest(bytes)) != hash {
            return Err("Keyword artifact checksum mismatch".into());
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn missing_and_changed_model_files_fail_before_model_parsing() {
        let root = tempfile::tempdir().unwrap();
        assert!(verify(root.path()).is_err());
        std::fs::write(root.path().join(MODELS[0].0), b"malformed model").unwrap();
        assert!(verify(root.path()).unwrap_err().contains("checksum"));
    }
}
