use super::{AudioService, failure, resample, turn::TurnDetector, vad};
use crate::core::JarvisError;
use cpal::{
    SizedSample,
    traits::{DeviceTrait, HostTrait, StreamTrait},
};
use serde_json::{Value, json};
use std::{
    collections::VecDeque,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU32, Ordering},
        mpsc::{self, Receiver, Sender},
    },
    time::{Duration, Instant},
};
use windows::Win32::System::Com::{COINIT_MULTITHREADED, CoInitializeEx, CoUninitialize};

struct Capture {
    id: String,
    done: Arc<AtomicBool>,
    progress: Arc<Mutex<Progress>>,
    stop: Sender<()>,
    result: Receiver<Result<(), JarvisError>>,
    samples: Arc<Mutex<Vec<f32>>>,
}
struct Progress {
    phase: &'static str,
    level: f32,
    xruns: u32,
    heartbeat: Instant,
    error: Option<String>,
}

enum SpeechCommand {
    Status(Sender<Result<Value, JarvisError>>),
    Inventory(Sender<Result<Value, JarvisError>>),
    Speak(
        String,
        String,
        Option<usize>,
        Sender<Result<Value, JarvisError>>,
    ),
    Stop(Sender<Result<(), JarvisError>>),
}

#[derive(Default)]
pub struct WindowsAudio {
    capture: Mutex<Option<Capture>>,
    speaker: Mutex<Option<Sender<SpeechCommand>>>,
}

impl WindowsAudio {
    fn speaker(&self) -> Result<Sender<SpeechCommand>, JarvisError> {
        let mut slot = self.speaker.lock().map_err(failure)?;
        if let Some(sender) = &*slot {
            return Ok(sender.clone());
        }
        let (tx, rx) = mpsc::channel();
        let (ready_tx, ready_rx) = mpsc::sync_channel(1);
        std::thread::Builder::new()
            .name("jarvis-speech-output".into())
            .spawn(move || {
                // COM objects never cross threads. Text is always plain text, never XML or a filename.
                let initialized = unsafe { CoInitializeEx(None, COINIT_MULTITHREADED).ok() };
                if let Err(error) = initialized {
                    let _ = ready_tx.send(Err(failure(error)));
                    return;
                }
                match super::sapi::Speaker::new() {
                    Err(error) => {
                        let _ = ready_tx.send(Err(error));
                    }
                    Ok(voice) => {
                        let _ = ready_tx.send(Ok(()));
                        while let Ok(command) = rx.recv() {
                            match command {
                                SpeechCommand::Status(reply) => {
                                    let _ = reply.send(voice.output_status());
                                }
                                SpeechCommand::Inventory(reply) => {
                                    let _ = reply.send(voice.inventory());
                                }
                                SpeechCommand::Speak(text, language, output, reply) => {
                                    let _ = reply.send(voice.speak(&text, &language, output));
                                }
                                SpeechCommand::Stop(reply) => {
                                    let _ = reply.send(voice.stop());
                                }
                            }
                        }
                        let _ = voice.stop();
                    }
                }
                unsafe {
                    CoUninitialize();
                }
            })
            .map_err(failure)?;
        ready_rx
            .recv_timeout(Duration::from_secs(10))
            .map_err(failure)??;
        *slot = Some(tx.clone());
        Ok(tx)
    }

    fn take(&self, id: &str) -> Result<Capture, JarvisError> {
        let mut slot = self.capture.lock().map_err(failure)?;
        if slot.as_ref().is_none_or(|c| c.id != id) {
            return Err(failure("Recording expired or belongs to another session"));
        }
        Ok(slot.take().unwrap())
    }
}

