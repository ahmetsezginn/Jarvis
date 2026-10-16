use jarvis_core::{
    audit::{AuditDecision, MemoryAuditSink},
    core::{RequestSource, ToolRequest, ToolStatus},
    executor::Executor,
    files::{FileCatalog, FileRoot, SearchArguments},
    platform::fake::FakeDesktopPlatform,
    policy::{DefaultPolicyEngine, PolicyDecision, PolicyEngine},
    tools::ToolMetadata,
    tools::{ToolRegistry, files::FileCatalogTool},
};
use serde_json::json;
use std::{fs, sync::Arc};

fn fixture() -> (
    tempfile::TempDir,
    Arc<FileCatalog>,
    Arc<FakeDesktopPlatform>,
    Arc<MemoryAuditSink>,
    Executor,
) {
    let directory = tempfile::tempdir().unwrap();
    fs::create_dir(directory.path().join("Alt klasör")).unwrap();
    fs::write(directory.path().join("Bütçe.xlsx"), b"test document").unwrap();
    fs::write(
        directory.path().join("Alt klasör").join("Bütçe.xlsx"),
        b"second",
    )
    .unwrap();
    fs::write(
        directory.path().join("danger.ps1"),
        b"not executable in this catalog",
    )
    .unwrap();
    fs::write(directory.path().join(".env"), b"secret").unwrap();
    fs::write(directory.path().join("private.key"), b"secret").unwrap();
    fs::create_dir(directory.path().join("node_modules")).unwrap();
    fs::write(
        directory.path().join("node_modules").join("hidden.txt"),
        b"excluded",
    )
    .unwrap();
    let catalog = Arc::new(
        FileCatalog::new(vec![FileRoot {
            name: "Belgeler".into(),
            path: directory.path().to_path_buf(),
        }])
        .unwrap(),
    );
    let platform = Arc::new(FakeDesktopPlatform::default());
    let audit = Arc::new(MemoryAuditSink::default());
    let mut registry = ToolRegistry::new();
    for tool in FileCatalogTool::all(catalog.clone()) {
        registry.register(tool).unwrap();
    }
    let executor = Executor::new(
        registry,
        Arc::new(DefaultPolicyEngine),
        audit.clone(),
        platform.clone(),
    );
    (directory, catalog, platform, audit, executor)
}
fn request(
    executor: &Executor,
    tool: &str,
    args: serde_json::Value,
) -> jarvis_core::core::ToolResult {
    executor.execute(ToolRequest::new(tool, args, RequestSource::Brain))
}
fn search(catalog: &FileCatalog, query: &str) -> serde_json::Value {
    catalog
        .search(&serde_json::from_value::<SearchArguments>(json!({"query":query})).unwrap())
        .unwrap()
}

#[test]
fn filename_word_prefixes_preserve_numeric_versions_and_scope() {
    let (directory, catalog, _, _, executor) = fixture();
    for name in [
        "motor-bakimi.txt",
        "ucus-bileti.pdf",
        "rapor-2024.pdf",
        "rapor-2025.pdf",
    ] {
        fs::write(directory.path().join(name), b"synthetic").unwrap();
    }
    catalog.refresh().unwrap();
    for (query, expected) in [
        ("motor bakım", "motor-bakimi.txt"),
        ("uçuş bilet", "ucus-bileti.pdf"),
        ("rapor 2024", "rapor-2024.pdf"),
    ] {
        let result = request(&executor, "search_files", json!({"query":query}));
        assert_eq!(result.status, ToolStatus::Success);
        assert_eq!(result.data["total"], 1);
        assert_eq!(result.data["entries"][0]["name"], expected);
    }
    assert_eq!(search(&catalog, "rapor 202")["total"], 0);
    let folder = search(&catalog, "Alt klasör")["entries"][0]["entry_id"].clone();
    let scoped = request(
        &executor,
        "search_files",
        json!({"query":"motor bakım", "folder_id":folder}),
    );
    assert_eq!(scoped.data["total"], 0);
}

