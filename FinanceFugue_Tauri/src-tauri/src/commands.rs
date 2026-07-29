use crate::models::Client;
use crate::storage::{self, StorageManager};
use std::sync::{Arc, Mutex};
use tauri::{Manager, State, WebviewUrl, WebviewWindowBuilder};
use chrono::Local;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::fs;
use tracing::{info, error, warn, debug};
use sha2::{Sha256, Digest};


pub struct AppState {
    pub storage: StorageManager,
    pub clients: Mutex<Vec<Client>>,
}

#[tauri::command]
pub fn get_clients(state: State<'_, Arc<AppState>>) -> Vec<Client> {
    debug!("IPC: get_clients called");
    let clients = state.clients.lock().unwrap_or_else(|e| {
        error!("Mutex poisoned in get_clients: {}", e);
        e.into_inner()
    });
    let count = clients.len();
    info!("IPC: get_clients returning {} clients", count);
    clients.clone()
}

#[tauri::command]
pub fn save_client(client: Client, state: State<'_, Arc<AppState>>) -> Result<Vec<Client>, String> {
    debug!("IPC: save_client called — id={}, name={}", client.id, client.name);
    let mut clients = state.clients.lock().unwrap_or_else(|e| {
        error!("Mutex poisoned in save_client: {}", e);
        e.into_inner()
    });
    let snapshot = clients.clone();
    let is_new = !clients.iter().any(|c| c.id == client.id);
    if let Some(pos) = clients.iter().position(|c| c.id == client.id) {
        info!("IPC: save_client — updating existing client '{}' at position {}", client.name, pos);
        clients[pos] = client;
    } else {
        info!("IPC: save_client — adding new client '{}'", client.name);
        clients.push(client);
    }
    info!("IPC: save_client — saving {} clients to storage", clients.len());
    state.storage.save_clients(&clients).map_err(|e| {
        error!("IPC: save_client FAILED — rolling back in-memory state: {}", e);
        *clients = snapshot;
        e
    })?;
    info!("IPC: save_client — success, is_new={}", is_new);
    Ok(clients.clone())
}

#[tauri::command]
pub fn delete_client(client_id: String, state: State<'_, Arc<AppState>>) -> Result<Vec<Client>, String> {
    debug!("IPC: delete_client called — client_id={}", client_id);
    let mut clients = state.clients.lock().unwrap_or_else(|e| {
        error!("Mutex poisoned in delete_client: {}", e);
        e.into_inner()
    });
    let snapshot = clients.clone();
    let before = clients.len();
    clients.retain(|c| c.id != client_id);
    let deleted = before - clients.len();
    info!("IPC: delete_client — removed {} client(s) with id={}", deleted, client_id);
    state.storage.save_clients(&clients).map_err(|e| {
        error!("IPC: delete_client FAILED — rolling back: {}", e);
        *clients = snapshot;
        e
    })?;
    info!("IPC: delete_client — success, remaining {} clients", clients.len());
    Ok(clients.clone())
}

#[tauri::command]
pub fn delete_order(client_id: String, order_id: String, state: State<'_, Arc<AppState>>) -> Result<Vec<Client>, String> {
    debug!("IPC: delete_order called — client_id={}, order_id={}", client_id, order_id);
    let mut clients = state.clients.lock().unwrap_or_else(|e| {
        error!("Mutex poisoned in delete_order: {}", e);
        e.into_inner()
    });
    let snapshot = clients.clone();
    let client = clients.iter_mut().find(|c| c.id == client_id).ok_or_else(|| {
        error!("IPC: delete_order — client '{}' not found!", client_id);
        "Клиент не найден".to_string()
    })?;
    let before = client.orders.len();
    client.orders.retain(|o| o.id != order_id);
    let deleted = before - client.orders.len();
    info!("IPC: delete_order — removed {} order(s). Remaining: {}", deleted, client.orders.len());
    state.storage.save_clients(&clients).map_err(|e| {
        error!("IPC: delete_order FAILED — rolling back: {}", e);
        *clients = snapshot;
        e
    })?;
    info!("IPC: delete_order — success");
    Ok(clients.clone())
}

