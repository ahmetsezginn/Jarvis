use crate::core::JarvisError;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{HashMap, HashSet, VecDeque},
    fs,
    path::{Path, PathBuf},
    sync::{Mutex, RwLock},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use uuid::Uuid;

const MAX_ENTRIES: usize = 20_000;
const MAX_DEPTH: usize = 16;
const SCAN_BUDGET: Duration = Duration::from_secs(2);

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct FileRoot {
    pub name: String,
    pub path: PathBuf,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FileKind {
    File,
    Directory,
}
#[derive(Debug, Clone, Serialize)]
pub struct FileEntry {
    pub entry_id: String,
    pub name: String,
    pub kind: FileKind,
    pub location: String,
    pub size_bytes: u64,
    pub modified_unix: Option<u64>,
    #[serde(skip)]
    path: PathBuf,
    #[serde(skip)]
    modified: Option<SystemTime>,
    #[serde(skip)]
    created: Option<SystemTime>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SearchArguments {
    pub query: String,
    pub kind: Option<FileKind>,
    pub folder_id: Option<String>,
    pub extension: Option<String>,
    pub category: Option<FileCategory>,
    #[serde(default = "recursive_default")]
    pub recursive: bool,
    #[serde(default)]
    pub exclude_ids: Vec<String>,
    pub modified_after: Option<u64>,
    pub modified_before: Option<u64>,
    #[serde(default)]
    pub sort: FileSort,
    #[serde(default)]
    pub offset: usize,
    #[serde(default = "default_limit")]
    pub limit: usize,
}
fn recursive_default() -> bool {
    true
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FileCategory {
    Text,
    Document,
    Image,
    Spreadsheet,
    Presentation,
}
impl FileCategory {
    fn matches(&self, path: &Path) -> bool {
        let ext = path
            .extension()
            .unwrap_or_default()
            .to_string_lossy()
            .to_lowercase();
        match self {
            Self::Text => matches!(ext.as_str(), "txt" | "md" | "rtf" | "doc" | "docx" | "odt"),
            Self::Document => matches!(
                ext.as_str(),
                "txt"
                    | "md"
                    | "rtf"
                    | "doc"
                    | "docx"
                    | "odt"
                    | "pdf"
                    | "xlsx"
                    | "xls"
                    | "pptx"
                    | "ppt"
            ),
            Self::Image => matches!(
                ext.as_str(),
                "png" | "jpg" | "jpeg" | "webp" | "gif" | "bmp" | "tiff"
            ),
            Self::Spreadsheet => matches!(ext.as_str(), "xlsx" | "xls" | "csv" | "ods"),
            Self::Presentation => matches!(ext.as_str(), "pptx" | "ppt" | "odp" | "pdf" | "txt"),
        }
    }
}
#[derive(Debug, Default, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FileSort {
    #[default]
    Name,
    Newest,
    Largest,
}
fn default_limit() -> usize {
    20
}
#[derive(Default)]
struct Snapshot {
    entries: HashMap<String, FileEntry>,
    refreshed_unix: Option<u64>,
    partial: bool,
    inaccessible: usize,
    excluded: usize,
}
pub struct FileCatalog {
    roots: Vec<FileRoot>,
    snapshot: RwLock<Snapshot>,
    refresh_lock: Mutex<()>,
}
impl FileCatalog {
    pub fn new(roots: Vec<FileRoot>) -> Result<Self, JarvisError> {
        if roots.len() > 16
            || roots.iter().any(|r| {
                r.name.trim().is_empty()
                    || r.name.len() > 256
                    || !r.path.is_absolute()
                    || r.path.parent().is_none()
            })
        {
            return Err(invalid(
                "file roots require names and absolute non-volume paths (maximum 16)",
            ));
        }
        Ok(Self {
            roots,
            snapshot: RwLock::new(Snapshot::default()),
            refresh_lock: Mutex::new(()),
        })
    }
    fn ensure_ready(&self) -> Result<(), JarvisError> {
        if self
            .snapshot
            .read()
            .map_err(lock_error)?
            .refreshed_unix
            .is_none()
        {
            self.refresh()?;
        }
        Ok(())
    }
    pub fn refresh(&self) -> Result<Value, JarvisError> {
        let _guard = self.refresh_lock.lock().map_err(lock_error)?;
        let started = Instant::now();
        let mut next = Snapshot::default();
        let mut queue = VecDeque::new();
        let mut seen = HashSet::new();
        for root in &self.roots {
            match checked_root(&root.path) {
                Ok(path) => queue.push_back((path, root.name.clone(), 0)),
                Err(_) => {
                    next.inaccessible += 1;
                    next.partial = true;
                }
            }
        }
        let mut visited = 0;
        'scan: while let Some((path, name, depth)) = queue.pop_front() {
            if !seen.insert(path.clone()) {
                continue;
            }
            if started.elapsed() >= SCAN_BUDGET || visited >= MAX_ENTRIES {
                next.partial = true;
                break;
            }
            let metadata = match fs::symlink_metadata(&path) {
                Ok(m) => m,
                Err(_) => {
                    next.inaccessible += 1;
                    next.partial = true;
                    continue;
                }
            };
            if linked(&metadata) {
                next.excluded += 1;
                continue;
            }
            insert(&mut next, path.clone(), name, &metadata);
            visited += 1;
            if !metadata.is_dir() {
                continue;
            }
            if depth >= MAX_DEPTH {
                next.partial = true;
                continue;
            }
            let children = match fs::read_dir(&path) {
                Ok(v) => v,
                Err(_) => {
                    next.inaccessible += 1;
                    next.partial = true;
                    continue;
                }
            };
            for child in children {
                if started.elapsed() >= SCAN_BUDGET || visited + queue.len() >= MAX_ENTRIES {
                    next.partial = true;
                    break 'scan;
                }
                let child = match child {
                    Ok(c) => c,
                    Err(_) => {
                        next.inaccessible += 1;
                        next.partial = true;
                        continue;
                    }
                };
                let name = child.file_name().to_string_lossy().into_owned();
                let metadata = match fs::symlink_metadata(child.path()) {
                    Ok(m) => m,
                    Err(_) => {
                        next.inaccessible += 1;
                        next.partial = true;
                        continue;
                    }
                };
                if excluded_name(&name) || linked(&metadata) || cloud_only(&metadata) {
                    next.excluded += 1;
                    continue;
                }
                queue.push_back((child.path(), name, depth + 1));
            }
        }
        if !self.roots.is_empty() && next.entries.is_empty() && next.inaccessible > 0 {
            return Err(JarvisError::ExecutionFailed {
                message: "no configured file root could be scanned; previous catalog retained"
                    .into(),
            });
        }
        next.refreshed_unix = Some(now());
        *self.snapshot.write().map_err(lock_error)? = next;
        self.status()
    }
    pub fn status(&self) -> Result<Value, JarvisError> {
        let s = self.snapshot.read().map_err(lock_error)?;
        let files = s
            .entries
            .values()
            .filter(|e| e.kind == FileKind::File)
            .count();
        Ok(
            json!({"roots": self.roots, "indexed": s.refreshed_unix.is_some(), "refreshed_unix": s.refreshed_unix, "files": files, "directories": s.entries.len()-files, "partial": s.partial, "inaccessible": s.inaccessible, "excluded": s.excluded, "scope": "configured_roots_only", "contents_read": false}),
        )
    }
    pub fn search(&self, args: &SearchArguments) -> Result<Value, JarvisError> {
        self.ensure_ready()?;
        let folder = args
            .folder_id
            .as_ref()
            .map(|id| self.checked_entry(id))
            .transpose()?;
        if folder
            .as_ref()
            .is_some_and(|e| e.kind != FileKind::Directory)
        {
            return Err(invalid("folder_id must identify a directory"));
        }
        if !args.recursive && folder.is_none() {
            return Err(invalid("direct search requires a catalog-backed folder_id"));
        }
        if args.exclude_ids.len() > 100 || args.exclude_ids.iter().any(|id| id.len() > 128) {
            return Err(invalid("invalid bounded exclusions"));
        }
        let s = self.snapshot.read().map_err(lock_error)?;
        let query = normalized(&args.query);
        let query_words: Vec<_> = query
            .split(|c: char| !c.is_alphanumeric())
            .filter(|s| !s.is_empty())
            .collect();
        let mut values: Vec<_> = s
            .entries
            .values()
            .filter(|e| {
                (query.is_empty()
                    || query == "*"
                    || name_matches(&e.name, &query, &query_words)
                    || e.path.file_name().is_some_and(|name| {
                        name_matches(&name.to_string_lossy(), &query, &query_words)
                    }))
                    && args.kind.is_none_or(|kind| e.kind == kind)
                    && !args.exclude_ids.contains(&e.entry_id)
                    && args
                        .category
                        .as_ref()
                        .is_none_or(|c| e.kind == FileKind::File && c.matches(&e.path))
                    && folder.as_ref().is_none_or(|f| {
                        if args.recursive {
                            e.path != f.path && e.path.starts_with(&f.path)
                        } else {
                            e.path.parent() == Some(f.path.as_path())
                        }
                    })
                    && args.extension.as_ref().is_none_or(|ext| {
                        e.path.extension().is_some_and(|v| {
                            v.to_string_lossy()
                                .eq_ignore_ascii_case(ext.trim_start_matches('.'))
                        })
                    })
                    && args
                        .modified_after
                        .is_none_or(|t| e.modified_unix.is_some_and(|m| m >= t))
                    && args
                        .modified_before
                        .is_none_or(|t| e.modified_unix.is_some_and(|m| m <= t))
            })
            .collect();
        values.sort_by(|a, b| match args.sort {
            FileSort::Name => normalized(&a.name)
                .cmp(&normalized(&b.name))
                .then(a.location.cmp(&b.location)),
            FileSort::Newest => b
                .modified_unix
                .cmp(&a.modified_unix)
                .then(a.location.cmp(&b.location)),
            FileSort::Largest => b
                .size_bytes
                .cmp(&a.size_bytes)
                .then(a.location.cmp(&b.location)),
        });
        Ok(
            json!({"entries": values.iter().skip(args.offset).take(args.limit).collect::<Vec<_>>(), "total": values.len(), "offset": args.offset, "partial": s.partial, "refreshed_unix": s.refreshed_unix}),
        )
    }
    pub fn list(&self, id: &str, offset: usize, limit: usize) -> Result<Value, JarvisError> {
        let folder = self.checked_entry(id)?;
        if folder.kind != FileKind::Directory {
            return Err(invalid("entry is not a directory"));
        }
        let s = self.snapshot.read().map_err(lock_error)?;
        let mut entries: Vec<_> = s
            .entries
            .values()
            .filter(|e| e.path.parent() == Some(folder.path.as_path()))
            .collect();
        entries.sort_by(|a, b| a.location.cmp(&b.location));
        Ok(
            json!({"folder": folder, "entries": entries.iter().skip(offset).take(limit).collect::<Vec<_>>(), "total": entries.len(), "offset": offset, "partial": s.partial, "refreshed_unix": s.refreshed_unix}),
        )
    }
    pub fn checked_entry(&self, id: &str) -> Result<FileEntry, JarvisError> {
        let entry = self
            .snapshot
            .read()
            .map_err(lock_error)?
            .entries
            .get(id)
            .cloned()
            .ok_or_else(|| invalid("unknown or expired file catalog ID; search again"))?;
        // Revalidate every component: an ancestor replaced with a junction cannot escape scope.
        let root = self
            .roots
            .iter()
            .filter_map(|r| checked_root(&r.path).ok())
            .find(|r| entry.path.starts_with(r))
            .ok_or_else(|| denied("entry is outside active roots"))?;
        let mut cursor = entry.path.as_path();
        loop {
            let metadata = fs::symlink_metadata(cursor)
                .map_err(|_| invalid("catalog entry is stale; refresh and search again"))?;
            if linked(&metadata) || cloud_only(&metadata) {
                return Err(denied("linked or cloud-only targets are excluded"));
            }
            if cursor == root {
                break;
            }
            cursor = cursor
                .parent()
                .ok_or_else(|| denied("invalid catalog ancestry"))?;
        }
        let metadata = fs::metadata(&entry.path).map_err(|_| invalid("catalog entry is stale"))?;
        if metadata.created().ok() != entry.created
            || metadata.is_dir() != (entry.kind == FileKind::Directory)
            || (entry.kind == FileKind::File
                && (metadata.len() != entry.size_bytes
                    || metadata.modified().ok() != entry.modified))
        {
            return Err(invalid("catalog entry changed; refresh and search again"));
        }
        let canonical = entry
            .path
            .canonicalize()
            .map_err(|_| invalid("catalog entry is stale"))?;
        if canonical != entry.path {
            return Err(denied("catalog target changed"));
        }
        Ok(entry)
    }
    pub fn open(
        &self,
        id: &str,
        kind: FileKind,
        platform: &dyn crate::platform::DesktopPlatform,
    ) -> Result<Value, JarvisError> {
        let entry = self.checked_entry(id)?;
        if entry.kind != kind {
            return Err(invalid("catalog entry has the wrong kind"));
        }
        if kind == FileKind::Directory {
            platform.open_folder(&entry.path)?;
        } else {
            if !document_extension(&entry.path) {
                return Err(denied(
                    "only supported document/media types can be opened; programs, scripts and shortcuts are excluded",
                ));
            }
            platform.open_file(&entry.path)?;
        }
        Ok(json!({"opened":true,"entry":entry}))
    }
    pub fn open_with_app(
        &self,
        id: &str,
        app: &crate::apps::DiscoveredApplication,
        platform: &dyn crate::platform::DesktopPlatform,
    ) -> Result<Value, JarvisError> {
        let entry = self.checked_entry(id)?;
        if entry.kind != FileKind::File
            || !entry
                .path
                .extension()
                .is_some_and(|e| e.eq_ignore_ascii_case("pdf"))
        {
            return Err(denied(
                "browser file opening supports local PDF documents only",
            ));
        }
        if !matches!(
            app.canonical_name().to_ascii_lowercase().as_str(),
            "google chrome" | "microsoft edge"
        ) {
            return Err(denied(
                "selected application has no supported local PDF adapter",
            ));
        }
        platform.open_file_with_app(&entry.path, app)?;
        Ok(
            json!({"opened":true,"entry":entry,"app_id":app.app_id(),"application":app.canonical_name()}),
        )
    }
    pub fn open_parent(
        &self,
        id: &str,
        platform: &dyn crate::platform::DesktopPlatform,
    ) -> Result<Value, JarvisError> {
        let entry = self.checked_entry(id)?;
        let parent = entry
            .path
            .parent()
            .ok_or_else(|| invalid("entry has no parent"))?;
        let parent_id = self
            .snapshot
            .read()
            .map_err(lock_error)?
            .entries
            .values()
            .find(|e| e.path == parent)
            .map(|e| e.entry_id.clone())
            .ok_or_else(|| denied("parent is outside the catalog"))?;
        self.open(&parent_id, FileKind::Directory, platform)
    }
}

fn name_matches(name: &str, query: &str, words: &[&str]) -> bool {
    let name = normalized(name);
    name.contains(query)
        || (!words.is_empty()
            && words.iter().all(|word| {
                name.split(|c: char| !c.is_alphanumeric())
                    .any(|part| word_matches(part, word))
            }))
}
fn word_matches(part: &str, query: &str) -> bool {
    if part == query {
        return true;
    }
    // Name tokens may include suffixes while a human clue uses a root (or vice versa).
    // This is generic prefix matching, not language/document-specific rewriting.
    // Short acronyms and numeric versions must retain exact token identity.
    let (short, long) = if part.len() <= query.len() {
        (part, query)
    } else {
        (query, part)
    };
    short.chars().count() >= 4
        && !short.chars().any(|c| c.is_numeric())
        && !long.chars().any(|c| c.is_numeric())
        && long.starts_with(short)
}
fn insert(snapshot: &mut Snapshot, path: PathBuf, name: String, metadata: &fs::Metadata) {
    let modified = metadata.modified().ok();
    let entry = FileEntry {
        entry_id: Uuid::new_v4().to_string(),
        name,
        kind: if metadata.is_dir() {
            FileKind::Directory
        } else {
            FileKind::File
        },
        location: path.display().to_string(),
        size_bytes: if metadata.is_file() {
            metadata.len()
        } else {
            0
        },
        modified_unix: modified
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok().map(|d| d.as_secs())),
        modified,
        created: metadata.created().ok(),
        path,
    };
    snapshot.entries.insert(entry.entry_id.clone(), entry);
}
fn checked_root(path: &Path) -> Result<PathBuf, JarvisError> {
    for ancestor in path.ancestors() {
        if ancestor.file_name().is_some_and(|v| {
            matches!(
                v.to_string_lossy().to_lowercase().as_str(),
                ".ssh" | ".aws" | ".azure" | ".gnupg" | "credentials" | "secrets"
            )
        }) {
            return Err(denied("sensitive roots are excluded"));
        }
        let metadata =
            fs::symlink_metadata(ancestor).map_err(|_| invalid("root is unavailable"))?;
        if linked(&metadata) {
            return Err(denied("root contains a link or junction"));
        }
    }
    if !path.is_dir() {
        return Err(invalid("root is not a directory"));
    }
    path.canonicalize()
        .map_err(|_| invalid("root is unavailable"))
}
fn excluded_name(name: &str) -> bool {
    let name = name.to_lowercase();
    name.starts_with('.')
        || matches!(
            name.as_str(),
            "node_modules"
                | "target"
                | "models"
                | "__pycache__"
                | "appdata"
                | "$recycle.bin"
                | "system volume information"
                | "credentials"
                | "secrets"
        )
        || name.ends_with(".pem")
        || name.ends_with(".key")
        || name.ends_with(".pfx")
        || name.ends_with(".kdbx")
}
fn linked(metadata: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        metadata.file_attributes() & 0x400 != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}
fn cloud_only(metadata: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        metadata.file_attributes() & (0x1000 | 0x40000 | 0x400000) != 0
    }
    #[cfg(not(windows))]
    {
        let _ = metadata;
        false
    }
}
fn document_extension(path: &Path) -> bool {
    path.extension().is_some_and(|e| {
        matches!(
            e.to_string_lossy().to_lowercase().as_str(),
            "txt"
                | "md"
                | "pdf"
                | "docx"
                | "xlsx"
                | "pptx"
                | "csv"
                | "tsv"
                | "rtf"
                | "odt"
                | "ods"
                | "odp"
                | "png"
                | "jpg"
                | "jpeg"
                | "gif"
                | "webp"
                | "bmp"
                | "mp3"
                | "wav"
                | "flac"
                | "mp4"
                | "mkv"
                | "avi"
        )
    })
}
pub fn normalized(value: &str) -> String {
    value
        .to_lowercase()
        .chars()
        .filter(|c| *c != '\u{307}')
        .map(|c| match c {
            'ı' => 'i',
            'ç' => 'c',
            'ğ' => 'g',
            'ö' => 'o',
            'ş' => 's',
            'ü' => 'u',
            _ => c,
        })
        .collect()
}
fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}
fn invalid(message: &str) -> JarvisError {
    JarvisError::InvalidArguments {
        message: message.into(),
    }
}
fn denied(reason: &str) -> JarvisError {
    JarvisError::PolicyDenied {
        reason: reason.into(),
    }
}
fn lock_error<T>(_: std::sync::PoisonError<T>) -> JarvisError {
    JarvisError::Internal {
        message: "file catalog lock poisoned".into(),
    }
}
