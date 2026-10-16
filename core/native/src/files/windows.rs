use super::FileRoot;
use crate::core::JarvisError;
use std::path::PathBuf;
use windows::{
    Win32::{
        System::Com::{COINIT_APARTMENTTHREADED, CoInitializeEx, CoTaskMemFree, CoUninitialize},
        UI::Shell::{
            FOLDERID_Desktop, FOLDERID_Documents, FOLDERID_Downloads, KF_FLAG_DONT_VERIFY,
            SHGetKnownFolderPath,
        },
    },
    core::GUID,
};

pub fn known_roots() -> Result<Vec<FileRoot>, JarvisError> {
    unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok() }.map_err(failed)?;
    struct Apartment;
    impl Drop for Apartment {
        fn drop(&mut self) {
            unsafe { CoUninitialize() };
        }
    }
    let _apartment = Apartment;
    let mut roots = Vec::new();
    for (name, id) in [
        ("Desktop", FOLDERID_Desktop),
        ("Documents", FOLDERID_Documents),
        ("Downloads", FOLDERID_Downloads),
    ] {
        match known_path(&id) {
            Ok(path) => roots.push(FileRoot {
                name: name.into(),
                path,
            }),
            Err(error) => {
                tracing::warn!(target: "jarvis.files", root_name = name, error_category = "file_root_unavailable", error = %error, "Known file root unavailable; keeping other roots")
            }
        }
    }
    Ok(roots)
}
fn known_path(id: &GUID) -> Result<PathBuf, JarvisError> {
    let pointer = unsafe { SHGetKnownFolderPath(id, KF_FLAG_DONT_VERIFY, None) }.map_err(failed)?;
    let value = unsafe { pointer.to_string() };
    unsafe {
        CoTaskMemFree(Some(pointer.0.cast()));
    }
    Ok(PathBuf::from(value.map_err(|error| {
        JarvisError::ConfigurationError {
            message: error.to_string(),
        }
    })?))
}
fn failed(error: windows::core::Error) -> JarvisError {
    JarvisError::ConfigurationError {
        message: format!("known folder lookup failed: {error}"),
    }
}
