//! Native Shell enumeration. COM objects remain on this thread and never cross IPC.
use crate::{
    apps::{ApplicationSource, DiscoveredApplication, TrustedLaunchTarget},
    core::JarvisError,
};
use windows::{
    Win32::{
        Storage::EnhancedStorage::PKEY_AppUserModel_ID,
        System::Com::{
            CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED, CoCreateInstance, CoInitializeEx,
            CoTaskMemFree, CoUninitialize,
        },
        UI::Shell::{
            AO_NONE, ApplicationActivationManager, BHID_EnumItems, IApplicationActivationManager,
            IEnumShellItems, IShellItem, IShellItem2, SHCreateItemFromParsingName,
            SIGDN_NORMALDISPLAY,
        },
    },
    core::{Interface, PCWSTR, PWSTR, w},
};

struct Apartment;
impl Apartment {
    fn new() -> windows::core::Result<Self> {
        // Each caller initializes and balances its own apartment reference.
        unsafe {
            CoInitializeEx(None, COINIT_APARTMENTTHREADED).ok()?;
        }
        Ok(Self)
    }
}
impl Drop for Apartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}

fn owned_string(pointer: PWSTR) -> windows::core::Result<String> {
    // Shell strings are CoTaskMem allocated, including on conversion failure.
    let result = unsafe { pointer.to_string() };
    unsafe {
        CoTaskMemFree(Some(pointer.0.cast()));
    }
    Ok(result?)
}

pub(crate) fn discover() -> Result<Vec<DiscoveredApplication>, JarvisError> {
    enumerate().map_err(|error| JarvisError::ApplicationDiscoveryFailed {
        message: format!("Windows AppsFolder enumeration failed: {error}"),
    })
}

fn enumerate() -> windows::core::Result<Vec<DiscoveredApplication>> {
    let _apartment = Apartment::new()?;
    let folder: IShellItem = unsafe { SHCreateItemFromParsingName(w!("shell:AppsFolder"), None)? };
    let items: IEnumShellItems = unsafe { folder.BindToHandler(None, &BHID_EnumItems)? };
    let mut applications = Vec::new();
    let started = std::time::Instant::now();
    for index in 0..=10_000 {
        let mut next = [None];
        let mut fetched = 0;
        unsafe {
            items.Next(&mut next, Some(&mut fetched))?;
        }
        if fetched == 0 {
            return Ok(applications);
        }
        if index == 10_000 || started.elapsed() > std::time::Duration::from_secs(60) {
            return Err(windows::core::Error::from_hresult(windows::core::HRESULT(
                0x800705B4_u32 as i32,
            )));
        }
        let item = next[0].take().ok_or_else(|| {
            windows::core::Error::from_hresult(windows::core::HRESULT(0x80004005_u32 as i32))
        })?;
        let item2: IShellItem2 = item.cast()?;
        // Desktop items commonly have no packaged AUMID; existing shortcuts cover them.
        let Ok(raw_id) = (unsafe { item2.GetString(&PKEY_AppUserModel_ID) }) else {
            continue;
        };
        let aumid = owned_string(raw_id)?;
        if !super::super::model::valid_packaged_aumid(&aumid) {
            continue;
        }
        let name = owned_string(unsafe { item.GetDisplayName(SIGDN_NORMALDISPLAY)? })?;
        if name.trim().is_empty() {
            continue;
        }
        let application = DiscoveredApplication::new(
            ApplicationSource::WindowsAppsFolder,
            &aumid,
            name,
            Vec::new(),
            None,
            TrustedLaunchTarget::PackagedApplication {
                aumid: aumid.clone(),
            },
        )
        .map_err(|_| {
            windows::core::Error::from_hresult(windows::core::HRESULT(0x80070057_u32 as i32))
        })?;
        applications.push(application);
    }
    unreachable!()
}

pub(crate) fn activate(aumid: &str) -> windows::core::Result<()> {
    let _apartment = Apartment::new()?;
    let manager: IApplicationActivationManager =
        unsafe { CoCreateInstance(&ApplicationActivationManager, None, CLSCTX_INPROC_SERVER)? };
    let identity: Vec<u16> = aumid.encode_utf16().chain(Some(0)).collect();
    unsafe {
        manager.ActivateApplication(PCWSTR(identity.as_ptr()), PCWSTR::null(), AO_NONE)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn opt_in_live_apps_folder_enumeration() {
        if std::env::var("JARVIS_RUN_WINDOWS_APPS_TESTS").as_deref() != Ok("1") {
            return;
        }
        let apps = super::discover().expect("live AppsFolder enumeration");
        assert!(
            !apps.is_empty(),
            "expected at least one packaged app for this opt-in test"
        );
        for app in &apps {
            assert_eq!(
                app.source(),
                crate::apps::ApplicationSource::WindowsAppsFolder
            );
            assert!(app.launch().path().is_none());
        }
        println!("AppsFolder discovered {} packaged applications", apps.len());
    }
}