impl AudioService for WindowsAudio {
    fn status(&self) -> Result<Value, JarvisError> {
        let host = cpal::default_host();
        let devices: Vec<_> = host.input_devices().map_err(failure)?.take(32).enumerate().map(|(i,d)|
            json!({"index":i, "name":d.description().map(|x| x.name().to_owned()).unwrap_or_else(|_| "Microphone".into())})).collect();
        let recording = self
            .capture
            .lock()
            .map_err(failure)?
            .as_ref()
            .is_some_and(|c| !c.done.load(Ordering::Acquire));
        let mut status = json!({"devices":devices, "recording":recording,
            "model_available":super::transcribe::model_path().is_file(),
            "recognizer":"Whisper small / CPU", "speaker":"Windows local voice", "max_seconds":30});
        let inventory = (|| -> Result<Value, JarvisError> {
            let (tx, rx) = mpsc::channel();
            self.speaker()?
                .send(SpeechCommand::Inventory(tx))
                .map_err(failure)?;
            rx.recv_timeout(Duration::from_secs(10)).map_err(failure)?
        })();
        match inventory {
            Ok(data) => status
                .as_object_mut()
                .unwrap()
                .extend(data.as_object().unwrap().clone()),
            Err(error) => {
                status["output_error"] = json!(error.to_string());
            }
        }
        Ok(status)
    }

    fn start(&self, device: Option<usize>, automatic: bool) -> Result<Value, JarvisError> {
        if !super::transcribe::model_path().is_file() {
            return Err(failure("Provision the local Whisper model first"));
        }
        let mut slot = self.capture.lock().map_err(failure)?;
        if slot
            .as_ref()
            .is_some_and(|c| !c.done.load(Ordering::Acquire))
        {
            return Err(failure("A recording is already active"));
        }
        if let Some(old) = slot.take() {
            let _ = old.stop.send(());
        }
        self.stop()?; // Half duplex: never capture the assistant's own speech.
        let progress = Arc::new(Mutex::new(Progress {
            phase: if automatic { "waiting" } else { "listening" },
            level: 0.,
            xruns: 0,
            heartbeat: Instant::now(),
            error: None,
        }));
        let done = Arc::new(AtomicBool::new(false));
        let thread_progress = progress.clone();
        let thread_done = done.clone();
        let samples = Arc::new(Mutex::new(Vec::new()));
        let thread_samples = samples.clone();
        let (stop_tx, stop_rx) = mpsc::channel();
        let (result_tx, result_rx) = mpsc::channel();
        let (ready_tx, ready_rx) = mpsc::sync_channel(1);
        std::thread::Builder::new()
            .name("jarvis-microphone".into())
            .spawn(move || {
                let result = capture(
                    device,
                    automatic,
                    &stop_rx,
                    ready_tx,
                    thread_progress.clone(),
                );
                let result = result.and_then(|pcm| {
                    *thread_samples.lock().map_err(failure)? = pcm;
                    Ok(())
                });
                if let Ok(mut state) = thread_progress.lock() {
                    state.phase = if result.is_ok() { "complete" } else { "error" };
                    state.level = 0.;
                    state.error = result.as_ref().err().map(ToString::to_string);
                }
                thread_done.store(true, Ordering::Release);
                let _ = result_tx.send(result);
                // Expire even a completed utterance if its client disappears before finish.
                while Arc::strong_count(&thread_samples) > 1 {
                    let Ok(mut state) = thread_progress.lock() else {
                        break;
                    };
                    let Ok(mut pcm) = thread_samples.lock() else {
                        break;
                    };
                    if pcm.is_empty() {
                        break;
                    }
                    if state.heartbeat.elapsed() > Duration::from_secs(6) {
                        *pcm = Vec::new();
                        state.phase = "error";
                        state.error =
                            Some("Microphone client disconnected; recording discarded".into());
                        break;
                    }
                    drop(pcm);
                    drop(state);
                    if !matches!(
                        stop_rx.recv_timeout(Duration::from_millis(100)),
                        Err(mpsc::RecvTimeoutError::Timeout)
                    ) {
                        break;
                    }
                }
            })
            .map_err(failure)?;
        ready_rx
            .recv_timeout(Duration::from_secs(10))
            .map_err(failure)??;
        let id = uuid::Uuid::new_v4().to_string();
        *slot = Some(Capture {
            id: id.clone(),
            done,
            progress,
            stop: stop_tx,
            result: result_rx,
            samples,
        });
        Ok(json!({"recording_id":id, "max_seconds":30}))
    }

