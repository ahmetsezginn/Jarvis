use jarvis_core::{
    audit::{AuditDecision, MemoryAuditSink},
    core::{RequestSource, ToolRequest},
    executor::Executor,
    ipc::{CONTROL_PROTOCOL_VERSION, ControlSession, RequestEnvelope},
    organizer::{AddItem, ListItems, Organizer, UpdateItem},
    platform::fake::FakeDesktopPlatform,
    policy::{PolicyDecision, PolicyEngine},
    tools::{ToolMetadata, ToolRegistry, organizer::OrganizerTool},
};
use serde_json::{Value, json};
use std::sync::Arc;
use uuid::Uuid;

fn add(title: &str, date: &str) -> AddItem {
    serde_json::from_value(json!({"kind":"task","title":title,"due_date":date})).unwrap()
}
fn list(kind: &str, period: &str) -> ListItems {
    serde_json::from_value(json!({"kind":kind,"period":period})).unwrap()
}

#[test]
fn tasks_and_notes_survive_restart_without_changing_unicode() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("private.sqlite3");
    let id = {
        let store = Organizer::new(path.clone());
        store
            .add(&add("Kira ödemesini yap", "today"))
            .unwrap()
            .record_id
    };
    let store = Organizer::new(path);
    let page = store.list(&list("task", "today")).unwrap();
    assert_eq!(page.total, 1);
    assert_eq!(page.items[0].record_id, id);
    assert_eq!(page.items[0].title, "Kira ödemesini yap");
    let note: AddItem = serde_json::from_value(json!({"kind":"note","title":"Tarif","body":"İki kaşık un; SQL '); DROP TABLE personal_items; --"})).unwrap();
    store.add(&note).unwrap();
    assert_eq!(store.list(&list("task", "all")).unwrap().total, 1);
    assert_eq!(
        store.list(&list("note", "all")).unwrap().items[0].body,
        note.body
    );
}

#[test]
fn today_tomorrow_overdue_and_undated_are_distinct() {
    let store = Organizer::in_memory();
    for (title, date) in [
        ("today", "today"),
        ("tomorrow", "tomorrow"),
        ("late", "2000-01-01"),
        ("someday", "none"),
    ] {
        store.add(&add(title, date)).unwrap();
    }
    for (period, title) in [
        ("today", "today"),
        ("tomorrow", "tomorrow"),
        ("overdue", "late"),
        ("undated", "someday"),
    ] {
        let page = store.list(&list("task", period)).unwrap();
        assert_eq!(page.total, 1);
        assert_eq!(page.items[0].title, title);
    }
}

#[test]
fn completion_reopening_rescheduling_and_optimistic_conflicts() {
    let store = Organizer::in_memory();
    let item = store.add(&add("Send report", "today")).unwrap();
    let update: UpdateItem = serde_json::from_value(
        json!({"record_id":item.record_id,"expected_version":1,"status":"done"}),
    )
    .unwrap();
    assert_eq!(store.update(&update).unwrap().status, "done");
    assert!(store.update(&update).is_err());
    assert_eq!(store.list(&list("task", "today")).unwrap().total, 0);
    let update: UpdateItem = serde_json::from_value(json!({"record_id":item.record_id,"expected_version":2,"status":"open","due_date":"tomorrow","title":"Revised report"})).unwrap();
    assert_eq!(store.update(&update).unwrap().version, 3);
    assert_eq!(
        store.list(&list("task", "tomorrow")).unwrap().items[0].title,
        "Revised report"
    );
}

#[test]
fn pagination_query_and_archiving_preserve_all_other_rows() {
    let store = Organizer::in_memory();
    for i in 0..12 {
        store
            .add(&add(&format!("Prepare sample {i}"), "none"))
            .unwrap();
    }
    let mut args = list("task", "all");
    args.query = "prepare SAMPLE".into();
    let first = store.list(&args).unwrap();
    assert_eq!(first.total, 12);
    assert_eq!(first.items.len(), 5);
    args.offset = first.next_offset.unwrap();
    let second = store.list(&args).unwrap();
    assert!(
        second
            .items
            .iter()
            .all(|a| first.items.iter().all(|b| a.record_id != b.record_id))
    );
    let item = &first.items[0];
    store
        .update(
            &serde_json::from_value(
                json!({"record_id":item.record_id,"expected_version":1,"status":"archived"}),
            )
            .unwrap(),
        )
        .unwrap();
    assert_eq!(store.list(&list("task", "all")).unwrap().total, 11);
    let mut args = list("task", "all");
    args.status = "all".into();
    assert_eq!(store.list(&args).unwrap().total, 12);
}

