use crate::{
    core::{JarvisError, RiskLevel},
    files::{FileCatalog, FileKind, SearchArguments},
    tools::{Tool, ToolContext, ToolOutput},
};
use serde::Deserialize;
use serde_json::Value;
use std::sync::Arc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Empty {}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct EntryArguments {
    entry_id: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ListArguments {
    entry_id: String,
    #[serde(default)]
    offset: usize,
    #[serde(default = "default_limit")]
    limit: usize,
}
fn default_limit() -> usize {
    20
}
pub struct FileCatalogTool {
    name: &'static str,
    catalog: Arc<FileCatalog>,
}
impl FileCatalogTool {
    pub fn all(catalog: Arc<FileCatalog>) -> Vec<Arc<dyn Tool>> {
        [
            "file_catalog_status",
            "refresh_file_catalog",
            "search_files",
            "list_directory",
            "open_file",
            "open_directory",
            "open_containing_folder",
        ]
        .into_iter()
        .map(|name| {
            Arc::new(Self {
                name,
                catalog: catalog.clone(),
            }) as Arc<dyn Tool>
        })
        .collect()
    }
}
fn parse<T: serde::de::DeserializeOwned>(value: &Value) -> Result<T, JarvisError> {
    serde_json::from_value(value.clone()).map_err(|e| JarvisError::InvalidArguments {
        message: e.to_string(),
    })
}
fn bounds(offset: usize, limit: usize) -> Result<(), JarvisError> {
    if offset > 20_000 || !(1..=20).contains(&limit) {
        return Err(JarvisError::InvalidArguments {
            message: "offset <= 20000 and limit 1..20 required".into(),
        });
    }
    Ok(())
}
impl Tool for FileCatalogTool {
    fn name(&self) -> &'static str {
        self.name
    }
    fn risk_level(&self) -> RiskLevel {
        if self.name.starts_with("open_") {
            RiskLevel::Low
        } else {
            RiskLevel::ReadOnly
        }
    }
    fn validate(&self, arguments: &Value) -> Result<(), JarvisError> {
        match self.name {
            "file_catalog_status" | "refresh_file_catalog" => {
                let _: Empty = parse(arguments)?;
            }
            "search_files" => {
                let args: SearchArguments = parse(arguments)?;
                bounds(args.offset, args.limit)?;
                if args.query.len() > 256
                    || args.exclude_ids.len() > 100
                    || args
                        .exclude_ids
                        .iter()
                        .any(|id| id.is_empty() || id.len() > 128)
                    || (!args.recursive && args.folder_id.is_none())
                    || args.query.chars().any(char::is_control)
                    || args.extension.as_ref().is_some_and(|e| {
                        e.len() > 16
                            || !e
                                .trim_start_matches('.')
                                .chars()
                                .all(|c| c.is_ascii_alphanumeric())
                    })
                    || matches!((args.modified_after,args.modified_before),(Some(a),Some(b)) if a>b)
                {
                    return Err(JarvisError::InvalidArguments {
                        message: "invalid bounded file search".into(),
                    });
                }
            }
            "list_directory" => {
                let args: ListArguments = parse(arguments)?;
                bounds(args.offset, args.limit)?;
                self.catalog.checked_entry(&args.entry_id)?;
            }
            _ => {
                let args: EntryArguments = parse(arguments)?;
                self.catalog.checked_entry(&args.entry_id)?;
            }
        }
        Ok(())
    }
    fn execute(&self, context: &ToolContext, arguments: &Value) -> Result<ToolOutput, JarvisError> {
        self.validate(arguments)?;
        match self.name {
            "file_catalog_status" => self.catalog.status(),
            "refresh_file_catalog" => self.catalog.refresh(),
            "search_files" => self.catalog.search(&parse(arguments)?),
            "list_directory" => {
                let args: ListArguments = parse(arguments)?;
                self.catalog.list(&args.entry_id, args.offset, args.limit)
            }
            "open_containing_folder" => {
                let args: EntryArguments = parse(arguments)?;
                self.catalog.open_parent(&args.entry_id, context.platform())
            }
            _ => {
                let args: EntryArguments = parse(arguments)?;
                self.catalog.open(
                    &args.entry_id,
                    if self.name == "open_file" {
                        FileKind::File
                    } else {
                        FileKind::Directory
                    },
                    context.platform(),
                )
            }
        }
    }
}