    fn poll(&self, id: Option<&str>) -> Result<Value, JarvisError> {
        let mut output = json!({"speaking":false,"output_phase":"idle"});
        if let Some(sender) = self.speaker.lock().map_err(failure)?.clone() {
            let (tx, rx) = mpsc::channel();
            sender.send(SpeechCommand::Status(tx)).map_err(failure)?;
            output = rx.recv_timeout(Duration::from_secs(2)).map_err(failure)??;
        }
        if let Some(id) = id {
            let slot = self.capture.lock().map_err(failure)?;
            let capture = slot
                .as_ref()
                .filter(|c| c.id == id)
                .ok_or_else(|| failure("Recording expired or belongs to another session"))?;
            let mut state = capture.progress.lock().map_err(failure)?;
            if state.heartbeat.elapsed() <= Duration::from_secs(6) {
                state.heartbeat = Instant::now();
            } else {
                *capture.samples.lock().map_err(failure)? = Vec::new();
                state.phase = "error";
                state.error = Some("Microphone client disconnected; recording discarded".into());
            }
            output["phase"] = json!(state.phase);
            output["level"] = json!(state.level);
            output["xruns"] = json!(state.xruns);
            output["error"] = json!(state.error);
        }
        Ok(output)
    }

    fn finish(&self, id: &str, language: &str) -> Result<Value, JarvisError> {
        let capture = self.take(id)?;
        let _ = capture.stop.send(());
        capture
            .result
            .recv_timeout(Duration::from_secs(10))
            .map_err(failure)??;
        {
            let state = capture.progress.lock().map_err(failure)?;
            if state.heartbeat.elapsed() > Duration::from_secs(6) || state.phase == "error" {
                return Err(failure("Recording expired; nothing sent"));
            }
        }
        let pcm = std::mem::take(&mut *capture.samples.lock().map_err(failure)?);
        let duration_ms = pcm.len() * 1000 / 16000;
        let (text, detected) = super::transcribe::recognize(&pcm, language)?;
        Ok(
            json!({"text":text, "language":detected, "duration_ms":duration_ms, "engine":"whisper-small-cpu"}),
        )
    }
    fn cancel(&self, id: &str) -> Result<Value, JarvisError> {
        let capture = self.take(id)?;
        let _ = capture.stop.send(());
        // Wait for stream teardown, never transcribe cancelled audio.
        let _discarded = capture
            .result
            .recv_timeout(Duration::from_secs(5))
            .map_err(failure)?;
        Ok(json!({"cancelled":true}))
    }
    fn speak(
        &self,
        text: &str,
        language: &str,
        output: Option<usize>,
    ) -> Result<Value, JarvisError> {
        if self
            .capture
            .lock()
            .map_err(failure)?
            .as_ref()
            .is_some_and(|c| !c.done.load(Ordering::Acquire))
        {
            return Err(failure("Speech output is muted while recording"));
        }
        let (tx, rx) = mpsc::channel();
        self.speaker()?
            .send(SpeechCommand::Speak(
                text.into(),
                language.into(),
                output,
                tx,
            ))
            .map_err(failure)?;
        rx.recv_timeout(Duration::from_secs(10)).map_err(failure)?
    }
    fn stop(&self) -> Result<Value, JarvisError> {
        let sender = self.speaker.lock().map_err(failure)?.clone();
        if let Some(sender) = sender {
            let (tx, rx) = mpsc::channel();
            sender.send(SpeechCommand::Stop(tx)).map_err(failure)?;
            rx.recv_timeout(Duration::from_secs(5)).map_err(failure)??;
        }
        Ok(json!({"stopped":true}))
    }
}

// Stream notifications are typed: isolated xruns do not terminate a healthy stream.
// Sustained loss rejects the utterance instead of sending potentially clipped commands.
fn recoverable(kind: cpal::ErrorKind) -> bool {
    matches!(
        kind,
        cpal::ErrorKind::Xrun | cpal::ErrorKind::DeviceChanged | cpal::ErrorKind::RealtimeDenied
    )
}

fn check_health(xruns: u32, dropped: bool) -> Result<(), JarvisError> {
    if dropped || xruns >= 8 {
        Err(failure(
            "Microphone lost too much audio. Try another input device or reduce system load; nothing was sent.",
        ))
    } else {
        Ok(())
    }
}

