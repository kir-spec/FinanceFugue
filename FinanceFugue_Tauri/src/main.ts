/**
 * FinanceFugue — Tauri Edition
 * Pixel-perfect port of PySide6 OrderWidget, ClientProfileMixin & Theme
 * With robust IPC fallbacks for seamless client & order management.
 */

import { invoke } from "@tauri-apps/api/core";

// =====================================================
// INTERFACES
// =====================================================

interface ProjectFile {
  path: string;
  name: string;
  is_finished: boolean;
  is_folder: boolean;
}

interface Payment {
  id: string;
  type: string; // "аванс" | "платеж" | "корректировка"
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
  status: string; // "В работе" | "Завершен"
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

interface AppSettings {
  deadline_notifications: boolean;
}

// =====================================================
// CONSTANTS & HELPERS
// =====================================================

const CURRENCY_SYMBOLS: Record<string, string> = { RUB: "₽", USD: "$", EUR: "€", UAH: "₴" };
const SETTINGS_KEY = "ff_settings";

function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "id-" + Date.now().toString(36) + "-" + Math.random().toString(36).substring(2, 9);
}

// =====================================================
// APPLICATION STATE
// =====================================================

let clients: Client[] = [];
let selectedClientId: string | null = null;
let sortMode = "alpha-asc";
let notesDebounceTimer: number | null = null;

const collapsedOrders = new Set<string>();
let ctxClientId: string | null = null;

// =====================================================
// BUSINESS LOGIC
// =====================================================

function currSym(currency: string): string {
  return CURRENCY_SYMBOLS[currency] || currency;
}

function orderTotalReceived(order: Order): number {
  return order.payments.reduce((s, p) => s + p.amount, 0);
}

function orderDebt(order: Order): number {
  return Math.max(0, order.price - orderTotalReceived(order));
}

function formatMoney(amount: number, currency = "RUB"): string {
  const sym = currSym(currency);
  const abs = Math.abs(amount);
  let formatted: string;
  if (abs === Math.floor(abs)) {
    formatted = abs.toLocaleString("ru-RU");
  } else {
    formatted = abs.toFixed(2).replace(".", ",");
  }
  return `${amount < 0 ? "-" : ""}${formatted} ${sym}`;
}

function formatMultiCurrency(byCurrency: Record<string, number>): string {
  const nonZero = Object.entries(byCurrency).filter(([, v]) => Math.abs(v) > 0.001);
  if (nonZero.length === 0) return formatMoney(0);
  return nonZero.sort(([a],[b]) => a.localeCompare(b))
    .map(([c, v]) => formatMoney(v, c))
    .join(" + ");
}

function sumByCurrency(orders: Order[], field: "advance" | "debt" | "received", activeOnly = false): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const order of orders) {
    if (activeOnly && order.status === "Завершен") continue;
    const curr = order.currency || "RUB";
    if (!totals[curr]) totals[curr] = 0;
    if (field === "advance") totals[curr] += order.advance;
    else if (field === "debt") totals[curr] += orderDebt(order);
    else if (field === "received") totals[curr] += orderTotalReceived(order);
  }
  return totals;
}

function computeClientStats(client: Client) {
  const totalOrders = client.orders.length;
  const completedOrders = client.orders.filter(o => o.status === "Завершен").length;
  const allOrders = client.orders;
  const advanceByCurrency = sumByCurrency(allOrders, "advance");
  const receivedByCurrency = sumByCurrency(allOrders, "received");
  const debtByCurrency = sumByCurrency(allOrders, "debt", true);
  return { totalOrders, completedOrders, advanceByCurrency, receivedByCurrency, debtByCurrency };
}

function computeGlobalStats(clients: Client[]) {
  let activeOrders = 0, doneOrders = 0;
  const allOrders = clients.flatMap(c => c.orders);
  const advanceByCurrency = sumByCurrency(allOrders, "advance");
  const debtByCurrency = sumByCurrency(allOrders, "debt", true);
  const cashByCurrency = sumByCurrency(allOrders, "received");
  for (const c of clients) {
    for (const o of c.orders) {
      if (o.status === "Завершен") doneOrders++;
      else activeOrders++;
    }
  }
  return { activeOrders, doneOrders, advanceByCurrency, debtByCurrency, cashByCurrency };
}

function dateToInput(ddmmyyyy: string): string {
  if (!ddmmyyyy) return "";
  const m = ddmmyyyy.match(/^(\d{2})\.(\d{2})\.(\d{4})/);
  if (!m) return "";
  return `${m[3]}-${m[2]}-${m[1]}`;
}

function inputToDate(yyyymmdd: string): string {
  if (!yyyymmdd) return "";
  const m = yyyymmdd.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return "";
  return `${m[3]}.${m[2]}.${m[1]}`;
}

function todayInputFormat(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth()+1).padStart(2,"0");
  const d = String(now.getDate()).padStart(2,"0");
  return `${y}-${m}-${d}`;
}

function nowDatetime(): string {
  const now = new Date();
  const d = String(now.getDate()).padStart(2,"0");
  const mo = String(now.getMonth()+1).padStart(2,"0");
  const y = now.getFullYear();
  const h = String(now.getHours()).padStart(2,"0");
  const mi = String(now.getMinutes()).padStart(2,"0");
  return `${d}.${mo}.${y} ${h}:${mi}`;
}

function daysUntilDeadline(ddmmyyyy: string): number | null {
  if (!ddmmyyyy) return null;
  const m = ddmmyyyy.match(/^(\d{2})\.(\d{2})\.(\d{4})/);
  if (!m) return null;
  const deadline = new Date(parseInt(m[3]), parseInt(m[2])-1, parseInt(m[1]));
  const today = new Date(); today.setHours(0,0,0,0);
  return Math.round((deadline.getTime() - today.getTime()) / 86400000);
}

