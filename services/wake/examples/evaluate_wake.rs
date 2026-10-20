//! Explicit local-file evaluation of the production detector. Never captures or opens apps.
#[path = "../src/artifacts.rs"]
mod artifacts;
#[path = "../src/detector.rs"]
mod detector;
#[path = "../src/litert.rs"]
mod litert;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "C:\\Program Files\\JARVIS\\Wake\\runtime".into());
    let mut detector = detector::Detector::open(std::path::Path::new(&root))?;
    let mut failures = 0;
    for entry in std::fs::read_dir("target/wake-fixtures")? {
        let path = entry?.path();
        if path.extension().is_none_or(|ext| ext != "wav") {
            continue;
        }
        let bytes = std::fs::read(&path)?;
        if bytes.len() < 44 || !bytes.starts_with(b"RIFF") || &bytes[8..12] != b"WAVE" {
            return Err("Invalid WAV".into());
        }
        let mut offset = 12;
        let mut rate = 0;
        let mut pcm = vec![];
        while offset + 8 <= bytes.len() {
            let count = u32::from_le_bytes(bytes[offset + 4..offset + 8].try_into()?) as usize;
            if offset + 8 + count > bytes.len() {
                return Err("Truncated WAV".into());
            }
            let chunk = &bytes[offset + 8..offset + 8 + count];
            match &bytes[offset..offset + 4] {
                b"fmt " => {
                    if chunk.len() < 16
                        || u16::from_le_bytes(chunk[..2].try_into()?) != 1
                        || u16::from_le_bytes(chunk[2..4].try_into()?) != 1
                        || u16::from_le_bytes(chunk[14..16].try_into()?) != 16
                    {
                        return Err("Mono PCM16 required".into());
                    }
                    rate = u32::from_le_bytes(chunk[4..8].try_into()?);
                }
                b"data" => {
                    pcm = chunk
                        .chunks_exact(2)
                        .map(|sample| i16::from_le_bytes(sample.try_into().unwrap()))
                        .collect()
                }
                _ => {}
            }
            offset += 8 + count + (count % 2);
        }
        if rate == 0 || pcm.is_empty() {
            return Err("Missing PCM".into());
        }
        let mut resampled: Vec<i16> = (0..pcm.len() * 16000 / rate as usize)
            .map(|i| pcm[(i * rate as usize / 16000).min(pcm.len() - 1)])
            .collect();
        resampled.splice(..0, vec![0; 16000]);
        resampled.extend(vec![0; 16000]);
        detector.reset()?;
        let started = std::time::Instant::now();
        let mut detected = false;
        let mut maximum = 0.0f32;
        for chunk in resampled.chunks(320) {
            detected |= detector.feed(chunk)?;
            maximum = maximum.max(detector.score());
        }
        let expected = path
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("wake-");
        println!(
            "{} expected={} detected={} neural_score={:.5} decode_ms={:.2}",
            path.file_name().unwrap().to_string_lossy(),
            expected,
            detected,
            maximum,
            started.elapsed().as_secs_f64() * 1000.0
        );
        if detected != expected {
            failures += 1;
        }
    }
    if failures > 0 {
        return Err(format!("{failures} wake fixture failures").into());
    }
    Ok(())
}
