//! Windows Voice Capture DSP in source mode. Native AEC owns capture/render synchronization.
//! No recordings, loopback PCM, endpoint IDs or COM objects cross the control pipe.
use super::failure;
use crate::core::JarvisError;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::{
    cell::{Cell, UnsafeCell},
    mem::ManuallyDrop,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::Duration,
};
use windows::{
    Win32::{
        Foundation::PROPERTYKEY,
        Media::{
            Audio::{
                DEVICE_STATE_ACTIVE, EDataFlow, IMMDevice, IMMDeviceEnumerator, MMDeviceEnumerator,
                WAVEFORMATEX, eCapture, eRender,
            },
            DxMediaObjects::{
                DMO_MEDIA_TYPE, DMO_OUTPUT_DATA_BUFFER, IMediaBuffer, IMediaBuffer_Impl,
                IMediaObject,
            },
        },
        System::Com::{
            CLSCTX_ALL, COINIT_APARTMENTTHREADED, CoCreateInstance, CoInitializeEx, CoTaskMemFree,
            CoUninitialize, StructuredStorage::PROPVARIANT,
        },
        UI::Shell::PropertiesSystem::IPropertyStore,
    },
    core::{GUID, Interface, PCWSTR, implement},
};

const AEC: GUID = GUID::from_u128(0x745057c7_f353_4f2d_a7ee_58434477730e);
const PROPERTIES: GUID = GUID::from_u128(0x6f52c567_0360_4bd2_9617_ccbf1421c939);
const AUDIO: GUID = GUID::from_u128(0x73647561_0000_0010_8000_00aa00389b71);
const PCM: GUID = GUID::from_u128(0x00000001_0000_0010_8000_00aa00389b71);
const WAVE: GUID = GUID::from_u128(0x05589f81_c356_11ce_bf01_00aa0055595a);

struct Com;
impl Drop for Com {
    fn drop(&mut self) {
        unsafe { CoUninitialize() }
    }
}

#[implement(IMediaBuffer)]
struct Buffer {
    bytes: UnsafeCell<[u8; 3200]>,
    length: Cell<u32>,
}
impl IMediaBuffer_Impl for Buffer_Impl {
    fn SetLength(&self, length: u32) -> windows::core::Result<()> {
        if length > 3200 {
            return Err(windows::core::Error::from_hresult(windows::core::HRESULT(
                0x80070057u32 as i32,
            )));
        }
        self.length.set(length);
        Ok(())
    }
    fn GetMaxLength(&self) -> windows::core::Result<u32> {
        Ok(3200)
    }
    fn GetBufferAndLength(
        &self,
        bytes: *mut *mut u8,
        length: *mut u32,
    ) -> windows::core::Result<()> {
        // The DMO invokes this synchronously on its owning capture thread. Storage is fixed,
        // survives every ProcessOutput call, and is not read until that call returns.
        unsafe {
            if !bytes.is_null() {
                *bytes = self.bytes.get().cast();
            }
            if !length.is_null() {
                *length = self.length.get();
            }
        }
        Ok(())
    }
}

pub struct EchoCapture {
    dmo: IMediaObject,
    buffer: IMediaBuffer,
    _render: cpal::Stream,
    render_failed: Arc<AtomicBool>,
    enumerator: IMMDeviceEnumerator,
    input_id: String,
    output_id: String,
    _com: Com,
}

fn endpoint_id(device: &IMMDevice) -> windows::core::Result<String> {
    let id = unsafe { device.GetId()? };
    let result = unsafe { id.to_string() };
    unsafe {
        CoTaskMemFree(Some(id.0.cast()));
    }
    Ok(result?)
}

fn endpoint_index(
    enumerator: &IMMDeviceEnumerator,
    flow: EDataFlow,
    id: &str,
) -> Result<u16, JarvisError> {
    let devices =
        unsafe { enumerator.EnumAudioEndpoints(flow, DEVICE_STATE_ACTIVE) }.map_err(failure)?;
    for index in 0..unsafe { devices.GetCount() }.map_err(failure)?.min(256) {
        let device = unsafe { devices.Item(index) }.map_err(failure)?;
        if endpoint_id(&device).map_err(failure)? == id {
            return Ok(index as u16);
        }
    }
    Err(failure(
        "The selected echo-cancellation endpoint is no longer available",
    ))
}

