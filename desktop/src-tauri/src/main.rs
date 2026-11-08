#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod downloads;
mod menu;
mod navigation;

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .setup(|app| {
            menu::install(app)?;

            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                    .title("Kontext Studio")
                    .inner_size(1440.0, 900.0)
                    .min_inner_size(1024.0, 700.0)
                    .center()
                    .visible(false)
                    .initialization_script(include_str!("inject.js"))
                    .on_navigation(navigation::allow_navigation)
                    .on_new_window(|url, _features| navigation::new_window(url))
                    .on_download(downloads::handle_download)
                    .build()?;

            backend::start(app.handle().clone(), window)?;
            Ok(())
        })
        .on_menu_event(menu::handle)
        .invoke_handler(tauri::generate_handler![downloads::save_bytes])
        .build(tauri::generate_context!())
        .expect("error while building Kontext Studio")
        .run(|_app, event| {
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                backend::shutdown();
            }
        });
}
