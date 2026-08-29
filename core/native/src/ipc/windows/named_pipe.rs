use std::{
    ffi::c_void,
    io::{self, Read, Write},
    mem::size_of,
    ptr::null_mut,
    sync::atomic::{AtomicBool, Ordering},
};

use windows_sys::{
    Win32::{
        Foundation::{
            CloseHandle, ERROR_BROKEN_PIPE, ERROR_NO_DATA, ERROR_PIPE_CONNECTED, HANDLE,
            INVALID_HANDLE_VALUE, LocalFree,
        },
        Security::{
            Authorization::{
                ConvertSidToStringSidW, ConvertStringSecurityDescriptorToSecurityDescriptorW,
                SDDL_REVISION_1,
            },
            GetTokenInformation, PSECURITY_DESCRIPTOR, SECURITY_ATTRIBUTES, TOKEN_QUERY,
            TOKEN_USER, TokenUser,
        },
        Storage::FileSystem::{
            FILE_FLAG_FIRST_PIPE_INSTANCE, FlushFileBuffers, PIPE_ACCESS_DUPLEX, ReadFile,
            WriteFile,
        },
        System::{
            Pipes::{
                ConnectNamedPipe, CreateNamedPipeW, DisconnectNamedPipe, PIPE_READMODE_BYTE,
                PIPE_REJECT_REMOTE_CLIENTS, PIPE_TYPE_BYTE, PIPE_UNLIMITED_INSTANCES, PIPE_WAIT,
            },
            Threading::{GetCurrentProcess, OpenProcessToken},
        },
    },
    core::PWSTR,
};

use crate::ipc::{IpcListener, IpcStream};

const PIPE_BUFFER_SIZE: u32 = 64 * 1024;

pub struct NamedPipeListener {
    endpoint: String,
    security_descriptor: String,
    first_instance: AtomicBool,
}

impl NamedPipeListener {
    pub fn for_current_user() -> io::Result<Self> {
        let sid = current_user_sid()?;
        Ok(Self {
            endpoint: pipe_endpoint_for_sid(&sid),
            security_descriptor: format!("D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;{sid})"),
            first_instance: AtomicBool::new(true),
        })
    }

    fn create_instance(&self) -> io::Result<OwnedPipeHandle> {
        let name = wide_null(&self.endpoint);
        let descriptor = LocalSecurityDescriptor::from_sddl(&self.security_descriptor)?;
        let attributes = SECURITY_ATTRIBUTES {
            nLength: u32::try_from(size_of::<SECURITY_ATTRIBUTES>()).unwrap_or(u32::MAX),
            lpSecurityDescriptor: descriptor.as_ptr(),
            bInheritHandle: 0,
        };
        let first_instance = self.first_instance.swap(false, Ordering::SeqCst);
        let open_mode = PIPE_ACCESS_DUPLEX
            | if first_instance {
                FILE_FLAG_FIRST_PIPE_INSTANCE
            } else {
                0
            };
        let pipe_mode =
            PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS;

        // SAFETY: all pointers remain valid for the duration of the call, the pipe name is
        // NUL-terminated, and SECURITY_ATTRIBUTES references a live self-relative descriptor.
        let handle = unsafe {
            CreateNamedPipeW(
                name.as_ptr(),
                open_mode,
                pipe_mode,
                PIPE_UNLIMITED_INSTANCES,
                PIPE_BUFFER_SIZE,
                PIPE_BUFFER_SIZE,
                5_000,
                &attributes,
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            return Err(io::Error::last_os_error());
        }
        Ok(OwnedPipeHandle(handle))
    }
}

impl IpcListener for NamedPipeListener {
    fn endpoint(&self) -> &str {
        &self.endpoint
    }

    fn accept(&self) -> io::Result<Box<dyn IpcStream>> {
        let pipe = self.create_instance()?;
        // SAFETY: pipe owns a valid server-side named-pipe handle and no OVERLAPPED structure is
        // used because this listener deliberately performs a synchronous accept.
        let connected = unsafe { ConnectNamedPipe(pipe.0, null_mut()) };
        if connected == 0 {
            let error = io::Error::last_os_error();
            if error.raw_os_error() != Some(ERROR_PIPE_CONNECTED as i32) {
                return Err(error);
            }
        }
        Ok(Box::new(NamedPipeStream { pipe }))
    }
}

pub fn current_user_pipe_endpoint() -> io::Result<String> {
    current_user_sid().map(|sid| pipe_endpoint_for_sid(&sid))
}

fn pipe_endpoint_for_sid(sid: &str) -> String {
    format!(r"\\.\pipe\jarvis-core-{sid}-v1")
}

struct NamedPipeStream {
    pipe: OwnedPipeHandle,
}

impl Read for NamedPipeStream {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        if buffer.is_empty() {
            return Ok(0);
        }
        let requested = buffer.len().min(u32::MAX as usize) as u32;
        let mut read = 0_u32;
        // SAFETY: the handle is valid, buffer is writable for requested bytes, and synchronous
        // I/O requires a null OVERLAPPED pointer.
        let succeeded = unsafe {
            ReadFile(
                self.pipe.0,
                buffer.as_mut_ptr(),
                requested,
                &mut read,
                null_mut(),
            )
        };
        if succeeded == 0 {
            let error = io::Error::last_os_error();
            if matches!(
                error.raw_os_error(),
                Some(code) if code == ERROR_BROKEN_PIPE as i32 || code == ERROR_NO_DATA as i32
            ) {
                return Ok(0);
            }
            return Err(error);
        }
        Ok(read as usize)
    }
}