#[test]
fn discovery_preserves_direct_scope_category_and_rejections() {
    let (directory, catalog, _, _, executor) = fixture();
    fs::write(directory.path().join("random.txt"), b"note").unwrap();
    fs::write(
        directory.path().join("Alt klasör").join("nested.txt"),
        b"note",
    )
    .unwrap();
    catalog.refresh().unwrap();
    let root = search(&catalog, "Belgeler")["entries"][0]["entry_id"]
        .as_str()
        .unwrap()
        .to_owned();
    let found = request(
        &executor,
        "search_files",
        json!({"query":"*", "folder_id":root,
        "recursive":false, "category":"text"}),
    );
    assert_eq!(found.status, ToolStatus::Success);
    let data = found.data;
    assert_eq!(data["total"], 1);
    assert_eq!(data["entries"][0]["name"], "random.txt");
    let id = data["entries"][0]["entry_id"].as_str().unwrap();
    let rejected = request(
        &executor,
        "search_files",
        json!({"query":"*", "folder_id":root,
        "recursive":true, "category":"text", "exclude_ids":[id]}),
    );
    let data = rejected.data;
    assert_eq!(data["total"], 1);
    assert_eq!(data["entries"][0]["name"], "nested.txt");
    for args in [
        json!({"query":"*","recursive":false}),
        json!({"query":"*","category":"script"}),
        json!({"query":"*","exclude_ids":vec!["id";101]}),
        json!({"query":"*","recursive":"false"}),
    ] {
        assert_ne!(
            request(&executor, "search_files", args).status,
            ToolStatus::Success
        );
    }
}

#[test]
fn selected_browser_open_validates_both_catalogs_and_audits() {
    use jarvis_core::{
        apps::{
            ApplicationCatalog, ApplicationSource, DiscoveredApplication, TrustedLaunchTarget,
            fake::FakeApplicationDiscovery,
        },
        config::ApplicationPreferences,
    };
    let (directory, files, platform, audit, _) = fixture();
    fs::write(directory.path().join("CV.pdf"), b"fixture PDF").unwrap();
    fs::write(directory.path().join("chrome.exe"), b"fixture app").unwrap();
    let app = DiscoveredApplication::new(
        ApplicationSource::AdministrativeOverride,
        "chrome",
        "Google Chrome",
        vec![],
        None,
        TrustedLaunchTarget::Executable {
            path: directory.path().join("chrome.exe"),
            arguments: vec![],
        },
    )
    .unwrap();
    let bad_app = DiscoveredApplication::new(
        ApplicationSource::AdministrativeOverride,
        "shell",
        "Spotify",
        vec![],
        None,
        TrustedLaunchTarget::Executable {
            path: directory.path().join("chrome.exe"),
            arguments: vec![],
        },
    )
    .unwrap();
    let apps = Arc::new(ApplicationCatalog::new(
        Arc::new(FakeApplicationDiscovery::succeeding(vec![
            app.clone(),
            bad_app.clone(),
        ])),
        ApplicationPreferences::default(),
    ));
    apps.refresh().unwrap();
    let executor = jarvis_core::build_executor_with_files(
        platform.clone(),
        apps.clone(),
        audit.clone(),
        files.clone(),
    )
    .unwrap();
    let found = search(&files, "CV.pdf");
    let id = found["entries"][0]["entry_id"].as_str().unwrap();
    let result = request(
        &executor,
        "open_file_with_app",
        json!({"entry_id":id,"app_id":app.app_id()}),
    );
    assert_eq!(result.status, ToolStatus::Success);
    let mut denied_registry = ToolRegistry::new();
    denied_registry
        .register(Arc::new(
            jarvis_core::tools::files::OpenFileWithAppTool::new(files.clone(), apps),
        ))
        .unwrap();
    let denied_audit = Arc::new(MemoryAuditSink::default());
    let denied_executor = Executor::new(
        denied_registry,
        Arc::new(Deny),
        denied_audit.clone(),
        platform.clone(),
    );
    assert_eq!(
        request(
            &denied_executor,
            "open_file_with_app",
            json!({"entry_id":id,"app_id":app.app_id()})
        )
        .status,
        ToolStatus::Denied
    );
    assert_eq!(denied_audit.events()[0].decision, AuditDecision::Deny);
    assert_eq!(
        platform.calls().opened_files_with_apps,
        vec![(
            directory.path().join("CV.pdf").canonicalize().unwrap(),
            app.app_id().to_string()
        )]
    );
    for args in [
        json!({"entry_id":id,"app_id":"invented"}),
        json!({"entry_id":"invented","app_id":app.app_id()}),
        json!({"entry_id":id,"app_id":app.app_id(),"path":"arbitrary"}),
        json!({"entry_id":id,"app_id":bad_app.app_id()}),
    ] {
        assert_ne!(
            request(&executor, "open_file_with_app", args).status,
            ToolStatus::Success
        );
    }
    let script = search(&files, "danger.ps1");
    assert_ne!(
        request(
            &executor,
            "open_file_with_app",
            json!({"entry_id":script["entries"][0]["entry_id"],"app_id":app.app_id()})
        )
        .status,
        ToolStatus::Success
    );
    files.refresh().unwrap();
    assert_ne!(
        request(
            &executor,
            "open_file_with_app",
            json!({"entry_id":id,"app_id":app.app_id()})
        )
        .status,
        ToolStatus::Success
    );
    assert_eq!(platform.calls().opened_files_with_apps.len(), 1);
    assert!(!audit.events().is_empty());
}