#[tauri::command]
pub fn delete_payment(client_id: String, order_id: String, payment_id: String, state: State<'_, Arc<AppState>>) -> Result<Vec<Client>, String> {
    debug!("IPC: delete_payment called — client_id={}, order_id={}, payment_id={}", client_id, order_id, payment_id);
    let mut clients = state.clients.lock().unwrap_or_else(|e| {
        error!("Mutex poisoned in delete_payment: {}", e);
        e.into_inner()
    });
    let snapshot = clients.clone();
    let client = clients.iter_mut().find(|c| c.id == client_id).ok_or_else(|| {
        error!("IPC: delete_payment — client '{}' not found!", client_id);
        "Клиент не найден".to_string()
    })?;
    let order = client.orders.iter_mut().find(|o| o.id == order_id).ok_or_else(|| {
        error!("IPC: delete_payment — order '{}' not found for client '{}'!", order_id, client_id);
        "Заказ не найден".to_string()
    })?;
    let before = order.payments.len();
    order.payments.retain(|p| p.id != payment_id);
    let deleted = before - order.payments.len();
    info!("IPC: delete_payment — removed {} payment(s)", deleted);
    state.storage.save_clients(&clients).map_err(|e| {
        error!("IPC: delete_payment FAILED — rolling back: {}", e);
        *clients = snapshot;
        e
    })?;
    info!("IPC: delete_payment — success");
    Ok(clients.clone())
}

#[tauri::command]
pub fn open_path(path: String) -> Result<(), String> {
    info!("IPC: open_path — opening path: {}", path);
    let result = open::that(&path);
    match &result {
        Ok(_) => info!("IPC: open_path — success: {}", path),
        Err(e) => warn!("IPC: open_path — failed to open '{}': {}", path, e),
    }
    result.map_err(|e| format!("Не удалось открыть '{}': {}", path, e))
}

// === FILE & ZIP OPERATIONS ===

#[tauri::command]
pub fn create_backup_zip(file_paths: Vec<String>, db_json: String) -> Result<Vec<u8>, String> {
    info!("IPC: create_backup_zip — {} file(s) to add to backup", file_paths.len());
    let mut buffer = std::io::Cursor::new(Vec::new());
    let mut zip_writer = zip::ZipWriter::new(&mut buffer);
    let options = zip::write::FileOptions::<()>::default()
        .compression_method(zip::CompressionMethod::Deflated);

    zip_writer.start_file("pro_database.json", options).map_err(|e| {
        error!("IPC: create_backup_zip — failed to add pro_database.json: {}", e);
        e.to_string()
    })?;
    let db_size = db_json.len();
    zip_writer.write_all(db_json.as_bytes()).map_err(|e| {
        error!("IPC: create_backup_zip — failed to write DB JSON ({} bytes): {}", db_size, e);
        e.to_string()
    })?;
    debug!("IPC: create_backup_zip — wrote {} bytes of DB JSON", db_size);

    let mut added = 0usize;
    for path in &file_paths {
        let p = Path::new(path);
        if !p.exists() {
            warn!("IPC: create_backup_zip — file not found, skipping: {}", path);
            continue;
        }
        let name = match p.file_name() {
            Some(n) => n.to_string_lossy().to_string(),
            None => {
                warn!("IPC: create_backup_zip — cannot get filename from path, skipping: {}", path);
                continue;
            }
        };
        let rel_path = format!("attached_files/{}", name);
        zip_writer.start_file(&rel_path, options).map_err(|e| {
            error!("IPC: create_backup_zip — failed to start '{}': {}", rel_path, e);
            e.to_string()
        })?;
        let mut f = fs::File::open(p).map_err(|e| {
            error!("IPC: create_backup_zip — cannot open '{}': {}", path, e);
            e.to_string()
        })?;
        let bytes_copied = std::io::copy(&mut f, &mut zip_writer).map_err(|e| {
            error!("IPC: create_backup_zip — io::copy failed for '{}': {}", path, e);
            e.to_string()
        })?;
        debug!("IPC: create_backup_zip — added '{}' ({} bytes)", rel_path, bytes_copied);
        added += 1;
    }

    zip_writer.finish().map_err(|e| {
        error!("IPC: create_backup_zip — zip finish failed: {}", e);
        e.to_string()
    })?;
    let result = buffer.into_inner();
    info!("IPC: create_backup_zip — success. {} files added, zip size: {} bytes", added, result.len());
    Ok(result)
}

