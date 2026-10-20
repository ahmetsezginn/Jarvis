//! The only activation target is the protected install's fixed user-context task.
use crate::config::Config;
use std::os::windows::{io::AsRawHandle, process::CommandExt};
use std::{
    ffi::OsStr,
    path::PathBuf,
    process::{Command, Stdio},
};
use windows::{
    Win32::System::{
        Com::{
            CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED, CoCreateInstance, CoInitializeEx,
            CoUninitialize,
        },
        TaskScheduler::{
            IRegisteredTask, ITaskService, TASK_STATE_QUEUED, TASK_STATE_READY, TASK_STATE_RUNNING,
            TaskScheduler,
        },
        Variant::VARIANT,
    },
    core::BSTR,
};
use windows_sys::Win32::System::RemoteDesktop::{
    WTS_SESSIONSTATE_UNLOCK, WTSActive, WTSDomainName, WTSFreeMemory, WTSGetActiveConsoleSessionId,
    WTSINFOEXW, WTSQuerySessionInformationW, WTSSessionInfoEx, WTSUserName,
};
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObjectExtendedLimitInformation,
        SetInformationJobObject,
    },
};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
pub const TASK_NAME: &str = "Launch";
pub const TASK_FOLDER: &str = "\\JARVIS";
pub fn request_activation() -> Result<()> {
    use windows_service::{
        service::{ServiceAccess, ServiceState, UserEventCode},
        service_manager::{ServiceManager, ServiceManagerAccess},
    };
    let manager = ServiceManager::local_computer(None::<&str>, ServiceManagerAccess::CONNECT)?;
    let service = manager.open_service(
        crate::runtime::SERVICE,
        ServiceAccess::USER_DEFINED_CONTROL | ServiceAccess::QUERY_STATUS,
    )?;
    if service.query_status()?.current_state == ServiceState::Stopped {
        return Task::connect()?.activate();
    }
    service.notify(UserEventCode::from_raw(128)?)?;
    Ok(())
}
pub fn install_root() -> Result<PathBuf> {
    Ok(std::env::current_exe()?
        .parent()
        .ok_or("Missing install root")?
        .to_path_buf())
}
pub fn config() -> Result<Config> {
    let bytes = std::fs::read(install_root()?.join("config.json"))?;
    if bytes.len() > 8192 {
        return Err("Oversized wake configuration".into());
    }
    let value: Config = serde_json::from_slice(&bytes)?;
    value.validate()?;
    let expected =
        PathBuf::from(std::env::var_os("SystemRoot").ok_or("Missing Windows directory")?)
            .join("System32/WindowsPowerShell/v1.0/powershell.exe");
    if !value
        .powershell
        .to_string_lossy()
        .replace('/', "\\")
        .eq_ignore_ascii_case(&expected.to_string_lossy().replace('/', "\\"))
    {
        return Err("Installed launcher is not Windows PowerShell".into());
    }
    Ok(value)
}
pub struct Task {
    registered: IRegisteredTask,
    _com: Com,
}
struct Com;
impl Drop for Com {
    fn drop(&mut self) {
        unsafe {
            CoUninitialize();
        }
    }
}
impl Task {
    pub fn connect() -> Result<Self> {
        unsafe {
            CoInitializeEx(None, COINIT_MULTITHREADED).ok()?;
        }
        let com = Com;
        let scheduler: ITaskService =
            unsafe { CoCreateInstance(&TaskScheduler, None, CLSCTX_INPROC_SERVER)? };
        let empty = VARIANT::default();
        unsafe {
            scheduler.Connect(&empty, &empty, &empty, &empty)?;
            let registered = scheduler
                .GetFolder(&BSTR::from(TASK_FOLDER))?
                .GetTask(&BSTR::from(TASK_NAME))?;
            Ok(Self {
                registered,
                _com: com,
            })
        }
    }
    pub fn running(&self) -> Result<bool> {
        let state = unsafe { self.registered.State()? };
        if state == TASK_STATE_RUNNING || state == TASK_STATE_QUEUED {
            Ok(true)
        } else if state == TASK_STATE_READY {
            Ok(false)
        } else {
            Err("Installed JARVIS launch task is disabled or unavailable".into())
        }
    }
    pub fn activate(&self) -> Result<()> {
        if !self.running()? {
            unsafe {
                self.registered.Run(&VARIANT::default())?;
            }
        }
        Ok(())
    }
}
pub fn owner_active(config: &Config) -> bool {
    unsafe {
        let session = WTSGetActiveConsoleSessionId();
        if session == u32::MAX {
            return false;
        }
        let mut info = std::ptr::null_mut();
        let mut size = 0;
        if WTSQuerySessionInformationW(
            std::ptr::null_mut(),
            session,
            WTSSessionInfoEx,
            &mut info,
            &mut size,
        ) == 0
            || info.is_null()
        {
            return false;
        }
        let unlocked = if size as usize >= std::mem::size_of::<WTSINFOEXW>() {
            let info = &*info.cast::<WTSINFOEXW>();
            info.Level == 1
                && info.Data.WTSInfoExLevel1.SessionState == WTSActive
                && info.Data.WTSInfoExLevel1.SessionFlags == WTS_SESSIONSTATE_UNLOCK as i32
        } else {
            false
        };
        WTSFreeMemory(info.cast());
        if !unlocked {
            return false;
        }
        let query = |class| -> Option<String> {
            let mut pointer = std::ptr::null_mut();
            let mut count = 0;
            if WTSQuerySessionInformationW(
                std::ptr::null_mut(),
                session,
                class,
                &mut pointer,
                &mut count,
            ) == 0
                || pointer.is_null()
            {
                return None;
            }
            let result =
                String::from_utf16_lossy(std::slice::from_raw_parts(pointer, count as usize / 2))
                    .trim_end_matches('\0')
                    .to_owned();
            WTSFreeMemory(pointer.cast());
            Some(result)
        };
        match (query(WTSDomainName), query(WTSUserName)) {
            (Some(domain), Some(user)) if !user.is_empty() => {
                format!("{domain}\\{user}").eq_ignore_ascii_case(&config.owner_account)
            }
            _ => false,
        }
    }
}
pub fn desktop() -> Result<()> {
    let config = config()?;
    let mut session = 0;
    if unsafe {
        windows_sys::Win32::System::RemoteDesktop::ProcessIdToSessionId(
            std::process::id(),
            &mut session,
        )
    } == 0
        || session == 0
        || !owner_active(&config)
    {
        return Err("Desktop bootstrap requires the owner's unlocked interactive session".into());
    }
    let script = config.repository.join("jarvis.ps1");
    if !script.is_file() {
        return Err("Installed JARVIS repository was moved or removed".into());
    }
    let job = Job::new()?;
    let mut child = Command::new(&config.powershell)
        .args([
            OsStr::new("-NoProfile"),
            OsStr::new("-WindowStyle"),
            OsStr::new("Hidden"),
            OsStr::new("-File"),
            script.as_os_str(),
            OsStr::new("-Desktop"),
            OsStr::new("-StopCoreOnExit"),
        ])
        .current_dir(&config.repository)
        .env("JARVIS_WAKE_LAUNCH", "1")
        .creation_flags(0x08000000) // CREATE_NO_WINDOW; no extra terminal window.
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;
    if unsafe { AssignProcessToJobObject(job.0, child.as_raw_handle()) } == 0 {
        let error = std::io::Error::last_os_error();
        let _ = child.kill();
        let _ = child.wait();
        return Err(error.into());
    }
    let status = child.wait()?;
    drop(job); // Also terminates descendants if the launcher crashed unexpectedly.
    if !status.success() {
        return Err("JARVIS desktop launcher failed".into());
    }
    Ok(())
}
struct Job(HANDLE);
impl Job {
    fn new() -> Result<Self> {
        let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if handle.is_null() {
            return Err(std::io::Error::last_os_error().into());
        }
        let job = Self(handle);
        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if unsafe {
            SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
                std::mem::size_of_val(&limits) as u32,
            )
        } == 0
        {
            return Err(std::io::Error::last_os_error().into());
        }
        Ok(job)
    }
}
impl Drop for Job {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0);
        }
    }
}
