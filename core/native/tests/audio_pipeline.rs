use jarvis_core::{
    audio::AudioService,
    audit::MemoryAuditSink,
    core::{JarvisError, RequestSource, ToolRequest, ToolStatus},
    executor::Executor,
    platform::fake::FakeDesktopPlatform,
    policy::{DefaultPolicyEngine, PolicyDecision, PolicyEngine},
    tools::ToolMetadata,
    tools::{ToolRegistry, audio::AudioTool},
};
use serde_json::{Value, json};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicUsize, Ordering},
};

#[derive(Default)]
struct FakeAudio(AtomicUsize, Mutex<Option<(String, String, Option<usize>)>>);
impl FakeAudio {
    fn response(&self) -> Result<Value, JarvisError> {
        self.0.fetch_add(1, Ordering::SeqCst);
        Ok(json!({"ok":true}))
    }
}
impl AudioService for FakeAudio {
    fn status(&self) -> Result<Value, JarvisError> {
        self.response()
    }
    fn start(&self, _: Option<usize>, _: bool) -> Result<Value, JarvisError> {
        self.response()
    }
    fn poll(&self, _: Option<&str>) -> Result<Value, JarvisError> {
        self.response()
    }
    fn finish(&self, _: &str, _: &str) -> Result<Value, JarvisError> {
        self.response()
    }
    fn cancel(&self, _: &str) -> Result<Value, JarvisError> {
        self.response()
    }
    fn speak(
        &self,
        text: &str,
        language: &str,
        output: Option<usize>,
    ) -> Result<Value, JarvisError> {
        *self.1.lock().unwrap() = Some((text.into(), language.into(), output));
        self.response()
    }
    fn stop(&self) -> Result<Value, JarvisError> {
        self.response()
    }
}
struct Deny;
impl PolicyEngine for Deny {
    fn evaluate(&self, _: &ToolRequest, _: &ToolMetadata) -> PolicyDecision {
        PolicyDecision::Deny {
            reason: "test".into(),
        }
    }
}
fn executor(audio: Arc<FakeAudio>, policy: Arc<dyn PolicyEngine>) -> Executor {
    let mut registry = ToolRegistry::new();
    for tool in AudioTool::all(audio) {
        registry.register(tool).unwrap();
    }
    Executor::new(
        registry,
        policy,
        Arc::new(MemoryAuditSink::default()),
        Arc::new(FakeDesktopPlatform::default()),
    )
}
#[test]
fn malformed_voice_requests_and_paths_never_reach_devices() {
    let audio = Arc::new(FakeAudio::default());
    let engine = executor(audio.clone(), Arc::new(DefaultPolicyEngine));
    for (name, args) in [
        ("speech_start", json!({"device_index":true})),
        ("speech_start", json!({"automatic":"yes"})),
        ("speech_poll", json!({"recording_id":"fake"})),
        ("speech_start", json!({"device_index":32})),
        ("speech_start", json!({"path":"C:\\record.wav"})),
        ("speech_finish", json!({"recording_id":"fake"})),
        (
            "speech_finish",
            json!({"recording_id":uuid::Uuid::new_v4().to_string(),"language":"shell"}),
        ),
        ("speech_stop", json!({"text":"unexpected"})),
        ("speech_speak", json!({"text":""})),
        ("speech_speak", json!({"text":"hello", "language":"auto"})),
        (
            "speech_speak",
            json!({"text":"hello", "output_device_index":32}),
        ),
        (
            "speech_speak",
            json!({"text":"hello", "output_device_index":true}),
        ),
        ("speech_speak", json!({"text":"a".repeat(1025)})),
        ("speech_status", Value::Null),
    ] {
        assert_eq!(
            engine
                .execute(ToolRequest::new(name, args, RequestSource::Brain))
                .status,
            ToolStatus::Failed
        );
    }
    assert_eq!(audio.0.load(Ordering::SeqCst), 0);
}
#[test]
fn voice_operations_use_the_normal_policy_boundary() {
    let audio = Arc::new(FakeAudio::default());
    let engine = executor(audio.clone(), Arc::new(Deny));
    for (name, args) in [
        ("speech_start", json!({"automatic":true})),
        (
            "speech_poll",
            json!({"recording_id":uuid::Uuid::new_v4().to_string()}),
        ),
    ] {
        assert_eq!(
            engine
                .execute(ToolRequest::new(name, args, RequestSource::Brain))
                .status,
            ToolStatus::Denied
        );
    }
    assert_eq!(audio.0.load(Ordering::SeqCst), 0);
    let engine = executor(audio.clone(), Arc::new(DefaultPolicyEngine));
    for (name, args) in [
        ("speech_start", json!({})),
        ("speech_start", json!({"automatic":true})),
        ("speech_poll", json!({})),
        (
            "speech_poll",
            json!({"recording_id":uuid::Uuid::new_v4().to_string()}),
        ),
        ("speech_speak", json!({"text":"Hello"})),
        (
            "speech_speak",
            json!({"text":"Merhaba", "language":"tr", "output_device_index":1}),
        ),
        ("speech_stop", json!({})),
    ] {
        assert_eq!(
            engine
                .execute(ToolRequest::new(name, args, RequestSource::Brain))
                .status,
            ToolStatus::Success
        );
    }
    assert_eq!(audio.0.load(Ordering::SeqCst), 7);
    assert_eq!(
        *audio.1.lock().unwrap(),
        Some(("Merhaba".into(), "tr".into(), Some(1)))
    );
}

