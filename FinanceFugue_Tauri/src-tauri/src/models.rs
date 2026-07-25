use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProjectFile {
    pub path: String,
    pub name: String,
    #[serde(default)]
    pub is_finished: bool,
    #[serde(default)]
    pub is_folder: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Payment {
    #[serde(default = "generate_uuid")]
    pub id: String,
    #[serde(default)]
    pub r#type: String, // "аванс", "платеж", "корректировка"
    #[serde(default)]
    pub amount: f64,
    #[serde(default)]
    pub date: String,
    #[serde(default)]
    pub note: String,
}

fn generate_uuid() -> String {
    Uuid::new_v4().to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Order {
    pub id: String,
    pub service_type: String,
    #[serde(default)]
    pub price: f64,
    #[serde(default = "default_currency")]
    pub currency: String,
    #[serde(default)]
    pub advance: f64,
    #[serde(default)]
    pub created_at: String,
    #[serde(default)]
    pub deadline: String,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default)]
    pub files: Vec<ProjectFile>,
    #[serde(default)]
    pub payments: Vec<Payment>,
}

fn default_currency() -> String {
    "RUB".to_string()
}

fn default_status() -> String {
    "В работе".to_string()
}

impl Order {
    pub fn total_received(&self) -> f64 {
        self.payments.iter().map(|p| p.amount).sum()
    }

    pub fn total_advance_received(&self) -> f64 {
        self.payments
            .iter()
            .filter(|p| p.r#type == "аванс")
            .map(|p| p.amount)
            .sum()
    }

    pub fn total_payments_received(&self) -> f64 {
        self.payments
            .iter()
            .filter(|p| p.r#type == "платеж")
            .map(|p| p.amount)
            .sum()
    }

    pub fn total_corrections_received(&self) -> f64 {
        self.payments
            .iter()
            .filter(|p| p.r#type == "корректировка")
            .map(|p| p.amount)
            .sum()
    }

    pub fn debt(&self) -> f64 {
        (self.price - self.total_received()).max(0.0)
    }

    pub fn remaining_debt(&self) -> f64 {
        (self.price - self.advance - self.total_payments_received() - self.total_corrections_received()).max(0.0)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Client {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub email: String,
    #[serde(default)]
    pub social_link: String,
    #[serde(default)]
    pub notes: String,
    #[serde(default)]
    pub orders: Vec<Order>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardStats {
    pub total_clients: usize,
    pub total_orders: usize,
    pub active_orders: usize,
    pub total_revenue: f64,
    pub total_debt: f64,
}
