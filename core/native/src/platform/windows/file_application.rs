//! Explicit local PDF browser adapters; no shell, user arguments or cloud upload.
use crate::{
    apps::{DiscoveredApplication, TrustedLaunchTarget},
    core::JarvisError,
};
use std::{
    os::windows::ffi::OsStrExt,
    path::{Path, PathBuf},
    process::Command,
};
use windows::{
    Win32::{
        System::Com::{
            CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED, CoCreateInstance, CoInitializeEx,
            CoUninitialize, IPersistFile, STGM_READ,
        },
        UI::Shell::{IShellLinkW, ShellLink},
    },
    core::{Interface, PCWSTR},
};

struct Apartment;
impl Drop for Apartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}
fn failure(message: impl Into<String>) -> JarvisError {
    JarvisError::ExecutionFailed {
        message: message.into(),
    }
}
fn shortcut_target(path: &Path) -> Result<PathBuf, JarvisError> {
    unsafe {
        CoInitializeEx(None, COINIT_APARTMENTTHREADED)
            .ok()
            .map_err(|e| failure(e.to_string()))?;
        let _apartment = Apartment;
        let link: IShellLinkW = CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER)
            .map_err(|e| failure(e.to_string()))?;
        let persist: IPersistFile = link.cast().map_err(|e| failure(e.to_string()))?;
        let wide: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
        persist
            .Load(PCWSTR(wide.as_ptr()), STGM_READ)
            .map_err(|e| failure(e.to_string()))?;
        let mut target = [0u16; 32768];
        link.GetPath(&mut target, std::ptr::null_mut(), 0)
            .map_err(|e| failure(e.to_string()))?;
        let mut args = [0u16; 32768];
        link.GetArguments(&mut args)
            .map_err(|e| failure(e.to_string()))?;
        if args[0] != 0 {
            return Err(failure("browser shortcuts with arguments are unsupported"));
        }
        let end = target
            .iter()
            .position(|c| *c == 0)
            .ok_or_else(|| failure("unbounded shortcut target"))?;
        Ok(PathBuf::from(
            String::from_utf16(&target[..end]).map_err(|e| failure(e.to_string()))?,
        ))
    }
}
pub(super) fn open(path: &Path, app: &DiscoveredApplication) -> Result<(), JarvisError> {
    let expected = match app.canonical_name().to_ascii_lowercase().as_str() {
        "google chrome" => "chrome.exe",
        "microsoft edge" => "msedge.exe",
        _ => return Err(failure("unsupported file application")),
    };
    let executable = match app.launch() {
        TrustedLaunchTarget::Shortcut(shortcut) => shortcut_target(shortcut)?,
        TrustedLaunchTarget::Executable { path, arguments } if arguments.is_empty() => path.clone(),
        _ => return Err(failure("unsupported browser launch target")),
    };
    if !executable.is_absolute()
        || !executable.is_file()
        || !executable
            .file_name()
            .is_some_and(|n| n.eq_ignore_ascii_case(expected))
    {
        return Err(failure(
            "catalog browser target does not match its PDF adapter",
        ));
    }
    // Exactly one Core-owned absolute document argument; never reuse shortcut flags.
    Command::new(
        executable
            .canonicalize()
            .map_err(|e| failure(e.to_string()))?,
    )
    .arg(browser_document_path(path))
    .spawn()
    .map(|_| ())
    .map_err(|e| failure(e.to_string()))
}

fn browser_document_path(path: &Path) -> PathBuf {
    // Browsers accept ordinary absolute Windows paths, not necessarily verbatim Win32 paths.
    let value = path.to_string_lossy();
    if let Some(unc) = value.strip_prefix(r"\\?\UNC\") {
        PathBuf::from(format!(r"\\{unc}"))
    } else if let Some(local) = value.strip_prefix(r"\\?\") {
        PathBuf::from(local)
    } else {
        path.to_path_buf()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn browser_path_preserves_spaces_and_removes_only_verbatim_prefix() {
        assert_eq!(
            browser_document_path(Path::new(r"\\?\C:\Downloads\CV TR.pdf")),
            PathBuf::from(r"C:\Downloads\CV TR.pdf")
        );
        assert_eq!(
            browser_document_path(Path::new(r"\\?\UNC\server\share\CV.pdf")),
            PathBuf::from(r"\\server\share\CV.pdf")
        );
    }
}
