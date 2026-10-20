//! Private, local personal tasks and notes. No model-supplied storage paths or SQL.
use std::{path::PathBuf, sync::Mutex, time::Duration};

use chrono::{Days, Local, NaiveDate};
use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::core::JarvisError;

const MAX_ITEMS: i64 = 10_000;
mod routines;
pub use routines::{CopyResult, CopyTasks, RecurrenceBinding, SetRecurrence};

fn invalid(message: &str) -> JarvisError {
    JarvisError::InvalidArguments {
        message: message.into(),
    }
}
fn storage(_: rusqlite::Error) -> JarvisError {
    // Do not leak note text, SQL parameters or private storage locations into logs.
    JarvisError::ExecutionFailed {
        message: "personal organizer storage is unavailable".into(),
    }
}
fn stored_count(db: &Connection) -> Result<i64, JarvisError> {
    db.query_row(
        "SELECT (SELECT count(*) FROM personal_items) + (SELECT count(*) FROM daily_occurrences)",
        [],
        |r| r.get(0),
    )
    .map_err(storage)
}

pub fn local_clock() -> serde_json::Value {
    let now = Local::now();
    serde_json::json!({"local_date": now.format("%Y-%m-%d").to_string(),
        "weekday": now.format("%A").to_string(), "local_time": now.to_rfc3339(),
        "timezone": "operating_system_local", "date_precision": "day",
        "scheduled_notifications": false})
}

fn date_at(value: &str, today: NaiveDate) -> Result<Option<String>, JarvisError> {
    let date = match value {
        "" | "none" => return Ok(None),
        "today" => today,
        "yesterday" => today
            .checked_sub_days(Days::new(1))
            .ok_or_else(|| invalid("date overflow"))?,
        "tomorrow" => today
            .checked_add_days(Days::new(1))
            .ok_or_else(|| invalid("date overflow"))?,
        _ => {
            let parsed = NaiveDate::parse_from_str(value, "%Y-%m-%d").map_err(|_| {
                invalid("date must be yesterday, today, tomorrow, none or YYYY-MM-DD")
            })?;
            if parsed.format("%Y-%m-%d").to_string() != value {
                return Err(invalid("date must use YYYY-MM-DD"));
            }
            parsed
        }
    };
    Ok(Some(date.format("%Y-%m-%d").to_string()))
}

fn text(value: &str, max: usize, required: bool) -> Result<(), JarvisError> {
    if value.chars().count() > max
        || (required && value.trim().is_empty())
        || value
            .chars()
            .any(|c| c.is_control() && c != '\n' && c != '\t')
    {
        return Err(invalid(
            "invalid personal item text length or control character",
        ));
    }
    Ok(())
}

