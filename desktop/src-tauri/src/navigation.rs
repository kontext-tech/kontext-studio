use tauri::webview::NewWindowResponse;
use tauri::{Url, Wry};

/// Keep the webview on the local app and its splash page. Everything else is
/// handed to the system browser.
pub fn allow_navigation(url: &Url) -> bool {
    if is_local(url) {
        return true;
    }
    let _ = open::that(url.as_str());
    false
}

pub fn new_window(url: Url) -> NewWindowResponse<Wry> {
    if is_local(&url) {
        NewWindowResponse::Allow
    } else {
        let _ = open::that(url.as_str());
        NewWindowResponse::Deny
    }
}

fn is_local(url: &Url) -> bool {
    match url.scheme() {
        "tauri" | "about" => true,
        "http" | "https" => matches!(
            url.host_str(),
            Some("127.0.0.1" | "localhost" | "::1" | "tauri.localhost")
        ),
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::is_local;
    use tauri::Url;

    #[test]
    fn allows_local_origins() {
        for value in [
            "http://127.0.0.1:47800/",
            "http://localhost:47800/",
            "tauri://localhost/",
            "about:blank",
        ] {
            assert!(is_local(&Url::parse(value).unwrap()), "{value}");
        }
    }

    #[test]
    fn rejects_external_origins() {
        for value in [
            "https://example.com/",
            "http://192.168.1.2:8080/",
            "mailto:hello@example.com",
        ] {
            assert!(!is_local(&Url::parse(value).unwrap()), "{value}");
        }
    }
}
