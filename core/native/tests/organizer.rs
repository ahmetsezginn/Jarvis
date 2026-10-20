use jarvis_core::{
    audit::{AuditDecision, MemoryAuditSink},
    core::{RequestSource, ToolRequest},
    executor::Executor,
    ipc::{CONTROL_PROTOCOL_VERSION, ControlSession, RequestEnvelope},
    organizer::{AddItem, CopyTasks, ListItems, Organizer, SetRecurrence, UpdateItem},
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
    db.pragma_update(None, "user_version", 3).unwrap();
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

fn update_item(
    store: &Organizer,
    item: &jarvis_core::organizer::Item,
    patch: Value,
) -> jarvis_core::organizer::Item {
    let mut args = patch.as_object().unwrap().clone();
    args.insert("record_id".into(), json!(item.record_id));
    args.insert("expected_version".into(), json!(item.version));
    if let Some(day) = &item.occurrence_date {
        args.insert("occurrence_date".into(), json!(day));
    }
    store
        .update(&serde_json::from_value(Value::Object(args)).unwrap())
        .unwrap()
}

#[test]
fn daily_completion_is_per_day_and_survives_restart_without_read_writes() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("organizer.sqlite3");
    let store = Organizer::new(path.clone());
    let item=store.add(&serde_json::from_value(json!({"kind":"task","title":"Read a chapter","due_date":"2028-02-28","recurrence":"daily"})).unwrap()).unwrap();
    let done = update_item(&store, &item, json!({"status":"done"}));
    assert_eq!(done.status, "done");
    assert!(
        store
            .list(&list("task", "2028-02-28"))
            .unwrap()
            .items
            .is_empty()
    );
    let leap = store
        .list(&list("task", "2028-02-29"))
        .unwrap()
        .items
        .remove(0);
    assert_eq!(leap.status, "open");
    assert_eq!(leap.record_id, item.record_id);
    assert_eq!(leap.occurrence_date.as_deref(), Some("2028-02-29"));
    assert_eq!(store.list(&list("task", "2028-02-27")).unwrap().total, 0);
    let bytes = std::fs::read(&path).unwrap();
    for _ in 0..3 {
        assert_eq!(store.list(&list("task", "2028-03-01")).unwrap().total, 1);
    }
    assert_eq!(std::fs::read(&path).unwrap(), bytes);
    drop(store);
    let store = Organizer::new(path);
    let mut args = list("task", "2028-02-28");
    args.status = "done".into();
    assert_eq!(store.list(&args).unwrap().total, 1);
    assert_eq!(
        store.list(&list("task", "2028-03-01")).unwrap().items[0].status,
        "open"
    );
    let stop = update_item(&store, &leap, json!({"recurrence":"none"}));
    assert_eq!(stop.recurrence.as_deref(), Some("none"));
    assert_eq!(store.list(&list("task", "2028-03-01")).unwrap().total, 0);
    assert_eq!(store.list(&args).unwrap().total, 1);
}

#[test]
fn converting_existing_task_keeps_identity_and_daily_edits_are_isolated() {
    let store = Organizer::in_memory();
    let ordinary = store.add(&add("Stretch", "none")).unwrap();
    let daily = update_item(
        &store,
        &ordinary,
        json!({"recurrence":"daily","due_date":"none"}),
    );
    assert_eq!(daily.record_id, ordinary.record_id);
    assert_eq!(daily.due_date, daily.occurrence_date);
    assert!(daily.due_date.is_some());
    let revised = update_item(
        &store,
        &daily,
        json!({"title":"Stretch gently","body":"Ten minutes","status":"done"}),
    );
    assert_eq!(revised.title, "Stretch gently");
    assert_eq!(
        store.list(&list("task", "tomorrow")).unwrap().items[0].title,
        "Stretch"
    );
    let stale:UpdateItem=serde_json::from_value(json!({"record_id":daily.record_id,"expected_version":daily.version,"occurrence_date":daily.occurrence_date,"status":"done"})).unwrap();
    assert!(store.update(&stale).is_err());
    for patch in [
        json!({"status":"done"}),
        json!({"occurrence_date":"today","status":"done"}),
        json!({"occurrence_date":revised.occurrence_date,"due_date":"tomorrow"}),
    ] {
        let mut args = patch.as_object().unwrap().clone();
        args.insert("record_id".into(), json!(revised.record_id));
        args.insert("expected_version".into(), json!(revised.version));
        let parsed: UpdateItem = serde_json::from_value(Value::Object(args)).unwrap();
        assert!(store.update(&parsed).is_err());
    }
}

