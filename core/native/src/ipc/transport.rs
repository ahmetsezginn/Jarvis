use std::io::{self, Read, Write};

pub trait IpcStream: Read + Write + Send {}

impl<T> IpcStream for T where T: Read + Write + Send {}

pub trait IpcListener: Send + Sync {
    fn endpoint(&self) -> &str;
    fn accept(&self) -> io::Result<Box<dyn IpcStream>>;
}
