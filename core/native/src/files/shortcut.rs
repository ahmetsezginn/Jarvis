//! Bounded metadata adapter, never an instruction to execute a .url file itself.
use crate::core::JarvisError;
use std::{fs::File, io::Read, path::Path};

const MAX_BYTES: u64 = 16 * 1024;

/// Constructible only by native shortcut validation; not an IPC/model argument.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GameShortcutTarget {
    steam_app_id: u32,
}
impl GameShortcutTarget {
    pub fn steam_app_id(&self) -> u32 {
        self.steam_app_id
    }
    pub(crate) fn uri(&self) -> String {
        format!("steam://rungameid/{}", self.steam_app_id)
    }
}

fn denied(reason: &str) -> JarvisError {
    JarvisError::PolicyDenied {
        reason: reason.into(),
    }
}

pub(super) fn read(path: &Path) -> Result<(File, GameShortcutTarget), JarvisError> {
    let mut options = File::options();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        // Keep parsed metadata stable; never follow a replaced final reparse point.
        options.share_mode(1).custom_flags(0x00200000);
    }
    let mut file = options
        .open(path)
        .map_err(|_| denied("Shortcut metadata is unavailable"))?;
    let metadata = file
        .metadata()
        .map_err(|_| denied("Shortcut metadata is unavailable"))?;
    if !metadata.is_file() || metadata.len() > MAX_BYTES {
        return Err(denied("Shortcut metadata exceeds its supported bounds"));
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 {
            return Err(denied("Linked shortcuts are excluded"));
        }
    }
    let mut bytes = Vec::new();
    (&mut file)
        .take(MAX_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| denied("Shortcut metadata could not be read"))?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err(denied("Shortcut metadata exceeds its supported bounds"));
    }
    let target = parse(&bytes)?;
    Ok((file, target))
}

fn parse(bytes: &[u8]) -> Result<GameShortcutTarget, JarvisError> {
    let text = if let Some(data) = bytes.strip_prefix(&[0xff, 0xfe]) {
        if !data.len().is_multiple_of(2) {
            return Err(denied("Malformed shortcut text"));
        }
        let units: Vec<_> = data
            .chunks_exact(2)
            .map(|p| u16::from_le_bytes([p[0], p[1]]))
            .collect();
        String::from_utf16(&units).map_err(|_| denied("Malformed shortcut text"))?
    } else {
        String::from_utf8(
            bytes
                .strip_prefix(&[0xef, 0xbb, 0xbf])
                .unwrap_or(bytes)
                .to_vec(),
        )
        .map_err(|_| denied("Unsupported shortcut text encoding"))?
    };
    if text
        .chars()
        .any(|c| c.is_control() && !matches!(c, '\r' | '\n' | '\t'))
    {
        return Err(denied("Malformed shortcut text"));
    }
    let mut in_shortcut = false;
    let mut seen_section = false;
    let mut url = None;
    for line in text.lines().map(str::trim) {
        if line.is_empty() || line.starts_with(';') {
            continue;
        }
        if let Some(section) = line.strip_prefix('[').and_then(|s| s.strip_suffix(']')) {
            in_shortcut = section.eq_ignore_ascii_case("InternetShortcut");
            if in_shortcut {
                if seen_section {
                    return Err(denied("Ambiguous shortcut sections"));
                }
                seen_section = true;
            }
        } else if let Some((key, value)) = line.split_once('=')
            && in_shortcut
            && key.trim().eq_ignore_ascii_case("URL")
        {
            if url.is_some() {
                return Err(denied("Ambiguous shortcut targets"));
            }
            url = Some(value.trim());
        }
    }
    let url = url.ok_or_else(|| denied("Shortcut has no supported target"))?;
    const PREFIX: &str = "steam://rungameid/";
    if !url
        .get(..PREFIX.len())
        .is_some_and(|p| p.eq_ignore_ascii_case(PREFIX))
    {
        return Err(denied("Only Steam game-launch shortcuts are supported"));
    }
    let digits = &url[PREFIX.len()..];
    if !(1..=10).contains(&digits.len()) || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return Err(denied(
            "Steam shortcut must contain only a game ID, without arguments",
        ));
    }
    let steam_app_id = digits
        .parse::<u32>()
        .ok()
        .filter(|id| *id > 0)
        .ok_or_else(|| denied("Invalid Steam game ID"))?;
    Ok(GameShortcutTarget { steam_app_id })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn standard_metadata_and_encodings_produce_only_a_normalized_game_target() {
        let text = "[{000214A0-0000-0000-C000-000000000046}]\r\nProp3=19,0\r\n[InternetShortcut]\r\nIDList=\r\nIconIndex=0\r\nURL=steam://rungameid/00000440\r\nIconFile=C:\\untrusted.exe\r\n";
        let utf16: Vec<_> = [0xff, 0xfe]
            .into_iter()
            .chain(text.encode_utf16().flat_map(u16::to_le_bytes))
            .collect();
        for bytes in [
            text.as_bytes().to_vec(),
            utf16,
            [b"\xef\xbb\xbf".as_slice(), text.as_bytes()].concat(),
        ] {
            let target = parse(&bytes).unwrap();
            assert_eq!(target.steam_app_id(), 440);
            assert_eq!(target.uri(), "steam://rungameid/440");
        }
    }
    #[test]
    fn protocols_arguments_duplicate_targets_and_non_app_game_ids_fail_closed() {
        for target in [
            "https://example.com",
            "file:///C:/bad.exe",
            "javascript:alert(1)",
            "steam://install/440",
            "steam://run/440",
            "steam://rungameid/0",
            "steam://rungameid/-1",
            "steam://rungameid/4294967296",
            "steam://rungameid/12345678901234567890",
            "steam://rungameid/440/",
            "steam://rungameid/440?x=1",
            "steam://rungameid/440#x",
            "steam://rungameid/440 -flag",
            "steam://rungameid/440%20-flag",
            "steam://rungameid/４４０",
            "steam://rungameid/440\0",
            "steam://rungameid/440\nURL=steam://rungameid/570",
        ] {
            assert!(
                parse(format!("[InternetShortcut]\nURL={target}\n").as_bytes()).is_err(),
                "{target:?}"
            );
        }
        for text in [
            "URL=steam://rungameid/440",
            "[Other]\nURL=steam://rungameid/440",
            "[InternetShortcut]\nURL=steam://rungameid/440\n[InternetShortcut]\nURL=steam://rungameid/570",
        ] {
            assert!(parse(text.as_bytes()).is_err());
        }
    }
}
