use crate::models::Client;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use fs2::FileExt;
use tracing::{info, error, warn, debug};

pub fn app_data_dir() -> Option<PathBuf> {
    dirs::data_local_dir().map(|d| d.join("FinanceFugue"))
}

pub fn read_db_config() -> Option<PathBuf> {
    let config_path = app_data_dir()?.join("db_dir.txt");
    if !config_path.exists() {
        debug!("read_db_config — config file not found at {:?}", config_path);
        return None;
    }
    let content = fs::read_to_string(&config_path).ok()?;
    let dir = content.trim();
    if dir.is_empty() || !Path::new(dir).is_dir() {
        warn!("read_db_config — stored path invalid or missing: '{}'", dir);
        return None;
    }
    let db_path = PathBuf::from(dir).join("pro_database.json");
    info!("read_db_config — using custom DB path: {:?}", db_path);
    Some(db_path)
}

pub fn save_db_dir(dir: &str) -> Result<(), String> {
    let config_dir = app_data_dir().ok_or_else(|| "Не удалось определить директорию для конфигурации".to_string())?;
    fs::create_dir_all(&config_dir).map_err(|e| format!("Не удалось создать директорию конфигурации: {}", e))?;
    fs::write(config_dir.join("db_dir.txt"), dir).map_err(|e| format!("Не удалось сохранить конфигурацию: {}", e))?;
    info!("save_db_dir — saved DB directory: {:?}", dir);
    Ok(())
}

pub struct StorageManager {
    db_path: PathBuf,
    lock_file: Option<File>,
}

impl StorageManager {
    pub fn new() -> Self {
        let db_path = Self::resolve_db_path();
        info!("StorageManager::new — DB path: {:?}", db_path);
        
        let mut manager = StorageManager {
            db_path,
            lock_file: None,
        };

        manager.acquire_lock();
        debug!("StorageManager::new — initialised successfully, lock acquired");
        manager
    }

    fn resolve_db_path() -> PathBuf {
        if let Some(custom) = read_db_config() {
            info!("resolve_db_path — using custom config path: {:?}", custom);
            return custom;
        }
        debug!("resolve_db_path — no custom config, checking defaults");

        let local_path = PathBuf::from("pro_database.json");
        if local_path.exists() {
            info!("resolve_db_path — found local DB at {:?}", local_path);
            return local_path;
        }
        debug!("resolve_db_path — no local DB, checking AppData");

        if let Some(data_dir) = dirs::data_local_dir() {
            let app_dir = data_dir.join("FinanceFugue");
            debug!("resolve_db_path — data_dir={:?}, app_dir={:?}", data_dir, app_dir);
            if let Err(e) = fs::create_dir_all(&app_dir) {
                error!("resolve_db_path — failed to create AppData directory {:?}: {}", app_dir, e);
                warn!("resolve_db_path — falling back to local pro_database.json");
                return local_path;
            }
            let db_path = app_dir.join("pro_database.json");
            debug!("resolve_db_path — resolved to {:?}", db_path);
            return db_path;
        }

        warn!("resolve_db_path — no data_local_dir, using local fallback");
        local_path
    }

    fn acquire_lock(&mut self) {
        let lock_path = self.db_path.with_extension("lock");
        debug!("acquire_lock — attempting to open lock file {:?}", lock_path);
        match OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(&lock_path)
        {
            Ok(file) => {
                debug!("acquire_lock — lock file opened, trying exclusive lock");
                if let Err(e) = file.try_lock_exclusive() {
                    warn!("acquire_lock — failed to get exclusive lock (another instance?): {}", e);
                } else {
                    info!("acquire_lock — exclusive lock acquired on {:?}", lock_path);
                }
                self.lock_file = Some(file);
                debug!("acquire_lock — lock_file stored in manager");
            }
            Err(e) => {
                error!("acquire_lock — could not open lock file {:?}: {}", lock_path, e);
            }
        }
    }

    pub fn db_path(&self) -> &PathBuf {
        debug!("db_path — returning {:?}", self.db_path);
        &self.db_path
    }

    pub fn load_clients(&self) -> Vec<Client> {
        debug!("load_clients — checking {:?}", self.db_path);
        if !self.db_path.exists() {
            info!("load_clients — DB file does not exist yet, returning empty list");
            return Vec::new();
        }

        let metadata = fs::metadata(&self.db_path);
        match &metadata {
            Ok(m) => debug!("load_clients — DB file size: {} bytes", m.len()),
            Err(_) => {}
        }

        match File::open(&self.db_path) {
            Ok(mut file) => {
                let mut content = String::new();
                if let Err(e) = file.read_to_string(&mut content) {
                    error!("load_clients — error reading DB file: {}", e);
                    return Vec::new();
                }

                debug!("load_clients — read {} bytes from DB file", content.len());

                if content.trim().is_empty() {
                    debug!("load_clients — DB file is empty, returning empty list");
                    return Vec::new();
                }

                match serde_json::from_str::<Vec<Client>>(&content) {
                    Ok(clients) => {
                        info!("load_clients — loaded {} clients from DB", clients.len());
                        debug!("load_clients — first client: {:?}", clients.first().map(|c| &c.name));
                        clients
                    }
                    Err(e) => {
                        error!("load_clients — JSON parse error: {}", e);
                        debug!("load_clients — raw content (first 200 chars): {}", &content[..content.len().min(200)]);
                        Vec::new()
                    }
                }
            }
            Err(e) => {
                error!("load_clients — failed to open DB file {:?}: {}", self.db_path, e);
                Vec::new()
            }
        }
    }

    pub fn save_clients(&self, clients: &[Client]) -> Result<(), String> {
        debug!("save_clients — serializing {} clients to JSON", clients.len());
        let json_str = serde_json::to_string_pretty(clients)
            .map_err(|e| format!("Failed to serialize clients to JSON: {}", e))?;
        debug!("save_clients — JSON size: {} bytes", json_str.len());

        let tmp_path = self.db_path.with_extension("tmp");
        debug!("save_clients — writing to temp file {:?}", tmp_path);
        
        {
            let mut tmp_file = File::create(&tmp_path)
                .map_err(|e| format!("Failed to create temp DB file {:?}: {}", tmp_path, e))?;
            tmp_file.write_all(json_str.as_bytes())
                .map_err(|e| format!("Failed to write temp DB file: {}", e))?;
            debug!("save_clients — temp file written, syncing");
            tmp_file.sync_all()
                .map_err(|e| format!("Failed to sync temp DB file: {}", e))?;
        }

        debug!("save_clients — renaming {:?} -> {:?}", tmp_path, self.db_path);
        fs::rename(&tmp_path, &self.db_path)
            .map_err(|e| format!("Failed to atomically rename DB file: {}", e))?;

        let final_size = fs::metadata(&self.db_path).map(|m| m.len()).unwrap_or(0);
        info!("save_clients — atomically saved {} clients to DB ({} bytes)", clients.len(), final_size);
        Ok(())
    }
}