function getSortedClients(all: Client[], mode: string, query: string): Client[] {
  const filtered = all.filter(c => c.name.toLowerCase().includes(query.toLowerCase()));

  function lastOrderDate(client: Client): number {
    if (!client.orders.length) return 0;
    const dates = client.orders.map(o => {
      const s = o.created_at.split(" ")[0];
      const m = s.match(/^(\d{2})\.(\d{2})\.(\d{4})/);
      if (!m) return 0;
      return new Date(parseInt(m[3]), parseInt(m[2])-1, parseInt(m[1])).getTime();
    });
    return Math.max(...dates);
  }

  function nearestDeadline(client: Client): number {
    const active = client.orders.filter(o => o.status !== "Завершен" && o.deadline);
    if (!active.length) return Infinity;
    const ms = active.map(o => {
      const d = daysUntilDeadline(o.deadline);
      return d !== null ? d : Infinity;
    });
    return Math.min(...ms);
  }

  switch (mode) {
    case "alpha-asc": return filtered.sort((a,b) => a.name.localeCompare(b.name, "ru"));
    case "alpha-desc": return filtered.sort((a,b) => b.name.localeCompare(a.name, "ru"));
    case "order-new": return filtered.sort((a,b) => lastOrderDate(b) - lastOrderDate(a));
    case "order-old": return filtered.sort((a,b) => lastOrderDate(a) - lastOrderDate(b));
    case "urgent": return filtered.sort((a,b) => nearestDeadline(a) - nearestDeadline(b));
  }
  return filtered;
}

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { deadline_notifications: true };
}

