use crate::core::JarvisError;

use super::DiscoveredApplication;

pub trait ApplicationDiscovery: Send + Sync {
    fn discover(&self) -> Result<Vec<DiscoveredApplication>, JarvisError>;
}