#[tauri::command]
pub fn export_files_zip(file_paths: Vec<String>) -> Result<Vec<u8>, String> {
    info!("IPC: export_files_zip — {} file(s) to export", file_paths.len());
    let mut buffer = std::io::Cursor::new(Vec::new());
    let mut zip_writer = zip::ZipWriter::new(&mut buffer);
    let options = zip::write::FileOptions::<()>::default()
        .compression_method(zip::CompressionMethod::Deflated);

    let mut added = 0usize;
    for path in &file_paths {
        let p = Path::new(path);
        if !p.exists() {
            warn!("IPC: export_files_zip — file not found, skipping: {}", path);
            continue;
        }
        let name = match p.file_name() {
            Some(n) => n.to_string_lossy().to_string(),
            None => {
                warn!("IPC: export_files_zip — cannot get filename from path, skipping: {}", path);
                continue;
            }
        };
        zip_writer.start_file(&name, options).map_err(|e| {
            error!("IPC: export_files_zip — failed to start '{}': {}", name, e);
            e.to_string()
        })?;
        let mut f = fs::File::open(p).map_err(|e| {
            error!("IPC: export_files_zip — cannot open '{}': {}", path, e);
            e.to_string()
        })?;
        let bytes_copied = std::io::copy(&mut f, &mut zip_writer).map_err(|e| {
            error!("IPC: export_files_zip — io::copy failed for '{}': {}", path, e);
            e.to_string()
        })?;
        debug!("IPC: export_files_zip — added '{}' ({} bytes)", name, bytes_copied);
        added += 1;
    }

    zip_writer.finish().map_err(|e| {
        error!("IPC: export_files_zip — zip finish failed: {}", e);
        e.to_string()
    })?;
    let result = buffer.into_inner();
    info!("IPC: export_files_zip — success. {} files exported, zip size: {} bytes", added, result.len());
    Ok(result)
}

#[tauri::command]
pub fn get_database_size(state: State<'_, Arc<AppState>>) -> Result<u64, String> {
    let db_path = state.storage.db_path();
    debug!("IPC: get_database_size — path: {:?}", db_path);
    if !db_path.exists() {
        info!("IPC: get_database_size — DB file does not exist, returning 0");
        return Ok(0);
    }
    let size = fs::metadata(db_path).map(|m| m.len()).map_err(|e| {
        error!("IPC: get_database_size — metadata error: {}", e);
        e.to_string()
    })?;
    info!("IPC: get_database_size — {} bytes ({:.2} KB)", size, size as f64 / 1024.0);
    Ok(size)
}

#[tauri::command]
pub fn delete_database(state: State<'_, Arc<AppState>>) -> Result<(), String> {
    info!("IPC: delete_database called");
    let db_path = state.storage.db_path();
    let lock_path = db_path.with_extension("lock");
    if db_path.exists() {
        fs::remove_file(&db_path).map_err(|e| {
            error!("IPC: delete_database — failed to remove DB file {:?}: {}", db_path, e);
            e.to_string()
        })?;
        info!("IPC: delete_database — removed DB file {:?}", db_path);
    } else {
        warn!("IPC: delete_database — DB file {:?} does not exist", db_path);
    }
    if lock_path.exists() {
        if let Err(e) = fs::remove_file(&lock_path) {
            warn!("IPC: delete_database — failed to remove lock file {:?}: {}", lock_path, e);
        } else {
            info!("IPC: delete_database — removed lock file {:?}", lock_path);
        }
    }
    info!("IPC: delete_database — complete");
    Ok(())
}

#[tauri::command]
pub fn rename_file(old_path: String, new_name: String) -> Result<String, String> {
    debug!("IPC: rename_file — old_path={}, new_name={}", old_path, new_name);
    let new_name = new_name.trim().to_string();
    if new_name.is_empty() || new_name.contains("..") || new_name.contains('/') || new_name.contains('\\') {
        warn!("IPC: rename_file — invalid new_name '{}'", new_name);
        return Err("Недопустимое имя файла".to_string());
    }
    let p = Path::new(&old_path);
    if !p.exists() {
        warn!("IPC: rename_file — source file not found: {}", old_path);
        return Err(format!("Файл не найден: {}", old_path));
    }
    let parent = p.parent().ok_or_else(|| {
        error!("IPC: rename_file — cannot determine parent of '{}'", old_path);
        "Не удалось определить родительскую директорию".to_string()
    })?;
    let new_path = parent.join(&new_name);
    fs::rename(p, &new_path).map_err(|e| {
        error!("IPC: rename_file — rename failed '{}' -> '{}': {}", old_path, new_path.display(), e);
        e.to_string()
    })?;
    info!("IPC: rename_file — success: '{}' -> '{}'", old_path, new_path.display());
    Ok(new_path.to_string_lossy().to_string())
}