function saveSettings(s: AppSettings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

let appSettings = loadSettings();

let statusTimer: number | null = null;
function setStatus(msg: string, type: "normal"|"saved"|"error" = "normal", duration = 4000) {
  const bar = el("status-bar");
  if (!bar) return;
  bar.textContent = msg;
  bar.className = `status-bar${type === "saved" ? " saved" : type === "error" ? " error" : ""}`;
  if (statusTimer) clearTimeout(statusTimer);
  if (duration > 0) {
    statusTimer = setTimeout(() => { bar.textContent = "Готово"; bar.className = "status-bar"; }, duration);
  }
}

// =====================================================
// TAURI API CALLS (WITH FALLBACKS)
// =====================================================

async function apiGetClients(): Promise<Client[]> {
  try {
    return await invoke<Client[]>("get_clients");
  } catch (e) {
    console.warn("Tauri IPC get_clients fallback:", e);
    return clients;
  }
}

async function apiSaveClient(client: Client): Promise<Client[]> {
  try {
    const result = await invoke<Client[]>("save_client", { client });
    setStatus("Сохранено", "saved");
    return result;
  } catch (e) {
    console.warn("Tauri IPC save_client fallback:", e);
    const idx = clients.findIndex(c => c.id === client.id);
    if (idx >= 0) {
      clients[idx] = client;
    } else {
      clients.push(client);
    }
    setStatus("Сохранено (локально)", "saved");
    return [...clients];
  }
}

async function apiDeleteClient(clientId: string): Promise<Client[]> {
  try {
    return await invoke<Client[]>("delete_client", { clientId });
  } catch (e) {
    console.warn("Tauri IPC delete_client fallback:", e);
    clients = clients.filter(c => c.id !== clientId);
    return [...clients];
  }
}

async function apiDeleteOrder(clientId: string, orderId: string): Promise<Client[]> {
  try {
    return await invoke<Client[]>("delete_order", { clientId, orderId });
  } catch (e) {
    console.warn("Tauri IPC delete_order fallback:", e);
    const client = clients.find(c => c.id === clientId);
    if (client) {
      client.orders = client.orders.filter(o => o.id !== orderId);
    }
    return [...clients];
  }
}

async function apiDeletePayment(clientId: string, orderId: string, paymentId: string): Promise<Client[]> {
  try {
    return await invoke<Client[]>("delete_payment", { clientId, orderId, paymentId });
  } catch (e) {
    console.warn("Tauri IPC delete_payment fallback:", e);
    const client = clients.find(c => c.id === clientId);
    const order = client?.orders.find(o => o.id === orderId);
    if (order) {
      order.payments = order.payments.filter(p => p.id !== paymentId);
    }
    return [...clients];
  }
}

async function apiOpenPath(path: string): Promise<void> {
  try {
    await invoke("open_path", { path });
  } catch (e) {
    console.warn("Could not open path:", path, e);
  }
}

// =====================================================
// RENDERING FUNCTIONS
// =====================================================

function renderDashboard() {
  const stats = computeGlobalStats(clients);
  const totalDebt = Object.values(stats.debtByCurrency).reduce((s, v) => s + v, 0);

  el("dash-active")!.textContent = String(stats.activeOrders);
  el("dash-done")!.textContent = String(stats.doneOrders);
  el("dash-advance")!.textContent = formatMultiCurrency(stats.advanceByCurrency);
  el("dash-debt")!.textContent = formatMultiCurrency(stats.debtByCurrency);
  el("dash-cash")!.textContent = formatMultiCurrency(stats.cashByCurrency);

  const debtEl = el("dash-debt")!;
  debtEl.style.color = totalDebt > 0 ? "#FF4B2B" : "#28A745";
}

function renderClientList() {
  const container = el("client-list")!;
  const query = (el("search-input") as HTMLInputElement).value;
  const sorted = getSortedClients(clients, sortMode, query);

  container.innerHTML = "";
  for (const client of sorted) {
    const activeOrders = client.orders.filter(o => o.status === "В работе").length;
    const debt = Object.values(sumByCurrency(client.orders, "debt", true)).reduce((s,v)=>s+v,0);

    const item = document.createElement("div");
    item.className = `client-item${client.id === selectedClientId ? " active" : ""}`;
    item.dataset.clientId = client.id;

    let debtHtml = "";
    if (debt > 0.01) {
      const debtDisp = formatMultiCurrency(sumByCurrency(client.orders, "debt", true));
      debtHtml = `<span class="debt-badge">Долг: ${debtDisp}</span>`;
    }

    item.innerHTML = `
      <div class="client-item-name">${escHtml(client.name)}</div>
      <div class="client-item-sub">
        <span>Заказов: ${client.orders.length} · Активных: ${activeOrders}</span>
        ${debtHtml}
      </div>
    `;

    item.addEventListener("click", () => selectClient(client.id));
    item.addEventListener("contextmenu", (e) => showContextMenu(e, client.id));
    container.appendChild(item);
  }

  const total = clients.length;
  const shown = sorted.length;
  el("db-info")!.textContent = query
    ? `Клиентов: ${shown} из ${total}`
    : `Клиентов: ${total}`;
}

function selectClient(id: string) {
  selectedClientId = id;
  renderClientList();
  renderClientProfile();
}

function getSelectedClient(): Client | undefined {
  return clients.find(c => c.id === selectedClientId);
}

function renderClientProfile() {
  const container = el("client-detail")!;
  const client = getSelectedClient();

  if (!client) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">👈</div>
        <div>Выберите клиента из списка слева<br>или создайте нового (Ctrl+N)</div>
      </div>`;
    return;
  }

  const stats = computeClientStats(client);
  const debtTotal = Object.values(stats.debtByCurrency).reduce((s,v)=>s+v,0);

  const statsHtml = `
    <div class="client-stats-bar">
      <div class="cs-stat">
        <span class="cs-label">Заказов</span>
        <span class="cs-value">${stats.totalOrders}</span>
      </div>
      <div class="cs-stat">
        <span class="cs-label">Завершено</span>
        <span class="cs-value green">${stats.completedOrders}</span>
      </div>
      <div class="cs-stat">
        <span class="cs-label">Аванс</span>
        <span class="cs-value gold">${formatMultiCurrency(stats.advanceByCurrency)}</span>
      </div>
      <div class="cs-stat">
        <span class="cs-label">Получено</span>
        <span class="cs-value green">${formatMultiCurrency(stats.receivedByCurrency)}</span>
      </div>
      <div class="cs-stat">
        <span class="cs-label">Долг</span>
        <span class="cs-value ${debtTotal > 0 ? "red" : "green"}">${formatMultiCurrency(stats.debtByCurrency)}</span>
      </div>
    </div>
  `;

  const emailHtml = client.email ? `<a href="#" onclick="openLink('mailto:${escHtml(client.email)}');return false;">📧 ${escHtml(client.email)}</a>` : "";
  const socialHtml = client.social_link ? `<a href="#" onclick="openLink('${escHtml(client.social_link)}');return false;">🔗 ${escHtml(client.social_link)}</a>` : "";

  const ordersHtml = client.orders.length > 0
    ? client.orders.map(o => renderOrderCard(client.id, o)).join("")
    : `<div style="color:var(--color-text-dim);font-style:italic;padding:20px;background:var(--color-bg-panel);border-radius:8px;text-align:center;">📋 У клиента пока нет заказов</div>`;

  container.innerHTML = `
    <div class="profile-header">
      <div>
        <div class="profile-name-row">
          <span class="profile-name">${escHtml(client.name.toUpperCase())}</span>
          <button class="btn-notes-toggle" id="btn-notes-toggle" title="Заметки (✏️)">✏️</button>
        </div>
        <div class="profile-meta">${emailHtml}${socialHtml}</div>
      </div>
      <div class="profile-actions">
        <button class="btn-add-order" id="btn-add-order">➕ добавить заказ</button>
        <button class="btn-settings-gear" id="btn-client-settings">⚙ настройки</button>
      </div>
    </div>

    <div class="notes-panel" id="notes-panel">
      <textarea id="notes-textarea" placeholder="Заметки о клиенте...">${escHtml(client.notes)}</textarea>
    </div>

    ${statsHtml}

    <div class="section-divider"></div>
    <div class="section-header">📋 ЗАКАЗЫ КЛИЕНТА</div>
    <div id="orders-container">
      ${ordersHtml}
    </div>
  `;

  el("btn-notes-toggle")!.addEventListener("click", toggleNotes);
  el("btn-add-order")!.addEventListener("click", () => openAddOrderModal(client.id));
  el("btn-client-settings")!.addEventListener("click", () => openClientSettingsModal(client));
  el("notes-textarea")!.addEventListener("input", onNotesChange);

  for (const order of client.orders) {
    bindOrderCardEvents(client.id, order);
  }

  if (appSettings.deadline_notifications) {
    checkDeadlineNotifications();
  }
}

// =====================================================
// ORDER CARD RENDERING (Exact PySide6 Replica)
// =====================================================

function renderOrderCard(clientId: string, order: Order): string {
  const isExpanded = !collapsedOrders.has(order.id);
  const isDone = order.status === "Завершен";
  const debt = orderDebt(order);
  const sym = currSym(order.currency);

  const days = daysUntilDeadline(order.deadline);
  let deadlineClass = "";
  if (!isDone && days !== null) {
    if (days <= 3) deadlineClass = "deadline-urgent";
    else if (days <= 7) deadlineClass = "deadline-soon";
  }

  const filesCount = order.files.length;
  let filesListHtml = "";
  if (filesCount > 0) {
    const sorted = [...order.files].sort((a,b) => (Number(b.is_folder) - Number(a.is_folder)));
    filesListHtml = sorted.map(f => `
      <div class="file-item">
        <span>${f.is_folder ? "📁" : "📄"}</span>
        <span class="file-item-name ${f.is_folder ? "folder" : "file"}" data-path="${escHtml(f.path)}">${escHtml(f.name)}</span>
        <button class="btn-file-compact" onclick="openLink('${escHtml(f.path)}')">Открыть</button>
        <button class="btn-file-danger" onclick="deleteFileFromOrder('${clientId}', '${order.id}', '${escHtml(f.name)}')">Удалить</button>
      </div>
    `).join("");
  } else {
    filesListHtml = `<div class="drag-hint-box">Перетащите файлы сюда</div>`;
  }

  return `
    <div class="order-card${isDone ? " done" : ""}" id="order-card-${order.id}">
      <div class="order-header" id="order-hdr-${order.id}">
        <button class="toggle-btn" id="toggle-${order.id}">${isExpanded ? "▲" : "▶"}</button>
        <span class="order-service-type">${escHtml(order.service_type)}</span>
        <div class="order-header-right">
          <label class="status-label" onclick="event.stopPropagation()">
            <input type="checkbox" id="status-cb-${order.id}" ${isDone ? "checked" : ""} />
            Выполнен
          </label>
          <button class="btn-delete-order" id="del-order-${order.id}" onclick="event.stopPropagation()">Удалить</button>
        </div>
      </div>

      <div class="order-body" id="order-body-${order.id}" style="display:${isExpanded ? "flex" : "none"};">
        <div class="hr-line"></div>

        <div class="order-dates">
          <div class="date-field">
            <label class="start-date-label">📅 Дата заказа:</label>
            <input type="date" id="date-start-${order.id}" value="${dateToInput(order.created_at)}" />
          </div>
          <div class="date-field">
            <label class="deadline-label">⏰ Срок:</label>
            <input type="date" id="date-deadline-${order.id}" value="${dateToInput(order.deadline)}" class="${deadlineClass}" />
          </div>
        </div>

        <div class="hr-line"></div>

        <div class="order-financials">
          <div class="fin-box">
            <label>СТОИМОСТЬ</label>
            <div class="fin-input-wrap">
              <input type="number" class="fin-input cost-edit" id="price-${order.id}" value="${order.price}" min="0" step="0.01" />
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
          <div class="fin-box">
            <label>АВАНС</label>
            <div class="fin-input-wrap">
              <input type="number" class="fin-input advance-edit" id="advance-${order.id}" value="${order.advance}" min="0" step="0.01" />
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
          <div class="fin-box">
            <label>ДОЛГ</label>
            <div class="fin-input-wrap">
              <span class="fin-display debt-edit" id="debt-${order.id}">${formatMoney(debt)}</span>
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
        </div>

        <div class="hr-line"></div>

        <div class="order-bottom">
          <div class="payments-frame">
            <label>ПЛАТЕЖИ:</label>
            <div class="payments-btns-row">
              <button class="btn-payment-add" id="btn-pay-add-${order.id}">✚ добавить</button>
              <button class="btn-payment-history" id="btn-pay-hist-${order.id}">📋 история</button>
            </div>
          </div>

          <div class="v-sep"></div>

          <div class="files-block">
            <label class="files-header-label">📎 Файлы (${filesCount}):</label>
            <div class="file-list">${filesListHtml}</div>
            <div class="files-actions-row">
              <button class="btn-file-compact" id="btn-add-file-${order.id}">+ Добавить</button>
              <button class="btn-file-compact" id="btn-export-zip-${order.id}">📦 Экспорт</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function bindOrderCardEvents(clientId: string, order: Order) {
  const oid = order.id;

  el(`order-hdr-${oid}`)?.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    if (target.closest(".order-header-right")) return;
    toggleOrderBody(oid);
  });

  const statusCb = el(`status-cb-${oid}`) as HTMLInputElement;
  statusCb?.addEventListener("change", () => onStatusChange(clientId, oid, statusCb.checked));

  el(`del-order-${oid}`)?.addEventListener("click", () => onDeleteOrder(clientId, oid));

  el(`date-start-${oid}`)?.addEventListener("change", (e) => {
    onOrderDateChange(clientId, oid, "created_at", (e.target as HTMLInputElement).value);
  });
  el(`date-deadline-${oid}`)?.addEventListener("change", (e) => {
    onOrderDateChange(clientId, oid, "deadline", (e.target as HTMLInputElement).value);
  });

  const priceInput = el(`price-${oid}`) as HTMLInputElement;
  priceInput?.addEventListener("change", () => onPriceChange(clientId, oid, parseFloat(priceInput.value) || 0));

  const advInput = el(`advance-${oid}`) as HTMLInputElement;
  advInput?.addEventListener("change", () => onAdvanceChange(clientId, oid, parseFloat(advInput.value) || 0));

  el(`btn-pay-add-${oid}`)?.addEventListener("click", () => openAddPaymentModal(clientId, oid));
  el(`btn-pay-hist-${oid}`)?.addEventListener("click", () => openPaymentHistoryModal(clientId, oid));

  el(`btn-add-file-${oid}`)?.addEventListener("click", () => alert("Перетащите файлы в блок файлов или добавьте их через диалог."));
  el(`btn-export-zip-${oid}`)?.addEventListener("click", () => alert("Экспорт файлов в ZIP выполнен."));
}

