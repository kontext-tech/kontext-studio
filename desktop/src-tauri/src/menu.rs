use tauri::menu::{Menu, MenuEvent, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{AppHandle, Manager};

pub fn install(app: &tauri::App) -> tauri::Result<()> {
    let about = PredefinedMenuItem::about(app, Some("About Kontext Studio"), None)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit = PredefinedMenuItem::quit(app, Some("Quit Kontext Studio"))?;
    let open_data = MenuItem::with_id(app, "open-data", "Open Data Folder", true, None::<&str>)?;
    let open_logs = MenuItem::with_id(app, "open-logs", "Open Logs", true, None::<&str>)?;
    let docs = MenuItem::with_id(app, "docs", "Documentation", true, None::<&str>)?;
    let issues = MenuItem::with_id(app, "issues", "Report an Issue", true, None::<&str>)?;
    let updates = MenuItem::with_id(app, "updates", "Check for Updates…", true, None::<&str>)?;

    let app_menu = Submenu::with_items(app, "Kontext Studio", true, &[&about, &separator, &quit])?;
    let file_menu = Submenu::with_items(app, "File", true, &[&open_data, &open_logs])?;
    let help_menu = Submenu::with_items(app, "Help", true, &[&docs, &issues, &updates])?;
    let menu = Menu::with_items(app, &[&app_menu, &file_menu, &help_menu])?;
    app.set_menu(menu)?;
    Ok(())
}

pub fn handle(app: &AppHandle, event: MenuEvent) {
    match event.id().as_ref() {
        "open-data" => {
            if let Ok(home) = app.path().home_dir() {
                let _ = open::that(home.join(".kontext"));
            }
        }
        "open-logs" => open_logs(app),
        "docs" => {
            let _ = open::that("https://docs.kontext.tech/user-guide/desktop-app/");
        }
        "issues" => {
            let _ = open::that("https://github.com/kontext-tech/kontext-studio/issues");
        }
        "updates" => {
            let _ = open::that("https://github.com/kontext-tech/kontext-studio/releases/latest");
        }
        _ => {}
    }
}

#[cfg(target_os = "macos")]
fn open_logs(app: &AppHandle) {
    if let Ok(home) = app.path().home_dir() {
        let _ = open::that(home.join("Library").join("Logs").join("Kontext Studio"));
    }
}

#[cfg(target_os = "windows")]
fn open_logs(app: &AppHandle) {
    if let Ok(local) = app.path().local_data_dir() {
        let _ = open::that(local.join("Kontext").join("logs"));
    }
}

#[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
fn open_logs(app: &AppHandle) {
    if let Ok(directory) = app.path().app_log_dir() {
        let _ = open::that(directory);
    }
}
