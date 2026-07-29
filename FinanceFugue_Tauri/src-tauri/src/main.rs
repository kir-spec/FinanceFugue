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
        .plugin(tauri_plugin_dialog::init())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            get_clients,
            save_client,
            delete_client,
            delete_order,
            delete_payment,
            open_path,
            create_backup_zip,
            export_files_zip,
            get_database_size,
            delete_database,
            rename_file,
            delete_file,
            copy_file_to,
            get_db_dir,
            save_db_dir,
            get_saved_db_dir,
            open_settings_window,
            open_eula_window,
            open_client_settings_window,
            set_pending_client_id,
            get_pending_client_id,
            read_text_file,
            save_file_bytes,
            has_password,
            check_password,
            set_password,
            backup_db,
            list_db_backups,
            restore_db_backup,
            migrate_db_dir,
            get_attached_files_dir,
            link_file,
            add_folder_link,
            save_settings_to_file,
            load_settings_from_file,
            backup_settings,
            list_settings_backups,
            restore_settings_backup,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