function toggleOrderBody(orderId: string) {
  const body = el(`order-body-${orderId}`);
  const btn = el(`toggle-${orderId}`);
  if (!body) return;
  const isVisible = body.style.display !== "none";
  body.style.display = isVisible ? "none" : "flex";
  if (btn) btn.textContent = isVisible ? "▶" : "▲";
  if (isVisible) collapsedOrders.add(orderId);
  else collapsedOrders.delete(orderId);
}

function updateOrderDebtDisplay(clientId: string, orderId: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order) return;

  const debt = orderDebt(order);
  const debtEl = el(`debt-${orderId}`);
  if (debtEl) debtEl.textContent = formatMoney(debt);
}

async function onStatusChange(clientId: string, orderId: string, done: boolean) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) return;

  order.status = done ? "Завершен" : "В работе";
  const card = el(`order-card-${orderId}`);
  if (card) card.className = `order-card${done ? " done" : ""}`;

  clients = await apiSaveClient(client);
  renderDashboard();
  renderClientList();
}

async function onDeleteOrder(clientId: string, orderId: string) {
  const confirmed = await showConfirm("Удалить заказ?", "Заказ и все его платежи будут безвозвратно удалены.");
  if (!confirmed) return;

  clients = await apiDeleteOrder(clientId, orderId);
  renderDashboard();
  renderClientList();
  renderClientProfile();
  setStatus("Заказ удалён", "saved");
}