#[tauri::command]
pub fn delete_file(path: String) -> Result<(), String> {
    debug!("IPC: delete_file — path={}", path);
    let p = Path::new(&path);
    if p.exists() {
        fs::remove_file(p).map_err(|e| {
            error!("IPC: delete_file — failed to delete '{}': {}", path, e);
            e.to_string()
        })?;
        info!("IPC: delete_file — deleted '{}'", path);
    } else {
        warn!("IPC: delete_file — file not found, nothing to delete: {}", path);
    }
    Ok(())
}

#[tauri::command]
pub fn copy_file_to(source: String, dest_dir: String) -> Result<String, String> {
    debug!("IPC: copy_file_to — source={}, dest_dir={}", source, dest_dir);
    let src = Path::new(&source);
    let dir = Path::new(&dest_dir);
    fs::create_dir_all(dir).map_err(|e| {
        error!("IPC: copy_file_to — failed to create dir '{}': {}", dest_dir, e);
        e.to_string()
    })?;
    debug!("IPC: copy_file_to — ensured directory exists: {}", dest_dir);
    let name = match src.file_name() {
        Some(n) => n.to_string_lossy().to_string(),
        None => return Err("Не удалось определить имя исходного файла".to_string()),
    };
    let dest = dir.join(&name);
    if dest.exists() {
        let stem = dest.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| name.clone());
        let ext = dest.extension().map(|e| format!(".{}", e.to_string_lossy())).unwrap_or_default();
        let timestamp = Local::now().format("%H%M%S").to_string();
        let dest = dir.join(format!("{}_{}{}", stem, timestamp, ext));
        warn!("IPC: copy_file_to — destination exists, saving as '{}'", dest.display());
        fs::copy(src, &dest).map_err(|e| {
            error!("IPC: copy_file_to — copy failed '{}' -> '{}': {}", source, dest.display(), e);
            e.to_string()
        })?;
        info!("IPC: copy_file_to — success (duplicate renamed): '{}' -> '{}'", source, dest.display());
        return Ok(dest.to_string_lossy().to_string());
    }
    fs::copy(src, &dest).map_err(|e| {
        error!("IPC: copy_file_to — copy failed '{}' -> '{}': {}", source, dest.display(), e);
        e.to_string()
    })?;
    info!("IPC: copy_file_to — success: '{}' -> '{}'", source, dest.display());
    Ok(dest.to_string_lossy().to_string())
}

#[tauri::command]
pub fn get_db_dir(state: State<'_, Arc<AppState>>) -> Result<String, String> {
    let db_path = state.storage.db_path();
    debug!("IPC: get_db_dir — db_path: {:?}", db_path);
    let parent = db_path.parent().ok_or_else(|| {
        error!("IPC: get_db_dir — cannot determine parent of {:?}", db_path);
        "Не удалось определить директорию базы данных".to_string()
    })?;
    let dir = parent.to_string_lossy().to_string();
    info!("IPC: get_db_dir — returning '{}'", dir);
    Ok(dir)
}

#[tauri::command]
pub fn save_db_dir(dir: String) -> Result<(), String> {
    info!("IPC: save_db_dir — dir={}", dir);
    storage::save_db_dir(&dir)?;
    info!("IPC: save_db_dir — success");
    Ok(())
}

#[tauri::command]
pub fn get_saved_db_dir() -> Result<Option<String>, String> {
    let custom = storage::read_db_config();
    Ok(custom.map(|p| p.parent().map(|d| d.to_string_lossy().to_string()).unwrap_or_default()))
}

#[tauri::command]
pub fn open_settings_window(app: tauri::AppHandle) -> Result<(), String> {
    info!("IPC: open_settings_window");
    if let Some(win) = app.get_webview_window("settings") {
        warn!("open_settings_window — settings window already exists, focusing");
        let _ = win.set_focus();
        return Ok(());
    }
    WebviewWindowBuilder::new(
        &app,
        "settings",
        WebviewUrl::App("index.html".into()),
    )
    .title("FinanceFugue — Настройки")
    .inner_size(500.0, 600.0)
    .resizable(false)
    .build()
    .map_err(|e| {
        error!("open_settings_window — failed: {}", e);
        e.to_string()
    })?;
    info!("open_settings_window — success");
    Ok(())
}

