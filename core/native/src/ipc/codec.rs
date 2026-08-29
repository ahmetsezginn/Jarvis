use std::io::{self, Read, Write};

use serde::Serialize;
use thiserror::Error;

pub const MAX_FRAME_SIZE: usize = 1024 * 1024;
const HEADER_SIZE: usize = 4;

#[derive(Debug, Error)]
pub enum FrameError {
    #[error("invalid frame: {message}")]
    InvalidFrame { message: String },
    #[error("frame payload of {size} bytes exceeds the {maximum} byte limit")]
    FrameTooLarge { size: usize, maximum: usize },
    #[error("frame I/O failed: {0}")]
    Io(#[from] io::Error),
    #[error("message serialization failed: {0}")]
    Serialization(#[from] serde_json::Error),
}

impl FrameError {
    #[must_use]
    pub const fn code(&self) -> &'static str {
        match self {
            Self::FrameTooLarge { .. } => "frame_too_large",
            Self::InvalidFrame { .. } | Self::Io(_) => "invalid_frame",
            Self::Serialization(_) => "internal_protocol_error",
        }
    }
}

pub fn read_frame(reader: &mut impl Read) -> Result<Option<Vec<u8>>, FrameError> {
    let mut header = [0_u8; HEADER_SIZE];
    let header_read = read_until_full(reader, &mut header)?;
    if header_read == 0 {
        return Ok(None);
    }
    if header_read != HEADER_SIZE {
        return Err(FrameError::InvalidFrame {
            message: "truncated length prefix".to_owned(),
        });
    }

    let payload_length = u32::from_be_bytes(header) as usize;
    if payload_length == 0 {
        return Err(FrameError::InvalidFrame {
            message: "zero-length payloads are not valid control messages".to_owned(),
        });
    }
    if payload_length > MAX_FRAME_SIZE {
        return Err(FrameError::FrameTooLarge {
            size: payload_length,
            maximum: MAX_FRAME_SIZE,
        });
    }

    let mut payload = vec![0_u8; payload_length];
    let body_read = read_until_full(reader, &mut payload)?;
    if body_read != payload_length {
        return Err(FrameError::InvalidFrame {
            message: format!(
                "truncated payload: expected {payload_length} bytes, read {body_read}"
            ),
        });
    }
    Ok(Some(payload))
}

pub fn write_json_frame(writer: &mut impl Write, value: &impl Serialize) -> Result<(), FrameError> {
    let payload = serde_json::to_vec(value)?;
    write_frame(writer, &payload)
}

pub fn write_frame(writer: &mut impl Write, payload: &[u8]) -> Result<(), FrameError> {
    if payload.is_empty() {
        return Err(FrameError::InvalidFrame {
            message: "zero-length payloads are not valid control messages".to_owned(),
        });
    }
    if payload.len() > MAX_FRAME_SIZE {
        return Err(FrameError::FrameTooLarge {
            size: payload.len(),
            maximum: MAX_FRAME_SIZE,
        });
    }
    let length = u32::try_from(payload.len()).map_err(|_| FrameError::FrameTooLarge {
        size: payload.len(),
        maximum: MAX_FRAME_SIZE,
    })?;
    writer.write_all(&length.to_be_bytes())?;
    writer.write_all(payload)?;
    writer.flush()?;
    Ok(())
}

fn read_until_full(reader: &mut impl Read, buffer: &mut [u8]) -> Result<usize, io::Error> {
    let mut total = 0;
    while total < buffer.len() {
        match reader.read(&mut buffer[total..]) {
            Ok(0) => break,
            Ok(read) => total += read,
            Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
            Err(error) => return Err(error),
        }
    }
    Ok(total)
}

#[cfg(test)]
mod tests {
    use std::io::Cursor;

    use serde_json::json;

    use super::*;

    #[test]
    fn valid_frame_uses_big_endian_length_and_round_trips() {
        let mut encoded = Vec::new();
        write_json_frame(&mut encoded, &json!({"status": "ok"})).unwrap();

        let declared = u32::from_be_bytes(encoded[..HEADER_SIZE].try_into().unwrap()) as usize;
        assert_eq!(declared, encoded.len() - HEADER_SIZE);
        assert_eq!(
            read_frame(&mut Cursor::new(encoded))
                .unwrap()
                .unwrap()
                .len(),
            declared
        );
    }

    #[test]
    fn partial_header_is_rejected() {
        let error = read_frame(&mut Cursor::new(vec![0, 0])).unwrap_err();
        assert_eq!(error.code(), "invalid_frame");
    }

    #[test]
    fn partial_body_is_rejected() {
        let mut encoded = 10_u32.to_be_bytes().to_vec();
        encoded.extend_from_slice(b"short");
        let error = read_frame(&mut Cursor::new(encoded)).unwrap_err();
        assert_eq!(error.code(), "invalid_frame");
    }

    #[test]
    fn oversized_frame_is_rejected_before_allocation() {
        let encoded = ((MAX_FRAME_SIZE + 1) as u32).to_be_bytes();
        let error = read_frame(&mut Cursor::new(encoded)).unwrap_err();
        assert_eq!(error.code(), "frame_too_large");
    }

    #[test]
    fn zero_length_frame_is_rejected() {
        let error = read_frame(&mut Cursor::new(0_u32.to_be_bytes())).unwrap_err();
        assert_eq!(error.code(), "invalid_frame");
    }
}
