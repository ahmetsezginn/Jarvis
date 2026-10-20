use crate::resample::Mono16k;
use cpal::{
    SizedSample,
    traits::{DeviceTrait, HostTrait, StreamTrait},
};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicU32, AtomicU64, Ordering},
    mpsc::{self, Receiver, SyncSender},
};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
pub struct Capture {
    _stream: cpal::Stream,
    pub frames: Receiver<Vec<i16>>,
    pub fault: Arc<Mutex<Option<String>>>,
    pub discontinuities: Arc<AtomicU64>,
    pub peak: Arc<AtomicU32>,
    pub input_name: String,
    default_id: Option<cpal::DeviceId>,
}
impl Capture {
    pub fn open(selected: Option<&str>) -> Result<Self> {
        let host = cpal::default_host();
        let device = if let Some(name) = selected {
            let mut matches = host
                .input_devices()?
                .filter(|device| device.description().is_ok_and(|info| info.name() == name));
            let device = matches.next().ok_or(
                "Configured wake microphone is unavailable; no fallback microphone was opened",
            )?;
            if matches.next().is_some() {
                return Err("Configured wake microphone name is ambiguous".into());
            }
            device
        } else {
            host.default_input_device()
                .ok_or("Default microphone unavailable")?
        };
        let input_name = device.description()?.name().to_owned();
        let default_id = if selected.is_none() {
            Some(device.id()?)
        } else {
            None
        };
        let format = device.default_input_config()?;
        let (tx, frames) = mpsc::sync_channel(8);
        let fault = Arc::new(Mutex::new(None));
        let discontinuities = Arc::new(AtomicU64::new(0));
        let peak = Arc::new(AtomicU32::new(0));
        let config = format.config();
        let stream = match format.sample_format() {
            cpal::SampleFormat::F32 => stream(
                &device,
                config,
                tx,
                fault.clone(),
                discontinuities.clone(),
                peak.clone(),
                |v: &f32| *v,
            )?,
            cpal::SampleFormat::I16 => stream(
                &device,
                config,
                tx,
                fault.clone(),
                discontinuities.clone(),
                peak.clone(),
                |v: &i16| *v as f32 / 32768.0,
            )?,
            cpal::SampleFormat::U16 => stream(
                &device,
                config,
                tx,
                fault.clone(),
                discontinuities.clone(),
                peak.clone(),
                |v: &u16| (*v as f32 - 32768.0) / 32768.0,
            )?,
            _ => return Err("Unsupported microphone sample format".into()),
        };
        stream.play()?;
        Ok(Self {
            _stream: stream,
            frames,
            fault,
            discontinuities,
            peak,
            input_name,
            default_id,
        })
    }

    pub fn default_changed(&self) -> bool {
        let Some(opened) = self.default_id.as_ref() else {
            return false;
        };
        let current = cpal::default_host()
            .default_input_device()
            .and_then(|d| d.id().ok());
        current.as_ref() != Some(opened)
    }
}
fn stream<T: SizedSample>(
    device: &cpal::Device,
    config: cpal::StreamConfig,
    tx: SyncSender<Vec<i16>>,
    fault: Arc<Mutex<Option<String>>>,
    gaps: Arc<AtomicU64>,
    peak: Arc<AtomicU32>,
    float: impl Fn(&T) -> f32 + Send + 'static,
) -> Result<cpal::Stream> {
    let mut resample = Mono16k::new(config.sample_rate, config.channels)?;
    let errors = gaps.clone();
    Ok(device.build_input_stream(
        config,
        move |samples: &[T], _| {
            // A driver-controlled callback cannot allocate an unbounded frame or backlog.
            if samples.len() > 38400 || !samples.len().is_multiple_of(config.channels as usize) {
                gaps.fetch_add(1, Ordering::Relaxed);
                return;
            }
            let frame = resample.convert(samples, &float);
            let amplitude = frame
                .iter()
                .map(|sample| (*sample as f32).abs() / 32768.0)
                .fold(0.0f32, f32::max);
            peak.fetch_max(amplitude.to_bits(), Ordering::Relaxed);
            if !frame.is_empty() && tx.try_send(frame).is_err() {
                gaps.fetch_add(1, Ordering::Relaxed);
            }
        },
        move |error| {
            if error.kind() == cpal::ErrorKind::Xrun {
                errors.fetch_add(1, Ordering::Relaxed);
            } else if let Ok(mut target) = fault.lock() {
                *target = Some(error.to_string());
            }
        },
        None,
    )?)
}
