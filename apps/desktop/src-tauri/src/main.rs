// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[tauri::command]
async fn check_backend_health() -> Result<String, String> {
    // Check if the Python backend is running on http://127.0.0.1:8420
    match reqwest::get("http://127.0.0.1:8420/health").await {
        Ok(response) => {
            if response.status().is_success() {
                Ok("Backend is healthy".to_string())
            } else {
                Err(format!("Backend returned status: {}", response.status()))
            }
        }
        Err(e) => Err(format!("Backend connection failed: {}", e)),
    }
}

#[tauri::command]
fn get_backend_url() -> String {
    "http://127.0.0.1:8420".to_string()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            check_backend_health,
            get_backend_url
        ])
        .setup(|_app| {
            #[cfg(debug_assertions)]
            {
                let window = _app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
