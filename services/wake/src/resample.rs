//! Bounded, streaming box-filter downsampler. No saved or transported recordings.
pub struct Mono16k {
    channels: usize,
    rate: u32,
    phase: u32,
    weighted: f64,
}
impl Mono16k {
    pub fn new(rate: u32, channels: u16) -> Result<Self, &'static str> {
        if !(16000..=192000).contains(&rate) || !(1..=32).contains(&channels) {
            return Err("Unsupported microphone format");
        }
        Ok(Self {
            channels: channels.into(),
            rate,
            phase: 0,
            weighted: 0.0,
        })
    }
    pub fn convert<T>(&mut self, samples: &[T], float: impl Fn(&T) -> f32) -> Vec<i16> {
        let mut output = Vec::with_capacity(samples.len() / self.channels + 1);
        for frame in samples.chunks_exact(self.channels) {
            let mono = frame.iter().map(|x| float(x) as f64).sum::<f64>() / self.channels as f64;
            let mono = if mono.is_finite() {
                mono.clamp(-1.0, 1.0)
            } else {
                0.0
            };
            let mut remaining = 16000;
            while remaining > 0 {
                let weight = remaining.min(self.rate - self.phase);
                self.weighted += mono * weight as f64;
                self.phase += weight;
                remaining -= weight;
                if self.phase == self.rate {
                    output
                        .push((self.weighted / self.rate as f64 * i16::MAX as f64).round() as i16);
                    self.phase = 0;
                    self.weighted = 0.0;
                }
            }
        }
        output
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn downsampling_is_chunk_independent_and_preserves_time_and_level() {
        for rate in [16000, 44100, 48000, 96000] {
            let samples = vec![0.25f32; rate * 2];
            let full = Mono16k::new(rate as u32, 2)
                .unwrap()
                .convert(&samples, |v| *v);
            let mut streaming = Mono16k::new(rate as u32, 2).unwrap();
            let divided: Vec<_> = samples
                .chunks(142)
                .flat_map(|chunk| streaming.convert(chunk, |v| *v))
                .collect();
            assert_eq!(full, divided);
            assert_eq!(full.len(), 16000);
            assert!(full.iter().all(|v| *v == 8192));
        }
        assert!(Mono16k::new(0, 2).is_err());
        assert!(Mono16k::new(48000, 0).is_err());
    }
    #[test]
    fn malformed_samples_do_not_enter_decoder() {
        assert_eq!(
            Mono16k::new(16000, 1)
                .unwrap()
                .convert(&[f32::NAN, f32::INFINITY, 4.0], |v| *v),
            [0, 0, 32767]
        );
    }
}
