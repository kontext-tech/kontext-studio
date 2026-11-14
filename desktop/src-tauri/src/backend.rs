use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
#[cfg(unix)]
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use serde::Deserialize;
use tauri::{AppHandle, Manager, WebviewWindow};

static BACKEND: Mutex<Option<Child>> = Mutex::new(None);
static SHUTTING_DOWN: AtomicBool = AtomicBool::new(false);

const READY_MARKER: &str = "@@KONTEXT_READY@@";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(120);
const LOG_LIMIT_BYTES: u64 = 10 * 1024 * 1024;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReadyPayload {
    port: u16,
    pid: u32,
    launch_url: String,
}

pub fn start(app: AppHandle, window: WebviewWindow) -> tauri::Result<()> {
    let resource_dir = app.path().resource_dir()?;
    let python = python_executable(&resource_dir);
    if !python.is_file() {
        let _ = window.show();
        show_error(
            &app,
            "The bundled Python runtime is missing. Reinstall Kontext Studio.",
        );
        return Ok(());
    }

    let wheelhouse = resource_dir.join("wheelhouse");
    let log_path = log_path(&app)?;
    rotate_log(&log_path);
    let home = app.path().home_dir()?;

    let mut child = Command::new(&python)
        .args([
            "-E",
            "-s",
            "-B",
            "-u",
            "-m",
            "kontext.studio",
            "desktop",
            "--preferred-port",
            "47800",
            "--parent-pid",
            &std::process::id().to_string(),
        ])
        .env("KONTEXT_PYTHON_RUNTIME_WHEELHOUSE", &wheelhouse)
        .current_dir(home)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| {
            let _ = window.show();
            show_error(
                &app,
                &format!("Could not start the Kontext server: {error}"),
            );
            tauri::Error::Io(error)
        })?;

    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    *lock_backend() = Some(child);

    let ready = Arc::new(AtomicBool::new(false));

    if let Some(stdout) = stdout {
        let app_handle = app.clone();
        let log_path = log_path.clone();
        let ready_flag = ready.clone();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                let Some(json) = line.strip_prefix(READY_MARKER) else {
                    append_log(&log_path, &line);
                    continue;
                };
                let Ok(payload) = serde_json::from_str::<ReadyPayload>(json) else {
                    append_log(&log_path, "invalid ready payload");
                    continue;
                };
                append_log(
                    &log_path,
                    &format!(
                        "server ready on port {} (pid {})",
                        payload.port, payload.pid
                    ),
                );
                ready_flag.store(true, Ordering::SeqCst);
                let app_for_main = app_handle.clone();
                let _ = app_handle.run_on_main_thread(move || {
                    if let Some(window) = app_for_main.get_webview_window("main") {
                        match payload.launch_url.parse::<tauri::Url>() {
                            Ok(url) => {
                                let _ = window.navigate(url);
                            }
                            Err(error) => eprintln!("invalid launch URL: {error}"),
                        }
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                });
            }
        });
    }

    if let Some(stderr) = stderr {
        let log_path = log_path.clone();
        thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                append_log(&log_path, &line);
            }
        });
    }

    let app_for_monitor = app.clone();
    let ready_for_monitor = ready.clone();
    thread::spawn(move || {
        let deadline = Instant::now() + STARTUP_TIMEOUT;
        while Instant::now() < deadline {
            if ready_for_monitor.load(Ordering::SeqCst) {
                monitor_for_exit(app_for_monitor, ready_for_monitor);
                return;
            }
            if backend_exited() {
                show_error(
                    &app_for_monitor,
                    "Kontext Studio could not start. Open Help → Open Logs for details.",
                );
                return;
            }
            thread::sleep(Duration::from_millis(250));
        }
        if !ready_for_monitor.load(Ordering::SeqCst) {
            show_error(
                &app_for_monitor,
                "Kontext Studio took too long to start. Open Help → Open Logs for details.",
            );
        }
    });

    Ok(())
}

pub fn shutdown() {
    SHUTTING_DOWN.store(true, Ordering::SeqCst);
    let Some(mut child) = lock_backend().take() else {
        return;
    };

    // Closing stdin is the normal desktop quit signal; SIGTERM is the backstop.
    drop(child.stdin.take());
    #[cfg(unix)]
    unsafe {
        libc::kill(child.id() as i32, libc::SIGTERM);
    }

    let deadline = Instant::now() + Duration::from_secs(8);
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if Instant::now() < deadline => {
                thread::sleep(Duration::from_millis(100));
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                break;
            }
        }
    }
}

fn backend_exited() -> bool {
    let mut guard = lock_backend();
    match guard.as_mut() {
        Some(child) => matches!(child.try_wait(), Ok(Some(_))),
        None => true,
    }
}

fn monitor_for_exit(app: AppHandle, ready: Arc<AtomicBool>) {
    while ready.load(Ordering::SeqCst) {
        thread::sleep(Duration::from_millis(500));
        if !backend_exited() {
            continue;
        }
        if !SHUTTING_DOWN.load(Ordering::SeqCst) {
            show_error(
                &app,
                "The Kontext server stopped unexpectedly. Open Help → Open Logs for details.",
            );
        }
        return;
    }
}

fn lock_backend() -> std::sync::MutexGuard<'static, Option<Child>> {
    BACKEND
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn python_executable(resource_dir: &Path) -> PathBuf {
    #[cfg(target_os = "macos")]
    {
        resource_dir.join("python").join("bin").join("python3")
    }
    #[cfg(target_os = "windows")]
    {
        resource_dir.join("python").join("python.exe")
    }
    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    {
        resource_dir.join("python").join("bin").join("python3")
    }
}

fn log_path(app: &AppHandle) -> tauri::Result<PathBuf> {
    Ok(log_dir(app)?.join("desktop.log"))
}

fn log_dir(app: &AppHandle) -> tauri::Result<PathBuf> {
    #[cfg(target_os = "macos")]
    let directory = app
        .path()
        .home_dir()?
        .join("Library")
        .join("Logs")
        .join("Kontext Studio");
    #[cfg(target_os = "windows")]
    let directory = app.path().local_data_dir()?.join("Kontext").join("logs");
    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    let directory = app.path().app_log_dir()?;

    fs::create_dir_all(&directory).map_err(tauri::Error::Io)?;
    #[cfg(unix)]
    let _ = fs::set_permissions(&directory, fs::Permissions::from_mode(0o700));
    Ok(directory)
}

fn append_log(path: &Path, line: &str) {
    let mut options = OpenOptions::new();
    options.create(true).append(true);
    #[cfg(unix)]
    options.mode(0o600);
    if let Ok(mut file) = options.open(path) {
        let _ = writeln!(file, "{line}");
    }
    #[cfg(unix)]
    let _ = fs::set_permissions(path, fs::Permissions::from_mode(0o600));
}

fn rotate_log(path: &Path) {
    let Ok(metadata) = fs::metadata(path) else {
        return;
    };
    if metadata.len() <= LOG_LIMIT_BYTES {
        return;
    }
    let rotated = path.with_extension("log.1");
    let _ = fs::remove_file(&rotated);
    let _ = fs::rename(path, rotated);
}

fn show_error(app: &AppHandle, message: &str) {
    let description = match log_path(app) {
        Ok(path) => format!("{message}\n\nLog file: {}", path.display()),
        Err(_) => message.to_string(),
    };
    let _ = app.run_on_main_thread(move || {
        rfd::MessageDialog::new()
            .set_title("Kontext Studio")
            .set_description(description)
            .set_level(rfd::MessageLevel::Error)
            .show();
    });
}
