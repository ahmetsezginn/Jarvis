use crate::{
    audio::Capture,
    detector::Detector,
    launcher::{self, Task},
    state::Gate,
};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{
        atomic::Ordering,
        mpsc::{Receiver, RecvTimeoutError},
    },
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use windows_service::service::ServiceState;
use windows_service::service_control_handler::ServiceStatusHandle;
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
pub const SERVICE: &str = "JarvisWake";
pub enum Control {
    Stop,
    Pause,
    Continue,
    Activate,
}
#[derive(Serialize)]
pub struct Report {
    schema: u32,
    pid: u32,
    updated_unix_ms: u128,
    phase: &'static str,
    owner_active: bool,
    desktop_running: bool,
    microphone_open: bool,
    wake_count: u64,
    discontinuities: u64,
    error: Option<String>,
    private_bytes: usize,
    working_set_bytes: usize,
    cpu_time_100ns: u64,
    input_peak: f32,
    wake_score: f32,
    input_name: Option<String>,
}
pub fn report_path() -> PathBuf {
    PathBuf::from(std::env::var_os("ProgramData").unwrap_or_else(|| "C:\\ProgramData".into()))
        .join("JARVIS/Wake/status.json")
}
fn publish(report: &mut Report) -> Result<()> {
    use windows_sys::Win32::{
        Foundation::FILETIME,
        System::{
            ProcessStatus::{GetProcessMemoryInfo, PROCESS_MEMORY_COUNTERS_EX},
            Threading::{GetCurrentProcess, GetProcessTimes},
        },
    };
    unsafe {
        let process = GetCurrentProcess();
        let mut memory = PROCESS_MEMORY_COUNTERS_EX::default();
        if GetProcessMemoryInfo(
            process,
            (&mut memory as *mut PROCESS_MEMORY_COUNTERS_EX).cast(),
            std::mem::size_of_val(&memory) as u32,
        ) != 0
        {
            report.private_bytes = memory.PrivateUsage;
            report.working_set_bytes = memory.WorkingSetSize;
        }
        let mut times = [FILETIME::default(); 4];
        let [creation, exit, kernel, user] = &mut times;
        if GetProcessTimes(process, creation, exit, kernel, user) != 0 {
            report.cpu_time_100ns = times[2..]
                .iter()
                .map(|time| (time.dwHighDateTime as u64) << 32 | time.dwLowDateTime as u64)
                .sum();
        }
    }
    report.updated_unix_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    std::fs::write(report_path(), serde_json::to_vec_pretty(report)?)?;
    Ok(())
}
pub fn run(controls: Receiver<Control>, handle: &ServiceStatusHandle) -> Result<()> {
    let config = launcher::config()?;
    let runtime = launcher::install_root()?.join("runtime");
    let mut task: Option<Task> = None;
    let mut engine: Option<(Capture, Detector, Instant)> = None;
    let mut paused = false;
    let mut next_attempt = Instant::now();
    let mut gate = Gate::new(Instant::now());
    let mut report = Report {
        schema: 1,
        pid: std::process::id(),
        updated_unix_ms: 0,
        phase: "starting",
        owner_active: false,
        desktop_running: false,
        microphone_open: false,
        wake_count: 0,
        discontinuities: 0,
        error: None,
        private_bytes: 0,
        working_set_bytes: 0,
        cpu_time_100ns: 0,
        input_peak: 0.0,
        wake_score: 0.0,
        input_name: None,
    };
    let mut last_publish = Instant::now() - Duration::from_secs(2);
    let mut last_route_check = Instant::now();
    loop {
        let mut requested = false;
        match controls.recv_timeout(Duration::from_millis(50)) {
            Ok(Control::Stop) | Err(RecvTimeoutError::Disconnected) => break,
            Ok(Control::Pause) => {
                paused = true;
                crate::windows::status(handle, ServiceState::Paused, 0)?;
            }
            Ok(Control::Continue) => {
                paused = false;
                crate::windows::status(handle, ServiceState::Running, 0)?;
            }
            Ok(Control::Activate) => requested = true,
            Err(RecvTimeoutError::Timeout) => {}
        }
        report.owner_active = launcher::owner_active(&config);
        if task.is_none() && Instant::now() >= next_attempt {
            match Task::connect() {
                Ok(connected) => {
                    task = Some(connected);
                    report.error = None;
                }
                Err(error) => {
                    report.error = Some(error.to_string());
                    next_attempt = Instant::now() + Duration::from_secs(5);
                }
            }
        }
        report.desktop_running = false;
        let task_ready = match &task {
            Some(task) => match task.running() {
                Ok(running) => {
                    report.desktop_running = running;
                    true
                }
                Err(error) => {
                    report.error = Some(error.to_string());
                    false
                }
            },
            None => false,
        };
        if !task_ready && task.is_some() {
            task = None;
            next_attempt = Instant::now() + Duration::from_secs(5);
        }
        if requested && report.owner_active && task_ready && !report.desktop_running {
            engine = None;
            if let Some(task) = &task {
                match task.activate() {
                    Ok(()) => report.error = None,
                    Err(error) => report.error = Some(error.to_string()),
                }
            }
            // Task Scheduler updates the task state asynchronously. Do not re-open
            // the microphone in the gap before the first running-state observation.
            next_attempt = Instant::now() + Duration::from_secs(3);
        }
        let should_listen = !paused && report.owner_active && task_ready && !report.desktop_running;
        if !should_listen {
            engine = None;
            report.phase = if paused {
                "paused"
            } else if !report.owner_active {
                "no_unlocked_owner"
            } else if report.desktop_running {
                "assistant_running"
            } else {
                "launch_unavailable"
            };
        } else {
            if last_route_check.elapsed() >= Duration::from_secs(1) {
                last_route_check = Instant::now();
                if engine
                    .as_ref()
                    .is_some_and(|(capture, _, _)| capture.default_changed())
                {
                    // Drop old PCM/features before reopening the new Windows default.
                    engine = None;
                    next_attempt = Instant::now();
                }
            }
            if engine.is_none() && Instant::now() >= next_attempt {
                let opened = (|| -> Result<_> {
                    let detector = Detector::open(&runtime)?;
                    Ok((
                        Capture::open(config.microphone.as_deref())?,
                        detector,
                        Instant::now(),
                    ))
                })();
                match opened {
                    Ok(opened) => {
                        engine = Some(opened);
                        report.error = None;
                        report.discontinuities = 0;
                    }
                    Err(error) => {
                        report.error = Some(error.to_string());
                        next_attempt = Instant::now() + Duration::from_secs(5);
                    }
                }
            }
            let outcome = (|| -> Result<bool> {
                let Some((capture, detector, armed)) = &mut engine else {
                    return Ok(false);
                };
                if let Some(error) = capture
                    .fault
                    .lock()
                    .map_err(|_| "Audio status lock poisoned")?
                    .as_ref()
                {
                    return Err(error.clone().into());
                }
                let gaps = capture.discontinuities.load(Ordering::Relaxed);
                if gaps != report.discontinuities || armed.elapsed() > Duration::from_secs(30) {
                    // Never join words across lost audio or unbounded utterance history.
                    for _ in capture.frames.try_iter().take(8) {}
                    detector.reset()?;
                    *armed = Instant::now();
                    report.discontinuities = gaps;
                }
                for frame in capture.frames.try_iter().take(8) {
                    let detected = detector.feed(&frame)?;
                    report.wake_score = report.wake_score.max(detector.score());
                    if detected {
                        return Ok(true);
                    }
                }
                Ok(false)
            })();
            match outcome {
                Ok(true)
                    if gate.allow(
                        Instant::now(),
                        report.owner_active,
                        report.desktop_running,
                        true,
                    ) =>
                {
                    engine = None; // Release WASAPI and queued PCM BEFORE starting the app.
                    if let Some(task) = &task {
                        match task.activate() {
                            Ok(()) => {
                                report.wake_count += 1;
                                report.error = None;
                            }
                            Err(error) => report.error = Some(error.to_string()),
                        }
                    }
                    next_attempt = Instant::now() + Duration::from_secs(3);
                    report.phase = "activating";
                }
                Err(error) => {
                    engine = None;
                    report.error = Some(error.to_string());
                    next_attempt = Instant::now() + Duration::from_secs(5);
                    report.phase = "retrying";
                }
                Ok(true) => {
                    // A rejected detection is consumed, never replayed after cooldown.
                    if let Some((capture, detector, _)) = &mut engine {
                        for _ in capture.frames.try_iter().take(8) {}
                        detector.reset()?;
                    }
                    report.phase = "cooldown";
                }
                _ => {
                    report.phase = if engine.is_some() {
                        "listening"
                    } else {
                        "retrying"
                    }
                }
            }
        }
        report.microphone_open = engine.is_some();
        report.input_name = engine
            .as_ref()
            .map(|(capture, _, _)| capture.input_name.clone());
        if last_publish.elapsed() >= Duration::from_secs(1) {
            report.input_peak = engine
                .as_ref()
                .map(|(capture, _, _)| f32::from_bits(capture.peak.swap(0, Ordering::Relaxed)))
                .unwrap_or(0.0);
            publish(&mut report)?;
            report.wake_score = 0.0;
            last_publish = Instant::now();
        }
    }
    drop(engine);
    report.microphone_open = false;
    report.phase = "stopped";
    publish(&mut report)
}
