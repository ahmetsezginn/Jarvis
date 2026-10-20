use crate::{core::JarvisError, files::GameShortcutTarget};
use windows::{
    Win32::{
        System::Com::{
            COINIT_APARTMENTTHREADED, COINIT_DISABLE_OLE1DDE, CoInitializeEx, CoUninitialize,
        },
        UI::{Shell::ShellExecuteW, WindowsAndMessaging::SW_SHOWNORMAL},
    },
    core::{PCWSTR, w},
};

struct Apartment;
impl Drop for Apartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}
pub(super) fn open(target: &GameShortcutTarget) -> Result<(), JarvisError> {
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE) }
        .ok()
        .map_err(|error| JarvisError::ExecutionFailed {
            message: format!("Steam activation initialization failed: {error}"),
        })?;
    let _apartment = Apartment;
    // Rebuild from a native-validated numeric ID. Never pass .url, IconFile, flags,
    // raw file text or model text to Windows; use only its registered Steam handler.
    let uri: Vec<_> = target.uri().encode_utf16().chain(Some(0)).collect();
    let result = unsafe {
        ShellExecuteW(
            None,
            w!("open"),
            PCWSTR(uri.as_ptr()),
            PCWSTR::null(),
            PCWSTR::null(),
            SW_SHOWNORMAL,
        )
    };
    if result.0 as isize <= 32 {
        return Err(JarvisError::ExecutionFailed {
            message: "Windows could not activate the registered Steam game handler".into(),
        });
    }
    Ok(())
}