#[tauri::command]
pub fn open_eula_window(app: tauri::AppHandle) -> Result<(), String> {
    info!("IPC: open_eula_window");
    if let Some(win) = app.get_webview_window("eula") {
        let _ = win.set_focus();
        return Ok(());
    }
    WebviewWindowBuilder::new(&app, "eula", WebviewUrl::App("index.html".into()))
        .title("FinanceFugue — Лицензионное соглашение")
        .inner_size(620.0, 500.0)
        .resizable(true)
        .build()
        .map_err(|e| { error!("open_eula_window — failed: {}", e); e.to_string() })?;
    info!("open_eula_window — success");
    Ok(())
}

// Pending client ID for separate settings window
static PENDING_CLIENT_ID: std::sync::Mutex<Option<String>> = std::sync::Mutex::new(None);

#[tauri::command]
pub fn set_pending_client_id(id: String) -> Result<(), String> {
    *PENDING_CLIENT_ID.lock().unwrap_or_else(|e| e.into_inner()) = Some(id);
    Ok(())
}

#[tauri::command]
pub fn get_pending_client_id() -> Result<Option<String>, String> {
    Ok(PENDING_CLIENT_ID.lock().unwrap_or_else(|e| e.into_inner()).take())
}

#[tauri::command]
pub fn open_client_settings_window(client_id: String, app: tauri::AppHandle) -> Result<(), String> {
    info!("IPC: open_client_settings_window — client_id={}", client_id);
    // Store the client ID for the new window to retrieve
    *PENDING_CLIENT_ID.lock().unwrap_or_else(|e| e.into_inner()) = Some(client_id.clone());
    if let Some(win) = app.get_webview_window("cs") { let _ = win.close(); }
    WebviewWindowBuilder::new(&app, "cs", WebviewUrl::App("index.html".into()))
        .title("FinanceFugue — Настройки клиента")
        .inner_size(480.0, 600.0)
        .resizable(false)
        .build()
        .map_err(|e| { error!("open_client_settings_window — failed: {}", e); e.to_string() })?;
    info!("open_client_settings_window — success");
    Ok(())
}

#[tauri::command]
pub fn read_text_file(path: String) -> Result<String, String> {
    debug!("IPC: read_text_file — path={}", path);
    let result = fs::read_to_string(&path);
    match &result {
        Ok(content) => info!("IPC: read_text_file — success, {} bytes read from '{}'", content.len(), path),
        Err(e) => error!("IPC: read_text_file — failed to read '{}': {}", path, e),
    }
    result.map_err(|e| format!("Не удалось прочитать файл: {}", e))
}

#[tauri::command]
pub fn save_file_bytes(dir: String, name: String, content: Vec<u8>) -> Result<String, String> {
    debug!("IPC: save_file_bytes — dir={}, name={}, content_len={}", dir, name, content.len());
    let name_trimmed = name.trim();
    if name_trimmed.is_empty() || name_trimmed.contains("..") || name_trimmed.contains('/') || name_trimmed.contains('\\') {
        warn!("IPC: save_file_bytes — invalid filename parameter '{}'", name);
        return Err("Недопустимое имя файла".to_string());
    }
    let dir_path = Path::new(&dir);
    fs::create_dir_all(dir_path).map_err(|e| {
        error!("IPC: save_file_bytes — failed to create dir '{}': {}", dir, e);
        format!("Не удалось создать директорию: {}", e)
    })?;
    let file_path = dir_path.join(name_trimmed);
    // If file exists, add a timestamp suffix
    let final_path = if file_path.exists() {
        let stem = file_path.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| name.clone());
        let ext = file_path.extension().map(|e| format!(".{}", e.to_string_lossy())).unwrap_or_default();
        let timestamp = Local::now().format("%H%M%S").to_string();
        let new_path = dir_path.join(format!("{}_{}{}", stem, timestamp, ext));
        warn!("IPC: save_file_bytes — destination exists, saving as '{}'", new_path.display());
        new_path
    } else {
        file_path
    };
    fs::write(&final_path, &content).map_err(|e| {
        error!("IPC: save_file_bytes — failed to write '{}': {}", final_path.display(), e);
        format!("Не удалось записать файл: {}", e)
    })?;
    info!("IPC: save_file_bytes — success: {} ({} bytes)", final_path.display(), content.len());
    Ok(final_path.to_string_lossy().to_string())
}

// === PASSWORD MANAGEMENT ===

fn get_password_path() -> Result<std::path::PathBuf, String> {
    let app_dir = dirs::data_local_dir()
        .map(|d| d.join("FinanceFugue"))
        .ok_or_else(|| "Не удалось определить директорию AppData".to_string())?;
    fs::create_dir_all(&app_dir).map_err(|e| e.to_string())?;
    Ok(app_dir.join("password_hash.txt"))
}

