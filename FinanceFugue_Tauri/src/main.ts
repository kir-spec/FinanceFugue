import { invoke } from "@tauri-apps/api/core";

interface ProjectFile {
  path: string;
  name: string;
  is_finished: boolean;
  is_folder: boolean;
}

interface Payment {
  id: string;
  type: string;
  amount: number;
  date: string;
  note: string;
}

interface Order {
  id: string;
  service_type: string;
  price: number;
  currency: string;
  advance: number;
  created_at: string;
  deadline: string;
  status: string;
  files: ProjectFile[];
  payments: Payment[];
}

interface Client {
  id: string;
  name: string;
  email: string;
  social_link: string;
  notes: string;
  orders: Order[];
}

interface DashboardStats {
  total_clients: number;
  total_orders: number;
  active_orders: number;
  total_revenue: number;
  total_debt: number;
}

let clients: Client[] = [];
let selectedClientId: string | null = null;

// Инициализация при загрузке
window.addEventListener("DOMContentLoaded", () => {
  loadClients();
  loadStats();
  setupEventListeners();
});

async function loadClients() {
  try {
    clients = await invoke<Client[]>("get_clients");
    renderClientList();
  } catch (err) {
    console.error("Ошибка загрузки клиентов:", err);
  }
}

async function loadStats() {
  try {
    const stats = await invoke<DashboardStats>("get_dashboard_stats");
    (document.getElementById("stat-clients") as HTMLElement).innerText = stats.total_clients.toString();
    (document.getElementById("stat-orders") as HTMLElement).innerText = stats.active_orders.toString();
    (document.getElementById("stat-revenue") as HTMLElement).innerText = `${stats.total_revenue.toLocaleString()} ₽`;
    (document.getElementById("stat-debt") as HTMLElement).innerText = `${stats.total_debt.toLocaleString()} ₽`;
  } catch (err) {
    console.error("Ошибка загрузки статистики:", err);
  }
}

function renderClientList(filter = "") {
  const container = document.getElementById("client-list") as HTMLElement;
  container.innerHTML = "";

  const filtered = clients.filter(c => c.name.toLowerCase().includes(filter.toLowerCase()));

  filtered.forEach(client => {
    const activeOrders = client.orders.filter(o => o.status === "В работе").length;
    
    const item = document.createElement("div");
    item.className = `client-item ${client.id === selectedClientId ? "active" : ""}`;
    item.innerHTML = `
      <div class="client-item-name">${client.name}</div>
      <div class="client-item-sub">
        <span>Заказов: ${client.orders.length}</span>
        <span>В работе: ${activeOrders}</span>
      </div>
    `;
    item.addEventListener("click", () => selectClient(client.id));
    container.appendChild(item);
  });
}

function selectClient(id: string) {
  selectedClientId = id;
  renderClientList((document.getElementById("search-input") as HTMLInputElement).value);
  renderClientDetail();
}