#[test]
fn natural_names_match_separators_without_guessing_unique_targets() {
    let (directory, catalog, _, _, _) = fixture();
    fs::write(directory.path().join("Ahmet-Sezgin-CV-TR.pdf"), b"fixture").unwrap();
    fs::write(directory.path().join("Ahmet_Sezgin_CV_EN.pdf"), b"fixture").unwrap();
    let result = search(&catalog, "ahmet sezgin cv tr");
    assert_eq!(result["total"], 1);
    assert_eq!(result["entries"][0]["name"], "Ahmet-Sezgin-CV-TR.pdf");
    assert_eq!(search(&catalog, "ahmet sezgin cv")["total"], 2);
    assert_eq!(search(&catalog, "ahmet sezgin missing")["total"], 0);
}

#[test]
fn recursive_scoped_metadata_search_filters_and_pagination() {
    let (_directory, catalog, _, _, executor) = fixture();
    assert_eq!(catalog.status().unwrap()["indexed"], false);
    let result = request(
        &executor,
        "search_files",
        json!({"query":"butce", "extension":"xlsx", "limit":1}),
    );
    assert_eq!(result.status, ToolStatus::Success);
    assert_eq!(result.data["total"], 2);
    assert_eq!(result.data["entries"].as_array().unwrap().len(), 1);
    let page = request(
        &executor,
        "search_files",
        json!({"query":"butce", "offset":1,"limit":1}),
    );
    assert_ne!(
        result.data["entries"][0]["entry_id"],
        page.data["entries"][0]["entry_id"]
    );
    for name in [".env", "private.key", "hidden.txt"] {
        assert_eq!(search(&catalog, name)["total"], 0);
    }
    assert_eq!(catalog.status().unwrap()["contents_read"], false);
    let newest = request(
        &executor,
        "search_files",
        json!({"query":"*", "sort":"newest", "modified_after":0}),
    );
    assert_eq!(newest.status, ToolStatus::Success);
    let largest = request(
        &executor,
        "search_files",
        json!({"query":"butce", "sort":"largest"}),
    );
    assert_eq!(largest.data["entries"][0]["size_bytes"], 13);
}