#[tauri::command]
pub fn has_password() -> Result<bool, String> {
    let p = get_password_path()?;
    Ok(p.exists())
}

#[tauri::command]
pub fn check_password(password: String) -> Result<bool, String> {
    let p = get_password_path()?;
    if !p.exists() {
        return Ok(true); // No password set
    }
    let stored_hash = fs::read_to_string(&p).map_err(|e| e.to_string())?;
    let mut hasher = Sha256::new();
    hasher.update(password.as_bytes());
    let current_hash: String = hasher.finalize().iter().map(|b| format!("{:02x}", b)).collect();
    Ok(stored_hash.trim() == current_hash)
}

#[tauri::command]
pub fn set_password(password: Option<String>) -> Result<(), String> {
    let p = get_password_path()?;
    if let Some(pwd) = password {
        let mut hasher = Sha256::new();
        hasher.update(pwd.as_bytes());
        let hash: String = hasher.finalize().iter().map(|b| format!("{:02x}", b)).collect();
        fs::write(&p, hash).map_err(|e| e.to_string())?;
        info!("IPC: set_password — password updated");
    } else {
        if p.exists() {
            fs::remove_file(&p).map_err(|e| e.to_string())?;
            info!("IPC: set_password — password removed");
        }
    }
    Ok(())
}

// === DATABASE BACKUP / RESTORE ===

fn backups_dir() -> Result<PathBuf, String> {
    let dir = storage::app_data_dir()
        .ok_or_else(|| "Не удалось определить директорию AppData".to_string())?
        .join("backups");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

#[tauri::command]
pub fn backup_db(state: State<'_, Arc<AppState>>, note: Option<String>) -> Result<String, String> {
    info!("IPC: backup_db called");
    let db_path = state.storage.db_path();
    if !db_path.exists() {
        return Err("Файл базы данных не найден".to_string());
    }
    let dir = backups_dir()?;
    let timestamp = Local::now().format("%Y%m%d_%H%M%S").to_string();
    let note_suffix = note.map(|n| format!("_{}", n.replace(' ', "_"))).unwrap_or_default();
    let target = dir.join(format!("pro_database_backup_{}{}.json", timestamp, note_suffix));
    fs::copy(db_path, &target).map_err(|e| e.to_string())?;
    let size = target.metadata().map(|m| m.len()).unwrap_or(0);
    info!("IPC: backup_db — success: {:?} ({} bytes)", target, size);
    Ok(target.to_string_lossy().to_string())
}

#[derive(serde::Serialize)]
pub struct DbBackupEntry {
    pub filename: String,
    pub size: u64,
    pub timestamp: String,
}

#[tauri::command]
pub fn list_db_backups() -> Result<Vec<DbBackupEntry>, String> {
    debug!("IPC: list_db_backups");
    let dir = backups_dir()?;
    let mut entries = Vec::new();
    if let Ok(read_dir) = fs::read_dir(&dir) {
        for entry in read_dir.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with("pro_database_backup_") && name.ends_with(".json") {
                let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
                let ts = entry.metadata()
                    .and_then(|m| m.modified())
                    .ok()
                    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                    .map(|d| d.as_secs().to_string())
                    .unwrap_or_default();
                entries.push(DbBackupEntry { filename: name, size, timestamp: ts });
            }
        }
    }
    entries.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
    info!("IPC: list_db_backups — {} backups found", entries.len());
    Ok(entries)
}

#[tauri::command]
pub fn restore_db_backup(filename: String, state: State<'_, Arc<AppState>>) -> Result<(), String> {
    info!("IPC: restore_db_backup — filename={}", filename);
    if filename.contains("..") || filename.contains('/') || filename.contains('\\') {
        return Err("Недопустимое имя файла".to_string());
    }
    let dir = backups_dir()?;
    let backup_path = dir.join(&filename);
    if !backup_path.exists() {
        return Err(format!("Бэкап не найден: {}", filename));
    }
    let db_path = state.storage.db_path().to_path_buf();
    // Create a pre-restore backup of current DB
    if db_path.exists() {
        let ts = Local::now().format("%Y%m%d_%H%M%S").to_string();
        let pre_backup = dir.join(format!("pro_database_backup_{}_pre_restore.json", ts));
        fs::copy(&db_path, &pre_backup).map_err(|e| e.to_string())?;
        info!("IPC: restore_db_backup — pre-restore backup saved: {:?}", pre_backup);
    }
    // Load backup data
    let data = fs::read(&backup_path).map_err(|e| e.to_string())?;
    // Parse and validate
    let clients: Vec<Client> = serde_json::from_slice(&data).map_err(|e| format!("Ошибка парсинга бэкапа: {}", e))?;
    // Save to current DB
    state.storage.save_clients(&clients).map_err(|e| e.to_string())?;
    // Update in-memory state
    let mut state_clients = state.clients.lock().unwrap_or_else(|e| e.into_inner());
    *state_clients = clients;
    info!("IPC: restore_db_backup — success, restored {} clients", state_clients.len());
    Ok(())
}

