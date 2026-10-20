use cpal::{
    SizedSample,
    traits::{DeviceTrait, HostTrait, StreamTrait},
};
use serde::Serialize;
use std::{
    ffi::OsString,
    path::PathBuf,
    sync::{Arc, Mutex, mpsc},
    time::{Duration, Instant},
};
use windows_service::{
    define_windows_service,
    service::{
        ServiceControl, ServiceControlAccept, ServiceExitCode, ServiceState, ServiceStatus,
        ServiceType,
    },
    service_control_handler::{self, ServiceControlHandlerResult},
    service_dispatcher,
};

const PROBE_SERVICE: &str = "JarvisWakeProbe";
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Clone, Default, Serialize)]
struct Probe {
    schema: u32,
    microphone_opened: bool,
    callback_count: u64,
    sample_count: u64,
    sample_rate: u32,
    channels: u16,
    input_name: String,
    error: Option<String>,
    underruns: u64,
    elapsed_ms: u128,
    service_context: bool,
}

pub fn run() -> Result<()> {
    match std::env::args().nth(1).as_deref() {
        Some("service") => {
            service_dispatcher::start(crate::runtime::SERVICE, ffi_service_main).map_err(Into::into)
        }
        Some("desktop") => crate::launcher::desktop(),
        Some("open") => {
            let config = crate::launcher::config()?;
            if !crate::launcher::owner_active(&config) {
                return Err("Installed owner has no unlocked active session".into());
            }
            crate::launcher::request_activation()
        }
        Some("service-probe") => {
            service_dispatcher::start(PROBE_SERVICE, ffi_probe_main).map_err(Into::into)
        }
        Some("probe-console") => {
            let (tx, rx) = mpsc::channel();
            let result = probe(Duration::from_secs(3), &rx, false);
            drop(tx);
            println!("{}", serde_json::to_string_pretty(&result)?);
            if result.microphone_opened && result.callback_count > 0 {
                Ok(())
            } else {
                Err("Microphone probe failed".into())
            }
        }
        _ => Err("Use service, desktop, open, probe-console or service-probe".into()),
    }
}
define_windows_service!(ffi_probe_main, probe_main);
fn probe_main(_: Vec<OsString>) {
    if let Err(error) = run_probe_service() {
        let _ = save_report(&Probe {
            schema: 1,
            service_context: true,
            error: Some(error.to_string()),
            ..Probe::default()
        });
    }
}
pub(crate) fn status(
    handle: &service_control_handler::ServiceStatusHandle,
    state: ServiceState,
    code: u32,
) -> Result<()> {
    handle.set_service_status(ServiceStatus {
        service_type: ServiceType::OWN_PROCESS,
        current_state: state,
        controls_accepted: if matches!(state, ServiceState::Running | ServiceState::Paused) {
            ServiceControlAccept::STOP
                | ServiceControlAccept::SHUTDOWN
                | ServiceControlAccept::PAUSE_CONTINUE
        } else {
            ServiceControlAccept::empty()
        },
        exit_code: ServiceExitCode::Win32(code),
        checkpoint: 0,
        wait_hint: Duration::default(),
        process_id: None,
    })?;
    Ok(())
}
define_windows_service!(ffi_service_main, service_main);
fn service_main(_: Vec<OsString>) {
    let _ = serve();
}
fn serve() -> Result<()> {
    use crate::runtime::Control;
    let (tx, rx) = mpsc::channel();
    let handle = service_control_handler::register(crate::runtime::SERVICE, move |control| {
        let event = match control {
            ServiceControl::Stop | ServiceControl::Shutdown => Control::Stop,
            ServiceControl::Pause => Control::Pause,
            ServiceControl::Continue => Control::Continue,
            ServiceControl::UserEvent(code) if code.to_raw() == 128 => Control::Activate,
            ServiceControl::Interrogate => return ServiceControlHandlerResult::NoError,
            _ => return ServiceControlHandlerResult::NotImplemented,
        };
        let _ = tx.send(event);
        ServiceControlHandlerResult::NoError
    })?;
    status(&handle, ServiceState::Running, 0)?;
    let outcome = crate::runtime::run(rx, &handle);
    if let Err(error) = &outcome {
        let report = serde_json::json!({"schema":1,"pid":std::process::id(),"phase":"failed","microphone_open":false,"error":error.to_string()});
        let _ = std::fs::write(
            crate::runtime::report_path(),
            serde_json::to_vec_pretty(&report)?,
        );
    }
    status(
        &handle,
        ServiceState::Stopped,
        if outcome.is_ok() { 0 } else { 1 },
    )?;
    outcome
}
fn run_probe_service() -> Result<()> {
    let (stop, rx) = mpsc::channel();
    let handle = service_control_handler::register(PROBE_SERVICE, move |event| match event {
        ServiceControl::Stop | ServiceControl::Shutdown => {
            let _ = stop.send(());
            ServiceControlHandlerResult::NoError
        }
        ServiceControl::Interrogate => ServiceControlHandlerResult::NoError,
        _ => ServiceControlHandlerResult::NotImplemented,
    })?;
    status(&handle, ServiceState::Running, 0)?;
    let result = probe(Duration::from_secs(3), &rx, true);
    let saved = save_report(&result);
    let success = result.microphone_opened && result.callback_count > 0 && saved.is_ok();
    status(&handle, ServiceState::Stopped, if success { 0 } else { 1 })?;
    saved
}
fn report_path() -> PathBuf {
    PathBuf::from(std::env::var_os("ProgramData").unwrap_or_else(|| "C:\\ProgramData".into()))
        .join("JARVIS/wake-probe/report.json")
}
fn save_report(report: &Probe) -> Result<()> {
    let path = report_path();
    std::fs::write(path, serde_json::to_vec_pretty(report)?)?;
    Ok(())
}

