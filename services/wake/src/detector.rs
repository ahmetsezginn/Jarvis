//! Native keyword model adapter; never returns command text or assistant instructions.
use std::path::Path;
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
pub struct Detector {
    neural: crate::litert::Neural,
}
impl Detector {
    pub fn open(root: &Path) -> Result<Self> {
        Ok(Self {
            neural: crate::litert::Neural::open(root)?,
        })
    }
    pub fn feed(&mut self, pcm: &[i16]) -> Result<bool> {
        self.neural.feed(pcm)
    }
    pub fn score(&self) -> f32 {
        self.neural.score
    }
    pub fn reset(&mut self) -> Result<()> {
        self.neural.reset()
    }
}
