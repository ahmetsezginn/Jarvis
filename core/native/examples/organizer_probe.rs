//! Test-only framed stdio fixture. Production still uses the user-local Named Pipe.
//! Store must be explicitly inside workspace/target; non-organizer execution is blocked.
use std::{io, path::PathBuf, sync::Arc};

use jarvis_core::{
    apps::{ApplicationCatalog, fake::FakeApplicationDiscovery},
    audit::MemoryAuditSink,
    build_executor_with_organizer,
    config::ApplicationPreferences,
    files::FileCatalog,
    ipc::{ControlSession, RequestEnvelope, error_response, read_frame, write_json_frame},
    organizer::Organizer,
    platform::fake::FakeDesktopPlatform,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let arguments: Vec<_> = std::env::args_os().skip(1).collect();
    if arguments.len() != 1 {
        return Err("test fixture requires an explicit isolated organizer.sqlite3 path".into());
    }
    let path = PathBuf::from(&arguments[0]);
    let target = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../target")
        .canonicalize()?;
    let parent = path
        .parent()
        .ok_or("missing fixture directory")?
        .canonicalize()?;
    if !parent.starts_with(&target) || path.file_name().is_none_or(|n| n != "organizer.sqlite3") {
        return Err("probe storage must be organizer.sqlite3 inside workspace/target".into());
    }
    let catalog = Arc::new(ApplicationCatalog::new(
        Arc::new(FakeApplicationDiscovery::succeeding(Vec::new())),
        ApplicationPreferences::default(),
    ));
    catalog.refresh()?;
    let executor = Arc::new(build_executor_with_organizer(
        Arc::new(FakeDesktopPlatform::default()),
        catalog,
        Arc::new(MemoryAuditSink::default()),
        Arc::new(FileCatalog::new(Vec::new())?),
        Arc::new(Organizer::new(parent.join("organizer.sqlite3"))),
    )?);
    let mut session = ControlSession::new(executor);
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    while let Some(payload) = read_frame(&mut input)? {
        let parsed = serde_json::from_slice::<RequestEnvelope>(&payload);
        let forbidden = parsed.as_ref().ok().filter(|request| {
            request.message_type == "execute_tool"
                && !matches!(
                    request.payload.get("tool").and_then(|v| v.as_str()),
                    Some(
                        "organizer_add" | "organizer_update" | "organizer_list" | "organizer_clock"
                    )
                )
        });
        let response = if let Some(request) = forbidden {
            error_response(
                request.request_id.clone(),
                "probe_forbidden_tool",
                "diagnostic fixture blocks all non-organizer execution",
            )
        } else {
            session.handle_payload(&payload)
        };
        write_json_frame(&mut output, &response)?;
    }
    Ok(())
}