impl EchoCapture {
    pub fn open(input_id: &str, output_id: &str) -> Result<Self, JarvisError> {
        // CPAL's device discovery on this same thread initializes an STA apartment.
        unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok() }.map_err(failure)?;
        let com = Com;
        let enumerator: IMMDeviceEnumerator =
            unsafe { CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL) }.map_err(failure)?;
        let input = endpoint_index(&enumerator, eCapture, input_id)?;
        let output = endpoint_index(&enumerator, eRender, output_id)?;
        let render_failed = Arc::new(AtomicBool::new(false));
        let render = silent_render(output_id, render_failed.clone())?;
        let dmo: IMediaObject =
            unsafe { CoCreateInstance(&AEC, None, CLSCTX_ALL) }.map_err(failure)?;
        let properties: IPropertyStore = dmo.cast().map_err(failure)?;
        // SDK wmcodecdsp.h: PID_FIRST_USABLE=2; SYSTEM_MODE=2, DEVICE_INDEXES=4.
        for (pid, value) in [
            (2, 0_i32),
            (4, (((output as u32) << 16) | input as u32) as i32),
        ] {
            unsafe {
                properties.SetValue(
                    &PROPERTYKEY {
                        fmtid: PROPERTIES,
                        pid,
                    },
                    &PROPVARIANT::from(value),
                )
            }
            .map_err(failure)?;
        }
        let mut wave = WAVEFORMATEX {
            wFormatTag: 1,
            nChannels: 1,
            nSamplesPerSec: 16000,
            nAvgBytesPerSec: 32000,
            nBlockAlign: 2,
            wBitsPerSample: 16,
            cbSize: 0,
        };
        let format = DMO_MEDIA_TYPE {
            majortype: AUDIO,
            subtype: PCM,
            bFixedSizeSamples: true.into(),
            bTemporalCompression: false.into(),
            lSampleSize: 2,
            formattype: WAVE,
            cbFormat: size_of::<WAVEFORMATEX>() as u32,
            pbFormat: (&mut wave as *mut WAVEFORMATEX).cast(),
            ..Default::default()
        };
        unsafe {
            dmo.SetOutputType(0, Some(&format), 0)
                .and_then(|_| dmo.AllocateStreamingResources())
        }
        .map_err(failure)?;
        let buffer: IMediaBuffer = Buffer {
            bytes: UnsafeCell::new([0; 3200]),
            length: Cell::new(0),
        }
        .into();
        Ok(Self {
            dmo,
            buffer,
            _render: render,
            render_failed,
            enumerator,
            input_id: input_id.into(),
            output_id: output_id.into(),
            _com: com,
        })
    }

    pub fn read(&self) -> Result<Vec<f32>, JarvisError> {
        if self.render_failed.load(Ordering::Relaxed) {
            return Err(failure("Echo reference stream was lost; nothing sent"));
        }
        unsafe { self.buffer.SetLength(0) }.map_err(failure)?;
        let mut data = [DMO_OUTPUT_DATA_BUFFER {
            pBuffer: ManuallyDrop::new(Some(self.buffer.clone())),
            ..Default::default()
        }];
        let mut status = 0;
        let processed = unsafe { self.dmo.ProcessOutput(0, &mut data, &mut status) };
        // DMO structs use ManuallyDrop; release the reference even if processing fails.
        unsafe {
            ManuallyDrop::drop(&mut data[0].pBuffer);
        }
        processed.map_err(failure)?;
        if data[0].dwStatus & 8 != 0 {
            return Err(failure(
                "Echo-cancelled audio was discontinuous; nothing sent",
            ));
        }
        let mut bytes = std::ptr::null_mut();
        let mut length = 0;
        unsafe {
            self.buffer
                .GetBufferAndLength(Some(&mut bytes), Some(&mut length))
        }
        .map_err(failure)?;
        if length > 3200 || length % 2 != 0 || (length != 0 && bytes.is_null()) {
            return Err(failure("Invalid echo-cancelled audio; nothing sent"));
        }
        if length == 0 {
            return Ok(Vec::new());
        }
        // Buffer is owned by this thread and processing has completed. Copy before next call.
        Ok(
            unsafe { std::slice::from_raw_parts(bytes, length as usize) }
                .chunks_exact(2)
                .map(|p| i16::from_le_bytes([p[0], p[1]]) as f32 / 32768.)
                .collect(),
        )
    }

    pub fn check_routes(&self) -> Result<(), JarvisError> {
        for id in [&self.input_id, &self.output_id] {
            let wide: Vec<_> = id.encode_utf16().chain(Some(0)).collect();
            let device =
                unsafe { self.enumerator.GetDevice(PCWSTR(wide.as_ptr())) }.map_err(failure)?;
            if unsafe { device.GetState() }.map_err(failure)? != DEVICE_STATE_ACTIVE {
                return Err(failure(
                    "Echo-cancellation audio route changed; nothing sent",
                ));
            }
        }
        Ok(())
    }
}
impl Drop for EchoCapture {
    fn drop(&mut self) {
        let _ = unsafe { self.dmo.FreeStreamingResources() };
    }
}