impl Write for NamedPipeStream {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        if buffer.is_empty() {
            return Ok(0);
        }
        let requested = buffer.len().min(u32::MAX as usize) as u32;
        let mut written = 0_u32;
        // SAFETY: the handle is valid, buffer is readable for requested bytes, and synchronous
        // I/O requires a null OVERLAPPED pointer.
        let succeeded = unsafe {
            WriteFile(
                self.pipe.0,
                buffer.as_ptr(),
                requested,
                &mut written,
                null_mut(),
            )
        };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(written as usize)
    }

    fn flush(&mut self) -> io::Result<()> {
        // SAFETY: the handle is a valid connected server-side pipe. Flushing before a protocol
        // rejection closes the pipe ensures that the client can read the typed error response.
        if unsafe { FlushFileBuffers(self.pipe.0) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

struct OwnedPipeHandle(HANDLE);

// SAFETY: a named-pipe HANDLE may be transferred to one connection thread. The wrapper is not
// Clone, and all access after transfer still requires &mut NamedPipeStream.
unsafe impl Send for OwnedPipeHandle {}

impl Drop for OwnedPipeHandle {
    fn drop(&mut self) {
        // SAFETY: this wrapper exclusively owns the handle. Disconnect may legitimately fail when
        // the client has already gone away; CloseHandle still releases the kernel object.
        unsafe {
            DisconnectNamedPipe(self.0);
            CloseHandle(self.0);
        }
    }
}

struct OwnedToken(HANDLE);

impl Drop for OwnedToken {
    fn drop(&mut self) {
        // SAFETY: this wrapper exclusively owns a token handle returned by OpenProcessToken.
        unsafe {
            CloseHandle(self.0);
        }
    }
}

struct LocalSecurityDescriptor(PSECURITY_DESCRIPTOR);

impl LocalSecurityDescriptor {
    fn from_sddl(sddl: &str) -> io::Result<Self> {
        let wide = wide_null(sddl);
        let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
        // SAFETY: wide is NUL-terminated and descriptor is a valid out pointer. Windows allocates
        // the returned self-relative security descriptor with LocalAlloc.
        let succeeded = unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                wide.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                null_mut(),
            )
        };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Self(descriptor))
    }

    fn as_ptr(&self) -> *mut c_void {
        self.0
    }
}

impl Drop for LocalSecurityDescriptor {
    fn drop(&mut self) {
        // SAFETY: ConvertStringSecurityDescriptorToSecurityDescriptorW returns LocalAlloc memory.
        unsafe {
            LocalFree(self.0);
        }
    }
}

fn current_user_sid() -> io::Result<String> {
    let mut token_handle: HANDLE = null_mut();
    // SAFETY: GetCurrentProcess returns a pseudo-handle valid in this process and token_handle is a
    // valid out pointer.
    let opened = unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token_handle) };
    if opened == 0 {
        return Err(io::Error::last_os_error());
    }
    let token = OwnedToken(token_handle);

    let mut required = 0_u32;
    // SAFETY: the first call intentionally supplies no buffer to obtain the required byte count.
    unsafe {
        GetTokenInformation(token.0, TokenUser, null_mut(), 0, &mut required);
    }
    if required == 0 {
        return Err(io::Error::last_os_error());
    }
    let mut buffer = vec![0_u8; required as usize];
    // SAFETY: buffer has the exact size returned by Windows and remains alive while TOKEN_USER and
    // its SID pointer are read.
    let received = unsafe {
        GetTokenInformation(
            token.0,
            TokenUser,
            buffer.as_mut_ptr().cast(),
            required,
            &mut required,
        )
    };
    if received == 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: a successful TokenUser query stores a properly aligned TOKEN_USER at buffer start.
    let token_user = unsafe { &*buffer.as_ptr().cast::<TOKEN_USER>() };
    let mut string_sid: PWSTR = null_mut();
    // SAFETY: token_user.User.Sid is valid for the lifetime of buffer and string_sid is an out
    // pointer receiving LocalAlloc memory.
    let converted = unsafe { ConvertSidToStringSidW(token_user.User.Sid, &mut string_sid) };
    if converted == 0 {
        return Err(io::Error::last_os_error());
    }
    let result = wide_ptr_to_string(string_sid);
    // SAFETY: ConvertSidToStringSidW allocates the returned string with LocalAlloc.
    unsafe {
        LocalFree(string_sid.cast());
    }
    result
}

fn wide_ptr_to_string(pointer: PWSTR) -> io::Result<String> {
    if pointer.is_null() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "Windows returned a null SID string",
        ));
    }
    let mut length = 0_usize;
    // SAFETY: pointer references a NUL-terminated string allocated by Windows.
    unsafe {
        while *pointer.add(length) != 0 {
            length += 1;
        }
        String::from_utf16(std::slice::from_raw_parts(pointer, length)).map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                format!("current-user SID is not valid UTF-16: {error}"),
            )
        })
    }
}

fn wide_null(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(Some(0)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn endpoint_is_stable_and_local_for_current_user() {
        let first = current_user_pipe_endpoint().unwrap();
        let second = current_user_pipe_endpoint().unwrap();
        assert_eq!(first, second);
        assert!(first.starts_with(r"\\.\pipe\jarvis-core-S-1-"));
        assert!(first.ends_with("-v1"));
    }

    #[test]
    fn listener_security_descriptor_is_restricted() {
        let listener = NamedPipeListener::for_current_user().unwrap();
        assert!(listener.security_descriptor.starts_with("D:P"));
        assert!(listener.security_descriptor.contains(";;;SY)"));
        assert!(listener.security_descriptor.contains(";;;BA)"));
        assert!(listener.security_descriptor.contains(";;;S-1-"));
    }
}
