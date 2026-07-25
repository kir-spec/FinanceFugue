#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod models;
mod storage;

use commands::*;
use storage::StorageManager;
use std::sync::{Arc, Mutex};
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();

    let storage = StorageManager::new();
    let clients = storage.load_clients();

    let app_state = Arc::new(AppState {
        storage,
        clients: Mutex::new(clients),
    });

    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            get_clients,
            save_client,
            delete_client,
            delete_order,
            delete_payment,
            add_payment,
            open_path
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