fn silent_render(id: &str, failed: Arc<AtomicBool>) -> Result<cpal::Stream, JarvisError> {
    // Source-mode DMO requires an active render stream, even before/after SAPI output.
    // A shared all-zero stream keeps the SAME selected endpoint alive without changing volume.
    let device = cpal::default_host()
        .output_devices()
        .map_err(failure)?
        .find(|d| d.id().is_ok_and(|value| value.id() == id))
        .ok_or_else(|| failure("Speech output has no matching echo reference"))?;
    let config = device.default_output_config().map_err(failure)?;
    let error = move |_| {
        failed.store(true, Ordering::Relaxed);
    };
    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => device.build_output_stream(
            config.into(),
            |data: &mut [f32], _| data.fill(0.),
            error,
            Some(Duration::from_secs(3)),
        ),
        cpal::SampleFormat::I16 => device.build_output_stream(
            config.into(),
            |data: &mut [i16], _| data.fill(0),
            error,
            Some(Duration::from_secs(3)),
        ),
        cpal::SampleFormat::I32 => device.build_output_stream(
            config.into(),
            |data: &mut [i32], _| data.fill(0),
            error,
            Some(Duration::from_secs(3)),
        ),
        cpal::SampleFormat::U16 => device.build_output_stream(
            config.into(),
            |data: &mut [u16], _| data.fill(32768),
            error,
            Some(Duration::from_secs(3)),
        ),
        _ => return Err(failure("Unsupported echo reference format")),
    }
    .map_err(failure)?;
    stream.play().map_err(failure)?;
    Ok(stream)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn buffer(samples: &[f32]) -> IMediaBuffer {
        assert!(samples.len() <= 1600);
        let mut bytes = [0; 3200];
        for (sample, output) in samples.iter().zip(bytes.chunks_exact_mut(2)) {
            output
                .copy_from_slice(&((*sample * 32767.).clamp(-32767., 32767.) as i16).to_le_bytes());
        }
        Buffer {
            bytes: UnsafeCell::new(bytes),
            length: Cell::new((samples.len() * 2) as u32),
        }
        .into()
    }

    #[test]
    fn dmo_buffer_rejects_overflow_and_has_stable_storage() {
        let input = buffer(&[0.25, -0.25]);
        assert!(unsafe { input.SetLength(3201) }.is_err());
        let mut ptr = std::ptr::null_mut();
        let mut length = 0;
        unsafe { input.GetBufferAndLength(Some(&mut ptr), Some(&mut length)) }.unwrap();
        assert_eq!(length, 4);
        assert!(!ptr.is_null());
        unsafe { input.GetBufferAndLength(None, None) }.unwrap();
        assert_eq!(unsafe { input.GetMaxLength() }.unwrap(), 3200);
    }

    fn fixture(name: &str, index: &str) -> Vec<f32> {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../target")
            .join(name)
            .join(index);
        let bytes = std::fs::read(path)
            .expect("Explicitly prepare the synthetic voice fixtures; no microphone recordings");
        assert!(bytes.len() < 2_000_000 && &bytes[..4] == b"RIFF");
        let mut offset = 12;
        let mut rate = 0;
        let mut samples = Vec::new();
        while offset + 8 <= bytes.len() {
            let n = u32::from_le_bytes(bytes[offset + 4..offset + 8].try_into().unwrap()) as usize;
            let data = &bytes[offset + 8..offset + 8 + n];
            match &bytes[offset..offset + 4] {
                b"fmt " => {
                    assert_eq!(u16::from_le_bytes(data[..2].try_into().unwrap()), 1);
                    assert_eq!(u16::from_le_bytes(data[2..4].try_into().unwrap()), 1);
                    rate = u32::from_le_bytes(data[4..8].try_into().unwrap());
                    assert_eq!(u16::from_le_bytes(data[14..16].try_into().unwrap()), 16);
                }
                b"data" => samples.extend(
                    data.chunks_exact(2)
                        .map(|x| i16::from_le_bytes([x[0], x[1]]) as f32 / 32768.),
                ),
                _ => {}
            }
            offset += 8 + n + n % 2;
        }
        assert!(!samples.is_empty());
        super::super::resample(&samples, rate)
    }

    #[test]
    #[ignore = "real native AEC filter + Silero with explicitly prepared synthetic fixtures; no audio device or agent"]
    fn real_filter_removes_echo_but_preserves_double_talk() {
        unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok() }.unwrap();
        let _com = Com;
        let dmo: IMediaObject = unsafe { CoCreateInstance(&AEC, None, CLSCTX_ALL) }.unwrap();
        let properties: IPropertyStore = dmo.cast().unwrap();
        for (pid, value) in [(2, PROPVARIANT::from(0_i32)), (3, PROPVARIANT::from(false))] {
            unsafe {
                properties.SetValue(
                    &PROPERTYKEY {
                        fmtid: PROPERTIES,
                        pid,
                    },
                    &value,
                )
            }
            .unwrap();
        }
        let mut wave = WAVEFORMATEX {
            wFormatTag: 1,
            nChannels: 1,
            nSamplesPerSec: 16000,
            nAvgBytesPerSec: 32000,
            nBlockAlign: 2,
            wBitsPerSample: 16,
            cbSize: 0,
        };
        let format = DMO_MEDIA_TYPE {
            majortype: AUDIO,
            subtype: PCM,
            bFixedSizeSamples: true.into(),
            lSampleSize: 2,
            formattype: WAVE,
            cbFormat: size_of::<WAVEFORMATEX>() as u32,
            pbFormat: (&mut wave as *mut WAVEFORMATEX).cast(),
            ..Default::default()
        };
        unsafe {
            dmo.SetInputType(0, Some(&format), 0)
                .and_then(|_| dmo.SetInputType(1, Some(&format), 0))
                .and_then(|_| dmo.SetOutputType(0, Some(&format), 0))
                .and_then(|_| dmo.AllocateStreamingResources())
        }
        .unwrap();
        let far = fixture("voice-bilingual-fixtures", "0.wav");
        let near = fixture("voice-quality-fixtures", "2.wav");
        let count = 16000 * 12;
        let mut reference = vec![0.; count];
        let mut microphone = vec![0.; count];
        for i in 0..count {
            reference[i] = far[i % far.len()] * 0.6;
            if i >= 800 {
                microphone[i] = reference[i - 800] * 0.55;
            }
            if i >= 16000 * 6 && i < 16000 * 6 + near.len() {
                microphone[i] += near[i - 16000 * 6] * 0.8;
            }
        }
        let mut clean = Vec::new();
        for (index, (render, mic)) in reference
            .chunks(320)
            .zip(microphone.chunks(320))
            .enumerate()
        {
            let render = buffer(render);
            let mic = buffer(mic);
            let timestamp = index as i64 * 200000;
            unsafe {
                dmo.ProcessInput(1, &render, 1, timestamp, 200000)
                    .and_then(|_| dmo.ProcessInput(0, &mic, 1, timestamp, 200000))
            }
            .unwrap();
            for _ in 0..10 {
                let output = buffer(&[]);
                let mut data = [DMO_OUTPUT_DATA_BUFFER {
                    pBuffer: ManuallyDrop::new(Some(output.clone())),
                    ..Default::default()
                }];
                let mut status = 0;
                let result = unsafe { dmo.ProcessOutput(0, &mut data, &mut status) };
                unsafe {
                    ManuallyDrop::drop(&mut data[0].pBuffer);
                }
                result.unwrap();
                let mut ptr = std::ptr::null_mut();
                let mut len = 0;
                unsafe { output.GetBufferAndLength(Some(&mut ptr), Some(&mut len)) }.unwrap();
                if len == 0 {
                    break;
                }
                clean.extend(
                    unsafe { std::slice::from_raw_parts(ptr, len as usize) }
                        .chunks_exact(2)
                        .map(|b| i16::from_le_bytes([b[0], b[1]]) as f32 / 32768.),
                );
            }
        }
        unsafe { dmo.FreeStreamingResources() }.unwrap();
        let energy =
            |data: &[f32]| data.iter().map(|s| s * s).sum::<f32>() / data.len().max(1) as f32;
        assert!(clean.len() >= 16000 * 10, "Only {} samples", clean.len());
        let original = energy(&microphone[16000 * 3..16000 * 5]);
        let residual = energy(&clean[16000 * 3..16000 * 5]);
        let near_speech = super::super::vad::contains_speech(&clean[16000 * 6..]).unwrap();
        let mut model = super::super::vad::load().unwrap();
        let mut window = std::collections::VecDeque::new();
        let mut turn = super::super::turn::TurnDetector::default();
        let mut onset = None;
        for (index, frame) in clean.chunks_exact(1600).enumerate() {
            window.extend(frame.iter().copied());
            while window.len() > 15360 {
                window.pop_front();
            }
            let speech = super::super::vad::probability(&mut model, window.make_contiguous())
                .unwrap()
                >= 0.5;
            turn.push(frame, speech);
            if turn.listening && onset.is_none() {
                onset = Some(index * 100);
            }
        }
        let onset = onset.expect("No interrupt onset");
        println!("Synthetic user onset detected at {onset}ms (injected at 6000ms)");
        assert!(
            (6000..=6800).contains(&onset),
            "Missed early user speech or treated echo as user speech"
        );
        println!(
            "Native filter echo residual ratio={:.5}; double-talk speech={near_speech}; {} samples",
            residual / original,
            clean.len()
        );
        assert!(residual < original * 0.15, "Echo suppression insufficient");
        assert!(near_speech, "User speech was lost with echo");
    }
}