#[test]
fn copying_a_day_is_atomic_idempotent_and_preserves_completed_originals() {
    let store = Organizer::in_memory();
    for title in ["Review invoice", "Water plants", "Prepare slides"] {
        store.add(&add(title, "yesterday")).unwrap();
    }
    let mut yesterday = list("task", "yesterday");
    yesterday.status = "all".into();
    let first = store.list(&yesterday).unwrap().items.remove(0);
    update_item(&store, &first, json!({"status":"done"}));
    let args: CopyTasks = serde_json::from_value(
        json!({"source_date":"yesterday","target_date":"today","expected_count":3}),
    )
    .unwrap();
    let wrong: CopyTasks = serde_json::from_value(
        json!({"source_date":"yesterday","target_date":"today","expected_count":2}),
    )
    .unwrap();
    assert!(store.copy_tasks(&wrong).is_err());
    assert_eq!(store.list(&list("task", "today")).unwrap().total, 0);
    let copied = store.copy_tasks(&args).unwrap();
    assert_eq!(copied.copied, 3);
    assert!(
        copied
            .items
            .iter()
            .all(|i| i.status == "open" && i.recurrence.is_none())
    );
    assert_eq!(store.copy_tasks(&args).unwrap().copied, 0);
    assert_eq!(store.copy_tasks(&args).unwrap().already_present, 3);
    let originals = store.list(&yesterday).unwrap();
    assert_eq!(originals.total, 3);
    assert_eq!(
        originals
            .items
            .iter()
            .filter(|i| i.status == "done")
            .count(),
        1
    );
    let today = store.list(&list("task", "today")).unwrap();
    assert_eq!(today.total, 3);
    assert!(
        today
            .items
            .iter()
            .all(|i| i.status == "open"
                && !originals.items.iter().any(|o| o.record_id == i.record_id))
    );
}

#[test]
fn daily_routines_are_not_duplicated_by_day_copy_and_notes_never_repeat() {
    let store = Organizer::in_memory();
    store.add(&serde_json::from_value(json!({"kind":"task","title":"Exercise","recurrence":"daily","due_date":"yesterday"})).unwrap()).unwrap();
    let args: CopyTasks = serde_json::from_value(
        json!({"source_date":"yesterday","target_date":"today","expected_count":1}),
    )
    .unwrap();
    let result = store.copy_tasks(&args).unwrap();
    assert_eq!(result.copied, 0);
    assert_eq!(result.already_present, 1);
    for invalid in [
        json!({"kind":"note","title":"a","recurrence":"daily"}),
        json!({"kind":"task","title":"a","recurrence":"weekly"}),
    ] {
        assert!(
            store
                .add(&serde_json::from_value(invalid).unwrap())
                .is_err()
        );
    }
}

#[test]
fn archived_tasks_are_not_in_the_copy_count_and_missing_count_fails_closed() {
    let store = Organizer::in_memory();
    store.add(&add("Active", "yesterday")).unwrap();
    let archived = store.add(&add("Old cancelled task", "yesterday")).unwrap();
    update_item(&store, &archived, json!({"status":"archived"}));
    let mut args = list("task", "yesterday");
    args.status = "all".into();
    let page = store.list(&args).unwrap();
    assert_eq!(page.total, 2);
    assert_eq!(page.copyable_total, 1);
    assert!(
        serde_json::from_value::<CopyTasks>(
            json!({"source_date":"yesterday","target_date":"today"})
        )
        .is_err()
    );
    let result=store.copy_tasks(&serde_json::from_value(json!({"source_date":"yesterday","target_date":"today","expected_count":page.copyable_total})).unwrap()).unwrap();
    assert_eq!(result.copied, 1);
    assert_eq!(
        store.list(&list("task", "today")).unwrap().items[0].title,
        "Active"
    );
}

