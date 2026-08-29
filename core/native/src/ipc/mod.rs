mod codec;
mod protocol;
mod server;
mod transport;

#[cfg(windows)]
pub mod windows;

pub use codec::{FrameError, MAX_FRAME_SIZE, read_frame, write_json_frame};
pub use protocol::{
    CONTROL_PROTOCOL_VERSION, RequestEnvelope, ResponseEnvelope, error_response, success_response,
};
pub use server::{ControlServer, ControlSession};
pub use transport::{IpcListener, IpcStream};

use std::sync::Arc;

use crate::{core::JarvisError, executor::Executor};

#[cfg(windows)]
pub fn serve(executor: Arc<Executor>) -> Result<(), JarvisError> {
    let listener = windows::NamedPipeListener::for_current_user().map_err(|error| {
        JarvisError::IpcUnavailable {
            message: error.to_string(),
        }
    })?;
    let endpoint = listener.endpoint().to_owned();
    tracing::info!(target: "jarvis.ipc", pipe_endpoint = %endpoint, "control server starting");
    println!("JARVIS Core listening on local named pipe {endpoint}");
    ControlServer::new(executor)
        .serve(&listener)
        .map_err(|error| JarvisError::IpcUnavailable {
            message: error.to_string(),
        })
}

#[cfg(not(windows))]
pub fn serve(_executor: Arc<Executor>) -> Result<(), JarvisError> {
    Err(JarvisError::PlatformUnsupported {
        platform: std::env::consts::OS.to_owned(),
    })
}