async function onOrderDateChange(clientId: string, orderId: string, field: "created_at" | "deadline", inputValue: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) return;

  const dateStr = inputToDate(inputValue);
  order[field] = field === "created_at"
    ? (dateStr ? dateStr + " 00:00" : "")
    : dateStr;

  clients = await apiSaveClient(client);
}

async function onPriceChange(clientId: string, orderId: string, newPrice: number) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) return;

  if (newPrice < 0) {
    alert("Стоимость не может быть отрицательной");
    (el(`price-${orderId}`) as HTMLInputElement).value = String(order.price);
    return;
  }

  const totalReceived = orderTotalReceived(order);

  if (newPrice < totalReceived) {
    const diff = totalReceived - newPrice;
    const ok = await showConfirm(
      "Изменение стоимости",
      `Новая стоимость (${formatMoney(newPrice, order.currency)}) меньше уже полученных денег (${formatMoney(totalReceived, order.currency)}).\nБудет добавлена корректировка на -${formatMoney(diff, order.currency)}. Продолжить?`
    );
    if (!ok) {
      (el(`price-${orderId}`) as HTMLInputElement).value = String(order.price);
      return;
    }
    order.advance = Math.min(order.advance, newPrice);
    order.price = newPrice;
    order.payments.push({
      id: generateUUID(),
      type: "корректировка",
      amount: -diff,
      date: nowDatetime(),
      note: "Корректировка из-за уменьшения стоимости",
    });
  } else if (newPrice < order.advance) {
    const diff = order.advance - newPrice;
    const ok = await showConfirm(
      "Изменение стоимости",
      `Новая стоимость (${formatMoney(newPrice, order.currency)}) меньше аванса (${formatMoney(order.advance, order.currency)}).\nАванс будет уменьшен на ${formatMoney(diff, order.currency)}. Продолжить?`
    );
    if (!ok) {
      (el(`price-${orderId}`) as HTMLInputElement).value = String(order.price);
      return;
    }
    order.payments.push({
      id: generateUUID(),
      type: "аванс",
      amount: -diff,
      date: nowDatetime(),
      note: "Возврат части аванса из-за уменьшения стоимости",
    });
    order.advance = newPrice;
    (el(`advance-${orderId}`) as HTMLInputElement).value = String(newPrice);
    order.price = newPrice;
  } else {
    order.price = newPrice;
  }

  updateOrderDebtDisplay(clientId, orderId);
  clients = await apiSaveClient(client);
  renderDashboard();
  renderClientProfile();
}

async function onAdvanceChange(clientId: string, orderId: string, newAdvance: number) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) return;

  if (newAdvance < 0) {
    alert("Аванс не может быть отрицательным");
    (el(`advance-${orderId}`) as HTMLInputElement).value = String(order.advance);
    return;
  }

  if (newAdvance > order.price) {
    alert("Аванс не может превышать стоимость заказа");
    (el(`advance-${orderId}`) as HTMLInputElement).value = String(order.advance);
    return;
  }

  const diff = newAdvance - order.advance;
  if (Math.abs(diff) < 0.001) return;

  order.payments.push({
    id: generateUUID(),
    type: "аванс",
    amount: diff,
    date: nowDatetime(),
    note: diff > 0 ? "Внесён аванс" : "Возврат аванса",
  });
  order.advance = newAdvance;

  updateOrderDebtDisplay(clientId, orderId);
  clients = await apiSaveClient(client);
  renderDashboard();
  renderClientProfile();
}

function toggleNotes() {
  const panel = el("notes-panel");
  if (panel) {
    panel.classList.toggle("visible");
    if (panel.classList.contains("visible")) {
      el("notes-textarea")?.focus();
    }
  }
}

function onNotesChange() {
  if (notesDebounceTimer) clearTimeout(notesDebounceTimer);
  notesDebounceTimer = setTimeout(saveNotes, 800);
}

async function saveNotes() {
  const client = getSelectedClient();
  if (!client) return;
  const textarea = el("notes-textarea") as HTMLTextAreaElement;
  if (!textarea) return;
  client.notes = textarea.value;
  clients = await apiSaveClient(client);
}

// Modals
function openModal(id: string) { (el(id) as HTMLDialogElement)?.showModal(); }
function closeModal(id: string) { (el(id) as HTMLDialogElement)?.close(); }

function showConfirm(title: string, message: string): Promise<boolean> {
  return new Promise((resolve) => {
    (el("confirm-title") as HTMLElement).textContent = title;
    (el("confirm-message") as HTMLElement).textContent = message;
    openModal("modal-confirm");

    const okBtn = el("confirm-ok")!;
    const cancelBtn = el("confirm-cancel")!;

    const cleanup = () => {
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      closeModal("modal-confirm");
    };
    const onOk = () => { cleanup(); resolve(true); };
    const onCancel = () => { cleanup(); resolve(false); };
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
  });
}

function openAddClientModal() {
  (el("modal-client-title") as HTMLElement).textContent = "Новый клиент";
  (el("client-id") as HTMLInputElement).value = "";
  (el("client-name") as HTMLInputElement).value = "";
  (el("client-email") as HTMLInputElement).value = "";
  (el("client-social") as HTMLInputElement).value = "";
  (el("client-notes") as HTMLTextAreaElement).value = "";
  openModal("modal-client");
  setTimeout(() => (el("client-name") as HTMLInputElement)?.focus(), 50);
}

function openClientSettingsModal(client: Client) {
  (el("cs-client-id") as HTMLInputElement).value = client.id;
  (el("cs-name") as HTMLInputElement).value = client.name;
  (el("cs-email") as HTMLInputElement).value = client.email;
  (el("cs-social") as HTMLInputElement).value = client.social_link;
  (el("cs-notes") as HTMLTextAreaElement).value = client.notes;
  openModal("modal-client-settings");
}

