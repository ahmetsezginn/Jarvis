//! Daily occurrences are projected on reads, persisted only when explicitly edited.
//! There is no background scheduler and listing never creates task records.
use super::*;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecurrenceBinding {
    pub record_id: String,
    pub expected_version: i64,
    #[serde(default)]
    pub occurrence_date: Option<String>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SetRecurrence {
    pub items: Vec<RecurrenceBinding>,
    pub recurrence: String,
}
impl SetRecurrence {
    fn updates(&self) -> Vec<UpdateItem> {
        self.items
            .iter()
            .map(|i| UpdateItem {
                record_id: i.record_id.clone(),
                expected_version: i.expected_version,
                title: None,
                body: None,
                due_date: None,
                status: None,
                recurrence: Some(self.recurrence.clone()),
                occurrence_date: i.occurrence_date.clone(),
            })
            .collect()
    }
    pub fn validate(&self) -> Result<(), JarvisError> {
        if !(2..=5).contains(&self.items.len()) {
            return Err(invalid("recurrence group requires two to five saved tasks"));
        }
        let unique: std::collections::HashSet<_> =
            self.items.iter().map(|i| &i.record_id).collect();
        if unique.len() != self.items.len() {
            return Err(invalid(
                "recurrence group requires two to five distinct saved tasks",
            ));
        }
        for update in self.updates() {
            update.validate()?;
        }
        Ok(())
    }
}
impl Organizer {
    pub fn set_recurrence(&self, args: &SetRecurrence) -> Result<Vec<Item>, JarvisError> {
        args.validate()?;
        self.with_db(|db| {
            let tx = db
                .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
                .map_err(storage)?;
            let mut items = Vec::new();
            for update in args.updates() {
                let item = update_in(&tx, &update)?;
                if item.kind != "task" {
                    return Err(invalid("only tasks support grouped recurrence"));
                }
                items.push(item);
            }
            tx.commit().map_err(storage)?;
            Ok(items)
        })
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CopyTasks {
    pub source_date: String,
    pub target_date: String,
    pub expected_count: usize,
}
#[derive(Debug, Serialize)]
pub struct CopyResult {
    pub saved: bool,
    pub source_date: String,
    pub target_date: String,
    pub matched: usize,
    pub copied: usize,
    pub already_present: usize,
    pub recurrence_copied: bool,
    pub items: Vec<Item>,
}

fn copied_item(db: &Connection, id: &str, day: &str) -> Result<Item, JarvisError> {
    let item=db.query_row("SELECT record_id,kind,title,body,due_date,status,version FROM personal_items WHERE record_id=?1",[id],item_row).optional().map_err(storage)?.ok_or_else(||invalid("previously copied task no longer exists"))?;
    if let Some((start, end)) = rule(db, id)? {
        let day = day.max(&start);
        let day = end.as_deref().map_or(day, |last| day.min(last));
        project(db, item, day, &start, end.as_deref())?
            .ok_or_else(|| invalid("previously copied schedule is unavailable"))
    } else {
        Ok(item)
    }
}
impl CopyTasks {
    pub fn validate(&self) -> Result<(), JarvisError> {
        let today = Local::now().date_naive();
        let source = date_at(&self.source_date, today)?;
        let target = date_at(&self.target_date, today)?;
        if source.is_none()
            || target.is_none()
            || source == target
            || self.expected_count == 0
            || self.expected_count > 100
        {
            return Err(invalid(
                "copy requires different dates and at most 100 tasks",
            ));
        }
        Ok(())
    }
}

pub(super) fn rule(
    db: &Connection,
    id: &str,
) -> Result<Option<(String, Option<String>)>, JarvisError> {
    db.query_row(
        "SELECT start_date,end_date FROM daily_rules WHERE record_id=?1",
        [id],
        |r| Ok((r.get(0)?, r.get(1)?)),
    )
    .optional()
    .map_err(storage)
}

pub(super) fn project(
    db: &Connection,
    mut item: Item,
    day: &str,
    start: &str,
    end: Option<&str>,
) -> Result<Option<Item>, JarvisError> {
    if day < start || end.is_some_and(|e| day > e) {
        return Ok(None);
    }
    let changed = db.query_row("SELECT title,body,status FROM daily_occurrences WHERE record_id=?1 AND occurrence_date=?2", params![item.record_id,day], |r| Ok((r.get::<_,String>(0)?,r.get::<_,String>(1)?,r.get::<_,String>(2)?))).optional().map_err(storage)?;
    if let Some((title, body, status)) = changed {
        item.title = title;
        item.body = body;
        item.status = status;
    } else {
        item.status = "open".into();
    }
    item.due_date = Some(day.into());
    item.occurrence_date = Some(day.into());
    item.recurrence = Some(if end.is_some() { "none" } else { "daily" }.into());
    Ok(Some(item))
}

pub(super) fn matching(
    db: &Connection,
    args: &ListItems,
    today: NaiveDate,
) -> Result<Vec<Item>, JarvisError> {
    let today_text = today.to_string();
    let exact = if ["all", "overdue", "undated"].contains(&args.period.as_str()) {
        None
    } else {
        date_at(&args.period, today)?
    };
    let mut stmt=db.prepare("SELECT record_id,kind,title,body,due_date,status,version FROM personal_items WHERE kind=?1 ORDER BY due_date IS NULL,due_date,created_at,record_id LIMIT 10001").map_err(storage)?;
    let rows = stmt.query_map([&args.kind], item_row).map_err(storage)?;
    let words: Vec<_> = args
        .query
        .to_lowercase()
        .split_whitespace()
        .map(str::to_owned)
        .collect();
    let mut result = Vec::new();
    for row in rows {
        let item = row.map_err(storage)?;
        let mut candidates = Vec::new();
        if let Some((start, end)) = rule(db, &item.record_id)? {
            // Do not invent a backlog for days never edited or completed.
            if ["overdue", "undated"].contains(&args.period.as_str()) {
                continue;
            }
            let day = exact.as_deref().unwrap_or_else(|| {
                let day = if today_text.as_str() < start.as_str() {
                    start.as_str()
                } else {
                    today_text.as_str()
                };
                end.as_deref().map_or(day, |e| day.min(e))
            });
            let mut days = vec![day.to_owned()];
            if args.period == "all" {
                let mut history=db.prepare("SELECT occurrence_date FROM daily_occurrences WHERE record_id=?1 ORDER BY occurrence_date LIMIT 10000").map_err(storage)?;
                for date in history
                    .query_map([&item.record_id], |r| r.get::<_, String>(0))
                    .map_err(storage)?
                {
                    let date = date.map_err(storage)?;
                    if date != day {
                        days.push(date);
                    }
                }
            }
            for day in days {
                if let Some(projected) = project(db, item.clone(), &day, &start, end.as_deref())? {
                    candidates.push(projected);
                }
            }
        } else {
            candidates.push(item);
        }
        for item in candidates {
            let matches_date = match args.period.as_str() {
                "all" => true,
                "undated" => item.due_date.is_none(),
                "overdue" => item.due_date.as_ref().is_some_and(|d| d < &today_text),
                _ => item.due_date == exact,
            };
            let haystack = format!("{} {}", item.title, item.body).to_lowercase();
            if matches_date
                && (args.status == "all" || item.status == args.status)
                && words.iter().all(|w| haystack.contains(w))
            {
                result.push(item);
            }
        }
    }
    result.sort_by(|a, b| {
        (a.due_date.is_none(), &a.due_date).cmp(&(b.due_date.is_none(), &b.due_date))
    });
    Ok(result)
}

pub(super) fn update_daily(
    db: &Connection,
    args: &UpdateItem,
    item: Item,
    start: String,
    end: Option<String>,
) -> Result<Item, JarvisError> {
    let day = args
        .occurrence_date
        .as_deref()
        .ok_or_else(|| invalid("daily task requires a current occurrence binding; list again"))?;
    let mut occurrence = project(db, item, day, &start, end.as_deref())?
        .ok_or_else(|| invalid("occurrence is outside the saved daily schedule"))?;
    if args.due_date.is_some() {
        return Err(invalid(
            "daily occurrences cannot be rescheduled; copy to another date or stop repetition",
        ));
    }
    if args.recurrence.as_deref() == Some("daily") && end.is_some() {
        return Err(invalid(
            "stopped routines cannot be silently restarted; create a new daily task",
        ));
    }
    if let Some(title) = &args.title {
        occurrence.title = title.trim().into();
    }
    if let Some(body) = &args.body {
        occurrence.body = body.clone();
    }
    if let Some(status) = &args.status {
        occurrence.status = status.clone();
    }
    if args.recurrence.as_deref() == Some("none") {
        db.execute(
            "UPDATE daily_rules SET end_date=?1 WHERE record_id=?2",
            params![day, occurrence.record_id],
        )
        .map_err(storage)?;
        occurrence.recurrence = Some("none".into());
    }
    let history_count = stored_count(db)?;
    let exists:bool=db.query_row("SELECT EXISTS(SELECT 1 FROM daily_occurrences WHERE record_id=?1 AND occurrence_date=?2)",params![occurrence.record_id,day],|r|r.get(0)).map_err(storage)?;
    if history_count >= MAX_ITEMS && !exists {
        return Err(invalid("daily occurrence history limit reached"));
    }
    db.execute("INSERT INTO daily_occurrences VALUES (?1,?2,?3,?4,?5) ON CONFLICT(record_id,occurrence_date) DO UPDATE SET title=excluded.title,body=excluded.body,status=excluded.status",params![occurrence.record_id,day,occurrence.title,occurrence.body,occurrence.status]).map_err(storage)?;
    occurrence.version += 1;
    db.execute(
        "UPDATE personal_items SET version=?1,updated_at=?2 WHERE record_id=?3",
        params![
            occurrence.version,
            Local::now().to_rfc3339(),
            occurrence.record_id
        ],
    )
    .map_err(storage)?;
    Ok(occurrence)
}

impl Organizer {
    pub fn copy_tasks(&self, args: &CopyTasks) -> Result<CopyResult, JarvisError> {
        args.validate()?;
        let today = Local::now().date_naive();
        let source = date_at(&args.source_date, today)?.expect("validated date");
        let target = date_at(&args.target_date, today)?.expect("validated date");
        self.with_db(|db| {
            let tx=db.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate).map_err(storage)?;
            let filter=ListItems {kind:"task".into(),status:"all".into(),period:source.clone(),query:String::new(),offset:0};
            let rows:Vec<_>=matching(&tx,&filter,today)?.into_iter().filter(|i|i.status!="archived").collect();
            if rows.len()>100 || args.expected_count!=rows.len() { return Err(invalid("source task count differs from the request; list that day before copying")); }
            let count=stored_count(&tx)?;
            let mut copied=0;
            let mut already_present=0;
            let mut items=Vec::new();
            for item in &rows {
                let prior:Option<String>=tx.query_row("SELECT copied_id FROM task_copies WHERE source_id=?1 AND source_date=?2 AND target_date=?3",params![item.record_id,source,target],|r|r.get(0)).optional().map_err(storage)?;
                let daily_target=if let Some((start,end))=rule(&tx,&item.record_id)? { target>=start && end.is_none_or(|e|target<=e) } else { false };
                if prior.is_some() || daily_target {
                    already_present+=1;
                    if items.len()<5 {items.push(copied_item(&tx,prior.as_deref().unwrap_or(&item.record_id),&target)?);}
                    continue;
                }
                if count+copied as i64>=MAX_ITEMS { return Err(invalid("personal item limit reached; no tasks copied")); }
                let id=Uuid::new_v4().to_string();
                tx.execute("INSERT INTO personal_items VALUES (?1,'task',?2,?3,?4,'open',1,?5,?5)",params![id,item.title,item.body,target,Local::now().to_rfc3339()]).map_err(storage)?;
                tx.execute("INSERT INTO task_copies VALUES (?1,?2,?3,?4)",params![item.record_id,source,target,id]).map_err(storage)?;
                copied+=1;
                if items.len()<5 { items.push(copied_item(&tx,&id,&target)?); }
            }
            tx.commit().map_err(storage)?;
            Ok(CopyResult{saved:true,source_date:source,target_date:target,matched:rows.len(),copied,already_present,recurrence_copied:false,items})
        })
    }
}