#[test]
fn invalid_inputs_do_not_modify_storage_and_notes_have_no_completion() {
    let store = Organizer::in_memory();
    for args in [
        json!({"kind":"task","title":" "}),
        json!({"kind":"task","title":"x","due_date":"2026-02-30"}),
        json!({"kind":"note","title":"x","due_date":"today"}),
        json!({"kind":"file","title":"x"}),
        json!({"kind":"task","title":"x".repeat(161)}),
    ] {
        assert!(store.add(&serde_json::from_value(args).unwrap()).is_err());
    }
    assert!(
        serde_json::from_value::<AddItem>(json!({"kind":"task","title":"x","path":"elsewhere"}))
            .is_err()
    );
    let item = store
        .add(
            &serde_json::from_value(json!({"kind":"note","title":"Shopping information"})).unwrap(),
        )
        .unwrap();
    assert!(
        store
            .update(
                &serde_json::from_value(
                    json!({"record_id":item.record_id,"expected_version":1,"status":"done"})
                )
                .unwrap()
            )
            .is_err()
    );
    assert!(
        store
            .update(
                &serde_json::from_value(
                    json!({"record_id":Uuid::new_v4(),"expected_version":1,"status":"done"})
                )
                .unwrap()
            )
            .is_err()
    );
    assert_eq!(store.list(&list("task", "all")).unwrap().total, 0);
    assert_eq!(
        store.list(&list("note", "all")).unwrap().items[0].version,
        1
    );
}

#[test]
fn corrupted_or_newer_storage_fails_closed_without_resetting_it() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("broken.sqlite3");
    std::fs::write(&path, b"corrupt personal data").unwrap();
    assert!(
        Organizer::new(path.clone())
            .add(&add("x", "today"))
            .is_err()
    );
    assert_eq!(std::fs::read(path).unwrap(), b"corrupt personal data");
    let path = dir.path().join("future.sqlite3");
    let db = rusqlite::Connection::open(&path).unwrap();
    db.pragma_update(None, "user_version", 2).unwrap();
    assert!(Organizer::new(path).add(&add("x", "today")).is_err());
}

#[test]
fn listing_before_first_save_does_not_create_user_storage() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("not-created").join("organizer.sqlite3");
    assert_eq!(
        Organizer::new(path.clone())
            .list(&list("task", "today"))
            .unwrap()
            .total,
        0
    );
    assert!(!path.parent().unwrap().exists());
}

#[test]
fn separate_instances_detect_concurrent_changes_without_overwriting() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("shared.sqlite3");
    let first = Organizer::new(path.clone());
    let item = first.add(&add("Review contract", "today")).unwrap();
    let second = Organizer::new(path);
    assert_eq!(
        second.list(&list("task", "today")).unwrap().items[0].version,
        1
    );
    let change: UpdateItem = serde_json::from_value(
        json!({"record_id":item.record_id,"expected_version":1,"status":"done"}),
    )
    .unwrap();
    first.update(&change).unwrap();
    assert!(second.update(&change).is_err());
    let mut args = list("task", "today");
    args.status = "done".into();
    assert_eq!(second.list(&args).unwrap().items[0].version, 2);
}

struct FixedPolicy(PolicyDecision);
impl PolicyEngine for FixedPolicy {
    fn evaluate(&self, _: &ToolRequest, _: &ToolMetadata) -> PolicyDecision {
        self.0.clone()
    }
}
fn request(kind: &str, payload: Value) -> RequestEnvelope {
    RequestEnvelope {
        protocol_version: CONTROL_PROTOCOL_VERSION,
        request_id: Uuid::new_v4().to_string(),
        message_type: kind.into(),
        payload,
    }
}
#[test]
fn ipc_mutations_require_policy_and_audit_omits_private_content() {
    for (decision, saved) in [
        (PolicyDecision::Allow, true),
        (
            PolicyDecision::Deny {
                reason: "test".into(),
            },
            false,
        ),
        (
            PolicyDecision::RequireConfirmation {
                reason: "test".into(),
            },
            false,
        ),
    ] {
        let store = Arc::new(Organizer::in_memory());
        let mut registry = ToolRegistry::new();
        for tool in OrganizerTool::all(store.clone()) {
            registry.register(tool).unwrap();
        }
        let audit = Arc::new(MemoryAuditSink::default());
        let executor = Arc::new(Executor::new(
            registry,
            Arc::new(FixedPolicy(decision)),
            audit.clone(),
            Arc::new(FakeDesktopPlatform::default()),
        ));
        let mut session = ControlSession::new(executor);
        assert!(
            session
                .handle_request(request(
                    "hello",
                    json!({"client":"jarvis-brain","client_version":"0.1.0"})
                ))
                .ok
        );
        let response = session.handle_request(request("execute_tool",json!({"tool":"organizer_add","arguments":{"kind":"task","title":"private user text","due_date":"today"}})));
        assert_eq!(response.ok, saved);
        assert_eq!(
            store.list(&list("task", "today")).unwrap().total,
            usize::from(saved)
        );
        let events = audit.events();
        assert_eq!(events[0].source, RequestSource::Brain);
        assert_eq!(events[0].decision == AuditDecision::Allow, saved);
        assert!(
            !serde_json::to_string(&events)
                .unwrap()
                .contains("private user text")
        );
    }
}
