/**
 * FinanceFugue — Tauri Edition
 * Pixel-perfect port of PySide6 OrderWidget, ClientProfileMixin & Theme
 * With robust IPC fallbacks for seamless client & order management.
 */

import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { open } from "@tauri-apps/plugin-dialog";

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

function safeNum(v: unknown, fallback = 0): number {
  return isFinite(v as number) ? (v as number) : fallback;
}

function orderRealReceived(order: Order): number {
  const sum = order.payments.reduce((s, p) => s + safeNum(p.amount), 0);
  return Math.round(sum * 100) / 100;
}

function orderDebt(order: Order): number {
  const price = safeNum(order.price);
  const received = orderRealReceived(order);
  return Math.round((price - received) * 100) / 100;
}

function formatMoney(amount: number, currency = "RUB"): string {
  if (!isFinite(amount)) amount = 0;
  amount = Math.round(amount * 100) / 100;
  const sym = currSym(currency);
  const abs = Math.abs(amount);
  const formatted = abs.toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return `${amount < 0 ? "-" : ""}${formatted} ${sym}`;
}

function formatMultiCurrency(byCurrency: Record<string, number>): string {
  const nonZero = Object.entries(byCurrency).filter(([, v]) => Math.abs(Math.round(v * 100) / 100) >= 0.01);
  if (nonZero.length === 0) return "0";
  return nonZero.sort(([a],[b]) => a.localeCompare(b))
    .map(([c, v]) => formatMoney(v, c))
    .join(" + ");
}

function sumByCurrency(orders: Order[], field: "advance" | "debt" | "received", activeOnly = false): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const order of orders) {
    if (activeOnly && order.status === "Завершен") continue;
    const curr = order.currency || "RUB";
    const val = safeNum(
      field === "advance" ? order.advance
        : field === "debt" ? orderDebt(order)
        : field === "received" ? orderRealReceived(order)
        : 0
    );
    totals[curr] = Math.round(((totals[curr] || 0) + val) * 100) / 100;
  }
  return totals;
}

function computeClientStats(client: Client) {
  const allOrders = client.orders;
  const totalOrders = allOrders.length;
  const completedOrders = allOrders.filter(o => o.status === "Завершен").length;
  return {
    totalOrders,
    completedOrders,
    advanceByCurrency: sumByCurrency(allOrders, "advance"),
    receivedByCurrency: sumByCurrency(allOrders, "received"),
    debtByCurrency: sumByCurrency(allOrders, "debt", true),
  };
}

function computeGlobalStats(clients: Client[]) {
  const allOrders = clients.flatMap(c => c.orders);
  const activeOrders = allOrders.filter(o => o.status !== "Завершен").length;
  const doneOrders = allOrders.length - activeOrders;
  return {
    activeOrders,
    doneOrders,
    advanceByCurrency: sumByCurrency(allOrders, "advance"),
    debtByCurrency: sumByCurrency(allOrders, "debt", true),
    receivedByCurrency: sumByCurrency(allOrders, "received"),
  };
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
    console.log("IPC → get_clients");
    const result = await invoke<Client[]>("get_clients");
    console.log(`IPC ← get_clients: ${result.length} clients`);
    return result;
  } catch (e) {
    console.warn("IPC ✗ get_clients fallback:", e);
    return clients;
  }
}

async function apiSaveClient(client: Client): Promise<Client[]> {
  console.log(`IPC → save_client: id=${client.id}, name="${client.name}"`);
  try {
    const result = await invoke<Client[]>("save_client", { client });
    console.log(`IPC ← save_client: success, total ${result.length} clients`);
    setStatus("Сохранено", "saved");
    return result;
  } catch (e) {
    console.warn(`IPC ✗ save_client fallback (${client.id}):`, e);
    const idx = clients.findIndex(c => c.id === client.id);
    if (idx >= 0) {
      clients[idx] = client;
      console.log(`  → local update at index ${idx}`);
    } else {
      clients.push(client);
      console.log(`  → local push, now ${clients.length} clients`);
    }
    setStatus("Сохранено (локально)", "saved");
    return [...clients];
  }
}

async function apiDeleteClient(clientId: string): Promise<Client[]> {
  console.log(`IPC → delete_client: clientId=${clientId}`);
  try {
    const result = await invoke<Client[]>("delete_client", { clientId });
    console.log(`IPC ← delete_client: success, ${result.length} clients remaining`);
    return result;
  } catch (e) {
    console.warn(`IPC ✗ delete_client fallback (${clientId}):`, e);
    clients = clients.filter(c => c.id !== clientId);
    console.log(`  → local filter, now ${clients.length} clients`);
    return [...clients];
  }
}

async function apiDeleteOrder(clientId: string, orderId: string): Promise<Client[]> {
  console.log(`IPC → delete_order: clientId=${clientId}, orderId=${orderId}`);
  try {
    const result = await invoke<Client[]>("delete_order", { clientId, orderId });
    console.log(`IPC ← delete_order: success`);
    return result;
  } catch (e) {
    console.warn(`IPC ✗ delete_order fallback:`, e);
    const client = clients.find(c => c.id === clientId);
    if (client) {
      client.orders = client.orders.filter(o => o.id !== orderId);
      console.log(`  → local filter, ${client.orders.length} orders remaining`);
    }
    return [...clients];
  }
}

async function apiDeletePayment(clientId: string, orderId: string, paymentId: string): Promise<Client[]> {
  console.log(`IPC → delete_payment: clientId=${clientId}, orderId=${orderId}, paymentId=${paymentId}`);
  try {
    const result = await invoke<Client[]>("delete_payment", { clientId, orderId, paymentId });
    console.log(`IPC ← delete_payment: success`);
    return result;
  } catch (e) {
    console.warn(`IPC ✗ delete_payment fallback:`, e);
    const client = clients.find(c => c.id === clientId);
    const order = client?.orders.find(o => o.id === orderId);
    if (order) {
      order.payments = order.payments.filter(p => p.id !== paymentId);
      console.log(`  → local filter, ${order.payments.length} payments remaining`);
    }
    return [...clients];
  }
}

async function apiOpenPath(path: string): Promise<void> {
  console.log(`IPC → open_path: "${path}"`);
  try {
    await invoke("open_path", { path });
    console.log(`IPC ← open_path: success`);
  } catch (e) {
    console.warn(`IPC ✗ open_path: "${path}"`, e);
  }
}

// =====================================================
// RENDERING FUNCTIONS
// =====================================================

function renderDashboard() {
  const stats = computeGlobalStats(clients);
  const totalDebt = Object.values(stats.debtByCurrency).reduce((s, v) => s + v, 0);
  console.log(`UI renderDashboard: active=${stats.activeOrders}, done=${stats.doneOrders}, debt=${formatMoney(totalDebt)}`);

  el("dash-active")!.textContent = String(stats.activeOrders);
  el("dash-done")!.textContent = String(stats.doneOrders);
  el("dash-advance")!.textContent = formatMultiCurrency(stats.advanceByCurrency);
  el("dash-debt")!.textContent = formatMultiCurrency(stats.debtByCurrency);
  el("dash-cash")!.textContent = formatMultiCurrency(stats.receivedByCurrency);

  const debtEl = el("dash-debt")!;
  debtEl.style.color = totalDebt > 0 ? "#FF4B2B" : totalDebt < 0 ? "#28A745" : "";
}

