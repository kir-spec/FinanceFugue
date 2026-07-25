use crate::models::{Client, Payment};
use crate::storage::StorageManager;
use std::sync::{Arc, Mutex};
use tauri::State;
use chrono::Local;

pub struct AppState {
    pub storage: StorageManager,
    pub clients: Mutex<Vec<Client>>,
}

#[tauri::command]
pub fn get_clients(state: State<'_, Arc<AppState>>) -> Vec<Client> {
    let clients = state.clients.lock().unwrap();
    clients.clone()
}

#[tauri::command]
pub fn save_client(client: Client, state: State<'_, Arc<AppState>>) -> Result<Vec<Client>, String> {
    let mut clients = state.clients.lock().unwrap();

    if let Some(pos) = clients.iter().position(|c| c.id == client.id) {
        clients[pos] = client;
    } else {
        clients.push(client);
    }

    state.storage.save_clients(&clients)?;
    Ok(clients.clone())
}

#[tauri::command]
pub fn delete_client(client_id: String, state: State<'_, Arc<AppState>>) -> Result<Vec<Client>, String> {
    let mut clients = state.clients.lock().unwrap();
    clients.retain(|c| c.id != client_id);
    state.storage.save_clients(&clients)?;
    Ok(clients.clone())
}

#[tauri::command]
pub fn delete_order(
    client_id: String,
    order_id: String,
    state: State<'_, Arc<AppState>>,
) -> Result<Vec<Client>, String> {
    let mut clients = state.clients.lock().unwrap();
    let client = clients
        .iter_mut()
        .find(|c| c.id == client_id)
        .ok_or("Клиент не найден")?;
    client.orders.retain(|o| o.id != order_id);
    state.storage.save_clients(&clients)?;
    Ok(clients.clone())
}

#[tauri::command]
pub fn delete_payment(
    client_id: String,
    order_id: String,
    payment_id: String,
    state: State<'_, Arc<AppState>>,
) -> Result<Vec<Client>, String> {
    let mut clients = state.clients.lock().unwrap();
    let client = clients
        .iter_mut()
        .find(|c| c.id == client_id)
        .ok_or("Клиент не найден")?;
    let order = client
        .orders
        .iter_mut()
        .find(|o| o.id == order_id)
        .ok_or("Заказ не найден")?;
    order.payments.retain(|p| p.id != payment_id);
    state.storage.save_clients(&clients)?;
    Ok(clients.clone())
}

#[tauri::command]
pub fn add_payment(
    client_id: String,
    order_id: String,
    amount: f64,
    payment_type: String,
    note: String,
    state: State<'_, Arc<AppState>>,
) -> Result<Vec<Client>, String> {
    let mut clients = state.clients.lock().unwrap();

    let client = clients
        .iter_mut()
        .find(|c| c.id == client_id)
        .ok_or_else(|| "Клиент не найден".to_string())?;

    let order = client
        .orders
        .iter_mut()
        .find(|o| o.id == order_id)
        .ok_or_else(|| "Заказ не найден".to_string())?;

    let payment = Payment {
        id: uuid::Uuid::new_v4().to_string(),
        r#type: payment_type,
        amount,
        date: Local::now().format("%d.%m.%Y %H:%M").to_string(),
        note,
    };

    order.payments.push(payment);

    state.storage.save_clients(&clients)?;
    Ok(clients.clone())
}

#[tauri::command]
pub fn open_path(path: String) -> Result<(), String> {
    open::that(&path).map_err(|e| format!("Не удалось открыть '{}': {}", path, e))
}