fn capture(
    device: Option<usize>,
    automatic: bool,
    stop: &Receiver<()>,
    ready: mpsc::SyncSender<Result<(), JarvisError>>,
    progress: Arc<Mutex<Progress>>,
) -> Result<Vec<f32>, JarvisError> {
    let start = || -> Result<_, JarvisError> {
        let host = cpal::default_host();
        let device = match device {
            Some(index) => host.input_devices().map_err(failure)?.nth(index),
            None => host.default_input_device(),
        }
        .ok_or_else(|| failure("Microphone unavailable. Check Windows microphone permissions."))?;
        let config = device.default_input_config().map_err(failure)?;
        let rate = config.sample_rate();
        let channels = usize::from(config.channels());
        if !(8000..=192000).contains(&rate) || channels == 0 || channels > 8 {
            return Err(failure("Unsupported microphone format"));
        }
        // Bounded callback queue. No mutex, inference, logging or IPC in the realtime callback.
        let (tx, rx) = mpsc::sync_channel::<Vec<f32>>(64);
        let (errors_tx, errors_rx) = mpsc::sync_channel::<String>(1);
        let xruns = Arc::new(AtomicU32::new(0));
        let dropped = Arc::new(AtomicBool::new(false));
        let stream = match config.sample_format() {
            cpal::SampleFormat::F32 => input::<f32>(
                &device,
                config.into(),
                tx,
                errors_tx,
                xruns.clone(),
                dropped.clone(),
                channels,
            ),
            cpal::SampleFormat::I16 => input::<i16>(
                &device,
                config.into(),
                tx,
                errors_tx,
                xruns.clone(),
                dropped.clone(),
                channels,
            ),
            cpal::SampleFormat::I32 => input::<i32>(
                &device,
                config.into(),
                tx,
                errors_tx,
                xruns.clone(),
                dropped.clone(),
                channels,
            ),
            cpal::SampleFormat::U16 => input::<u16>(
                &device,
                config.into(),
                tx,
                errors_tx,
                xruns.clone(),
                dropped.clone(),
                channels,
            ),
            _ => Err(failure("Unsupported microphone sample type")),
        }?;
        let detector = if automatic { Some(vad::load()?) } else { None };
        stream.play().map_err(failure)?;
        Ok((stream, rx, errors_rx, xruns, dropped, rate, detector))
    };
    let (stream, rx, errors, xruns, dropped, rate, mut detector) = match start() {
        Ok(value) => {
            let _ = ready.send(Ok(()));
            value
        }
        Err(error) => {
            let _ = ready.send(Err(error.clone()));
            return Err(error);
        }
    };
    let started = Instant::now();
    let mut timed_out = false;
    let mut pending = VecDeque::new();
    let mut window = VecDeque::new();
    let mut turn = TurnDetector::default();
    let mut manual = Vec::with_capacity(16000 * 30);
    let block = rate as usize / 10;
    loop {
        if let Ok(error) = errors.try_recv() {
            return Err(failure(error));
        }
        check_health(
            xruns.load(Ordering::Relaxed),
            dropped.load(Ordering::Relaxed),
        )?;
        if !matches!(stop.try_recv(), Err(mpsc::TryRecvError::Empty)) {
            break;
        }
        if progress.lock().map_err(failure)?.heartbeat.elapsed() > Duration::from_secs(6) {
            return Err(failure(
                "Microphone client disconnected; recording discarded",
            ));
        }
        if !automatic && started.elapsed() > Duration::from_secs(30) {
            timed_out = true;
            break;
        }
        match rx.recv_timeout(Duration::from_millis(100)) {
            Ok(samples) => pending.extend(samples),
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(_) => return Err(failure("Microphone stream stopped unexpectedly")),
        }
        while pending.len() >= block {
            let native: Vec<_> = pending.drain(..block).collect();
            let frame = resample(&native, rate);
            if frame.iter().any(|sample| !sample.is_finite()) {
                return Err(failure(
                    "Microphone returned invalid audio; recording discarded",
                ));
            }
            let level =
                (frame.iter().map(|s| s * s).sum::<f32>() / frame.len().max(1) as f32).sqrt();
            if let Some(model) = detector.as_mut() {
                window.extend(frame.iter().copied());
                while window.len() > 15360 {
                    window.pop_front();
                }
                let contiguous = window.make_contiguous();
                let probability = vad::probability(model, contiguous)?;
                turn.push(&frame, probability >= 0.5);
            } else {
                let remaining = (16000 * 30_usize).saturating_sub(manual.len());
                manual.extend(frame.iter().take(remaining));
            }
            let mut state = progress.lock().map_err(failure)?;
            state.phase = if !automatic || turn.listening {
                "listening"
            } else {
                "waiting"
            };
            state.level = (level * 8.).clamp(0., 1.);
            state.xruns = xruns.load(Ordering::Relaxed);
            if turn.complete || manual.len() >= 16000 * 30 {
                break;
            }
        }
        if turn.complete || manual.len() >= 16000 * 30 {
            break;
        }
    }
    drop(stream);
    if let Ok(error) = errors.try_recv() {
        return Err(failure(error));
    }
    check_health(
        xruns.load(Ordering::Relaxed),
        dropped.load(Ordering::Relaxed),
    )?;
    if turn.truncated || timed_out || manual.len() >= 16000 * 30 {
        return Err(failure(
            "Speech exceeded 30 seconds. Nothing sent; please use a shorter turn.",
        ));
    }
    if automatic {
        // A stop/idle limit must never send a partial automatically detected utterance.
        Ok(if turn.complete {
            turn.samples
        } else {
            Vec::new()
        })
    } else {
        for queued in rx.try_iter() {
            pending.extend(queued);
        }
        let tail: Vec<_> = pending.drain(..).collect();
        manual.extend(resample(&tail, rate));
        if manual.len() >= 16000 * 30 {
            return Err(failure("Recording limit reached; nothing sent"));
        }
        Ok(manual)
    }
}

