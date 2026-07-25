use crate::models::Client;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::PathBuf;
use fs2::FileExt;
use tracing::{info, error, warn};

pub struct StorageManager {
    db_path: PathBuf,
    lock_file: Option<File>,
}

impl StorageManager {
    pub fn new() -> Self {
        let db_path = Self::resolve_db_path();
        info!("FinanceFugue DB path: {:?}", db_path);
        
        let mut manager = StorageManager {
            db_path,
            lock_file: None,
        };

        manager.acquire_lock();
        manager
    }

    fn resolve_db_path() -> PathBuf {
        // First check if root pro_database.json exists in working directory
        let local_path = PathBuf::from("pro_database.json");
        if local_path.exists() {
            return local_path;
        }

        // Default to %LOCALAPPDATA%/FinanceFugue/pro_database.json
        if let Some(data_dir) = dirs::data_local_dir() {
            let app_dir = data_dir.join("FinanceFugue");
            if let Err(e) = fs::create_dir_all(&app_dir) {
                error!("Failed to create AppData directory {:?}: {}", app_dir, e);
            }
            return app_dir.join("pro_database.json");
        }

        local_path
    }

    fn acquire_lock(&mut self) {
        let lock_path = self.db_path.with_extension("lock");
        match OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(&lock_path)
        {
            Ok(file) => {
                if let Err(e) = file.try_lock_exclusive() {
                    warn!("Failed to lock DB file (another instance may be running): {}", e);
                } else {
                    info!("Successfully acquired exclusive lock on {:?}", lock_path);
                    self.lock_file = Some(file);
                }
            }
            Err(e) => {
                error!("Could not open lock file {:?}: {}", lock_path, e);
            }
        }
    }

    pub fn load_clients(&self) -> Vec<Client> {
        if !self.db_path.exists() {
            info!("DB file does not exist yet. Returning empty client list.");
            return Vec::new();
        }

        match File::open(&self.db_path) {
            Ok(mut file) => {
                let mut content = String::new();
                if let Err(e) = file.read_to_string(&mut content) {
                    error!("Error reading DB file: {}", e);
                    return Vec::new();
                }

                if content.trim().is_empty() {
                    return Vec::new();
                }

                match serde_json::from_str::<Vec<Client>>(&content) {
                    Ok(clients) => {
                        info!("Successfully loaded {} clients from DB", clients.len());
                        clients
                    }
                    Err(e) => {
                        error!("Error parsing DB JSON: {}", e);
                        Vec::new()
                    }
                }
            }
            Err(e) => {
                error!("Failed to open DB file {:?}: {}", self.db_path, e);
                Vec::new()
            }
        }
    }

    pub fn save_clients(&self, clients: &[Client]) -> Result<(), String> {
        let json_str = serde_json::to_string_pretty(clients)
            .map_err(|e| format!("Failed to serialize clients to JSON: {}", e))?;

        let tmp_path = self.db_path.with_extension("tmp");
        
        {
            let mut tmp_file = File::create(&tmp_path)
                .map_err(|e| format!("Failed to create temp DB file {:?}: {}", tmp_path, e))?;
            tmp_file.write_all(json_str.as_bytes())
                .map_err(|e| format!("Failed to write temp DB file: {}", e))?;
            tmp_file.sync_all()
                .map_err(|e| format!("Failed to sync temp DB file: {}", e))?;
        }

        fs::rename(&tmp_path, &self.db_path)
            .map_err(|e| format!("Failed to atomically rename DB file: {}", e))?;

        info!("Atomically saved {} clients to DB", clients.len());
        Ok(())
    }
}