#[derive(Debug, Clone, Serialize)]
pub struct Item {
    pub record_id: String,
    pub kind: String,
    pub title: String,
    pub body: String,
    pub due_date: Option<String>,
    pub status: String,
    pub version: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recurrence: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub occurrence_date: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddItem {
    pub kind: String,
    pub title: String,
    #[serde(default)]
    pub body: String,
    #[serde(default)]
    pub due_date: String,
    #[serde(default = "no_repeat")]
    pub recurrence: String,
}
fn no_repeat() -> String {
    "none".into()
}
impl AddItem {
    pub fn validate(&self) -> Result<(), JarvisError> {
        if !["task", "note"].contains(&self.kind.as_str()) {
            return Err(invalid("kind must be task or note"));
        }
        text(&self.title, 160, true)?;
        text(&self.body, 512, false)?;
        let due = date_at(&self.due_date, Local::now().date_naive())?;
        if !["none", "daily"].contains(&self.recurrence.as_str())
            || (self.kind == "note" && self.recurrence != "none")
        {
            return Err(invalid("only tasks support daily recurrence"));
        }
        if self.kind == "note" && due.is_some() {
            return Err(invalid("notes do not have due dates"));
        }
        Ok(())
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ListItems {
    pub kind: String,
    #[serde(default = "open")]
    pub status: String,
    #[serde(default = "all")]
    pub period: String,
    #[serde(default)]
    pub query: String,
    #[serde(default)]
    pub offset: usize,
}
fn open() -> String {
    "open".into()
}
fn all() -> String {
    "all".into()
}
impl ListItems {
    pub fn validate(&self) -> Result<(), JarvisError> {
        if !["task", "note"].contains(&self.kind.as_str())
            || !["open", "done", "archived", "all"].contains(&self.status.as_str())
            || self.offset > MAX_ITEMS as usize
        {
            return Err(invalid("invalid organizer list filter"));
        }
        text(&self.query, 160, false)?;
        if !["all", "undated", "overdue"].contains(&self.period.as_str())
            && date_at(&self.period, Local::now().date_naive())?.is_none()
        {
            return Err(invalid("invalid list period"));
        }
        if self.kind == "note" && self.period != "all" {
            return Err(invalid("notes require period all"));
        }
        Ok(())
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UpdateItem {
    pub record_id: String,
    pub expected_version: i64,
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub body: Option<String>,
    #[serde(default)]
    pub due_date: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub recurrence: Option<String>,
    #[serde(default)]
    pub occurrence_date: Option<String>,
}
impl UpdateItem {
    pub fn validate(&self) -> Result<(), JarvisError> {
        if Uuid::parse_str(&self.record_id).is_err() || self.expected_version < 1 {
            return Err(invalid("invalid personal item binding"));
        }
        if let Some(title) = &self.title {
            text(title, 160, true)?;
        }
        if let Some(body) = &self.body {
            text(body, 512, false)?;
        }
        if let Some(date) = &self.due_date {
            date_at(date, Local::now().date_naive())?;
        }
        if let Some(date) = &self.occurrence_date {
            let parsed = date_at(date, Local::now().date_naive())?;
            if parsed.as_deref() != Some(date) {
                return Err(invalid("occurrence binding requires an exact date"));
            }
        }
        if self
            .recurrence
            .as_ref()
            .is_some_and(|r| !["none", "daily"].contains(&r.as_str()))
        {
            return Err(invalid("recurrence must be none or daily"));
        }
        if let Some(status) = &self.status
            && !["open", "done", "archived"].contains(&status.as_str())
        {
            return Err(invalid("invalid item status"));
        }
        if self.title.is_none()
            && self.body.is_none()
            && self.due_date.is_none()
            && self.status.is_none()
            && self.recurrence.is_none()
        {
            return Err(invalid("at least one update is required"));
        }
        Ok(())
    }
}

#[derive(Debug, Serialize)]
pub struct ItemPage {
    pub local_date: String,
    pub period: String,
    pub total: usize,
    pub copyable_total: usize,
    pub offset: usize,
    pub next_offset: Option<usize>,
    pub items: Vec<Item>,
}

/// Lazy open: merely registering/listing tools never creates a personal database.
pub struct Organizer {
    path: Option<PathBuf>,
    connection: Mutex<Option<Connection>>,
}
impl Organizer {
    pub fn new(path: PathBuf) -> Self {
        Self {
            path: Some(path),
            connection: Mutex::new(None),
        }
    }
    pub fn in_memory() -> Self {
        Self {
            path: None,
            connection: Mutex::new(None),
        }
    }
    pub fn current_user() -> Result<Self, JarvisError> {
        #[cfg(windows)]
        let root = std::env::var_os("LOCALAPPDATA").map(PathBuf::from);
        #[cfg(not(windows))]
        let root = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/share")));
        root.map(|p| Self::new(p.join("JARVIS").join("organizer.sqlite3")))
            .ok_or_else(|| JarvisError::ConfigurationError {
                message: "local user data directory is unavailable".into(),
            })
    }
    fn with_db<T>(
        &self,
        action: impl FnOnce(&mut Connection) -> Result<T, JarvisError>,
    ) -> Result<T, JarvisError> {
        let mut guard = self.connection.lock().map_err(|_| JarvisError::Internal {
            message: "organizer lock unavailable".into(),
        })?;
        if guard.is_none() {
            let db = if let Some(path) = &self.path {
                let parent = path
                    .parent()
                    .ok_or_else(|| invalid("invalid storage directory"))?;
                std::fs::create_dir_all(parent).map_err(|_| JarvisError::ExecutionFailed {
                    message: "cannot create personal data directory".into(),
                })?;
                Connection::open(path).map_err(storage)?
            } else {
                Connection::open_in_memory().map_err(storage)?
            };
            db.busy_timeout(Duration::from_secs(2)).map_err(storage)?;
            let version: i64 = db
                .pragma_query_value(None, "user_version", |r| r.get(0))
                .map_err(storage)?;
            if version > 2 {
                return Err(JarvisError::ConfigurationError {
                    message: "personal database requires a newer JARVIS version".into(),
                });
            }
            if version == 0 {
                db.execute_batch("BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS personal_items (
                record_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('task','note')),
                title TEXT NOT NULL, body TEXT NOT NULL, due_date TEXT,
                status TEXT NOT NULL CHECK(status IN ('open','done','archived')), version INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                PRAGMA user_version=1; COMMIT;").map_err(storage)?;
            }
            if version < 2 {
                db.execute_batch("BEGIN IMMEDIATE;
                CREATE TABLE daily_rules (record_id TEXT PRIMARY KEY REFERENCES personal_items(record_id), start_date TEXT NOT NULL, end_date TEXT);
                CREATE TABLE daily_occurrences (record_id TEXT NOT NULL REFERENCES personal_items(record_id), occurrence_date TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(record_id, occurrence_date));
                CREATE TABLE task_copies (source_id TEXT NOT NULL, source_date TEXT NOT NULL, target_date TEXT NOT NULL, copied_id TEXT NOT NULL, PRIMARY KEY(source_id, source_date, target_date));
                PRAGMA user_version=2; COMMIT;").map_err(storage)?;
            }
            *guard = Some(db);
        }
        action(guard.as_mut().expect("initialized above"))
    }
    pub fn add(&self, args: &AddItem) -> Result<Item, JarvisError> {
        args.validate()?;
        let item = Item {
            record_id: Uuid::new_v4().to_string(),
            kind: args.kind.clone(),
            title: args.title.trim().into(),
            body: args.body.clone(),
            due_date: date_at(
                if args.recurrence == "daily" && ["", "none"].contains(&args.due_date.as_str()) {
                    "today"
                } else {
                    &args.due_date
                },
                Local::now().date_naive(),
            )?,
            status: "open".into(),
            version: 1,
            recurrence: (args.recurrence == "daily").then(|| "daily".into()),
            occurrence_date: None,
        };
        self.with_db(|db| {
            let tx = db
                .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
                .map_err(storage)?;
            let count = stored_count(&tx)?;
            if count >= MAX_ITEMS {
                return Err(invalid("personal item limit reached"));
            }
            let now = Local::now().to_rfc3339();
            tx.execute(
                "INSERT INTO personal_items VALUES (?1,?2,?3,?4,?5,?6,1,?7,?7)",
                params![
                    item.record_id,
                    item.kind,
                    item.title,
                    item.body,
                    item.due_date,
                    item.status,
                    now
                ],
            )
            .map_err(storage)?;
            if args.recurrence == "daily" {
                tx.execute(
                    "INSERT INTO daily_rules VALUES (?1,?2,NULL)",
                    params![item.record_id, item.due_date],
                )
                .map_err(storage)?;
            }
            tx.commit().map_err(storage)?;
            let mut item = item;
            if args.recurrence == "daily" {
                item.occurrence_date = item.due_date.clone();
            }
            Ok(item)
        })
    }
    pub fn list(&self, args: &ListItems) -> Result<ItemPage, JarvisError> {
        args.validate()?;
        let today = Local::now().date_naive();
        if self
            .path
            .as_ref()
            .map(|path| path.try_exists())
            .transpose()
            .map_err(|_| JarvisError::ExecutionFailed {
                message: "cannot access personal data directory".into(),
            })?
            == Some(false)
        {
            return Ok(ItemPage {
                local_date: today.to_string(),
                period: args.period.clone(),
                total: 0,
                copyable_total: 0,
                offset: args.offset,
                next_offset: None,
                items: Vec::new(),
            });
        }
        self.with_db(|db| {
            let matching = routines::matching(db, args, today)?;
            let total = matching.len();
            let copyable_total = matching
                .iter()
                .filter(|i| i.kind == "task" && i.status != "archived")
                .count();
            let items = matching.into_iter().skip(args.offset).take(5).collect();
            Ok(ItemPage {
                local_date: today.to_string(),
                period: args.period.clone(),
                total,
                copyable_total,
                offset: args.offset,
                next_offset: (args.offset + 5 < total).then_some(args.offset + 5),
                items,
            })
        })
    }
    pub fn update(&self, args: &UpdateItem) -> Result<Item, JarvisError> {
        args.validate()?;
        self.with_db(|db| {
            let tx = db
                .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
                .map_err(storage)?;
            let item = update_in(&tx, args)?;
            tx.commit().map_err(storage)?;
            Ok(item)
        })
    }
}
fn update_in(db: &Connection, args: &UpdateItem) -> Result<Item, JarvisError> {
    let mut item = db.query_row("SELECT record_id,kind,title,body,due_date,status,version FROM personal_items WHERE record_id=?1",
        [&args.record_id], item_row).optional().map_err(storage)?
        .ok_or_else(|| invalid("personal item no longer exists; list again"))?;
    if item.version != args.expected_version {
        return Err(invalid("personal item changed; list again before updating"));
    }
    if let Some((start, end)) = routines::rule(db, &item.record_id)? {
        let result = routines::update_daily(db, args, item, start, end)?;
        return Ok(result);
    }
    if args.occurrence_date.is_some() {
        return Err(invalid("ordinary task has no occurrence binding"));
    }
    if args.recurrence.as_deref() == Some("daily") {
        if item.kind != "task"
            || item.status != "open"
            || args.status.as_ref().is_some_and(|s| s != "open")
        {
            return Err(invalid("only open tasks can become daily"));
        }
        let start = match &args.due_date {
            Some(d) => date_at(d, Local::now().date_naive())?,
            None => item.due_date.clone(),
        }
        .unwrap_or_else(|| Local::now().date_naive().to_string());
        db.execute(
            "INSERT INTO daily_rules VALUES (?1,?2,NULL)",
            params![item.record_id, start],
        )
        .map_err(storage)?;
        item.due_date = Some(start.clone());
        item.occurrence_date = Some(start);
        item.recurrence = Some("daily".into());
    }
    if let Some(value) = &args.title {
        item.title = value.trim().into();
    }
    if let Some(value) = &args.body {
        item.body = value.clone();
    }
    if let Some(value) = &args.due_date {
        item.due_date = date_at(value, Local::now().date_naive())?;
    }
    if item.recurrence.as_deref() == Some("daily") {
        item.due_date = item.occurrence_date.clone();
    }
    if let Some(value) = &args.status {
        item.status = value.clone();
    }
    if item.kind == "note" && (item.due_date.is_some() || item.status == "done") {
        return Err(invalid("notes cannot have deadlines or completed status"));
    }
    item.version += 1;
    db.execute("UPDATE personal_items SET title=?1,body=?2,due_date=?3,status=?4,version=?5,updated_at=?6 WHERE record_id=?7",
        params![item.title,item.body,item.due_date,item.status,item.version,Local::now().to_rfc3339(),item.record_id]).map_err(storage)?;
    Ok(item)
}
fn item_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Item> {
    Ok(Item {
        record_id: row.get(0)?,
        kind: row.get(1)?,
        title: row.get(2)?,
        body: row.get(3)?,
        due_date: row.get(4)?,
        status: row.get(5)?,
        version: row.get(6)?,
        recurrence: None,
        occurrence_date: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capacity_failure_rolls_back_an_entire_copy_and_repeat_stop() {
        let store = Organizer::in_memory();
        for title in ["First", "Second"] {
            store
                .add(
                    &serde_json::from_value(
                        serde_json::json!({"kind":"task","title":title,"due_date":"yesterday"}),
                    )
                    .unwrap(),
                )
                .unwrap();
        }
        let daily = store
            .add(
                &serde_json::from_value(
                    serde_json::json!({"kind":"task","title":"Routine","recurrence":"daily"}),
                )
                .unwrap(),
            )
            .unwrap();
        store.with_db(|db| {
            db.execute_batch("WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<9996) INSERT INTO personal_items SELECT printf('filler-%d',x),'note','Fixture','','', 'open',1,'','' FROM n;").map_err(storage)?;
            Ok(())
        }).unwrap();
        let copy = CopyTasks {
            source_date: "yesterday".into(),
            target_date: "tomorrow".into(),
            expected_count: 2,
        };
        assert!(store.copy_tasks(&copy).is_err());
        let filter = ListItems {
            kind: "task".into(),
            status: "all".into(),
            period: "tomorrow".into(),
            query: String::new(),
            offset: 0,
        };
        assert_eq!(store.list(&filter).unwrap().total, 1); // only the pre-existing routine
        store.with_db(|db| {
            db.execute("INSERT INTO personal_items VALUES ('last','note','Fixture','','','open',1,'','')",[]).map_err(storage)?;
            Ok(())
        }).unwrap();
        let stop:UpdateItem=serde_json::from_value(serde_json::json!({"record_id":daily.record_id,"expected_version":1,"occurrence_date":daily.occurrence_date,"recurrence":"none"})).unwrap();
        assert!(store.update(&stop).is_err());
        assert_eq!(
            store.list(&filter).unwrap().items[0].recurrence.as_deref(),
            Some("daily")
        );
    }

    #[test]
    fn relative_dates_follow_calendar_boundaries_and_invalid_dates_fail() {
        for (date, tomorrow) in [
            ("2026-12-31", "2027-01-01"),
            ("2028-02-28", "2028-02-29"),
            ("2026-02-28", "2026-03-01"),
        ] {
            let date = NaiveDate::parse_from_str(date, "%Y-%m-%d").unwrap();
            assert_eq!(
                date_at("tomorrow", date).unwrap().as_deref(),
                Some(tomorrow)
            );
            let next = NaiveDate::parse_from_str(tomorrow, "%Y-%m-%d").unwrap();
            assert_eq!(
                date_at("yesterday", next).unwrap().as_deref(),
                Some(date.to_string().as_str())
            );
            assert_eq!(
                date_at("today", date).unwrap().as_deref(),
                Some(date.to_string().as_str())
            );
            assert!(date_at("none", date).unwrap().is_none());
            assert!(date_at("2026-02-29", date).is_err());
            assert!(date_at("2026-1-01", date).is_err());
            assert!(date_at("tomorrow at nine", date).is_err());
        }
    }

    #[test]
    fn daily_all_and_today_follow_a_changed_local_day_without_a_scheduler() {
        let store = Organizer::in_memory();
        let item=store.add(&serde_json::from_value(serde_json::json!({"kind":"task","title":"Plan day","recurrence":"daily","due_date":"2026-12-31"})).unwrap()).unwrap();
        store.update(&serde_json::from_value(serde_json::json!({"record_id":item.record_id,"expected_version":1,"occurrence_date":"2026-12-31","status":"done"})).unwrap()).unwrap();
        store
            .with_db(|db| {
                let day = NaiveDate::from_ymd_opt(2027, 1, 1).unwrap();
                for period in ["today", "all"] {
                    let args = ListItems {
                        kind: "task".into(),
                        status: "open".into(),
                        period: period.into(),
                        query: String::new(),
                        offset: 0,
                    };
                    let rows = routines::matching(db, &args, day)?;
                    assert_eq!(rows.len(), 1);
                    assert_eq!(rows[0].due_date.as_deref(), Some("2027-01-01"));
                }
                let args = ListItems {
                    kind: "task".into(),
                    status: "done".into(),
                    period: "all".into(),
                    query: String::new(),
                    offset: 0,
                };
                assert_eq!(
                    routines::matching(db, &args, day)?[0].due_date.as_deref(),
                    Some("2026-12-31")
                );
                Ok(())
            })
            .unwrap();
    }
}