#[test]
fn recurrence_group_is_atomic_and_returns_the_same_private_bindings() {
    let store = Organizer::in_memory();
    let first = store.add(&add("Read", "today")).unwrap();
    let second = store.add(&add("Stretch", "today")).unwrap();
    let make = |version| {
        serde_json::from_value::<SetRecurrence>(json!({"items":[{"record_id":first.record_id,"expected_version":1},{"record_id":second.record_id,"expected_version":version}],"recurrence":"daily"})).unwrap()
    };
    update_item(&store, &second, json!({"body":"Changed concurrently"}));
    assert!(store.set_recurrence(&make(1)).is_err());
    assert!(
        store
            .list(&list("task", "today"))
            .unwrap()
            .items
            .iter()
            .all(|i| i.recurrence.is_none())
    );
    let updated = store.set_recurrence(&make(2)).unwrap();
    assert_eq!(updated.len(), 2);
    assert_eq!(updated[0].record_id, first.record_id);
    assert_eq!(store.list(&list("task", "tomorrow")).unwrap().total, 2);
    let stop:SetRecurrence=serde_json::from_value(json!({"items":updated.iter().map(|i|json!({"record_id":i.record_id,"expected_version":i.version,"occurrence_date":i.occurrence_date})).collect::<Vec<_>>(),"recurrence":"none"})).unwrap();
    store.set_recurrence(&stop).unwrap();
    assert_eq!(store.list(&list("task", "tomorrow")).unwrap().total, 0);
    let duplicate:SetRecurrence=serde_json::from_value(json!({"items":[{"record_id":first.record_id,"expected_version":2},{"record_id":first.record_id,"expected_version":2}],"recurrence":"daily"})).unwrap();
    assert!(duplicate.validate().is_err());
}

#[test]
fn copy_replies_bind_target_statuses_and_reflect_later_edits_without_recopying() {
    let store = Organizer::in_memory();
    let source = store.add(&add("Practice", "yesterday")).unwrap();
    update_item(&store, &source, json!({"status":"done"}));
    let args: CopyTasks = serde_json::from_value(
        json!({"source_date":"yesterday","target_date":"today","expected_count":1}),
    )
    .unwrap();
    let copied = store.copy_tasks(&args).unwrap();
    assert_eq!(copied.items[0].status, "open");
    assert_ne!(copied.items[0].record_id, source.record_id);
    update_item(&store, &copied.items[0], json!({"status":"done"}));
    let repeated = store.copy_tasks(&args).unwrap();
    assert_eq!(repeated.copied, 0);
    assert_eq!(repeated.items[0].status, "done");
    assert_eq!(repeated.items[0].version, 2);
}

#[test]
fn a_previously_copied_then_moved_and_stopped_routine_returns_a_valid_day_binding() {
    let store = Organizer::in_memory();
    store.add(&add("Review notes", "yesterday")).unwrap();
    let args: CopyTasks = serde_json::from_value(
        json!({"source_date":"yesterday","target_date":"tomorrow","expected_count":1}),
    )
    .unwrap();
    let copied = store.copy_tasks(&args).unwrap().items.remove(0);
    let daily = update_item(
        &store,
        &copied,
        json!({"due_date":"today","recurrence":"daily"}),
    );
    let stopped = update_item(&store, &daily, json!({"status":"done","recurrence":"none"}));
    let repeated = store.copy_tasks(&args).unwrap();
    assert_eq!(repeated.copied, 0);
    assert_eq!(repeated.items[0].occurrence_date, stopped.occurrence_date);
    assert_eq!(repeated.items[0].status, "done");
    assert_eq!(
        update_item(&store, &repeated.items[0], json!({"status":"open"})).status,
        "open"
    );
}