// === DB MIGRATION ===

#[tauri::command]
pub fn migrate_db_dir(new_dir: String, move_files: bool, state: State<'_, Arc<AppState>>) -> Result<(), String> {
    info!("IPC: migrate_db_dir — new_dir={}, move_files={}", new_dir, move_files);
    let new_dir_path = Path::new(&new_dir);
    fs::create_dir_all(new_dir_path).map_err(|e| format!("Не удалось создать директорию: {}", e))?;

    let old_db_path = state.storage.db_path().to_path_buf();
    let new_db_path = new_dir_path.join("pro_database.json");

    // Copy DB file
    if old_db_path.exists() && old_db_path != new_db_path {
        fs::copy(&old_db_path, &new_db_path).map_err(|e| format!("Не удалось скопировать БД: {}", e))?;
        info!("IPC: migrate_db_dir — DB copied to {:?}", new_db_path);
    }

    // Optionally copy attached_files
    if move_files {
        let old_attached = old_db_path.parent()
            .map(|p| p.join("attached_files"))
            .unwrap_or_else(|| PathBuf::from("attached_files"));
        let new_attached = new_dir_path.join("attached_files");
        if old_attached.exists() && old_attached != new_attached {
            copy_dir_recursive(&old_attached, &new_attached)?;
            info!("IPC: migrate_db_dir — attached_files copied to {:?}", new_attached);
        }
    }

    // Save new config
    storage::save_db_dir(&new_dir)?;

    info!("IPC: migrate_db_dir — success. Restart required.");
    Ok(())
}

fn copy_dir_recursive(src: &Path, dst: &Path) -> Result<(), String> {
    fs::create_dir_all(dst).map_err(|e| format!("Не удалось создать директорию {:?}: {}", dst, e))?;
    for entry in fs::read_dir(src).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if src_path.is_dir() {
            copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            fs::copy(&src_path, &dst_path).map_err(|e| format!("Не удалось скопировать {:?}: {}", src_path, e))?;
        }
    }
    Ok(())
}

#[tauri::command]
pub fn get_attached_files_dir(state: State<'_, Arc<AppState>>) -> Result<String, String> {
    let db_path = state.storage.db_path();
    let attached = db_path.parent()
        .map(|p| p.join("attached_files"))
        .unwrap_or_else(|| PathBuf::from("attached_files"));
    Ok(attached.to_string_lossy().to_string())
}

#[tauri::command]
pub fn link_file(source: String, dest_dir: String) -> Result<String, String> {
    debug!("IPC: link_file — source={}, dest_dir={}", source, dest_dir);
    let src = Path::new(&source);
    if !src.exists() {
        return Err(format!("Файл не найден: {}", source));
    }
    let dir = Path::new(&dest_dir);
    fs::create_dir_all(dir).map_err(|e| format!("Не удалось создать директорию: {}", e))?;
    let name = match src.file_name() {
        Some(n) => n.to_string_lossy().to_string(),
        None => return Err("Не удалось определить имя файла".to_string()),
    };
    let dest = dir.join(&name);
    let final_path = if dest.exists() {
        let stem = dest.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| name.clone());
        let ext = dest.extension().map(|e| format!(".{}", e.to_string_lossy())).unwrap_or_default();
        let timestamp = Local::now().format("%H%M%S").to_string();
        dir.join(format!("{}_{}{}", stem, timestamp, ext))
    } else {
        dest
    };
    fs::copy(src, &final_path).map_err(|e| format!("Не удалось скопировать файл: {}", e))?;
    info!("IPC: link_file — success: {:?}", final_path);
    Ok(final_path.to_string_lossy().to_string())
}

