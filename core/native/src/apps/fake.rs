use std::sync::Mutex;

use crate::core::JarvisError;

use super::{ApplicationDiscovery, DiscoveredApplication};

pub struct FakeApplicationDiscovery {
    result: Mutex<Result<Vec<DiscoveredApplication>, JarvisError>>,
    calls: Mutex<usize>,
}

impl FakeApplicationDiscovery {
    #[must_use]
    pub fn succeeding(applications: Vec<DiscoveredApplication>) -> Self {
        Self {
            result: Mutex::new(Ok(applications)),
            calls: Mutex::new(0),
        }
    }

    #[must_use]
    pub fn failing(error: JarvisError) -> Self {
        Self {
            result: Mutex::new(Err(error)),
            calls: Mutex::new(0),
        }
    }

    pub fn set_result(&self, result: Result<Vec<DiscoveredApplication>, JarvisError>) {
        *self
            .result
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = result;
    }

    #[must_use]
    pub fn call_count(&self) -> usize {
        *self
            .calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

impl ApplicationDiscovery for FakeApplicationDiscovery {
    fn discover(&self) -> Result<Vec<DiscoveredApplication>, JarvisError> {
        *self
            .calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner) += 1;
        self.result
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }
}