fn input<T>(
    device: &cpal::Device,
    config: cpal::StreamConfig,
    pcm: mpsc::SyncSender<Vec<f32>>,
    error: mpsc::SyncSender<String>,
    xruns: Arc<AtomicU32>,
    dropped: Arc<AtomicBool>,
    channels: usize,
) -> Result<cpal::Stream, JarvisError>
where
    T: SizedSample,
    f32: cpal::FromSample<T>,
{
    device
        .build_input_stream(
            config,
            move |data: &[T], _| {
                for chunk in data.chunks(channels * 2048) {
                    let samples = chunk
                        .chunks_exact(channels)
                        .map(|frame| {
                            frame.iter().map(|s| s.to_sample::<f32>()).sum::<f32>()
                                / channels as f32
                        })
                        .collect();
                    if pcm.try_send(samples).is_err() {
                        dropped.store(true, Ordering::Relaxed);
                    }
                }
            },
            move |cause| {
                if cause.kind() == cpal::ErrorKind::Xrun {
                    xruns.fetch_add(1, Ordering::Relaxed);
                }
                if !recoverable(cause.kind()) {
                    let _ = error.try_send(cause.to_string());
                }
            },
            Some(Duration::from_secs(5)),
        )
        .map_err(failure)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn isolated_xrun_is_accepted_but_sustained_or_internal_audio_loss_is_rejected() {
        assert!(check_health(0, false).is_ok());
        assert!(check_health(1, false).is_ok());
        assert!(check_health(8, false).is_err());
        assert!(check_health(0, true).is_err());
    }
    #[test]
    fn transient_notifications_are_separate_from_device_failure() {
        assert!(recoverable(cpal::ErrorKind::Xrun));
        assert!(recoverable(cpal::ErrorKind::DeviceChanged));
        assert!(recoverable(cpal::ErrorKind::RealtimeDenied));
        for kind in [
            cpal::ErrorKind::DeviceNotAvailable,
            cpal::ErrorKind::PermissionDenied,
            cpal::ErrorKind::StreamInvalidated,
            cpal::ErrorKind::BackendError,
            cpal::ErrorKind::Other,
        ] {
            assert!(!recoverable(kind));
        }
    }
}
