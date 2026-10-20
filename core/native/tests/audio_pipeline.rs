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
struct FakeAudio(
    AtomicUsize,
    Mutex<Option<(String, String, Option<usize>)>>,
    Mutex<Option<String>>,
    Mutex<Option<(Option<usize>, Option<usize>)>>,
);
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
    fn start_interruptible(
        &self,
        device: Option<usize>,
        output: Option<usize>,
    ) -> Result<Value, JarvisError> {
        *self.3.lock().unwrap() = Some((device, output));
        self.response()
    }
    fn poll(&self, _: Option<&str>) -> Result<Value, JarvisError> {
        self.response()
    }
    fn finish(&self, _: &str, _: &str, vocabulary: &str) -> Result<Value, JarvisError> {
        *self.2.lock().unwrap() = Some(vocabulary.to_owned());
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
    for tool in AudioTool::all(audio, None) {
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
        ("speech_start", json!({"automatic":true,"barge_in":"yes"})),
        ("speech_start", json!({"barge_in":true})),
        ("speech_start", json!({"automatic":false,"barge_in":true})),
        ("speech_start", json!({"output_device_index":0})),
        (
            "speech_start",
            json!({"automatic":true,"barge_in":true,"output_device_index":32}),
        ),
        ("speech_poll", json!({"recording_id":"fake"})),
        ("speech_start", json!({"device_index":32})),
        ("speech_start", json!({"path":"C:\\record.wav"})),
        ("speech_finish", json!({"recording_id":"fake"})),
        (
            "speech_finish",
            json!({"recording_id":uuid::Uuid::new_v4().to_string(),"vocabulary":"caller hints forbidden"}),
        ),
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
#[ignore = "real microphone and speaker AEC-only test; pause wake, no desktop, quiet room; no recordings or agent actions"]
fn real_echo_source_keeps_own_speech_out_of_a_turn() {
    use std::time::{Duration, Instant};
    let mut registry = ToolRegistry::new();
    for tool in AudioTool::all(jarvis_core::audio::current_service(), None) {
        registry.register(tool).unwrap();
    }
    let engine = Executor::new(
        registry,
        Arc::new(DefaultPolicyEngine),
        Arc::new(MemoryAuditSink::default()),
        Arc::new(FakeDesktopPlatform::default()),
    );
    let call = |name: &str, args: Value| {
        let result = engine.execute(ToolRequest::new(name, args, RequestSource::Internal));
        assert_eq!(result.status, ToolStatus::Success, "{name}: {result:?}");
        result.data
    };
    let start = call("speech_start", json!({"automatic":true,"barge_in":true}));
    assert_eq!(start["echo_cancelled"], true);
    let id = start["recording_id"].as_str().unwrap();
    call(
        "speech_speak",
        json!({"text":"Bu bir yankı giderme denemesi. Jarvis konuşurken kendi sesini yeni bir istek olarak algılamamalı. Bu denemede hiçbir uygulama açılmayacak.","language":"tr"}),
    );
    let began = Instant::now();
    let mut polls = 0;
    let mut interrupted = false;
    let mut max_level = 0_f64;
    let mut phases = std::collections::BTreeSet::new();
    while began.elapsed() < Duration::from_secs(9) {
        std::thread::sleep(Duration::from_millis(100));
        let status = call("speech_poll", json!({"recording_id":id}));
        assert!(status["error"].is_null(), "{status:?}");
        interrupted |= status["interrupted"] == true;
        phases.insert(status["phase"].as_str().unwrap().to_owned());
        max_level = max_level.max(status["level"].as_f64().unwrap_or(0.));
        polls += 1;
    }
    call("speech_stop", json!({}));
    call("speech_cancel", json!({"recording_id":id}));
    println!(
        "AEC source polls={polls}, phases={phases:?}, max_clean_level={max_level:.4}, interrupted={interrupted}; no transcript or dispatch"
    );
    assert!(
        !interrupted,
        "Own speaker output or room speech triggered a turn; investigate acoustics before acceptance"
    );
    assert_eq!(phases, ["waiting".to_owned()].into());
}
#[test]
fn voice_operations_use_the_normal_policy_boundary() {
    let audio = Arc::new(FakeAudio::default());
    let engine = executor(audio.clone(), Arc::new(Deny));
    for (name, args) in [
        ("speech_start", json!({"automatic":true})),
        ("speech_start", json!({"automatic":true,"barge_in":true})),
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
fn interruptible_capture_binds_native_input_and_render_only_after_policy() {
    let audio = Arc::new(FakeAudio::default());
    let args = json!({"automatic":true,"barge_in":true,"device_index":2,"output_device_index":1});
    let denied = executor(audio.clone(), Arc::new(Deny)).execute(ToolRequest::new(
        "speech_start",
        args.clone(),
        RequestSource::Brain,
    ));
    assert_eq!(denied.status, ToolStatus::Denied);
    assert_eq!(*audio.3.lock().unwrap(), None);
    let allowed = executor(audio.clone(), Arc::new(DefaultPolicyEngine)).execute(ToolRequest::new(
        "speech_start",
        args,
        RequestSource::Brain,
    ));
    assert_eq!(allowed.status, ToolStatus::Success);
    assert_eq!(*audio.3.lock().unwrap(), Some((Some(2), Some(1))));
    assert_eq!(audio.0.load(Ordering::SeqCst), 1);
}

#[test]
fn recognition_spelling_context_comes_from_native_catalog_after_policy() {
    use jarvis_core::apps::{
        ApplicationCatalog, ApplicationSource, DiscoveredApplication, TrustedLaunchTarget,
        fake::FakeApplicationDiscovery,
    };
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("fixture.exe");
    std::fs::write(&path, b"fixture").unwrap();
    let app = DiscoveredApplication::new(
        ApplicationSource::AdministrativeOverride,
        "fixture",
        "Nebula Painter",
        Vec::new(),
        None,
        TrustedLaunchTarget::Executable {
            path,
            arguments: Vec::new(),
        },
    )
    .unwrap();
    let catalog = Arc::new(ApplicationCatalog::new(
        Arc::new(FakeApplicationDiscovery::succeeding(vec![app])),
        jarvis_core::config::ApplicationPreferences::default(),
    ));
    catalog.refresh().unwrap();
    let audio = Arc::new(FakeAudio::default());
    let mut registry = ToolRegistry::new();
    for tool in AudioTool::all(audio.clone(), Some(catalog)) {
        registry.register(tool).unwrap();
    }
    let engine = Executor::new(
        registry,
        Arc::new(DefaultPolicyEngine),
        Arc::new(MemoryAuditSink::default()),
        Arc::new(FakeDesktopPlatform::default()),
    );
    let response = engine.execute(ToolRequest::new(
        "speech_finish",
        json!({"recording_id":uuid::Uuid::new_v4().to_string()}),
        RequestSource::Brain,
    ));
    assert_eq!(response.status, ToolStatus::Success);
    assert_eq!(
        audio.2.lock().unwrap().as_deref(),
        Some("JARVIS, Nebula Painter")
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

#[test]
#[ignore = "explicit native Handy-provider bilingual inference; synthetic fixtures, no microphone or agent"]
fn real_handy_provider_transcribes_bilingual_and_auto_language() {
    let root = std::path::PathBuf::from(std::env::var("JARVIS_ASR_EVAL").unwrap());
    for (file, language, expected) in [
        ("3.wav", "tr", "tabloyu"),
        ("7.wav", "en", "spreadsheet"),
        ("1.wav", "auto", "merhaba"),
    ] {
        let samples = read_fixture_pcm(&root.join(file));
        let started = std::time::Instant::now();
        let text =
            jarvis_core::audio::transcribe_with_vocabulary(&samples, language, "JARVIS").unwrap();
        println!("{language} {file} {:?}: {text}", started.elapsed());
        assert!(text.to_lowercase().contains(expected), "{text}");
    }
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

#[test]
#[ignore = "explicit model/decoder comparison on synthetic fixtures, never microphone or agent"]
fn real_whisper_quality_comparison() {
    let root =
        std::path::PathBuf::from(std::env::var("JARVIS_ASR_EVAL").expect("Set fixture root"));
    let cases: Value =
        serde_json::from_slice(&std::fs::read(root.join("manifest.json")).unwrap()).unwrap();
    let mut rows = Vec::new();
    let mut failures = Vec::new();
    for case in cases.as_array().unwrap() {
        if let Ok(selection) = std::env::var("JARVIS_ASR_EVAL_FILES")
            && !selection
                .split(',')
                .any(|file| Some(file) == case["file"].as_str())
        {
            continue;
        }
        let original = read_fixture_pcm(&root.join(case["file"].as_str().unwrap()));
        for variant in ["clean", "quiet_noise"] {
            let mut random = 1949_u32;
            let samples: Vec<f32> = original
                .iter()
                .map(|sample| {
                    if variant == "clean" {
                        return *sample;
                    }
                    random = random.wrapping_mul(1664525).wrapping_add(1013904223);
                    sample * 0.12 + (random as f32 / u32::MAX as f32 * 2.0 - 1.0) * 0.003
                })
                .collect();
            let started = std::time::Instant::now();
            let language = std::env::var("JARVIS_ASR_EVAL_LANGUAGE")
                .unwrap_or_else(|_| case["language"].as_str().unwrap().into());
            let vocabulary = if std::env::var("JARVIS_ASR_EVAL_HINTS").as_deref() == Ok("1") {
                jarvis_core::audio::recognition_vocabulary(
                    [
                        "Steam", "Firefox", "Notepad", "Obsidian", "Spotify", "Chrome",
                    ]
                    .map(str::to_owned),
                )
            } else {
                String::new()
            };
            let text =
                jarvis_core::audio::transcribe_with_vocabulary(&samples, &language, &vocabulary)
                    .unwrap();
            let normalized = normalize_words(&text);
            let missing: Vec<_> = case["keywords"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|word| {
                    !format!(" {normalized} ")
                        .contains(&format!(" {} ", normalize_words(word.as_str().unwrap())))
                })
                .cloned()
                .collect();
            if !missing.is_empty() {
                failures.push(format!("{} {variant}: {text}", case["file"]));
            }
            let reference = normalize_words(case["text"].as_str().unwrap());
            rows.push(
                json!({"file":case["file"],"variant":variant,"language":language,
                "text":text,"reference":case["text"],"missing":missing,
                "word_errors":word_distance(&reference,&normalized),
                "reference_words":reference.split_whitespace().count(),
                "seconds":started.elapsed().as_secs_f64()}),
            );
            println!(
                "ASR_PROGRESS {} {variant} {:.2}s",
                case["file"],
                started.elapsed().as_secs_f64()
            );
        }
    }
    assert!(!rows.is_empty(), "No evaluation cases selected");
    println!(
        "ASR_EVAL {}",
        json!({"recognizer":jarvis_core::audio::recognizer_label().unwrap(),
                "legacy_decoder_override":std::env::var("JARVIS_WHISPER_DECODER").ok(),
                "hints":std::env::var("JARVIS_ASR_EVAL_HINTS").as_deref()==Ok("1"),"rows":rows})
    );
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}

fn normalize_words(text: &str) -> String {
    text.to_lowercase()
        .replace(['ı', 'İ'], "i")
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { ' ' })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn word_distance(reference: &str, hypothesis: &str) -> usize {
    let actual: Vec<_> = hypothesis.split_whitespace().collect();
    let mut previous: Vec<usize> = (0..=actual.len()).collect();
    for (row, expected) in reference.split_whitespace().enumerate() {
        let mut current = vec![row + 1; actual.len() + 1];
        for (column, observed) in actual.iter().enumerate() {
            current[column + 1] = (current[column] + 1)
                .min(previous[column + 1] + 1)
                .min(previous[column] + usize::from(expected != *observed));
        }
        previous = current;
    }
    previous[actual.len()]
}

#[test]
fn word_error_metric_counts_missing_negation_and_name_substitution() {
    assert_eq!(word_distance("do not open steam", "do open steam"), 1);
    assert_eq!(
        word_distance("merhaba jarvis nasilsin", "merhaba javi nasilsin"),
        1
    );
    assert_eq!(word_distance("", "invented words"), 2);
}

#[test]
#[ignore = "explicit local ASR noise controls with spelling context; no device or agent"]
fn real_whisper_spelling_context_does_not_create_words_from_noise() {
    let vocabulary = jarvis_core::audio::recognition_vocabulary(
        ["Nebula Painter", "Steam", "Firefox"].map(str::to_owned),
    );
    for amplitude in [0.0_f32, 0.001, 0.01, 0.1] {
        let mut random = 1777_u32;
        let noise: Vec<_> = (0..32000)
            .map(|_| {
                random = random.wrapping_mul(1664525).wrapping_add(1013904223);
                (random as f32 / u32::MAX as f32 * 2.0 - 1.0) * amplitude
            })
            .collect();
        let text =
            jarvis_core::audio::transcribe_with_vocabulary(&noise, "tr", &vocabulary).unwrap();
        assert!(text.is_empty(), "Noise {amplitude} created text: {text}");
    }
}