function renderClientDetail() {
  const container = document.getElementById("client-detail") as HTMLElement;
  const client = clients.find(c => c.id === selectedClientId);

  if (!client) {
    container.innerHTML = `<div class="empty-state"><span>👈 Выберите клиента из списка слева</span></div>`;
    return;
  }

  const ordersHtml = client.orders.map(order => {
    const totalReceived = order.payments.reduce((acc, p) => acc + p.amount, 0);
    const debt = Math.max(0, order.price - totalReceived);
    
    return `
      <div class="order-card">
        <div class="order-header">
          <span class="order-title">${order.service_type}</span>
          <span class="badge-tag">${order.status}</span>
        </div>
        <div class="order-finances">
          <div class="fin-item">Стоимость: <strong>${order.price.toLocaleString()} ${order.currency}</strong></div>
          <div class="fin-item">Получено: <strong>${totalReceived.toLocaleString()} ${order.currency}</strong></div>
          <div class="fin-item debt">Остаток долга: <strong>${debt.toLocaleString()} ${order.currency}</strong></div>
        </div>
        <div style="display: flex; gap: 8px; justify-content: flex-end;">
          <button class="btn btn-sm btn-primary" onclick="window.openPaymentModal('${client.id}', '${order.id}')">+ Оплата</button>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">
        <h2>${client.name}</h2>
        <div class="detail-meta">
          ${client.email ? `<span>📧 ${client.email}</span>` : ""}
          ${client.social_link ? `<span>🔗 ${client.social_link}</span>` : ""}
        </div>
      </div>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-sm btn-primary" onclick="window.openOrderModal('${client.id}')">+ Заказ</button>
        <button class="btn btn-sm btn-danger" onclick="window.deleteClient('${client.id}')">Удалить</button>
      </div>
    </div>
    ${client.notes ? `<div style="font-size: 13px; color: var(--text-muted); background: var(--bg-tertiary); padding: 10px; border-radius: 6px;">📝 ${client.notes}</div>` : ""}
    <div class="orders-section">
      <h3>Заказы клиента</h3>
      ${ordersHtml || "<div style='color: var(--text-muted); font-size: 13px;'>Нет активных заказов</div>"}
    </div>
  `;
}

function setupEventListeners() {
  const searchInput = document.getElementById("search-input") as HTMLInputElement;
  searchInput.addEventListener("input", (e) => {
    renderClientList((e.target as HTMLInputElement).value);
  });

  document.getElementById("btn-add-client")?.addEventListener("click", () => {
    (document.getElementById("form-client") as HTMLFormElement).reset();
    (document.getElementById("client-id") as HTMLInputElement).value = "";
    (document.getElementById("modal-client-title") as HTMLElement).innerText = "Новый клиент";
    (document.getElementById("modal-client") as HTMLDialogElement).showModal();
  });

  document.getElementById("form-client")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = (document.getElementById("client-id") as HTMLInputElement).value || crypto.randomUUID();
    const name = (document.getElementById("client-name") as HTMLInputElement).value;
    const email = (document.getElementById("client-email") as HTMLInputElement).value;
    const social_link = (document.getElementById("client-social") as HTMLInputElement).value;
    const notes = (document.getElementById("client-notes") as HTMLTextAreaElement).value;

    const existing = clients.find(c => c.id === id);
    const newClient: Client = {
      id,
      name,
      email,
      social_link,
      notes,
      orders: existing ? existing.orders : []
    };

    try {
      clients = await invoke<Client[]>("save_client", { client: newClient });
      selectClient(id);
      loadStats();
      (document.getElementById("modal-client") as HTMLDialogElement).close();
    } catch (err) {
      alert("Ошибка сохранения: " + err);
    }
  });

  document.getElementById("form-order")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const clientId = (document.getElementById("order-client-id") as HTMLInputElement).value;
    const service_type = (document.getElementById("order-service") as HTMLInputElement).value;
    const price = parseFloat((document.getElementById("order-price") as HTMLInputElement).value);
    const currency = (document.getElementById("order-currency") as HTMLSelectElement).value;
    const advance = parseFloat((document.getElementById("order-advance") as HTMLInputElement).value);
    const deadline = (document.getElementById("order-deadline") as HTMLInputElement).value;

    const client = clients.find(c => c.id === clientId);
    if (!client) return;

    const newOrder: Order = {
      id: crypto.randomUUID(),
      service_type,
      price,
      currency,
      advance,
      created_at: new Date().toLocaleDateString("ru-RU"),
      deadline,
      status: "В работе",
      files: [],
      payments: []
    };

    client.orders.push(newOrder);

    try {
      clients = await invoke<Client[]>("save_client", { client });
      selectClient(clientId);
      loadStats();
      (document.getElementById("modal-order") as HTMLDialogElement).close();
    } catch (err) {
      alert("Ошибка создания заказа: " + err);
    }
  });

  document.getElementById("form-payment")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const clientId = (document.getElementById("payment-client-id") as HTMLInputElement).value;
    const orderId = (document.getElementById("payment-order-id") as HTMLInputElement).value;
    const paymentType = (document.getElementById("payment-type") as HTMLSelectElement).value;
    const amount = parseFloat((document.getElementById("payment-amount") as HTMLInputElement).value);
    const note = (document.getElementById("payment-note") as HTMLInputElement).value;

    try {
      clients = await invoke<Client[]>("add_payment", {
        clientId,
        orderId,
        amount,
        paymentType,
        note
      });
      selectClient(clientId);
      loadStats();
      (document.getElementById("modal-payment") as HTMLDialogElement).close();
    } catch (err) {
      alert("Ошибка проведения платежа: " + err);
    }
  });
}

// Глобальные хелперы для кнопок в HTML
(window as any).openOrderModal = (clientId: string) => {
  (document.getElementById("form-order") as HTMLFormElement).reset();
  (document.getElementById("order-client-id") as HTMLInputElement).value = clientId;
  (document.getElementById("modal-order") as HTMLDialogElement).showModal();
};

(window as any).openPaymentModal = (clientId: string, orderId: string) => {
  (document.getElementById("form-payment") as HTMLFormElement).reset();
  (document.getElementById("payment-client-id") as HTMLInputElement).value = clientId;
  (document.getElementById("payment-order-id") as HTMLInputElement).value = orderId;
  (document.getElementById("modal-payment") as HTMLDialogElement).showModal();
};

(window as any).deleteClient = async (clientId: string) => {
  if (!confirm("Вы уверены, что хотите удалить этого клиента и все его заказы?")) return;
  try {
    clients = await invoke<Client[]>("delete_client", { clientId });
    selectedClientId = null;
    renderClientList();
    renderClientDetail();
    loadStats();
  } catch (err) {
    alert("Ошибка удаления: " + err);
  }
};