function renderClientList() {
  const container = el("client-list")!;
  const query = (el("search-input") as HTMLInputElement).value;
  const sorted = getSortedClients(clients, sortMode, query);
  console.log(`UI renderClientList: mode=${sortMode}, query="${query}", shown=${sorted.length}/${clients.length}`);

  container.innerHTML = "";
  for (const client of sorted) {
    const activeOrders = client.orders.filter(o => o.status === "В работе").length;
    const debtByCurrency = sumByCurrency(client.orders, "debt", true);

    const item = document.createElement("div");
    item.className = `client-item${client.id === selectedClientId ? " active" : ""}`;
    item.dataset.clientId = client.id;

    let debtHtml = "";
    const hasDebt = Object.values(debtByCurrency).some(v => v > 0.01);
    const hasOverpayment = Object.values(debtByCurrency).some(v => v < -0.01);
    if (hasDebt || hasOverpayment) {
      const debtDisp = formatMultiCurrency(debtByCurrency);
      const label = hasOverpayment && !hasDebt ? "Переплата" : "Долг";
      debtHtml = `<span class="debt-badge" style="color:${hasOverpayment && !hasDebt ? "var(--color-success)" : "var(--color-red)"}">${label}: ${debtDisp}</span>`;
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
  console.log(`UI selectClient: id=${id}`);
  if (notesDebounceTimer) { clearTimeout(notesDebounceTimer); notesDebounceTimer = null; }
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
  console.log(`UI renderClientProfile: client=${client ? client.name : "none"}, orders=${client ? client.orders.length : 0}`);

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

  const emailHtml = client.email ? `<a href="#" onclick="openLink('mailto:${jsEscape(client.email)}');return false;">📧 ${escHtml(client.email)}</a>` : "";
  const socialHtml = client.social_link ? `<a href="#" onclick="openLink('${jsEscape(client.social_link)}');return false;">🔗 ${escHtml(client.social_link)}</a>` : "";

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
    filesListHtml = sorted.map(f => {
      const statusIcon = f.is_finished ? "✅" : "⏳";
      const statusClass = f.is_finished ? "file-finished" : "file-pending";
      return `
      <div class="file-item ${statusClass}" data-filename="${escHtml(f.name)}" data-cid="${clientId}" data-oid="${order.id}">
        <span class="file-status-toggle" onclick="toggleFileFinished('${clientId}', '${order.id}', '${jsEscape(f.name)}')" title="${f.is_finished ? "Отметить как в работе" : "Отметить как выполнен"}">${statusIcon}</span>
        <span class="file-item-name ${f.is_folder ? "folder" : "file"}" data-path="${escHtml(f.path)}">${escHtml(f.name)}</span>
        <button class="btn-file-compact" onclick="openFolder('${jsEscape(f.path)}')">📂</button>
        <button class="btn-file-compact" onclick="renameFileInOrder('${clientId}', '${order.id}', '${jsEscape(f.name)}')">✏️</button>
        <button class="btn-file-danger" onclick="deleteFileFromOrder('${clientId}', '${order.id}', '${jsEscape(f.name)}')">🗑</button>
      </div>`;
    }).join("");
  } else {
    filesListHtml = `<div class="drag-hint-box">Перетащите файлы сюда</div>`;
  }

  return `
    <div class="order-card${isDone ? " done" : ""}" id="order-card-${order.id}" data-client-id="${clientId}" data-order-id="${order.id}">
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
  priceInput?.addEventListener("change", () => {
    const val = parseFloat(priceInput.value);
    if (!isFinite(val)) {
      alert("Введите корректное число для стоимости");
      priceInput.value = String(order.price);
      return;
    }
    onPriceChange(clientId, oid, val);
  });

  const advInput = el(`advance-${oid}`) as HTMLInputElement;
  advInput?.addEventListener("change", () => {
    const val = parseFloat(advInput.value);
    if (!isFinite(val)) {
      alert("Введите корректное число для аванса");
      advInput.value = String(order.advance);
      return;
    }
    onAdvanceChange(clientId, oid, val);
  });

  el(`btn-pay-add-${oid}`)?.addEventListener("click", () => openAddPaymentModal(clientId, oid));
  el(`btn-pay-hist-${oid}`)?.addEventListener("click", () => openPaymentHistoryModal(clientId, oid));

  el(`btn-add-file-${oid}`)?.addEventListener("click", async () => {
    console.log(`UI btn-add-file: clientId=${clientId}, orderId=${oid}`);
    const dbDir = await invoke<string>("get_db_dir");
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.addEventListener("change", async () => {
      const files = input.files;
      if (!files || !files.length) {
        console.warn(`btn-add-file: no files selected`);
        return;
      }
      const client = clients.find(c => c.id === clientId);
      const order = client?.orders.find(o => o.id === oid);
      if (!client || !order) {
        console.warn(`btn-add-file: client/order not found`);
        return;
      }
      console.log(`btn-add-file: ${files.length} file(s) selected`);
      let added = 0;
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        const targetDir = `${dbDir}/attached_files/${clientId}/${oid}`;
        try {
          // Read file content in JS (Tauri v2 doesn't expose File.path)
          const buf = await f.arrayBuffer();
          const bytes = new Uint8Array(buf);
          console.log(`IPC → save_file_bytes: name=${f.name}, size=${bytes.length}`);
          const newPath = await invoke<string>("save_file_bytes", { dir: targetDir, name: f.name, content: Array.from(bytes) });
          console.log(`IPC ← save_file_bytes: ${newPath}`);
          order.files.push({ path: newPath, name: f.name, is_finished: false, is_folder: false });
          added++;
        } catch (e) {
          console.warn("Failed to save file:", f.name, e);
        }
      }
      if (added > 0) {
        console.log(`  → ${added} files added`);
        clients = await apiSaveClient(client);
        renderClientProfile();
        setStatus(`Добавлено ${added} файлов`, "saved");
      }
    });
    input.click();
  });
  el(`btn-export-zip-${oid}`)?.addEventListener("click", () => exportOrderFilesZip(clientId, oid));
}

function toggleOrderBody(orderId: string) {
  const body = el(`order-body-${orderId}`);
  const btn = el(`toggle-${orderId}`);
  if (!body) return;
  const isVisible = body.style.display !== "none";
  console.log(`UI toggleOrderBody: orderId=${orderId}, collapsing=${!isVisible}`);
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
  console.debug(`UI updateOrderDebtDisplay: orderId=${orderId}, debt=${debt}`);
}

async function onStatusChange(clientId: string, orderId: string, done: boolean) {
  console.log(`UI onStatusChange: clientId=${clientId}, orderId=${orderId}, done=${done}`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) {
    console.warn(`onStatusChange: client/order not found`);
    return;
  }

  order.status = done ? "Завершен" : "В работе";
  const card = el(`order-card-${orderId}`);
  if (card) card.className = `order-card${done ? " done" : ""}`;

  clients = await apiSaveClient(client);
  renderDashboard();
  renderClientList();
}

async function onDeleteOrder(clientId: string, orderId: string) {
  console.log(`UI onDeleteOrder: clientId=${clientId}, orderId=${orderId}`);
  const confirmed = await showConfirm("Удалить заказ?", "Заказ и все его платежи будут безвозвратно удалены.");
  if (!confirmed) {
    console.log(`  → user cancelled`);
    return;
  }

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
  console.log(`UI onOrderDateChange: orderId=${orderId}, field=${field}, value=${dateStr}`);
  order[field] = field === "created_at"
    ? (dateStr ? dateStr + " 00:00" : "")
    : dateStr;

  clients = await apiSaveClient(client);
}

async function onPriceChange(clientId: string, orderId: string, newPrice: number) {
  console.log(`UI onPriceChange: orderId=${orderId}, newPrice=${newPrice}`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) {
    console.warn(`onPriceChange: client/order not found`);
    return;
  }

  if (!isFinite(newPrice)) {
    console.warn(`onPriceChange: invalid price`);
    (el(`price-${orderId}`) as HTMLInputElement).value = String(order.price);
    return;
  }

  if (newPrice < 0) {
    console.warn(`onPriceChange: negative price rejected`);
    alert("Стоимость не может быть отрицательной");
    (el(`price-${orderId}`) as HTMLInputElement).value = String(order.price);
    return;
  }

  const totalReceived = orderRealReceived(order);

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
  console.log(`UI onAdvanceChange: orderId=${orderId}, newAdvance=${newAdvance}`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !client) {
    console.warn(`onAdvanceChange: client/order not found`);
    return;
  }

  if (!isFinite(newAdvance)) {
    console.warn(`onAdvanceChange: invalid advance`);
    (el(`advance-${orderId}`) as HTMLInputElement).value = String(order.advance);
    return;
  }

  if (newAdvance < 0) {
    console.warn(`onAdvanceChange: negative advance rejected`);
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
  if (Math.abs(diff) < 0.001) {
    (el(`advance-${orderId}`) as HTMLInputElement).value = String(order.advance);
    return;
  }

  if (diff > 0) {
    order.payments.push({
      id: generateUUID(),
      type: "аванс",
      amount: diff,
      date: nowDatetime(),
      note: "Внесён аванс",
    });
  }
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
  if (!client) {
    console.warn("saveNotes: no client selected");
    return;
  }
  const textarea = el("notes-textarea") as HTMLTextAreaElement;
  if (!textarea) {
    console.warn("saveNotes: textarea not found");
    return;
  }
  client.notes = textarea.value;
  console.log(`UI saveNotes: client=${client.id}, notes length=${client.notes.length}`);
  clients = await apiSaveClient(client);
}

// Modals
function openModal(id: string) {
  console.log(`UI openModal: ${id}`);
  (el(id) as HTMLDialogElement)?.showModal();
}
function closeModal(id: string) {
  console.log(`UI closeModal: ${id}`);
  (el(id) as HTMLDialogElement)?.close();
}

function showConfirm(title: string, message: string): Promise<boolean> {
  console.log(`UI showConfirm: "${title}" — "${message.substring(0, 80)}..."`);
  return new Promise((resolve) => {
    (el("confirm-title") as HTMLElement).textContent = title;
    (el("confirm-message") as HTMLElement).textContent = message;
    openModal("modal-confirm");

    const okBtn = el("confirm-ok")!;
    const cancelBtn = el("confirm-cancel")!;
    const modal = el("modal-confirm") as HTMLDialogElement;

    const cleanup = () => {
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      modal.removeEventListener("close", onClose);
      closeModal("modal-confirm");
    };
    const onOk = () => { console.log(`  → confirm OK`); cleanup(); resolve(true); };
    const onCancel = () => { console.log(`  → confirm Cancel`); cleanup(); resolve(false); };
    const onClose = () => { console.log(`  → confirm Close`); cleanup(); resolve(false); };
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    modal.addEventListener("close", onClose);
  });
}

function openAddClientModal() {
  console.log(`UI openAddClientModal`);
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
  console.log(`UI openClientSettingsModal: client=${client.id} "${client.name}"`);
  (el("cs-client-id") as HTMLInputElement).value = client.id;
  (el("cs-name") as HTMLInputElement).value = client.name;
  (el("cs-email") as HTMLInputElement).value = client.email;
  (el("cs-social") as HTMLInputElement).value = client.social_link;
  (el("cs-notes") as HTMLTextAreaElement).value = client.notes;
  openModal("modal-client-settings");
}

function openAddOrderModal(clientId: string) {
  console.log(`UI openAddOrderModal: clientId=${clientId}`);
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
  console.log(`UI openAddPaymentModal: clientId=${clientId}, orderId=${orderId}`);
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
  console.log(`UI openPaymentHistoryModal: clientId=${clientId}, orderId=${orderId}`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order) {
    console.warn(`openPaymentHistoryModal: order not found`);
    return;
  }

  (el("ph-client-id") as HTMLInputElement).value = clientId;
  (el("ph-order-id") as HTMLInputElement).value = orderId;
  (el("ph-title") as HTMLElement).textContent = `История платежей — ${order.service_type}`;
  renderPaymentHistory(order, clientId);
  openModal("modal-payment-history");
}

function renderPaymentHistory(order: Order, clientId: string) {
  const totalReceived = orderRealReceived(order);
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
      <span class="ph-stat-label">${debt < 0 ? "Переплата" : "Долг"}</span>
      <span class="ph-stat-value" style="color:${debt > 0 ? "var(--color-red)" : debt < 0 ? "var(--color-success)" : ""}">${formatMoney(debt, order.currency)}</span>
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
  console.log(`UI openSettingsModal`);
  invoke("open_settings_window").catch(e => console.error("Failed to open settings window:", e));
}

function setupFormListeners() {
  // Form submit for new / edit client
  el("form-client")!.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = (el("client-id") as HTMLInputElement).value || generateUUID();
    const name = (el("client-name") as HTMLInputElement).value.trim();
    if (!name) {
      console.warn(`form-client submit: empty name`);
      alert("Введите имя или название клиента");
      return;
    }

    const existing = clients.find(c => c.id === id);
    const isNew = !existing;
    console.log(`UI form-client submit: id=${id}, name="${name}", isNew=${isNew}`);
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
    if (!client) {
      console.warn(`form-order submit: client ${clientId} not found`);
      return;
    }

    const serviceSelect = el("order-service-select") as HTMLSelectElement;
    let serviceType = serviceSelect.value;
    if (serviceType === "__custom__") {
      serviceType = (el("order-service-custom") as HTMLInputElement).value.trim();
      if (!serviceType) { console.warn(`form-order: empty custom service`); alert("Введите тип услуги"); return; }
    }

    const price = parseFloat((el("order-price") as HTMLInputElement).value);
    const currency = (el("order-currency") as HTMLSelectElement).value;
    const advance = parseFloat((el("order-advance") as HTMLInputElement).value);
    const deadlineInput = (el("order-deadline") as HTMLInputElement).value;
    console.log(`UI form-order submit: client=${clientId}, service=${serviceType}, price=${price}, advance=${advance}`);

    if (!isFinite(price)) { console.warn(`form-order: invalid price`); alert("Введите корректную стоимость"); return; }
    if (!isFinite(advance)) { console.warn(`form-order: invalid advance`); alert("Введите корректный аванс"); return; }
    if (price < 0) { console.warn(`form-order: negative price`); alert("Стоимость не может быть отрицательной"); return; }
    if (advance < 0) { console.warn(`form-order: negative advance`); alert("Аванс не может быть отрицательным"); return; }

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
    console.log(`UI form-payment submit: clientId=${clientId}, orderId=${orderId}`);
    const client = clients.find(c => c.id === clientId);
    const order = client?.orders.find(o => o.id === orderId);
    if (!client || !order) {
      console.warn(`form-payment: client/order not found`);
      return;
    }

    const paymentType = (el("payment-type") as HTMLSelectElement).value;
    const amount = parseFloat((el("payment-amount") as HTMLInputElement).value);
    const dateInput = (el("payment-date") as HTMLInputElement).value;
    const note = (el("payment-note") as HTMLInputElement).value.trim();
    console.log(`  → type=${paymentType}, amount=${amount}, date=${dateInput}`);

    if (!isFinite(amount)) { console.warn(`form-payment: invalid amount`); alert("Введите корректную сумму"); return; }
    if (amount === 0) { console.warn(`form-payment: zero amount rejected`); alert("Сумма не может быть нулём"); return; }

    const dateStr = dateInput ? inputToDate(dateInput) + " 00:00" : nowDatetime();

    order.payments.push({
      id: generateUUID(),
      type: paymentType,
      amount,
      date: dateStr,
      note,
    });

    if (paymentType === "аванс") {
      const totalAdvanceReceived = order.payments
        .filter(p => p.type === "аванс")
        .reduce((s, p) => s + p.amount, 0);
      order.advance = Math.max(0, totalAdvanceReceived);
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
    if (!client) {
      console.warn(`cs-save-btn: client ${id} not found`);
      return;
    }

    client.name = (el("cs-name") as HTMLInputElement).value.trim();
    client.email = (el("cs-email") as HTMLInputElement).value.trim();
    client.social_link = (el("cs-social") as HTMLInputElement).value.trim();
    client.notes = (el("cs-notes") as HTMLTextAreaElement).value;
    console.log(`UI cs-save-btn: saving client settings for "${client.name}"`);

    if (!client.name) { console.warn(`cs-save-btn: empty name`); alert("Имя обязательно"); return; }

    clients = await apiSaveClient(client);
    closeModal("modal-client-settings");
    renderClientList();
    renderClientProfile();
    setStatus("Настройки клиента сохранены", "saved");
  });

  el("cs-delete-btn")!.addEventListener("click", async () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) {
      console.warn(`cs-delete-btn: client ${id} not found`);
      return;
    }
    console.log(`UI cs-delete-btn: deleting client "${client.name}" (${id})`);

    const ok = await showConfirm(
      "Удалить клиента?",
      `Клиент "${client.name}" и все его заказы будут безвозвратно удалены.`
    );
    if (!ok) { console.log(`  → cancelled`); return; }

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
    if (!client) {
      console.warn(`cs-export-json: client ${id} not found`);
      return;
    }
    console.log(`UI cs-export-json: exporting "${client.name}"`);
    exportClientJson(client);
  });

  el("cs-export-files-zip")!.addEventListener("click", () => {
    const id = (el("cs-client-id") as HTMLInputElement).value;
    const client = clients.find(c => c.id === id);
    if (!client) {
      console.warn(`cs-export-files-zip: client ${id} not found`);
      return;
    }
    console.log(`UI cs-export-files-zip: exporting files for "${client.name}"`);
    exportClientFilesZip(id);
  });

  (el("order-service-select") as HTMLSelectElement).addEventListener("change", (e) => {
    const val = (e.target as HTMLSelectElement).value;
    el("order-service-custom-wrap")!.style.display = val === "__custom__" ? "block" : "none";
  });

  el("set-deadline-notify")!.addEventListener("change", (e) => {
    appSettings.deadline_notifications = (e.target as HTMLInputElement).checked;
    saveSettings(appSettings);
  });

  el("set-browse-db")!.addEventListener("click", async () => {
    console.log(`UI set-browse-db`);
    try {
      const selected = await open({ directory: true, multiple: false, title: "Выберите папку для хранения БД" });
      if (selected) {
        console.log(`  → selected: ${selected}`);
        await invoke("save_db_dir", { dir: selected });
        (el("set-db-path") as HTMLInputElement).value = selected;
        setStatus("Путь к БД сохранён. Перезапустите программу.", "saved");
      }
    } catch (e) {
      console.error("set-browse-db error:", e);
    }
  });

  el("set-export-json")!.addEventListener("click", () => {
    console.log(`UI set-export-json: exporting ${clients.length} clients`);
    const json = JSON.stringify(clients, null, 2);
    downloadFile("financefugue_export.json", json, "application/json");
  });

  el("set-backup-zip")!.addEventListener("click", () => {
    console.log(`UI set-backup-zip`);
    exportFullBackup();
  });

  el("set-import-folder")!.addEventListener("click", () => {
    console.log(`UI set-import-folder`);
    importFromFolder();
  });

  el("set-delete-files")!.addEventListener("click", () => {
    console.log(`UI set-delete-files`);
    deleteAllFiles();
  });

  el("set-delete-db")!.addEventListener("click", () => {
    console.log(`UI set-delete-db`);
    deleteDatabaseFull();
  });

  el("set-import-json")!.addEventListener("click", async () => {
    console.log(`UI set-import-json`);
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) { console.warn(`import-json: no file selected`); return; }
      try {
        const text = await file.text();
        console.log(`  → read ${text.length} bytes`);
        const imported: Client[] = JSON.parse(text);
        if (!Array.isArray(imported)) throw new Error("Неверный формат файла");
        console.log(`  → parsed ${imported.length} clients`);
        const ok = await showConfirm("Импорт данных", `Будет загружено ${imported.length} клиентов. Продолжить?`);
        if (!ok) { console.log(`  → user cancelled`); return; }
        for (const client of imported) {
          clients = await apiSaveClient(client);
        }
        if (clients.length > 0) selectedClientId = clients[0].id;
        renderDashboard();
        renderClientList();
        renderClientProfile();
        setStatus(`Импортировано ${imported.length} клиентов`, "saved");
      } catch (err) {
        console.error(`import-json error:`, err);
        alert(`Ошибка импорта: ${err}`);
      }
    });
    input.click();
  });
}

function showContextMenu(e: MouseEvent, clientId: string) {
  e.preventDefault();
  console.log(`UI showContextMenu: clientId=${clientId}`);
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
    console.log(`UI cm-add-order: ctxClientId=${ctxClientId}`);
    if (ctxClientId) {
      selectClient(ctxClientId);
      openAddOrderModal(ctxClientId);
    }
    hideContextMenu();
  });

  el("cm-edit-client")!.addEventListener("click", () => {
    console.log(`UI cm-edit-client: ctxClientId=${ctxClientId}`);
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
    if (!id) { console.warn(`cm-delete-client: no ctxClientId`); return; }
    const client = clients.find(c => c.id === id);
    if (!client) { console.warn(`cm-delete-client: client ${id} not found`); return; }
    console.log(`UI cm-delete-client: deleting "${client.name}"`);
    const ok = await showConfirm("Удалить клиента?", `Клиент "${client.name}" и все его заказы будут удалены.`);
    if (!ok) { console.log(`  → cancelled`); return; }
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
  console.log(`checkDeadlineNotifications: ${alerts.length} alert(s)`);
  if (alerts.length > 0) {
    console.warn(`Deadline alerts:`, alerts);
    setStatus(`⚠ Дедлайны: ${alerts.length} заказ(ов) требуют внимания`, "error", 10000);
  }
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      console.log(`KB: Escape`);
      document.querySelectorAll("dialog[open]").forEach(d => (d as HTMLDialogElement).close());
      hideContextMenu();
      return;
    }

    if (e.ctrlKey) {
      switch (e.key.toLowerCase()) {
        case "n":
          e.preventDefault();
          console.log(`KB: Ctrl+N — new client`);
          openAddClientModal();
          break;
        case "f":
          e.preventDefault();
          console.log(`KB: Ctrl+F — focus search`);
          const search = el("search-input") as HTMLInputElement;
          search?.focus();
          search?.select();
          break;
        case ",":
          e.preventDefault();
          console.log(`KB: Ctrl+, — settings`);
          openSettingsModal();
          break;
        case "s":
          e.preventDefault();
          if (e.shiftKey) {
            console.log(`KB: Ctrl+Shift+S — settings`);
            openSettingsModal();
          } else {
            console.log(`KB: Ctrl+S — save`);
            const client = getSelectedClient();
            if (client) {
              apiSaveClient(client)
                .then(updated => { clients = updated; setStatus("Сохранено вручную", "saved"); })
                .catch(e => setStatus(`Ошибка сохранения: ${e}`, "error"));
            }
          }
          break;
        case "o":
          e.preventDefault();
          console.log(`KB: Ctrl+O — file manager`);
          openFileManager();
          break;
        case "q":
          e.preventDefault();
          console.log(`KB: Ctrl+Q — quit`);
          window.close();
          break;
      }
    } else if (e.key === "F5") {
      e.preventDefault();
      console.log(`KB: F5 — refresh`);
      renderDashboard();
      renderClientList();
      renderClientProfile();
      setStatus("Обновлено", "saved");
    } else if (e.key === "Delete" && selectedClientId) {
      const client = clients.find(c => c.id === selectedClientId);
      if (client && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        console.log(`KB: Delete — delete current client`);
        onDeleteCurrentClient();
      }
    }
  });
}

function el(id: string): HTMLElement | null { return document.getElementById(id); }

function escHtml(s: string): string {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

function jsEscape(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, "\\n");
}

function downloadFile(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadBlob(name: string, data: number[], type: string) {
  const blob = new Blob([Uint8Array.from(data)], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function exportClientJson(client: Client) {
  console.log(`UI exportClientJson: "${client.name}"`);
  downloadFile(
    `${client.name.replace(/\s+/g,"_")}_orders.json`,
    JSON.stringify({ client: { name: client.name, email: client.email }, orders: client.orders }, null, 2),
    "application/json"
  );
}

async function exportFullBackup() {
  console.log(`UI exportFullBackup: collecting files from ${clients.length} clients`);
  const filePaths: string[] = [];
  for (const c of clients) {
    for (const o of c.orders) {
      for (const f of o.files) {
        if (f.path && !filePaths.includes(f.path)) filePaths.push(f.path);
      }
    }
  }
  console.log(`  → ${filePaths.length} files to backup`);
  const dbJson = JSON.stringify(clients, null, 2);
  try {
    console.log(`IPC → create_backup_zip`);
    const zipData = await invoke<number[]>("create_backup_zip", { filePaths, dbJson });
    console.log(`IPC ← create_backup_zip: ${zipData.length} bytes`);
    await downloadBlob(`financefugue_backup_${Date.now()}.zip`, zipData, "application/zip");
    setStatus("Бэкап ZIP создан", "saved");
  } catch (e) {
    console.error(`exportFullBackup error:`, e);
    setStatus(`Ошибка бэкапа: ${e}`, "error");
  }
}

async function exportOrderFilesZip(clientId: string, orderId: string) {
  console.log(`UI exportOrderFilesZip: clientId=${clientId}, orderId=${orderId}`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!order || !order.files.length) {
    console.warn(`exportOrderFilesZip: no files found`);
    setStatus("Нет файлов для экспорта", "normal");
    return;
  }
  const filePaths = order.files.map(f => f.path);
  console.log(`  → ${filePaths.length} files to export`);
  try {
    console.log(`IPC → export_files_zip`);
    const zipData = await invoke<number[]>("export_files_zip", { filePaths });
    console.log(`IPC ← export_files_zip: ${zipData.length} bytes`);
    const name = `${order.service_type.replace(/\s+/g,"_")}_files_${Date.now()}.zip`;
    await downloadBlob(name, zipData, "application/zip");
    setStatus("Файлы заказа экспортированы", "saved");
  } catch (e) {
    console.error(`exportOrderFilesZip error:`, e);
    setStatus(`Ошибка экспорта: ${e}`, "error");
  }
}

async function exportClientFilesZip(clientId: string) {
  console.log(`UI exportClientFilesZip: clientId=${clientId}`);
  const client = clients.find(c => c.id === clientId);
  if (!client) { console.warn(`exportClientFilesZip: client not found`); return; }
  const filePaths: string[] = [];
  for (const o of client.orders) {
    for (const f of o.files) {
      if (f.path && !filePaths.includes(f.path)) filePaths.push(f.path);
    }
  }
  if (!filePaths.length) {
    console.warn(`exportClientFilesZip: no files`);
    setStatus("Нет файлов для экспорта", "normal");
    return;
  }
  console.log(`  → ${filePaths.length} files to export`);
  try {
    console.log(`IPC → export_files_zip`);
    const zipData = await invoke<number[]>("export_files_zip", { filePaths });
    console.log(`IPC ← export_files_zip: ${zipData.length} bytes`);
    const name = `${client.name.replace(/\s+/g,"_")}_files_${Date.now()}.zip`;
    await downloadBlob(name, zipData, "application/zip");
    setStatus("Файлы клиента экспортированы", "saved");
  } catch (e) {
    console.error(`exportClientFilesZip error:`, e);
    setStatus(`Ошибка экспорта: ${e}`, "error");
  }
}

async function importFromFolder() {
  console.log(`UI importFromFolder`);
  const input = document.getElementById("folder-importer") as HTMLInputElement;
  input.value = "";
  input.click();
  input.onchange = async () => {
    const files = input.files;
    if (!files || !files.length) { console.warn(`importFromFolder: no files selected`); return; }
    const folderName = files[0].webkitRelativePath.split("/")[0];
    const clientName = folderName.replace(/[_-]/g, " ").replace(/\s+/g, " ").trim();
    console.log(`  → folder="${folderName}", clientName="${clientName}", ${files.length} files`);
    if (!clientName) { alert("Не удалось определить имя клиента из имени папки"); return; }
    const ok = await showConfirm(
      "Импорт из папки",
      `Импортировать файлы из "${folderName}" как клиента "${clientName}"?`
    );
    if (!ok) { console.log(`  → cancelled`); return; }
    let existing = clients.find(c => c.name.toLowerCase() === clientName.toLowerCase());
    if (!existing) {
      existing = {
        id: generateUUID(),
        name: clientName,
        email: "", social_link: "", notes: "",
        orders: [],
      };
      clients.push(existing);
      console.log(`  → created new client "${clientName}"`);
    }
    let fileCount = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const relPath = file.webkitRelativePath;
      const parts = relPath.split("/");
      const orderName = parts.length > 2 ? parts[1] : "Разное";
      let order = existing.orders.find(o => o.service_type === orderName);
      if (!order) {
        order = {
          id: generateUUID(),
          service_type: orderName,
          price: 0, currency: "RUB", advance: 0,
          created_at: nowDatetime(), deadline: "", status: "В работе",
          files: [], payments: [],
        };
        existing.orders.push(order);
        console.log(`  → created order "${orderName}"`);
      }
      const path = file.name;
      order.files.push({ path, name: file.name, is_finished: false, is_folder: false });
      fileCount++;
    }
    console.log(`  → imported ${fileCount} files into ${existing.orders.length} orders`);
    clients = await apiSaveClient(existing);
    renderDashboard(); renderClientList(); renderClientProfile();
    setStatus(`Импортировано ${fileCount} файлов`, "saved");
  };
}

async function deleteAllFiles() {
  console.log(`UI deleteAllFiles`);
  const choice = await showConfirm("Удалить все файлы", "Удалить только из программы (ссылки) или удалить файлы с диска? Нажмите «Подтвердить» для удаления из программы, «Отмена» — для отмены.");
  if (!choice) { console.log(`  → cancelled`); return; }
  let total = 0;
  for (const c of clients) {
    for (const o of c.orders) {
      const paths = o.files.map(f => f.path);
      for (const p of paths) {
        try { await invoke("delete_file", { path: p }); } catch (e) {
          console.warn("deleteAllFiles: failed to delete from disk:", p, e);
        }
      }
      total += o.files.length;
      o.files = [];
    }
  }
  console.log(`  → removed ${total} file references`);
  const json = JSON.stringify(clients, null, 2);
  clients = JSON.parse(json);
  for (const c of clients) {
    clients = await apiSaveClient(c);
  }
  renderDashboard(); renderClientList(); renderClientProfile();
  setStatus("Все файлы удалены", "saved");
}

async function deleteDatabaseFull() {
  console.log(`UI deleteDatabaseFull`);
  const ok = await showConfirm(
    "Очистить базу данных",
    "Все клиенты, заказы и файлы будут безвозвратно удалены! Продолжить?"
  );
  if (!ok) { console.log(`  → cancelled`); return; }
  const allPaths: string[] = [];
  for (const c of clients) {
    for (const o of c.orders) {
      for (const f of o.files) {
        if (f.path) allPaths.push(f.path);
      }
    }
  }
  console.log(`  → ${clients.length} clients, ${allPaths.length} files to clean up`);
  try {
    await invoke("delete_database");
    console.log(`IPC ← delete_database: success`);
    clients = [];
    selectedClientId = null;
  } catch (e) {
    console.error(`deleteDatabaseFull: delete_database error:`, e);
    setStatus(`Ошибка удаления БД: ${e}`, "error");
    return;
  }
  for (const path of allPaths) {
    try { await invoke("delete_file", { path }); } catch {}
  }
  renderDashboard(); renderClientList(); renderClientProfile();
  setStatus("База данных очищена", "saved");
}

async function updateDbSizeDisplay() {
  const btn = document.getElementById("set-db-size") as HTMLButtonElement;
  if (!btn) return;
  try {
    console.log(`IPC → get_database_size`);
    const size = await invoke<number>("get_database_size");
    console.log(`IPC ← get_database_size: ${size} bytes`);
    btn.textContent = size > 0 ? `Размер БД: ${(size / 1024).toFixed(1)} KB` : "Размер БД: —";
  } catch (e) {
    console.warn(`get_database_size error:`, e);
    btn.textContent = "Размер БД: —";
  }
}

// === FILE MANAGER ===

function openFileManager() {
  console.log(`UI openFileManager`);
  renderFileManager();
  openModal("modal-file-manager");
}

function renderFileManager() {
  const tree = document.getElementById("fm-tree")!;
  console.log(`UI renderFileManager`);
  const allFiles: { client: Client; order: Order; file: ProjectFile }[] = [];
  for (const c of clients) {
    for (const o of c.orders) {
      for (const f of o.files) {
        allFiles.push({ client: c, order: o, file: f });
      }
    }
  }
  if (!allFiles.length) {
    tree.innerHTML = `<div class="fm-empty">Файлов нет</div>`;
    return;
  }
  let html = "";
  const grouped: Record<string, Record<string, ProjectFile[]>> = {};
  for (const { client, order, file } of allFiles) {
    if (!grouped[client.id]) grouped[client.id] = {};
    if (!grouped[client.id][order.id]) grouped[client.id][order.id] = [];
    grouped[client.id][order.id].push(file);
  }
  for (const c of clients) {
    if (!grouped[c.id]) continue;
    html += `<div class="fm-client"><div class="fm-client-header">${escHtml(c.name)}</div>`;
    for (const o of c.orders) {
      if (!grouped[c.id][o.id]) continue;
      html += `<div class="fm-order"><div class="fm-order-header">${escHtml(o.service_type)}</div><div class="fm-files">`;
      for (const f of grouped[c.id][o.id]) {
        const statusIcon = f.is_finished ? "✅" : "⏳";
        html += `<div class="fm-file" data-path="${escHtml(f.path)}" data-name="${escHtml(f.name)}" data-cid="${c.id}" data-oid="${o.id}">
          <span>${statusIcon}</span>
          <span class="fm-file-name" title="${escHtml(f.path)}">${escHtml(f.name)}</span>
          <span class="fm-file-actions">
            <button class="fm-file-btn" data-action="open">📂</button>
            <button class="fm-file-btn" data-action="rename">✏️</button>
            <button class="fm-file-btn" data-action="toggle-status">${f.is_finished ? "🔄" : "✅"}</button>
            <button class="fm-file-btn" data-action="delete" style="color:var(--color-danger)">🗑</button>
          </span>
        </div>`;
      }
      html += `</div></div>`;
    }
    html += `</div>`;
  }
  tree.innerHTML = html;

  tree.querySelectorAll(".fm-file").forEach(el => {
    const fileEl = el as HTMLElement;
    const path = fileEl.dataset.path!;
    const name = fileEl.dataset.name!;
    const cid = fileEl.dataset.cid!;
    const oid = fileEl.dataset.oid!;

    fileEl.querySelectorAll("[data-action]").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const action = (btn as HTMLElement).dataset.action!;
        switch (action) {
          case "open":
            {
              const dir = parentDir(path);
              console.log(`FM openFolder: file="${path}", dir="${dir}"`);
              try { await invoke("open_path", { path: dir }); } catch { alert(`Не удалось открыть папку: ${dir}`); }
            }
            break;
          case "rename":
            (document.getElementById("rename-input") as HTMLInputElement).value = name;
            (document.getElementById("rename-input") as HTMLInputElement).dataset.oldPath = path;
            (document.getElementById("rename-input") as HTMLInputElement).dataset.cid = cid;
            (document.getElementById("rename-input") as HTMLInputElement).dataset.oid = oid;
            openModal("modal-rename");
            break;
          case "toggle-status":
            {
              const client = clients.find(x => x.id === cid);
              const order = client?.orders.find(x => x.id === oid);
              const file = order?.files.find(x => x.name === name);
              if (file) {
                file.is_finished = !file.is_finished;
                clients = await apiSaveClient(client!);
                renderFileManager();
                renderClientProfile();
              }
            }
            break;
          case "delete":
            {
              const ok = await showConfirm("Удалить файл", `Удалить "${name}" из заказа?`);
              if (!ok) return;
              const client = clients.find(x => x.id === cid);
              const order = client?.orders.find(x => x.id === oid);
              if (order) {
                order.files = order.files.filter(x => x.name !== name);
                clients = await apiSaveClient(client!);
                renderFileManager();
                renderClientProfile();
              }
            }
            break;
        }
      });
    });
  });
}

// === SYSTEM DIALOGS ===

async function openAbout() {
  console.log(`UI openAbout`);
  const dbDir = await invoke<string>("get_db_dir");
  const lines: string[] = [];
  for (const name of ["LICENSE", "EULA.md", "THIRD_PARTY_LICENSES.txt"]) {
    const tryPath = `${dbDir}/${name}`;
    try {
      console.log(`IPC → read_text_file: ${tryPath}`);
      const text = await invoke<string>("read_text_file", { path: tryPath });
      console.log(`IPC ← read_text_file: ${text.length} bytes`);
      lines.push(`\n─── ${name} ───\n${text}`);
    } catch {}
  }
  if (lines.length > 0) {
    const aboutContent = el("about-dialog-content")!;
    let html = `<div class="about-logo">💼 FinanceFugue</div>
<div class="about-version">Версия 25.7.2026</div>
<div class="about-desc">Профессиональный менеджер клиентов и заказов для фрилансеров</div>`;
    for (const line of lines) {
      html += `<pre style="font-size:10px;color:var(--color-text-dim);max-height:120px;overflow-y:auto;background:var(--color-bg-panel);padding:8px;border-radius:4px;margin-top:8px;text-align:left;white-space:pre-wrap;">${escHtml(line)}</pre>`;
    }
    aboutContent.innerHTML = html;
  }
  openModal("modal-about");
}

function openHelp() {
  console.log(`UI openHelp`);
  const helpPath = "help.html";
  invoke("open_path", { path: helpPath }).catch(() => {
    alert("Файл справки не найден. Откройте help.html вручную.");
  });
}

function checkEula() {
  const accepted = localStorage.getItem("ff_eula_accepted");
  if (!accepted) {
    alert(
      "Добро пожаловать в FinanceFugue!\n\n" +
      "Используя данное программное обеспечение, вы соглашаетесь с условиями лицензионного соглашения (EULA).\n\n" +
      "Приложение предоставляется «как есть» без каких-либо гарантий.\n" +
      "Автор: Kirill Fandeev (KVF SOFT)\n" +
      "Поддержка: KVF_SOFT@mail.ru"
    );
    localStorage.setItem("ff_eula_accepted", "true");
  }
}

function checkFirstRun() {
  const completed = localStorage.getItem("ff_first_run");
  if (!completed) {
    setTimeout(() => {
      alert("Добро пожаловать! 👋\n\nFinanceFugue — профессиональный менеджер клиентов и заказов.\n\n" +
        "Быстрые клавиши:\n" +
        "  Ctrl+N — новый клиент\n" +
        "  Ctrl+F — поиск\n" +
        "  Ctrl+O — файловый менеджер\n" +
        "  Ctrl+S — сохранить\n" +
        "  Ctrl+, — настройки\n" +
        "  Escape — закрыть диалог\n\n" +
        "Нажмите «➕ Новый клиент» чтобы начать работу.");
      localStorage.setItem("ff_first_run", "true");
    }, 500);
  }
}

// === DRAG-DROP HANDLER ===

let dragOverlay: HTMLDivElement | null = null;

function showDragOverlay() {
  if (!dragOverlay) {
    dragOverlay = document.createElement("div");
    dragOverlay.className = "drag-overlay";
    dragOverlay.innerHTML = '<div class="drag-overlay-text">📁 Отпустите файлы для добавления в заказ</div>';
    document.body.appendChild(dragOverlay);
  }
}

function hideDragOverlay() {
  if (dragOverlay) {
    dragOverlay.remove();
    dragOverlay = null;
  }
}

async function handleFileDrop(paths: string[], x: number, y: number) {
  console.log(`UI handleFileDrop: ${paths.length} file(s) at (${x},${y})`);
  hideDragOverlay();
  const el = document.elementFromPoint(x, y);
  if (!el) { console.warn(`handleFileDrop: no element at drop point`); return; }
  const card = (el as HTMLElement).closest(".order-card") as HTMLElement | null;
  if (!card) { console.warn(`handleFileDrop: not dropped on order card`); return; }
  const clientId = card.dataset.clientId;
  const orderId = card.dataset.orderId;
  if (!clientId || !orderId) { console.warn(`handleFileDrop: missing data attrs`); return; }
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!client || !order) { console.warn(`handleFileDrop: client/order not found`); return; }
  const dbDir = await invoke<string>("get_db_dir");
  console.log(`  → target: ${dbDir}`);
  let added = 0;
  for (const srcPath of paths) {
    const targetDir = `${dbDir}/attached_files/${clientId}/${orderId}`;
    try {
      console.log(`IPC → copy_file_to: ${srcPath}`);
      const newPath = await invoke<string>("copy_file_to", { source: srcPath, destDir: targetDir });
      console.log(`IPC ← copy_file_to: ${newPath}`);
      const name = srcPath.split(/[/\\]/).pop() || srcPath;
      order.files.push({ path: newPath, name, is_finished: false, is_folder: false });
      added++;
    } catch (e) {
      console.warn("Failed to copy dropped file:", srcPath, e);
    }
  }
  if (added > 0) {
    console.log(`  → ${added} files added via drag-drop`);
    clients = await apiSaveClient(client);
    renderClientProfile();
    setStatus(`Добавлено ${added} файлов (drag-drop)`, "saved");
  }
}

function setupDragDrop() {
  console.log("UI setupDragDrop: registering onDragDropEvent");
  getCurrentWindow().onDragDropEvent((event) => {
    const p = event.payload;
    console.log(`DnD event: type=${p.type}`);
    switch (p.type) {
      case "enter":
        showDragOverlay();
        break;
      case "over":
        break;
      case "drop":
        console.log(`DnD drop: ${p.paths.length} file(s) at (${p.position.x},${p.position.y})`);
        handleFileDrop(p.paths, p.position.x, p.position.y);
        break;
      case "leave":
        hideDragOverlay();
        break;
    }
  }).catch((e) => {
    console.error("DnD registration failed:", e);
  });
}

async function openLink(url: string) {
  try {
    await apiOpenPath(url);
  } catch {}
}
(window as any).openLink = openLink;

function parentDir(path: string): string {
  const idx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
  return idx >= 0 ? path.substring(0, idx) : path;
}

async function openFolder(path: string) {
  const dir = parentDir(path);
  console.log(`UI openFolder: file="${path}", dir="${dir}"`);
  await apiOpenPath(dir);
}
(window as any).openFolder = openFolder;

  async function onDeleteCurrentClient() {
    console.log(`UI onDeleteCurrentClient`);
    const client = getSelectedClient();
    if (!client) { console.warn(`onDeleteCurrentClient: no client selected`); return; }
    const ok = await showConfirm("Удалить клиента?", `Клиент "${client.name}" и все его заказы будут удалены.`);
    if (!ok) { console.log(`  → cancelled`); return; }
    clients = await apiDeleteClient(client.id);
    if (selectedClientId === client.id) selectedClientId = clients.length > 0 ? clients[0].id : null;
    renderDashboard();
    renderClientList();
    renderClientProfile();
  }

async function deleteFileFromOrder(clientId: string, orderId: string, fileName: string) {
  console.log(`UI deleteFileFromOrder: clientId=${clientId}, orderId=${orderId}, file="${fileName}"`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  if (!client || !order) { console.warn(`deleteFileFromOrder: client/order not found`); return; }
  const ok = await showConfirm("Удалить файл?", `Удалить файл '${fileName}' из заказа? Если файл существует на диске, он также будет удалён.`);
  if (!ok) { console.log(`  → cancelled`); return; }

  const file = order.files.find(f => f.name === fileName);
  if (file && file.path) {
    console.log(`IPC → delete_file: ${file.path}`);
    try { await invoke("delete_file", { path: file.path });
      console.log(`IPC ← delete_file: success`);
    } catch (e) {
      console.warn("deleteFileFromOrder: delete_file error:", file.path, e);
    }
  }
  order.files = order.files.filter(f => f.name !== fileName);
  clients = await apiSaveClient(client);
  renderClientProfile();
}

async function toggleFileFinished(clientId: string, orderId: string, fileName: string) {
  console.log(`UI toggleFileFinished: clientId=${clientId}, orderId=${orderId}, file="${fileName}"`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  const file = order?.files.find(f => f.name === fileName);
  if (!file) { console.warn(`toggleFileFinished: file not found`); return; }
  file.is_finished = !file.is_finished;
  console.log(`  → ${fileName}: is_finished=${file.is_finished}`);
  clients = await apiSaveClient(client!);
  renderClientProfile();
}

async function renameFileInOrder(clientId: string, orderId: string, oldName: string) {
  console.log(`UI renameFileInOrder: clientId=${clientId}, orderId=${orderId}, file="${oldName}"`);
  const client = clients.find(c => c.id === clientId);
  const order = client?.orders.find(o => o.id === orderId);
  const file = order?.files.find(f => f.name === oldName);
  if (!file) { console.warn(`renameFileInOrder: file not found`); return; }

  const input = document.getElementById("rename-input") as HTMLInputElement;
  input.value = oldName;
  input.dataset.oldPath = file.path;
  input.dataset.cid = clientId;
  input.dataset.oid = orderId;
  openModal("modal-rename");

  const confirmBtn = document.getElementById("rename-confirm")!;
  const modal = document.getElementById("modal-rename") as HTMLDialogElement;

  const handler = async () => {
    const newName = input.value.trim();
    if (!newName) { console.warn(`rename: empty name`); alert("Введите новое имя"); return; }
    console.log(`  → renaming "${oldName}" -> "${newName}"`);
    const x = clients.find(c => c.id === clientId);
    const o = x?.orders.find(o => o.id === orderId);
    const f = o?.files.find(f => f.name === oldName);
    if (f) {
      try {
        console.log(`IPC → rename_file: oldPath=${f.path}, newName=${newName}`);
        const newPath = await invoke<string>("rename_file", { oldPath: f.path, newName });
        console.log(`IPC ← rename_file: ${newPath}`);
        f.path = newPath;
        f.name = newName;
        clients = await apiSaveClient(x!);
        renderFileManager();
        renderClientProfile();
        setStatus("Файл переименован", "saved");
      } catch (e) {
        console.error(`renameFileInOrder error:`, e);
        alert(`Ошибка переименования: ${e}`);
      }
    }
    closeModal("modal-rename");
    cleanup();
  };

  const cleanup = () => {
    confirmBtn.removeEventListener("click", handler);
    modal.removeEventListener("close", cleanup);
  };

  confirmBtn.addEventListener("click", handler);
  modal.addEventListener("close", cleanup);
}
(window as any).deleteFileFromOrder = deleteFileFromOrder;
(window as any).toggleFileFinished = toggleFileFinished;
(window as any).renameFileInOrder = renameFileInOrder;

// =====================================================
// INITIALIZATION
// =====================================================

async function init() {
  console.log("=== FinanceFugue Initialization Start ===");
  try {
    const isLocked = await invoke<boolean>("has_password");
    if (isLocked) {
      el("lock-screen")!.style.display = "flex";
      
      const pwdInput = el("lock-password-input") as HTMLInputElement;
      const unlockBtn = el("btn-unlock");
      const errBox = el("lock-error")!;
      
      const tryUnlock = async () => {
        const pwd = pwdInput.value;
        if (!pwd) return;
        const valid = await invoke<boolean>("check_password", { password: pwd });
        if (valid) {
          el("lock-screen")!.style.display = "none";
          el("main-app")!.style.display = "block";
          continueInit();
        } else {
          errBox.textContent = "Неверный пароль";
          pwdInput.value = "";
          pwdInput.focus();
        }
      };
      
      unlockBtn?.addEventListener("click", tryUnlock);
      pwdInput?.addEventListener("keyup", (e) => {
        if (e.key === "Enter") tryUnlock();
      });
      pwdInput.focus();
      return; // Stop initialization until unlocked
    } else {
      el("main-app")!.style.display = "block";
    }
  } catch (e) {
    console.error("Failed to check password:", e);
    el("main-app")!.style.display = "block";
  }

  continueInit();
}

async function continueInit() {
  try {
    clients = await apiGetClients();
  } catch (e) {
    console.error("Failed to load clients:", e);
    clients = [];
  }

  console.log(`init: loaded ${clients.length} clients`);
  if (clients.length > 0 && !selectedClientId) {
    selectedClientId = clients[0].id;
    console.log(`init: auto-selected client id=${selectedClientId}`);
  }

  renderDashboard();
  renderClientList();
  renderClientProfile();
  setupFormListeners();
  setupContextMenu();
  setupKeyboardShortcuts();
  setupDragDrop();
  checkEula();
  checkFirstRun();

  el("btn-add-client")!.addEventListener("click", openAddClientModal);
  el("btn-file-manager")!.addEventListener("click", openFileManager);
  el("btn-settings")!.addEventListener("click", openSettingsModal);
  el("btn-help")!.addEventListener("click", openHelp);
  el("btn-about")!.addEventListener("click", openAbout);
  el("search-input")!.addEventListener("input", () => renderClientList());

  updateDbSizeDisplay();

  (el("sort-select") as HTMLSelectElement).addEventListener("change", (e) => {
    sortMode = (e.target as HTMLSelectElement).value;
    console.log(`UI sort-select: mode=${sortMode}`);
    renderClientList();
  });

  setTimeout(() => {
    if (appSettings.deadline_notifications) checkDeadlineNotifications();
  }, 1000);

  console.log("=== FinanceFugue Initialization Complete ===");
  setStatus("FinanceFugue готов к работе", "saved", 3000);
}

function initSettingsWindow() {
  console.log("=== Settings Window Init ===");
  el("main-app")!.style.display = "none";
  el("settings-page")!.style.display = "block";

  const closeBtn = el("settings-close-btn");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      getCurrentWindow().close().catch(e => console.error("close error:", e));
    });
  }

  invoke<string>("get_db_dir").then(dir => {
    (el("set-db-path") as HTMLInputElement).value = dir;
  }).catch(e => console.error("Failed to get DB dir:", e));

  invoke<Client[]>("get_clients").then(c => {
    clients = c;
    console.log(`settings: loaded ${clients.length} clients`);
  }).catch(e => console.error("Failed to load clients:", e));

  el("set-deadline-notify")!.addEventListener("change", (e) => {
    appSettings.deadline_notifications = (e.target as HTMLInputElement).checked;
    saveSettings(appSettings);
  });

  // Password management
  el("set-change-password")?.addEventListener("click", async () => {
    const hasPwd = await invoke<boolean>("has_password");
    if (hasPwd) {
      const oldPwd = prompt("Введите текущий пароль:");
      if (!oldPwd) return;
      const valid = await invoke<boolean>("check_password", { password: oldPwd });
      if (!valid) {
        alert("Неверный пароль.");
        return;
      }
    }
    const newPwd = prompt("Введите новый пароль:");
    if (newPwd) {
      await invoke("set_password", { password: newPwd });
      alert("Пароль успешно установлен.");
    }
  });

  el("set-remove-password")?.addEventListener("click", async () => {
    const hasPwd = await invoke<boolean>("has_password");
    if (!hasPwd) {
      alert("Пароль не установлен.");
      return;
    }
    const oldPwd = prompt("Введите текущий пароль для отключения защиты:");
    if (!oldPwd) return;
    const valid = await invoke<boolean>("check_password", { password: oldPwd });
    if (!valid) {
      alert("Неверный пароль.");
      return;
    }
    await invoke("set_password", { password: null });
    alert("Защита паролем отключена.");
  });


  el("set-browse-db")!.addEventListener("click", async () => {
    try {
      const selected = await open({ directory: true, multiple: false, title: "Выберите папку для хранения БД" });
      if (selected) {
        await invoke("save_db_dir", { dir: selected });
        (el("set-db-path") as HTMLInputElement).value = selected;
        setStatus("Путь к БД сохранён. Перезапустите программу.", "saved");
      }
    } catch (e) {
      console.error("set-browse-db error:", e);
    }
  });

  el("set-export-json")!.addEventListener("click", () => {
    const json = JSON.stringify(clients, null, 2);
    downloadFile("financefugue_export.json", json, "application/json");
  });

  el("set-backup-zip")!.addEventListener("click", async () => {
    const filePaths: string[] = [];
    for (const c of clients) {
      for (const o of c.orders) {
        for (const f of o.files) {
          if (f.path && !filePaths.includes(f.path)) filePaths.push(f.path);
        }
      }
    }
    const dbJson = JSON.stringify(clients, null, 2);
    try {
      const zipData = await invoke<number[]>("create_backup_zip", { filePaths, dbJson });
      await downloadBlob(`financefugue_backup_${Date.now()}.zip`, zipData, "application/zip");
      setStatus("Бэкап ZIP создан", "saved");
    } catch (e) {
      console.error(`exportFullBackup error:`, e);
      setStatus(`Ошибка бэкапа: ${e}`, "error");
    }
  });

  el("set-import-folder")!.addEventListener("click", () => {
    importFromFolder();
  });

  el("set-delete-files")!.addEventListener("click", async () => {
    const choice = await showConfirm("Удалить все файлы", "Файлы будут удалены с диска. Продолжить?");
    if (!choice) return;
    let deletedCount = 0;
    let failedCount = 0;
    for (const c of clients) {
      for (const o of c.orders) {
        const remainingFiles: ProjectFile[] = [];
        for (const f of o.files) {
          try {
            await invoke("delete_file", { path: f.path });
            deletedCount++;
          } catch (err) {
            console.warn(`Failed to delete file ${f.path}:`, err);
            failedCount++;
            remainingFiles.push(f);
          }
        }
        o.files = remainingFiles;
      }
    }
    for (const c of clients) {
      clients = await apiSaveClient(c);
    }
    renderClientProfile();
    if (failedCount > 0) {
      setStatus(`Удалено ${deletedCount} файлов, ошибок: ${failedCount}`, "error");
    } else {
      setStatus(`Удалено файлов: ${deletedCount}`, "saved");
    }
  });

  el("set-delete-db")!.addEventListener("click", async () => {
    const ok = await showConfirm("Очистить базу данных", "Все данные будут безвозвратно удалены! Продолжить?");
    if (!ok) return;
    try {
      await invoke("delete_database");
      clients = [];
      selectedClientId = null;
      renderDashboard();
      renderClientList();
      renderClientProfile();
      setStatus("База данных очищена", "saved");
    } catch (e) {
      console.error("delete_database error:", e);
      setStatus(`Ошибка очистки БД: ${e}`, "error");
    }
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
        setStatus(`Импортировано ${imported.length} клиентов`, "saved");
      } catch (err) {
        console.error(`import-json error:`, err);
        alert(`Ошибка импорта: ${err}`);
      }
    });
    input.click();
  });

  updateDbSizeDisplay();
  console.log("=== Settings Window Ready ===");
}

window.addEventListener("DOMContentLoaded", () => {
  const currentWindow = getCurrentWindow();
  const isSettingsWindow = currentWindow.label === "settings";
  if (isSettingsWindow) {
    initSettingsWindow();
  } else {
    init();
  }
});