#[test]
fn opening_uses_catalog_ids_revalidates_and_rejects_execution() {
    let (directory, catalog, platform, audit, executor) = fixture();
    let found = search(&catalog, "butce");
    let id = found["entries"][0]["entry_id"].as_str().unwrap();
    assert_eq!(
        request(&executor, "open_file", json!({"entry_id":id})).status,
        ToolStatus::Success
    );
    assert_eq!(platform.calls().opened_files.len(), 1);
    assert_eq!(
        request(&executor, "open_directory", json!({"entry_id":id})).status,
        ToolStatus::Failed
    );
    assert_eq!(
        request(&executor, "open_containing_folder", json!({"entry_id":id})).status,
        ToolStatus::Success
    );
    assert_eq!(platform.calls().opened_folders.len(), 1);
    let script = search(&catalog, "danger");
    let result = request(
        &executor,
        "open_file",
        json!({"entry_id":script["entries"][0]["entry_id"]}),
    );
    assert_eq!(result.error.unwrap().code, "policy_denied");
    let location = found["entries"][0]["location"].as_str().unwrap();
    fs::write(location, b"changed content with different length").unwrap();
    assert_eq!(
        request(&executor, "open_file", json!({"entry_id":id})).status,
        ToolStatus::Failed
    );
    assert_eq!(platform.calls().opened_files.len(), 1);
    assert!(
        audit
            .events()
            .iter()
            .all(|e| e.source == RequestSource::Brain)
    );
    let folder = search(&catalog, "Alt klasor");
    let folder_id = folder["entries"][0]["entry_id"].as_str().unwrap();
    let listing = request(&executor, "list_directory", json!({"entry_id":folder_id}));
    assert_eq!(listing.data["total"], 1);
    fs::remove_file(directory.path().join("Alt klasör").join("Bütçe.xlsx")).unwrap();
    assert_eq!(
        request(
            &executor,
            "open_file",
            json!({"entry_id":listing.data["entries"][0]["entry_id"]})
        )
        .status,
        ToolStatus::Failed
    );
}

#[test]
fn strict_arguments_unknown_ids_and_refresh_invalidation() {
    let (_directory, catalog, platform, _, executor) = fixture();
    let found = search(&catalog, "butce");
    for args in [
        json!({"path":"C:\\Windows\\cmd.exe"}),
        json!({"entry_id":"invented"}),
        json!({"entry_id":found["entries"][0]["entry_id"],"shell":"anything"}),
    ] {
        assert_ne!(
            request(&executor, "open_file", args).status,
            ToolStatus::Success
        );
    }
    for args in [
        json!({"query":"*","limit":21}),
        json!({"query":"*","unknown":true}),
        json!({"query":"*","modified_after":20,"modified_before":10}),
    ] {
        assert_ne!(
            request(&executor, "search_files", args).status,
            ToolStatus::Success
        );
    }
    catalog.refresh().unwrap();
    assert!(
        catalog
            .checked_entry(found["entries"][0]["entry_id"].as_str().unwrap())
            .is_err()
    );
    assert!(platform.calls().opened_files.is_empty());
}

struct Deny;

#[test]
fn file_tools_cross_the_versioned_ipc_executor_boundary() {
    use jarvis_core::ipc::{CONTROL_PROTOCOL_VERSION, ControlSession, RequestEnvelope};
    let (_dir, _catalog, platform, audit, executor) = fixture();
    let mut session = ControlSession::new(Arc::new(executor));
    let envelope = |message: &str, payload| RequestEnvelope {
        protocol_version: CONTROL_PROTOCOL_VERSION,
        request_id: uuid::Uuid::new_v4().to_string(),
        message_type: message.into(),
        payload,
    };
    assert!(
        session
            .handle_request(envelope(
                "hello",
                json!({"client":"jarvis-brain","client_version":"0.1.0"})
            ))
            .ok
    );
    let found = session.handle_request(envelope(
        "execute_tool",
        json!({"tool":"search_files","arguments":{"query":"butce"}}),
    ));
    assert!(found.ok);
    let id = found.payload.unwrap()["data"]["entries"][0]["entry_id"].clone();
    let opened = session.handle_request(envelope(
        "execute_tool",
        json!({"tool":"open_file","arguments":{"entry_id":id}}),
    ));
    assert!(opened.ok);
    assert_eq!(platform.calls().opened_files.len(), 1);
    assert!(
        audit
            .events()
            .iter()
            .all(|event| event.source == RequestSource::Brain)
    );
    let denied_path = session.handle_request(envelope(
        "execute_tool",
        json!({"tool":"open_file","arguments":{"path":"C:\\Windows\\cmd.exe"}}),
    ));
    assert!(!denied_path.ok);
    assert_eq!(platform.calls().opened_files.len(), 1);
}