fn stream<T: SizedSample>(
    device: &cpal::Device,
    config: &cpal::StreamConfig,
    state: Arc<Mutex<Probe>>,
) -> Result<cpal::Stream> {
    let errors = state.clone();
    Ok(device.build_input_stream(
        *config,
        move |samples: &[T], _| {
            // No saved PCM and no decoding: report only bounded signal-independent counters.
            if let Ok(mut report) = state.try_lock() {
                report.callback_count += 1;
                report.sample_count += samples.len() as u64;
            }
        },
        move |error| {
            if let Ok(mut report) = errors.lock() {
                if error.kind() == cpal::ErrorKind::Xrun {
                    report.underruns += 1;
                } else {
                    report.error = Some(error.to_string());
                }
            }
        },
        None,
    )?)
}
fn probe(duration: Duration, stop: &mpsc::Receiver<()>, service_context: bool) -> Probe {
    let state = Arc::new(Mutex::new(Probe {
        schema: 1,
        service_context,
        ..Probe::default()
    }));
    let started = Instant::now();
    let operation = (|| -> Result<()> {
        let host = cpal::default_host();
        let device = host
            .default_input_device()
            .ok_or("No default microphone in this Windows context")?;
        let format = device.default_input_config()?;
        {
            let mut report = state.lock().unwrap();
            report.sample_rate = format.sample_rate();
            report.channels = format.channels();
            report.input_name = device.description()?.name().to_owned();
        }
        let config = format.config();
        let input = match format.sample_format() {
            cpal::SampleFormat::F32 => stream::<f32>(&device, &config, state.clone())?,
            cpal::SampleFormat::I16 => stream::<i16>(&device, &config, state.clone())?,
            cpal::SampleFormat::U16 => stream::<u16>(&device, &config, state.clone())?,
            _ => return Err("Unsupported microphone format".into()),
        };
        input.play()?;
        state.lock().unwrap().microphone_opened = true;
        let _ = stop.recv_timeout(duration);
        drop(input); // Stream teardown before publishing the report.
        Ok(())
    })();
    let mut report = state.lock().unwrap().clone();
    report.elapsed_ms = started.elapsed().as_millis();
    if let Err(error) = operation {
        report.error = Some(error.to_string());
    }
    report
}
