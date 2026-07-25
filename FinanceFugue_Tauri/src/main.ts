/**
 * FinanceFugue — Tauri Edition
 * Full-featured TypeScript frontend matching the Python version's philosophy:
 * - Rich client cards with statistics
 * - Full order management (price/advance/debt, payments, files)
 * - Multi-currency support
 * - Sorting, search, context menu
 * - Payment history with grouped view and delete
 * - Deadline coloring and notifications
 * - Keyboard shortcuts
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
// CONSTANTS
// =====================================================

const CURRENCY_SYMBOLS: Record<string, string> = { RUB: "₽", USD: "$", EUR: "€", UAH: "₴" };
const SERVICE_TYPES = ["Монтаж звука","Монтаж аудио","Оркестровка","Нотный набор","Сведение","Аранжировка","Мастеринг","Консультация"];
const SETTINGS_KEY = "ff_settings";

// =====================================================
// APPLICATION STATE
// =====================================================

let clients: Client[] = [];
let selectedClientId: string | null = null;
let sortMode = "alpha-asc";
let notesDebounceTimer: number | null = null;

// Tracks which order IDs are collapsed (default = all expanded)
const collapsedOrders = new Set<string>();

// Context menu target
let ctxClientId: string | null = null;

// =====================================================
// BUSINESS LOGIC — PURE FUNCTIONS
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

// Date utilities: convert between "dd.MM.yyyy" (storage) and "yyyy-MM-dd" (HTML input)
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

// =====================================================
// SETTINGS
// =====================================================

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

// =====================================================
// STATUS BAR
// =====================================================

let statusTimer: number | null = null;

function setStatus(msg: string, type: "normal"|"saved"|"error" = "normal", duration = 4000) {
  const bar = document.getElementById("status-bar")!;
  bar.textContent = msg;
  bar.className = `status-bar${type === "saved" ? " saved" : type === "error" ? " error" : ""}`;
  if (statusTimer) clearTimeout(statusTimer);
  if (duration > 0) {
    statusTimer = setTimeout(() => { bar.textContent = "Готово"; bar.className = "status-bar"; }, duration);
  }
}

// =====================================================
// TAURI API CALLS
// =====================================================

async function apiGetClients(): Promise<Client[]> {
  return invoke<Client[]>("get_clients");
}

async function apiSaveClient(client: Client): Promise<Client[]> {
  const result = await invoke<Client[]>("save_client", { client });
  setStatus("Сохранено", "saved");
  return result;
}

async function apiDeleteClient(clientId: string): Promise<Client[]> {
  return invoke<Client[]>("delete_client", { clientId });
}

async function apiDeleteOrder(clientId: string, orderId: string): Promise<Client[]> {
  return invoke<Client[]>("delete_order", { clientId, orderId });
}

async function apiDeletePayment(clientId: string, orderId: string, paymentId: string): Promise<Client[]> {
  return invoke<Client[]>("delete_payment", { clientId, orderId, paymentId });
}

async function apiOpenPath(path: string): Promise<void> {
  await invoke("open_path", { path });
}

// =====================================================
// DASHBOARD RENDERING
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
  debtEl.style.color = totalDebt > 0 ? "#FF4B2B" : "#22c55e";
}

// =====================================================
// CLIENT LIST RENDERING
// =====================================================

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

  // Update db info
  const total = clients.length;
  const shown = sorted.length;
  el("db-info")!.textContent = query
    ? `Клиентов: ${shown} из ${total}`
    : `Клиентов: ${total}`;
}

// =====================================================
// CLIENT PROFILE RENDERING
// =====================================================

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

  // Client stats bar
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
    : `<div style="color:var(--text-muted);font-size:13px;padding:20px 0;">📋 У клиента пока нет заказов</div>`;

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

  // Bind events
  el("btn-notes-toggle")!.addEventListener("click", toggleNotes);
  el("btn-add-order")!.addEventListener("click", () => openAddOrderModal(client.id));
  el("btn-client-settings")!.addEventListener("click", () => openClientSettingsModal(client));
  el("notes-textarea")!.addEventListener("input", onNotesChange);

  // Bind order card events
  for (const order of client.orders) {
    bindOrderCardEvents(client.id, order);
  }

  // Check deadlines
  if (appSettings.deadline_notifications) {
    checkDeadlineNotifications();
  }
}

// =====================================================
// ORDER CARD RENDERING
// =====================================================

function renderOrderCard(clientId: string, order: Order): string {
  const isExpanded = !collapsedOrders.has(order.id);
  const isDone = order.status === "Завершен";
  const totalReceived = orderTotalReceived(order);
  const debt = orderDebt(order);
  const sym = currSym(order.currency);

  // Deadline styling
  const days = daysUntilDeadline(order.deadline);
  let deadlineClass = "";
  if (!isDone && days !== null) {
    if (days < 0) deadlineClass = "deadline-urgent";
    else if (days <= 3) deadlineClass = "deadline-urgent";
    else if (days <= 7) deadlineClass = "deadline-soon";
  }

  const debtClass = debt > 0.001 ? "debt-positive" : "debt-zero";

  // Files
  const filesCount = order.files.length;
  const filesHtml = filesCount > 0
    ? order.files.map(f => `
        <div class="file-item${f.is_finished ? " finished" : ""}">
          <span>${f.is_folder ? "📁" : "📄"}</span>
          <span class="file-item-name" data-path="${escHtml(f.path)}">${escHtml(f.name)}</span>
        </div>`).join("")
    : `<div class="no-files">Перетащите файлы сюда или прикрепите через заказ</div>`;

  return `
    <div class="order-card${isDone ? " done" : ""}" id="order-card-${order.id}" data-order-id="${order.id}" data-client-id="${clientId}">
      <div class="order-header" id="order-hdr-${order.id}">
        <button class="toggle-btn" id="toggle-${order.id}">${isExpanded ? "▲" : "▶"}</button>
        <span class="order-service-type">${escHtml(order.service_type)}</span>
        <span class="badge-status ${isDone ? "badge-done" : "badge-active"}">${isDone ? "✅ Завершён" : "🔵 В работе"}</span>
        <div class="order-header-right">
          <label class="status-label" onclick="event.stopPropagation()">
            <input type="checkbox" id="status-cb-${order.id}" ${isDone ? "checked" : ""} />
            Выполнен
          </label>
          <button class="btn-delete-order" id="del-order-${order.id}" onclick="event.stopPropagation()">Удалить</button>
        </div>
      </div>
      <div class="order-body" id="order-body-${order.id}" style="display:${isExpanded ? "block" : "none"};">
        <!-- Dates row -->
        <div class="order-dates">
          <div class="date-field">
            <label>📅 Дата заказа:</label>
            <input type="date" id="date-start-${order.id}" value="${dateToInput(order.created_at)}" />
          </div>
          <div class="date-field">
            <label>⏰ Срок:</label>
            <input type="date" id="date-deadline-${order.id}" value="${dateToInput(order.deadline)}" class="${deadlineClass}" />
          </div>
        </div>

        <!-- Financials -->
        <div class="order-financials">
          <div class="fin-field">
            <label>СТОИМОСТЬ</label>
            <div class="fin-input-wrap">
              <input type="number" class="fin-input price-input" id="price-${order.id}" value="${order.price}" min="0" step="0.01" />
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
          <div class="fin-field">
            <label>АВАНС</label>
            <div class="fin-input-wrap">
              <input type="number" class="fin-input advance-input" id="advance-${order.id}" value="${order.advance}" min="0" step="0.01" />
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
          <div class="fin-field">
            <label>ДОЛГ</label>
            <div class="fin-input-wrap">
              <span class="fin-display ${debtClass}" id="debt-${order.id}">${formatMoney(debt)}</span>
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
          <div class="fin-field">
            <label>ПОЛУЧЕНО</label>
            <div class="fin-input-wrap">
              <span class="fin-display debt-zero" id="recv-${order.id}">${formatMoney(totalReceived)}</span>
              <span class="fin-currency">${sym}</span>
            </div>
          </div>
        </div>

        <!-- Payments + Files -->
        <div class="order-bottom">
          <div class="payments-block">
            <div class="payments-label">ПЛАТЕЖИ:</div>
            <div class="payments-btns">
              <button class="btn-add-payment" id="btn-pay-add-${order.id}">✚ добавить</button>
              <button class="btn-payment-history" id="btn-pay-hist-${order.id}">📋 история</button>
            </div>
          </div>
          <div class="files-block">
            <div class="files-label">📎 Файлы (${filesCount}):</div>
            <div class="file-list" id="files-${order.id}">${filesHtml}</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function bindOrderCardEvents(clientId: string, order: Order) {
  const oid = order.id;

  // Toggle expand/collapse
  el(`order-hdr-${oid}`)?.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    // Ignore clicks on buttons/inputs inside header
    if (target.closest(".order-header-right")) return;
    toggleOrderBody(oid);
  });

  // Status checkbox
  const statusCb = el(`status-cb-${oid}`) as HTMLInputElement;
  statusCb?.addEventListener("change", () => onStatusChange(clientId, oid, statusCb.checked));

  // Delete order button
  el(`del-order-${oid}`)?.addEventListener("click", () => onDeleteOrder(clientId, oid));

  // Date inputs
  el(`date-start-${oid}`)?.addEventListener("change", (e) => {
    onOrderDateChange(clientId, oid, "created_at", (e.target as HTMLInputElement).value);
  });
  el(`date-deadline-${oid}`)?.addEventListener("change", (e) => {
    onOrderDateChange(clientId, oid, "deadline", (e.target as HTMLInputElement).value);
  });

  // Price input
  const priceInput = el(`price-${oid}`) as HTMLInputElement;
  priceInput?.addEventListener("change", () => onPriceChange(clientId, oid, parseFloat(priceInput.value) || 0));
  priceInput?.addEventListener("keydown", (e) => { if (e.key === "Enter") priceInput.blur(); });

  // Advance input
  const advInput = el(`advance-${oid}`) as HTMLInputElement;
  advInput?.addEventListener("change", () => onAdvanceChange(clientId, oid, parseFloat(advInput.value) || 0));
  advInput?.addEventListener("keydown", (e) => { if (e.key === "Enter") advInput.blur(); });

  // Payment buttons
  el(`btn-pay-add-${oid}`)?.addEventListener("click", () => openAddPaymentModal(clientId, oid));
  el(`btn-pay-hist-${oid}`)?.addEventListener("click", () => openPaymentHistoryModal(clientId, oid));

  // File clicks
  const fileList = el(`files-${oid}`);
  fileList?.querySelectorAll(".file-item-name").forEach(node => {
    (node as HTMLElement).addEventListener("click", () => {
      const path = (node as HTMLElement).dataset.path;
      if (path) apiOpenPath(path).catch(() => {});
    });
  });
}

function toggleOrderBody(orderId: string) {
  const body = el(`order-body-${orderId}`);
  const btn = el(`toggle-${orderId}`);
  if (!body) return;
  const isVisible = body.style.display !== "none";
  body.style.display = isVisible ? "none" : "block";
  if (btn) btn.textContent = isVisible ? "▶" : "▲";
  if (isVisible) collapsedOrders.add(orderId);
  else collapsedOrders.delete(orderId);
}

// =====================================================
// ORDER FINANCIAL SYNC (matching Python logic)
// =====================================================

function updateOrderDebtDisplay(clientId: string, orderId: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order) return;

  const debt = orderDebt(order);
  const received = orderTotalReceived(order);
  const sym = currSym(order.currency);

  const debtEl = el(`debt-${orderId}`);
  if (debtEl) {
    debtEl.textContent = formatMoney(debt);
    debtEl.className = `fin-display ${debt > 0.001 ? "debt-positive" : "debt-zero"}`;
  }
  const recvEl = el(`recv-${orderId}`);
  if (recvEl) recvEl.textContent = formatMoney(received);
}

async function onStatusChange(clientId: string, orderId: string, done: boolean) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) return;

  order.status = done ? "Завершен" : "В работе";

  // Update card visual
  const card = el(`order-card-${orderId}`);
  if (card) card.className = `order-card${done ? " done" : ""}`;
  const badge = card?.querySelector(".badge-status");
  if (badge) {
    badge.className = `badge-status ${done ? "badge-done" : "badge-active"}`;
    badge.textContent = done ? "✅ Завершён" : "🔵 В работе";
  }

  clients = await apiSaveClient(client);
  renderDashboard();
  renderClientList();
}

async function onDeleteOrder(clientId: string, orderId: string) {
  const confirmed = await showConfirm("Удалить заказ?", "Заказ и все его платежи будут безвозвратно удалены.");
  if (!confirmed) return;

  try {
    clients = await apiDeleteOrder(clientId, orderId);
    renderDashboard();
    renderClientList();
    renderClientProfile();
    setStatus("Заказ удалён", "saved");
  } catch (e) {
    setStatus(`Ошибка удаления: ${e}`, "error");
  }
}

async function onOrderDateChange(clientId: string, orderId: string, field: "created_at" | "deadline", inputValue: string) {
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) return;

  const dateStr = inputToDate(inputValue);
  order[field] = field === "created_at"
    ? (dateStr ? dateStr + " 00:00" : "")
    : dateStr;

  // Update deadline color
  if (field === "deadline") {
    const input = el(`date-deadline-${orderId}`) as HTMLInputElement;
    if (input) {
      const days = daysUntilDeadline(order.deadline);
      input.className = order.status !== "Завершен" && days !== null
        ? (days <= 3 ? "deadline-urgent" : days <= 7 ? "deadline-soon" : "")
        : "";
    }
  }

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
  const sym = currSym(order.currency);

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
      id: crypto.randomUUID(),
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
      id: crypto.randomUUID(),
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
    id: crypto.randomUUID(),
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

// =====================================================
// NOTES
// =====================================================

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

// =====================================================
// MODAL MANAGEMENT
// =====================================================

function openModal(id: string) {
  (el(id) as HTMLDialogElement)?.showModal();
}
function closeModal(id: string) {
  (el(id) as HTMLDialogElement)?.close();
}

// Confirm dialog
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

// Add Client modal
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

// Client Settings modal
function openClientSettingsModal(client: Client) {
  (el("cs-client-id") as HTMLInputElement).value = client.id;
  (el("cs-name") as HTMLInputElement).value = client.name;
  (el("cs-email") as HTMLInputElement).value = client.email;
  (el("cs-social") as HTMLInputElement).value = client.social_link;
  (el("cs-notes") as HTMLTextAreaElement).value = client.notes;
  openModal("modal-client-settings");
}

// Add Order modal
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

// Add Payment modal
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

// Payment History modal
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
  const sym = currSym(order.currency);
  const totalReceived = orderTotalReceived(order);
  const debt = orderDebt(order);

  // Stats
  el("ph-stats")!.innerHTML = `
    <div class="ph-stat">
      <span class="ph-stat-label">Стоимость</span>
      <span class="ph-stat-value">${formatMoney(order.price, order.currency)}</span>
    </div>
    <div class="ph-stat">
      <span class="ph-stat-label">Аванс</span>
      <span class="ph-stat-value" style="color:var(--accent-gold)">${formatMoney(order.advance, order.currency)}</span>
    </div>
    <div class="ph-stat">
      <span class="ph-stat-label">Получено</span>
      <span class="ph-stat-value" style="color:var(--accent-green)">${formatMoney(totalReceived, order.currency)}</span>
    </div>
    <div class="ph-stat">
      <span class="ph-stat-label">Долг</span>
      <span class="ph-stat-value" style="color:${debt > 0 ? "var(--accent-red)" : "var(--accent-green)"}">${formatMoney(debt, order.currency)}</span>
    </div>
  `;

  // Group payments
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
    html = `<div style="color:var(--text-muted);font-size:13px;padding:16px;text-align:center;">Платежей нет</div>`;
  }

  el("ph-list")!.innerHTML = html;

  // Bind delete buttons
  el("ph-list")!.querySelectorAll(".btn-ph-delete").forEach(btn => {
    btn.addEventListener("click", async () => {
      const paymentId = (btn as HTMLElement).dataset.paymentId!;
      const cid = (btn as HTMLElement).dataset.clientId!;
      const oid = (btn as HTMLElement).dataset.orderId!;
      const ok = await showConfirm("Удалить платёж?", "Платёж будет безвозвратно удалён.");
      if (!ok) return;
      try {
        clients = await apiDeletePayment(cid, oid, paymentId);
        // Re-render history in place
        const updClient = clients.find(c => c.id === cid);
        const updOrder = updClient?.orders.find(o => o.id === oid);
        if (updOrder) renderPaymentHistory(updOrder, cid);
        renderDashboard();
        renderClientList();
        // Update inline displays
        updateOrderDebtDisplay(cid, oid);
        setStatus("Платёж удалён", "saved");
      } catch (e) {
        setStatus(`Ошибка: ${e}`, "error");
      }
    });
  });
}

function paymentItemHtml(p: Payment, clientId: string, orderId: string, currency: string): string {
  const color = p.amount >= 0 ? "var(--accent-green)" : "var(--accent-red)";
  const sign = p.amount >= 0 ? "+" : "";
  return `
    <div class="ph-item">
      <span class="ph-item-date">${p.date}</span>
      <span class="ph-item-amount" style="color:${color}">${sign}${formatMoney(p.amount, currency)}</span>
      <span class="ph-item-note">${escHtml(p.note)}</span>
      <button class="btn-ph-delete" data-payment-id="${p.id}" data-client-id="${clientId}" data-order-id="${orderId}">🗑</button>
    </div>
  `;
}

// Settings modal
function openSettingsModal() {
  (el("set-deadline-notify") as HTMLInputElement).checked = appSettings.deadline_notifications;
  openModal("modal-settings");
}

// =====================================================
// FORM SUBMISSIONS
// =====================================================

function setupFormListeners() {
  // Add/Edit client form
  el("form-client")!.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = (el("client-id") as HTMLInputElement).value || crypto.randomUUID();
    const name = (el("client-name") as HTMLInputElement).value.trim();
    if (!name) return;

    // Check duplicate name (for new clients)
    const isNew = !(el("client-id") as HTMLInputElement).value;
    if (isNew && clients.some(c => c.name.toLowerCase() === name.toLowerCase())) {
      alert("Клиент с таким именем уже существует.");
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

    try {
      clients = await apiSaveClient(newClient);
      closeModal("modal-client");
      selectedClientId = id;
      renderDashboard();
      renderClientList();
      renderClientProfile();
      setStatus(`Клиент "${name}" сохранён`, "saved");
    } catch (err) {
      setStatus(`Ошибка: ${err}`, "error");
    }
  });

  // New order form
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
    if (advance > price) { alert("Аванс не может превышать стоимость"); return; }

    const newOrder: Order = {
      id: crypto.randomUUID(),
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
        id: crypto.randomUUID(),
        type: "аванс",
        amount: advance,
        date: nowDatetime(),
        note: "Первоначальный аванс",
      });
    }

    client.orders.push(newOrder);

    try {
      clients = await apiSaveClient(client);
      closeModal("modal-order");
      renderDashboard();
      renderClientList();
      renderClientProfile();
      setStatus("Заказ создан", "saved");
    } catch (err) {
      client.orders.pop();
      setStatus(`Ошибка: ${err}`, "error");
    }
  });

  // Add payment form
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
      id: crypto.randomUUID(),
      type: paymentType,
      amount,
      date: dateStr,
      note,
    });

    // Update advance tracking if this is an advance payment
    if (paymentType === "аванс" && amount > 0) {
      const totalAdvanceReceived = order.payments
        .filter(p => p.type === "аванс")
        .reduce((s, p) => s + p.amount, 0);
      order.advance = Math.max(order.advance, totalAdvanceReceived);
    }

    try {
      clients = await apiSaveClient(client);
      closeModal("modal-payment");
      renderDashboard();
      renderClientList();
      updateOrderDebtDisplay(clientId, orderId);
      renderClientProfile();
      setStatus("Платёж проведён", "saved");
    } catch (err) {
      order.payments.pop();
      setStatus(`Ошибка: ${err}`, "error");
    }
  });

  // Client settings save
  el("cs-save-btn")!.addEventListener("click", async () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) return;

    client.name = (el("cs-name") as HTMLInputElement).value.trim();
    client.email = (el("cs-email") as HTMLInputElement).value.trim();
    client.social_link = (el("cs-social") as HTMLInputElement).value.trim();
    client.notes = (el("cs-notes") as HTMLTextAreaElement).value;

    if (!client.name) { alert("Имя обязательно"); return; }

    try {
      clients = await apiSaveClient(client);
      closeModal("modal-client-settings");
      renderClientList();
      renderClientProfile();
      setStatus("Настройки клиента сохранены", "saved");
    } catch (err) {
      setStatus(`Ошибка: ${err}`, "error");
    }
  });

  // Client settings delete
  el("cs-delete-btn")!.addEventListener("click", async () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) return;

    const ok = await showConfirm(
      "Удалить клиента?",
      `Клиент "${client.name}" и все его заказы будут безвозвратно удалены.`
    );
    if (!ok) return;

    try {
      clients = await apiDeleteClient(id);
      if (selectedClientId === id) {
        selectedClientId = null;
      }
      closeModal("modal-client-settings");
      renderDashboard();
      renderClientList();
      renderClientProfile();
      setStatus(`Клиент "${client.name}" удалён`, "saved");
    } catch (err) {
      setStatus(`Ошибка: ${err}`, "error");
    }
  });

  // Client settings export
  el("cs-export-json")!.addEventListener("click", () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) return;
    exportClientJson(client);
  });

  // Order service type switch
  (el("order-service-select") as HTMLSelectElement).addEventListener("change", (e) => {
    const val = (e.target as HTMLSelectElement).value;
    el("order-service-custom-wrap")!.style.display = val === "__custom__" ? "block" : "none";
  });

  // App settings
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
        const ok = await showConfirm("Импорт данных", `Будет загружено ${imported.length} клиентов. Текущие данные будут заменены. Продолжить?`);
        if (!ok) return;
        for (const client of imported) {
          clients = await apiSaveClient(client);
        }
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

// =====================================================
// CONTEXT MENU
// =====================================================

function showContextMenu(e: MouseEvent, clientId: string) {
  e.preventDefault();
  ctxClientId = clientId;

  const menu = el("context-menu")!;
  menu.style.display = "block";
  menu.style.left = `${Math.min(e.clientX, window.innerWidth - 200)}px`;
  menu.style.top = `${Math.min(e.clientY, window.innerHeight - 150)}px`;
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
    if (selectedClientId === id) selectedClientId = null;
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

// =====================================================
// DEADLINE NOTIFICATIONS
// =====================================================

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

// =====================================================
// KEYBOARD SHORTCUTS
// =====================================================

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Close any modal on Escape
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
          // Manual save: re-save current client
          e.preventDefault();
          const client = getSelectedClient();
          if (client) {
            apiSaveClient(client).then(updated => {
              clients = updated;
              setStatus("Сохранено вручную", "saved");
            });
          }
          break;
        case "delete":
        case "backspace":
          break;
      }
    }
  });
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

function el(id: string): HTMLElement | null {
  return document.getElementById(id);
}

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
  } catch {
    // fallback: do nothing (can't open in browser from Tauri without shell permission)
  }
}
(window as any).openLink = openLink;

// =====================================================
// MAIN INITIALIZATION
// =====================================================

async function init() {
  try {
    clients = await apiGetClients();
  } catch (e) {
    console.error("Failed to load clients:", e);
    setStatus("Ошибка загрузки базы данных", "error", 0);
    clients = [];
  }

  renderDashboard();
  renderClientList();
  renderClientProfile();
  setupFormListeners();
  setupContextMenu();
  setupKeyboardShortcuts();

  // Sidebar buttons
  el("btn-add-client")!.addEventListener("click", openAddClientModal);
  el("btn-settings")!.addEventListener("click", openSettingsModal);

  // Search input
  el("search-input")!.addEventListener("input", () => renderClientList());

  // Sort select
  (el("sort-select") as HTMLSelectElement).addEventListener("change", (e) => {
    sortMode = (e.target as HTMLSelectElement).value;
    renderClientList();
  });

  // Deadline check on startup
  setTimeout(() => {
    if (appSettings.deadline_notifications) checkDeadlineNotifications();
  }, 1200);

  setStatus("FinanceFugue готов к работе", "saved", 3000);
}

window.addEventListener("DOMContentLoaded", init);