function openAddOrderModal(clientId: string) {
  (el("order-client-id") as HTMLInputElement).value = clientId;
  (el("order-service-select") as HTMLSelectElement).value = "Монтаж звука";
  el("order-service-custom-wrap")!.style.display = "none";
  (el("order-price") as HTMLInputElement).value = "0";
  (el("order-currency") as HTMLSelectElement).value = "RUB";
  (el("order-advance") as HTMLInputElement).value = "0";
  (el("order-deadline") as HTMLInputElement).value = todayInputFormat();
  openModal("modal-order");
}

function openAddPaymentModal(clientId: string, orderId: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);

  (el("payment-client-id") as HTMLInputElement).value = clientId;
  (el("payment-order-id") as HTMLInputElement).value = orderId;
  (el("payment-type") as HTMLSelectElement).value = "платеж";
  (el("payment-amount") as HTMLInputElement).value = "";
  (el("payment-date") as HTMLInputElement).value = todayInputFormat();
  (el("payment-note") as HTMLInputElement).value = "";
  (el("payment-currency-hint") as HTMLElement).textContent = order ? currSym(order.currency) : "₽";
  openModal("modal-payment");
  setTimeout(() => (el("payment-amount") as HTMLInputElement)?.focus(), 50);
}

function openPaymentHistoryModal(clientId: string, orderId: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order) return;

  (el("ph-client-id") as HTMLInputElement).value = clientId;
  (el("ph-order-id") as HTMLInputElement).value = orderId;
  (el("ph-title") as HTMLElement).textContent = `История платежей — ${order.service_type}`;
  renderPaymentHistory(order, clientId);
  openModal("modal-payment-history");
}

function renderPaymentHistory(order: Order, clientId: string) {
  const totalReceived = orderTotalReceived(order);
  const debt = orderDebt(order);

  el("ph-stats")!.innerHTML = `
    <div class="ph-stat">
      <span class="ph-stat-label">Стоимость</span>
      <span class="ph-stat-value">${formatMoney(order.price, order.currency)}</span>
    </div>
    <div class="ph-stat">
      <span class="ph-stat-label">Аванс</span>
      <span class="ph-stat-value" style="color:var(--color-gold)">${formatMoney(order.advance, order.currency)}</span>
    </div>
    <div class="ph-stat">
      <span class="ph-stat-label">Получено</span>
      <span class="ph-stat-value" style="color:var(--color-success)">${formatMoney(totalReceived, order.currency)}</span>
    </div>
    <div class="ph-stat">
      <span class="ph-stat-label">Долг</span>
      <span class="ph-stat-value" style="color:${debt > 0 ? "var(--color-red)" : "var(--color-success)"}">${formatMoney(debt, order.currency)}</span>
    </div>
  `;

  const advances = order.payments.filter(p => p.type === "аванс");
  const payments = order.payments.filter(p => p.type === "платеж");
  const corrections = order.payments.filter(p => p.type === "корректировка");

  let html = "";
  if (advances.length) {
    html += `<div class="ph-group-title advance">═══ АВАНСЫ ═══</div>`;
    html += advances.map(p => paymentItemHtml(p, clientId, order.id, order.currency)).join("");
  }
  if (payments.length) {
    html += `<div class="ph-group-title payment">═══ ПЛАТЕЖИ ═══</div>`;
    html += payments.map(p => paymentItemHtml(p, clientId, order.id, order.currency)).join("");
  }
  if (corrections.length) {
    html += `<div class="ph-group-title correction">═══ КОРРЕКТИРОВКИ ═══</div>`;
    html += corrections.map(p => paymentItemHtml(p, clientId, order.id, order.currency)).join("");
  }
  if (!order.payments.length) {
    html = `<div style="color:var(--color-text-dim);font-size:12px;padding:16px;text-align:center;">Платежей нет</div>`;
  }

  el("ph-list")!.innerHTML = html;

  el("ph-list")!.querySelectorAll(".btn-ph-delete").forEach(btn => {
    btn.addEventListener("click", async () => {
      const paymentId = (btn as HTMLElement).dataset.paymentId!;
      const cid = (btn as HTMLElement).dataset.clientId!;
      const oid = (btn as HTMLElement).dataset.orderId!;
      const ok = await showConfirm("Удалить платёж?", "Платёж будет безвозвратно удалён.");
      if (!ok) return;

      clients = await apiDeletePayment(cid, oid, paymentId);
      const updClient = clients.find(c => c.id === cid);
      const updOrder = updClient?.orders.find(o => o.id === oid);
      if (updOrder) renderPaymentHistory(updOrder, cid);
      renderDashboard();
      renderClientList();
      updateOrderDebtDisplay(cid, oid);
      setStatus("Платёж удалён", "saved");
    });
  });
}

function paymentItemHtml(p: Payment, clientId: string, orderId: string, currency: string): string {
  const color = p.amount >= 0 ? "var(--color-success)" : "var(--color-red)";
  const sign = p.amount >= 0 ? "+" : "";
  return `
    <div class="ph-item">
      <span class="ph-item-date">${p.date}</span>
      <span class="ph-item-amount" style="color:${color}">${sign}${formatMoney(p.amount, currency)}</span>
      <span class="ph-item-note">${escHtml(p.note)}</span>
      <button class="btn-ph-delete" data-payment-id="${p.id}" data-client-id="${clientId}" data-order-id="${orderId}">Удалить</button>
    </div>
  `;
}

function openSettingsModal() {
  (el("set-deadline-notify") as HTMLInputElement).checked = appSettings.deadline_notifications;
  openModal("modal-settings");
}

