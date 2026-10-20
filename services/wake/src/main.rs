//! Small native Windows service, built with JARVIS; never links Brain or Core ASR/LLM.
#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]
mod artifacts;
#[cfg(windows)]
mod audio;
mod config;
#[cfg(windows)]
mod detector;
#[cfg(windows)]
mod launcher;
#[cfg(windows)]
mod litert;
mod resample;
#[cfg(windows)]
mod runtime;
mod state;
#[cfg(windows)]
mod windows;

fn main() {
    #[cfg(windows)]
    if let Err(error) = windows::run() {
        eprintln!("JARVIS wake: {error}");
        std::process::exit(1);
    }
    #[cfg(not(windows))]
    {
        eprintln!("JARVIS wake requires Windows");
        std::process::exit(1);
    }
}