impl PolicyEngine for Deny {
    fn evaluate(&self, _: &ToolRequest, _: &ToolMetadata) -> PolicyDecision {
        PolicyDecision::Deny {
            reason: "test policy".into(),
        }
    }
}
#[test]
fn denied_search_and_refresh_do_not_scan() {
    let (_dir, catalog, platform, audit, _) = fixture();
    let mut registry = ToolRegistry::new();
    for tool in FileCatalogTool::all(catalog.clone()) {
        registry.register(tool).unwrap();
    }
    let executor = Executor::new(registry, Arc::new(Deny), audit.clone(), platform);
    assert_eq!(
        request(&executor, "search_files", json!({"query":"*"})).status,
        ToolStatus::Denied
    );
    assert_eq!(
        request(&executor, "refresh_file_catalog", json!({})).status,
        ToolStatus::Denied
    );
    assert_eq!(catalog.status().unwrap()["indexed"], false);
    assert!(
        audit
            .events()
            .iter()
            .all(|e| e.decision == AuditDecision::Deny)
    );
}

#[test]
fn failed_refresh_retains_previous_snapshot_and_reports_inaccessible_scope() {
    let (dir, catalog, _, _, _) = fixture();
    catalog.refresh().unwrap();
    fs::rename(dir.path(), dir.path().with_extension("unavailable")).unwrap();
    assert!(catalog.refresh().is_err());
    assert!(catalog.status().unwrap()["files"].as_u64().unwrap() > 0);
    fs::rename(dir.path().with_extension("unavailable"), dir.path()).unwrap();
}

#[test]
fn bounded_depth_and_file_scope_are_explicit() {
    let directory = tempfile::tempdir().unwrap();
    let mut child = directory.path().to_path_buf();
    for _ in 0..18 {
        child = child.join("nested");
        fs::create_dir(&child).unwrap();
    }
    fs::write(child.join("too-deep.txt"), b"test").unwrap();
    let catalog = FileCatalog::new(vec![FileRoot {
        name: "test".into(),
        path: directory.path().into(),
    }])
    .unwrap();
    assert_eq!(catalog.refresh().unwrap()["partial"], true);
    assert_eq!(search(&catalog, "too-deep")["total"], 0);
    let roots: Vec<FileRoot> = vec![FileRoot {
        name: "disk".into(),
        path: std::path::PathBuf::from(if cfg!(windows) { "C:\\" } else { "/" }),
    }];
    assert!(FileCatalog::new(roots).is_err());
}

#[cfg(windows)]
#[test]
fn junction_escape_is_never_followed() {
    // Opt-in native junction creation is unnecessary: file symlinks use the same reparse check.
    let dir = tempfile::tempdir().unwrap();
    let outside = tempfile::tempdir().unwrap();
    fs::write(outside.path().join("outside.txt"), b"outside").unwrap();
    if std::os::windows::fs::symlink_dir(outside.path(), dir.path().join("link")).is_err() {
        return;
    }
    let catalog = FileCatalog::new(vec![FileRoot {
        name: "test".into(),
        path: dir.path().into(),
    }])
    .unwrap();
    assert_eq!(search(&catalog, "outside")["total"], 0);
    assert_eq!(search(&catalog, "link")["total"], 0);
    assert!(catalog.status().unwrap()["excluded"].as_u64().unwrap() > 0);
}