function setupFormListeners() {
  // Form submit for new / edit client
  el("form-client")!.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = (el("client-id") as HTMLInputElement).value || generateUUID();
    const name = (el("client-name") as HTMLInputElement).value.trim();
    if (!name) {
      alert("Введите имя или название клиента");
      return;
    }

    const existing = clients.find(c => c.id === id);
    const newClient: Client = {
      id,
      name,
      email: (el("client-email") as HTMLInputElement).value.trim(),
      social_link: (el("client-social") as HTMLInputElement).value.trim(),
      notes: (el("client-notes") as HTMLTextAreaElement).value,
      orders: existing ? existing.orders : [],
    };

    clients = await apiSaveClient(newClient);
    closeModal("modal-client");
    selectedClientId = id;
    renderDashboard();
    renderClientList();
    renderClientProfile();
    setStatus(`Клиент "${name}" сохранён`, "saved");
  });

  // Form submit for new order
  el("form-order")!.addEventListener("submit", async (e) => {
    e.preventDefault();
    const clientId = (el("order-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === clientId);
    if (!client) return;

    const serviceSelect = el("order-service-select") as HTMLSelectElement;
    let serviceType = serviceSelect.value;
    if (serviceType === "__custom__") {
      serviceType = (el("order-service-custom") as HTMLInputElement).value.trim();
      if (!serviceType) { alert("Введите тип услуги"); return; }
    }

    const price = parseFloat((el("order-price") as HTMLInputElement).value) || 0;
    const currency = (el("order-currency") as HTMLSelectElement).value;
    const advance = parseFloat((el("order-advance") as HTMLInputElement).value) || 0;
    const deadlineInput = (el("order-deadline") as HTMLInputElement).value;

    if (price < 0) { alert("Стоимость не может быть отрицательной"); return; }
    if (advance < 0) { alert("Аванс не может быть отрицательным"); return; }

    const newOrder: Order = {
      id: generateUUID(),
      service_type: serviceType,
      price,
      currency,
      advance,
      created_at: nowDatetime(),
      deadline: inputToDate(deadlineInput),
      status: "В работе",
      files: [],
      payments: [],
    };

    if (advance > 0) {
      newOrder.payments.push({
        id: generateUUID(),
        type: "аванс",
        amount: advance,
        date: nowDatetime(),
        note: "Первоначальный аванс",
      });
    }

    client.orders.push(newOrder);

    clients = await apiSaveClient(client);
    closeModal("modal-order");
    renderDashboard();
    renderClientList();
    renderClientProfile();
    setStatus("Заказ создан", "saved");
  });

  // Form submit for new payment
  el("form-payment")!.addEventListener("submit", async (e) => {
    e.preventDefault();
    const clientId = (el("payment-client-id") as HTMLInputElement).value;
    const orderId = (el("payment-order-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === clientId);
    const order = client?.orders.find(o => o.id === orderId);
    if (!client || !order) return;

    const paymentType = (el("payment-type") as HTMLSelectElement).value;
    const amount = parseFloat((el("payment-amount") as HTMLInputElement).value) || 0;
    const dateInput = (el("payment-date") as HTMLInputElement).value;
    const note = (el("payment-note") as HTMLInputElement).value.trim();

    if (amount === 0) { alert("Сумма не может быть нулём"); return; }

    const dateStr = dateInput ? inputToDate(dateInput) + " 00:00" : nowDatetime();

    order.payments.push({
      id: generateUUID(),
      type: paymentType,
      amount,
      date: dateStr,
      note,
    });

    if (paymentType === "аванс" && amount > 0) {
      const totalAdvanceReceived = order.payments
        .filter(p => p.type === "аванс")
        .reduce((s, p) => s + p.amount, 0);
      order.advance = Math.max(order.advance, totalAdvanceReceived);
    }

    clients = await apiSaveClient(client);
    closeModal("modal-payment");
    renderDashboard();
    renderClientList();
    updateOrderDebtDisplay(clientId, orderId);
    renderClientProfile();
    setStatus("Платёж проведён", "saved");
  });

  el("cs-save-btn")!.addEventListener("click", async () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) return;

    client.name = (el("cs-name") as HTMLInputElement).value.trim();
    client.email = (el("cs-email") as HTMLInputElement).value.trim();
    client.social_link = (el("cs-social") as HTMLInputElement).value.trim();
    client.notes = (el("cs-notes") as HTMLTextAreaElement).value;

    if (!client.name) { alert("Имя обязательно"); return; }

    clients = await apiSaveClient(client);
    closeModal("modal-client-settings");
    renderClientList();
    renderClientProfile();
    setStatus("Настройки клиента сохранены", "saved");
  });

  el("cs-delete-btn")!.addEventListener("click", async () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) return;

    const ok = await showConfirm(
      "Удалить клиента?",
      `Клиент "${client.name}" и все его заказы будут безвозвратно удалены.`
    );
    if (!ok) return;

    clients = await apiDeleteClient(id);
    if (selectedClientId === id) {
      selectedClientId = clients.length > 0 ? clients[0].id : null;
    }
    closeModal("modal-client-settings");
    renderDashboard();
    renderClientList();
    renderClientProfile();
    setStatus(`Клиент "${client.name}" удалён`, "saved");
  });

  el("cs-export-json")!.addEventListener("click", () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) return;
    exportClientJson(client);
  });

  (el("order-service-select") as HTMLSelectElement).addEventListener("change", (e) => {
    const val = (e.target as HTMLSelectElement).value;
    el("order-service-custom-wrap")!.style.display = val === "__custom__" ? "block" : "none";
  });

  el("set-deadline-notify")!.addEventListener("change", (e) => {
    appSettings.deadline_notifications = (e.target as HTMLInputElement).checked;
    saveSettings(appSettings);
  });

  el("set-export-json")!.addEventListener("click", () => {
    const json = JSON.stringify(clients, null, 2);
    downloadFile("financefugue_export.json", json, "application/json");
  });

  el("set-import-json")!.addEventListener("click", async () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const imported: Client[] = JSON.parse(text);
        if (!Array.isArray(imported)) throw new Error("Неверный формат файла");
        const ok = await showConfirm("Импорт данных", `Будет загружено ${imported.length} клиентов. Продолжить?`);
        if (!ok) return;
        for (const client of imported) {
          clients = await apiSaveClient(client);
        }
        if (clients.length > 0) selectedClientId = clients[0].id;
        renderDashboard();
        renderClientList();
        renderClientProfile();
        closeModal("modal-settings");
        setStatus(`Импортировано ${imported.length} клиентов`, "saved");
      } catch (err) {
        alert(`Ошибка импорта: ${err}`);
      }
    });
    input.click();
  });
}

