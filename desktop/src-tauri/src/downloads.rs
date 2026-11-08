use std::path::{Path, PathBuf};

use tauri::webview::DownloadEvent;
use tauri::{Manager, Webview, Wry};

/// Save a blob handed over by the app page. WKWebView does not honor
/// `<a download>` for `blob:` URLs, so the page routes blob downloads here.
#[tauri::command]
pub fn save_bytes(name: String, bytes: Vec<u8>) -> Result<Option<String>, String> {
    let name = sanitize_name(&name);
    let Some(path) = rfd::FileDialog::new().set_file_name(&name).save_file() else {
        return Ok(None);
    };
    std::fs::write(&path, bytes).map_err(|error| error.to_string())?;
    Ok(Some(path.display().to_string()))
}

pub fn handle_download(webview: Webview<Wry>, event: DownloadEvent<'_>) -> bool {
    match event {
        DownloadEvent::Requested { url, destination } => {
            let name = url
                .path_segments()
                .and_then(|mut segments| segments.next_back())
                .filter(|segment| !segment.is_empty())
                .unwrap_or("download");
            let name = sanitize_name(name);
            let Ok(directory) = webview.app_handle().path().download_dir() else {
                return false;
            };
            *destination = unique_path(directory.join(name));
            true
        }
        DownloadEvent::Finished { success, .. } => {
            if !success {
                eprintln!("Kontext download did not finish");
            }
            true
        }
        _ => true,
    }
}

fn sanitize_name(name: &str) -> String {
    let base = Path::new(name)
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("download");
    let cleaned: String = base
        .chars()
        .filter(|ch| !ch.is_control())
        .map(|ch| {
            if matches!(ch, '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|') {
                '_'
            } else {
                ch
            }
        })
        .collect();
    let trimmed = cleaned.trim().trim_matches('.').to_string();
    if trimmed.is_empty() {
        "download".to_string()
    } else {
        trimmed
    }
}

fn unique_path(path: PathBuf) -> PathBuf {
    if !path.exists() {
        return path;
    }
    let stem = path
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("download");
    let extension = path.extension().and_then(|value| value.to_str());
    for index in 1..10_000 {
        let candidate = match extension {
            Some(ext) => path.with_file_name(format!("{stem} ({index}).{ext}")),
            None => path.with_file_name(format!("{stem} ({index})")),
        };
        if !candidate.exists() {
            return candidate;
        }
    }
    path
}

#[cfg(test)]
mod tests {
    use super::sanitize_name;

    #[test]
    fn strips_path_components() {
        assert_eq!(sanitize_name("../../etc/passwd"), "passwd");
        assert_eq!(sanitize_name("/tmp/report.csv"), "report.csv");
    }

    #[test]
    fn replaces_invalid_characters() {
        assert_eq!(sanitize_name("a:b*c?.csv"), "a_b_c_.csv");
        assert_eq!(sanitize_name("a<b>c|d.csv"), "a_b_c_d.csv");
    }

    #[test]
    fn falls_back_when_empty() {
        assert_eq!(sanitize_name("..."), "download");
        assert_eq!(sanitize_name("\n\t"), "download");
    }
}