#[test]
fn schema_one_migrates_atomically_without_losing_saved_items() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("old.sqlite3");
    let db = rusqlite::Connection::open(&path).unwrap();
    db.execute_batch("CREATE TABLE personal_items(record_id TEXT PRIMARY KEY,kind TEXT,title TEXT,body TEXT,due_date TEXT,status TEXT,version INTEGER,created_at TEXT,updated_at TEXT); PRAGMA user_version=1;").unwrap();
    db.execute("INSERT INTO personal_items VALUES (?1,'task','Keep me','original','2026-10-19','done',7,'a','a')",[Uuid::new_v4().to_string()]).unwrap();
    drop(db);
    let store = Organizer::new(path.clone());
    let mut args = list("task", "all");
    args.status = "all".into();
    let page = store.list(&args).unwrap();
    assert_eq!(page.items[0].title, "Keep me");
    assert_eq!(page.items[0].version, 7);
    store
        .add(
            &serde_json::from_value(json!({"kind":"task","title":"Daily","recurrence":"daily"}))
                .unwrap(),
        )
        .unwrap();
    assert_eq!(
        rusqlite::Connection::open(path)
            .unwrap()
            .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
            .unwrap(),
        2
    );
}

#[test]
fn copying_and_daily_writes_use_the_same_ipc_policy_boundary() {
    for allow in [false, true] {
        for tool in [
            "organizer_copy_tasks",
            "organizer_add",
            "organizer_update",
            "organizer_set_recurrence",
        ] {
            let store = Arc::new(Organizer::in_memory());
            let item = store.add(&add("Protected task", "yesterday")).unwrap();
            let second = if tool == "organizer_set_recurrence" {
                Some(
                    store
                        .add(&add("Protected second task", "yesterday"))
                        .unwrap(),
                )
            } else {
                None
            };
            let mut registry = ToolRegistry::new();
            for tool in OrganizerTool::all(store.clone()) {
                registry.register(tool).unwrap();
            }
            let audit = Arc::new(MemoryAuditSink::default());
            let decision = if allow {
                PolicyDecision::Allow
            } else {
                PolicyDecision::Deny {
                    reason: "test".into(),
                }
            };
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
            let arguments = match tool {
                "organizer_copy_tasks" => {
                    json!({"source_date":"yesterday","target_date":"today","expected_count":1})
                }
                "organizer_add" => {
                    json!({"kind":"task","title":"Protected daily task","recurrence":"daily"})
                }
                "organizer_set_recurrence" => {
                    json!({"items":[{"record_id":item.record_id,"expected_version":1},{"record_id":second.as_ref().unwrap().record_id,"expected_version":1}],"recurrence":"daily"})
                }
                _ => json!({"record_id":item.record_id,"expected_version":1,"recurrence":"daily"}),
            };
            let reply = session.handle_request(request(
                "execute_tool",
                json!({"tool":tool,"arguments":arguments}),
            ));
            assert_eq!(reply.ok, allow, "{tool}");
            assert_eq!(
                store.list(&list("task", "today")).unwrap().total,
                usize::from(allow)
                    * if tool == "organizer_set_recurrence" {
                        2
                    } else {
                        1
                    }
            );
            assert!(
                !serde_json::to_string(&audit.events())
                    .unwrap()
                    .contains("Protected")
            );
        }
    }
}

#[test]
fn copy_more_than_one_page_and_count_mismatch_never_truncates_or_partially_writes() {
    let store = Organizer::in_memory();
    for i in 0..8 {
        store
            .add(&add(&format!("Work item {i}"), "yesterday"))
            .unwrap();
    }
    let args: CopyTasks = serde_json::from_value(
        json!({"source_date":"yesterday","target_date":"today","expected_count":8}),
    )
    .unwrap();
    assert_eq!(store.copy_tasks(&args).unwrap().copied, 8);
    assert_eq!(store.list(&list("task", "today")).unwrap().total, 8);
    for bad in [
        json!({"source_date":"today","target_date":"today","expected_count":1}),
        json!({"source_date":"none","target_date":"tomorrow","expected_count":1}),
        json!({"source_date":"yesterday","target_date":"tomorrow","expected_count":101}),
    ] {
        assert!(
            store
                .copy_tasks(&serde_json::from_value(bad).unwrap())
                .is_err()
        );
    }
    assert_eq!(store.list(&list("task", "tomorrow")).unwrap().total, 0);
}