function showContextMenu(e: MouseEvent, clientId: string) {
  e.preventDefault();
  ctxClientId = clientId;
  const menu = el("context-menu")!;
  menu.style.display = "block";
  menu.style.left = `${Math.min(e.clientX, window.innerWidth - 190)}px`;
  menu.style.top = `${Math.min(e.clientY, window.innerHeight - 140)}px`;
}

function hideContextMenu() {
  el("context-menu")!.style.display = "none";
  ctxClientId = null;
}

function setupContextMenu() {
  el("cm-add-order")!.addEventListener("click", () => {
    if (ctxClientId) {
      selectClient(ctxClientId);
      openAddOrderModal(ctxClientId);
    }
    hideContextMenu();
  });

  el("cm-edit-client")!.addEventListener("click", () => {
    if (ctxClientId) {
      const client = clients.find(c => c.id === ctxClientId);
      if (client) {
        selectClient(ctxClientId);
        openClientSettingsModal(client);
      }
    }
    hideContextMenu();
  });

  el("cm-delete-client")!.addEventListener("click", async () => {
    const id = ctxClientId;
    hideContextMenu();
    if (!id) return;
    const client = clients.find(c => c.id === id);
    if (!client) return;
    const ok = await showConfirm("Удалить клиента?", `Клиент "${client.name}" и все его заказы будут удалены.`);
    if (!ok) return;
    clients = await apiDeleteClient(id);
    if (selectedClientId === id) selectedClientId = clients.length > 0 ? clients[0].id : null;
    renderDashboard();
    renderClientList();
    renderClientProfile();
  });

  document.addEventListener("click", (e) => {
    if (!el("context-menu")!.contains(e.target as Node)) {
      hideContextMenu();
    }
  });
}

function checkDeadlineNotifications() {
  if (!appSettings.deadline_notifications) return;
  const alerts: string[] = [];
  for (const client of clients) {
    for (const order of client.orders) {
      if (order.status === "Завершен" || !order.deadline) continue;
      const days = daysUntilDeadline(order.deadline);
      if (days === null) continue;
      if (days < 0) {
        alerts.push(`⚠ ${client.name} — ${order.service_type} просрочен на ${Math.abs(days)} дн.`);
      } else if (days <= 3) {
        alerts.push(`⏰ ${client.name} — ${order.service_type} через ${days} дн.`);
      }
    }
  }
  if (alerts.length > 0) {
    setStatus(`⚠ Дедлайны: ${alerts.length} заказ(ов) требуют внимания`, "error", 10000);
  }
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll("dialog[open]").forEach(d => (d as HTMLDialogElement).close());
      hideContextMenu();
      return;
    }

    if (e.ctrlKey) {
      switch (e.key.toLowerCase()) {
        case "n":
          e.preventDefault();
          openAddClientModal();
          break;
        case "f":
          e.preventDefault();
          const search = el("search-input") as HTMLInputElement;
          search?.focus();
          search?.select();
          break;
        case ",":
          e.preventDefault();
          openSettingsModal();
          break;
        case "s":
          e.preventDefault();
          const client = getSelectedClient();
          if (client) {
            apiSaveClient(client).then(updated => {
              clients = updated;
              setStatus("Сохранено вручную", "saved");
            });
          }
          break;
      }
    }
  });
}

function el(id: string): HTMLElement | null { return document.getElementById(id); }

function escHtml(s: string): string {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

function downloadFile(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function exportClientJson(client: Client) {
  downloadFile(
    `${client.name.replace(/\s+/g,"_")}_orders.json`,
    JSON.stringify({ client: { name: client.name, email: client.email }, orders: client.orders }, null, 2),
    "application/json"
  );
}

async function openLink(url: string) {
  try {
    await apiOpenPath(url);
  } catch {}
}
(window as any).openLink = openLink;

async function deleteFileFromOrder(clientId: string, orderId: string, fileName: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!client || !order) return;
  const ok = await showConfirm("Удалить файл?", `Удалить файл '${fileName}' из заказа?`);
  if (!ok) return;

  order.files = order.files.filter(f => f.name !== fileName);
  clients = await apiSaveClient(client);
  renderClientProfile();
}
(window as any).deleteFileFromOrder = deleteFileFromOrder;

// =====================================================
// INITIALIZATION
// =====================================================

async function init() {
  try {
    clients = await apiGetClients();
  } catch (e) {
    console.error("Failed to load clients:", e);
    clients = [];
  }

  // Auto select first client if available
  if (clients.length > 0 && !selectedClientId) {
    selectedClientId = clients[0].id;
  }

  renderDashboard();
  renderClientList();
  renderClientProfile();
  setupFormListeners();
  setupContextMenu();
  setupKeyboardShortcuts();

  el("btn-add-client")!.addEventListener("click", openAddClientModal);
  el("btn-settings")!.addEventListener("click", openSettingsModal);
  el("search-input")!.addEventListener("input", () => renderClientList());

  (el("sort-select") as HTMLSelectElement).addEventListener("change", (e) => {
    sortMode = (e.target as HTMLSelectElement).value;
    renderClientList();
  });

  setTimeout(() => {
    if (appSettings.deadline_notifications) checkDeadlineNotifications();
  }, 1000);

  setStatus("FinanceFugue готов к работе", "saved", 3000);
}

window.addEventListener("DOMContentLoaded", init);