#[tauri::command]
pub fn add_folder_link(folder_path: String, dest_dir: String) -> Result<String, String> {
    debug!("IPC: add_folder_link — folder_path={}, dest_dir={}", folder_path, dest_dir);
    let src = Path::new(&folder_path);
    if !src.is_dir() {
        return Err(format!("Папка не найдена: {}", folder_path));
    }
    let dir = Path::new(&dest_dir);
    fs::create_dir_all(dir).map_err(|e| format!("Не удалось создать директорию: {}", e))?;
    let name = match src.file_name() {
        Some(n) => n.to_string_lossy().to_string(),
        None => return Err("Не удалось определить имя папки".to_string()),
    };
    let dest = dir.join(&name);
    // Copy the entire folder recursively
    copy_dir_recursive(src, &dest)?;
    info!("IPC: add_folder_link — success: {:?}", dest);
    Ok(dest.to_string_lossy().to_string())
}

// === SETTINGS BACKUP (stored in AppData for cross-window access) ===

fn settings_path() -> Result<PathBuf, String> {
    let app_dir = storage::app_data_dir()
        .ok_or_else(|| "Не удалось определить директорию AppData".to_string())?;
    fs::create_dir_all(&app_dir).map_err(|e| e.to_string())?;
    Ok(app_dir.join("app_settings.json"))
}

#[tauri::command]
pub fn save_settings_to_file(settings_json: String) -> Result<(), String> {
    debug!("IPC: save_settings_to_file — {} bytes", settings_json.len());
    let p = settings_path()?;
    fs::write(&p, &settings_json).map_err(|e| e.to_string())?;
    info!("IPC: save_settings_to_file — success");
    Ok(())
}

#[tauri::command]
pub fn load_settings_from_file() -> Result<Option<String>, String> {
    debug!("IPC: load_settings_from_file");
    let p = settings_path()?;
    if !p.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&p).map_err(|e| e.to_string())?;
    info!("IPC: load_settings_from_file — success, {} bytes", content.len());
    Ok(Some(content))
}

#[tauri::command]
pub fn backup_settings(settings_json: String) -> Result<String, String> {
    info!("IPC: backup_settings");
    let dir = storage::app_data_dir()
        .ok_or_else(|| "Не удалось определить директорию AppData".to_string())?
        .join("settings_backups");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let timestamp = Local::now().format("%Y%m%d_%H%M%S").to_string();
    let target = dir.join(format!("app_settings_backup_{}.json", timestamp));
    fs::write(&target, &settings_json).map_err(|e| e.to_string())?;
    // Prune to 5 most recent
    if let Ok(entries) = fs::read_dir(&dir) {
        let mut backups: Vec<_> = entries
            .flatten()
            .filter(|e| e.file_name().to_string_lossy().starts_with("app_settings_backup_"))
            .collect();
        backups.sort_by(|a, b| b.file_name().cmp(&a.file_name()));
        for old in backups.into_iter().skip(5) {
            let _ = fs::remove_file(old.path());
        }
    }
    info!("IPC: backup_settings — saved to {:?}", target);
    Ok(target.to_string_lossy().to_string())
}

#[tauri::command]
pub fn list_settings_backups() -> Result<Vec<DbBackupEntry>, String> {
    debug!("IPC: list_settings_backups");
    let dir = storage::app_data_dir()
        .ok_or_else(|| "Не удалось определить директорию AppData".to_string())?
        .join("settings_backups");
    if !dir.exists() {
        return Ok(Vec::new());
    }
    let mut entries = Vec::new();
    for entry in fs::read_dir(&dir).map_err(|e| e.to_string())?.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with("app_settings_backup_") {
            let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
            let ts = entry.metadata()
                .and_then(|m| m.modified())
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs().to_string())
                .unwrap_or_default();
            entries.push(DbBackupEntry { filename: name, size, timestamp: ts });
        }
    }
    entries.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
    info!("IPC: list_settings_backups — {} found", entries.len());
    Ok(entries)
}

#[tauri::command]
pub fn restore_settings_backup(filename: String) -> Result<String, String> {
    info!("IPC: restore_settings_backup — {}", filename);
    if filename.contains("..") || filename.contains('/') || filename.contains('\\') {
        return Err("Недопустимое имя файла".to_string());
    }
    let dir = storage::app_data_dir()
        .ok_or_else(|| "Не удалось определить директорию AppData".to_string())?
        .join("settings_backups");
    let backup_path = dir.join(&filename);
    if !backup_path.exists() {
        return Err(format!("Бэкап не найден: {}", filename));
    }
    let content = fs::read_to_string(&backup_path).map_err(|e| e.to_string())?;
    info!("IPC: restore_settings_backup — success");
    Ok(content)
}