#[test]
#[ignore = "explicit local model inference with the public Whisper example WAV"]
fn real_whisper_transcribes_public_fixture_without_device_access() {
    let path = std::env::var("JARVIS_SPEECH_FIXTURE").expect("Set the public fixture WAV path");
    let samples = read_fixture_pcm(&std::path::PathBuf::from(path));
    let started = std::time::Instant::now();
    let text = jarvis_core::audio::transcribe(&samples, "en").unwrap();
    println!(
        "Public fixture transcription in {:?}: {}",
        started.elapsed(),
        text
    );
    let normalized = text.to_lowercase();
    assert!(
        normalized.contains("ask not") && normalized.contains("country"),
        "{text}"
    );
}

fn read_fixture_pcm(path: &std::path::Path) -> Vec<f32> {
    let bytes = std::fs::read(path).unwrap();
    assert_eq!(&bytes[..4], b"RIFF");
    let mut cursor = 12;
    let mut samples = None;
    while cursor + 8 <= bytes.len() {
        let length = u32::from_le_bytes(bytes[cursor + 4..cursor + 8].try_into().unwrap()) as usize;
        let end = cursor + 8 + length;
        assert!(end <= bytes.len());
        match &bytes[cursor..cursor + 4] {
            b"fmt " => {
                assert_eq!(
                    u16::from_le_bytes(bytes[cursor + 8..cursor + 10].try_into().unwrap()),
                    1
                );
                assert_eq!(
                    u16::from_le_bytes(bytes[cursor + 10..cursor + 12].try_into().unwrap()),
                    1
                );
                assert_eq!(
                    u32::from_le_bytes(bytes[cursor + 12..cursor + 16].try_into().unwrap()),
                    16000
                );
                assert_eq!(
                    u16::from_le_bytes(bytes[cursor + 22..cursor + 24].try_into().unwrap()),
                    16
                );
            }
            b"data" => {
                samples = Some(
                    bytes[cursor + 8..end]
                        .chunks_exact(2)
                        .map(|x| i16::from_le_bytes([x[0], x[1]]) as f32 / 32768.)
                        .collect::<Vec<_>>(),
                )
            }
            _ => (),
        }
        cursor = end + (length % 2);
    }
    samples.unwrap()
}

#[test]
#[ignore = "explicit installed-voice synthetic English/Turkish round-trip; no microphone or agent"]
fn real_whisper_bilingual_roundtrip_preserves_language_and_negative_commands() {
    let root = std::path::PathBuf::from(
        std::env::var("JARVIS_SPEECH_ROUNDTRIP").expect("Generate synthetic fixtures first"),
    );
    let cases: Value =
        serde_json::from_slice(&std::fs::read(root.join("manifest.json")).unwrap()).unwrap();
    let mut failures = Vec::new();
    for case in cases.as_array().unwrap() {
        let samples = read_fixture_pcm(&root.join(case["file"].as_str().unwrap()));
        for language in [case["language"].as_str().unwrap(), "auto"] {
            let started = std::time::Instant::now();
            let text = jarvis_core::audio::transcribe(&samples, language).unwrap();
            println!(
                "Synthetic fixture {} / {} / {:?}: {}",
                case["file"],
                language,
                started.elapsed(),
                text
            );
            let normalized = text.to_lowercase();
            if !case["keywords"]
                .as_array()
                .unwrap()
                .iter()
                .all(|word| normalized.contains(word.as_str().unwrap()))
            {
                failures.push(format!("{} / {}: {}", case["file"], language, text));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}
