# ТЗ: Исправление багов — Полный аудит

## Приоритет 1 (критически важно)

### 1.1. Rust — `unwrap()` на Mutex → паника процесса

**Файл:** `src-tauri/src/commands.rs:17,23,35,43,52,62`

**Проблема:** Шесть вызовов `.lock().unwrap()` на `Mutex<Vec<Client>>`. С `panic = "abort"` в `Cargo.toml:25` любой poisoned mutex **убивает процесс**.

**Исправление:** Заменить на:
```rust
let mut clients = state.clients.lock().unwrap_or_else(|e| {
    error!("Mutex poisoned: {}", e);
    e.into_inner()
});
```
`e.into_inner()` извлекает данные даже из poisoned mutex.

---

### 1.2. Rust — Path Traversal в `rename_file`

**Файл:** `src-tauri/src/commands.rs:163-172`

**Проблема:** `new_name` не валидируется. `"../../malicious.exe"` переименовывает файл в любую директорию.

**Исправление:** Добавить валидацию:
```rust
let new_name = new_name.trim();
if new_name.is_empty() || new_name.contains("..") || new_name.contains('/') || new_name.contains('\\') {
    return Err("Недопустимое имя файла".to_string());
}
```

---

### 1.3. TS — `renameFileInOrder`: `dataset.oldPath` не установлен

**Файл:** `src/main.ts:1225-1246` (permanent handler), `src/main.ts:1893-1921` (renameFileInOrder)

**Проблема:** Permanent handler на `rename-confirm` читает `dataset.oldPath` (line 1228), но `renameFileInOrder` устанавливает `dataset.oldName` (line 1904), а не `oldPath`. При вызове из order card `invoke("rename_file")` получает `undefined`.

**Исправление:** Унифицировать оба пути. Удалить permanent handler из `setupFormListeners` и использовать только `renameFileInOrder` как единый entry point для всех rename-операций. Оба пути должны устанавливать `dataset.oldPath` (полный путь нужен для IPC).

---

### 1.4. TS — `renameFileInOrder` leak listener при закрытии через Escape

**Файл:** `src/main.ts:1914-1929`

**Проблема:** Listener на `rename-confirm` удаляется только при клике на Confirm. Escape не удаляет его → накапливаются дубли.

**Исправление:** Добавить cleanup через `modal-rename` close event:
```typescript
const modal = document.getElementById("modal-rename") as HTMLDialogElement;
const cleanup = () => {
    confirmBtn.removeEventListener("click", handler);
    modal.removeEventListener("close", cleanup);
};
modal.addEventListener("close", cleanup);
```

---

### 1.5. TS — `jsEscape` не экранирует `"` → XSS в inline onclick

**Файл:** `src/main.ts:1422-1424`

**Проблема:** `jsEscape` экранирует `\`, `'`, `\n`, но не `"`. Имя файла с `"` ломает onclick-атрибут.

**Исправление:** Добавить экранирование кавычек:
```typescript
function jsEscape(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, "\\n");
}
```

---

## Приоритет 2 (важно)

### 2.1. TS — `deleteDatabaseFull`: рассинхронизация состояния

**Файл:** `src/main.ts:1598,1600`

**Проблема:** `delete_database` и `delete_file` в пустом `catch {}`. Если файлы не удалились, in-memory уже очищено.

**Исправление:** Проверять результат и показывать ошибку пользователю:
```typescript
try {
    await invoke("delete_database");
} catch (e) {
    setStatus(`Ошибка удаления БД: ${e}`, "error");
    return;
}
```

---

### 2.2. TS — `deleteAllFiles`/`deleteFileFromOrder`: silent file deletion failure

**Файл:** `src/main.ts:1568, 1888`

**Проблема:** `try { await invoke("delete_file", ...); } catch {}` — in-memory состояние обновляется, файлы на диске остаются.

**Исправление:** Считать удалёнными только те файлы, где `delete_file` прошёл успешно. Или показывать предупреждение о сбое.

---

### 2.3. TS — `notesDebounceTimer` стреляет в неверного клиента

**Файл:** `src/main.ts:839-851`

**Проблема:** Если переключить клиента в течение 800ms после изменения заметок, `saveNotes` сохраняет заметки **предыдущего** клиента.

**Исправление:** Сбрасывать таймер при смене клиента. Добавить в `selectClient`:
```typescript
function selectClient(id: string) {
    if (notesDebounceTimer) clearTimeout(notesDebounceTimer);
    notesDebounceTimer = null;
    ...
}
```

---

### 2.4. TS — `showConfirm` leak listener при Escape

**Файл:** `src/main.ts:857-876`

**Проблема:** Escape закрывает модалку, но listeners на `confirm-ok`/`confirm-cancel` не удаляются.

**Исправление:** Добавить cleanup через `close` event модалки:
```typescript
const modal = el("modal-confirm") as HTMLDialogElement;
const cleanup = () => {
    okBtn.removeEventListener("click", onOk);
    cancelBtn.removeEventListener("click", onCancel);
    modal.removeEventListener("close", cleanup);
};
modal.addEventListener("close", cleanup);
```

---

### 2.5. TS — Ctrl+S: floating promise + race

**Файл:** `src/main.ts:1385-1388`

**Проблема:** `apiSaveClient(client).then(...)` без `.catch()`. При быстром Ctrl+S гонка за состояние.

**Исправление:** Добавить `.catch()` и использовать `await`:
```typescript
case "s":
    e.preventDefault();
    if (!e.shiftKey) {
        const client = getSelectedClient();
        if (client) {
            try {
                const updated = await apiSaveClient(client);
                clients = updated;
                setStatus("Сохранено вручную", "saved");
            } catch (e) {
                setStatus(`Ошибка сохранения: ${e}`, "error");
            }
        }
    }
    break;
```

---

### 2.6. Rust — `Path::file_name().unwrap()` паникает на `..`

**Файл:** `src-tauri/src/commands.rs:97,118,188`

**Проблема:** `file_name()` возвращает `None` для путей оканчивающихся на `..`.

**Исправление:** Заменить `.unwrap()` на `.ok_or("...")?`:
```rust
let name = p.file_name().ok_or("Неверный путь")?.to_string_lossy().to_string();
```

---

### 2.7. Rust — `Path::parent().unwrap()` паникает на корневом пути

**Файл:** `src-tauri/src/commands.rs:168,205`

**Проблема:** `parent()` возвращает `None` для корневых путей (`/` или `C:\`).

**Исправление:**
```rust
let parent = p.parent().ok_or("Неверный путь")?;
```

---

### 2.8. Rust — In-memory state drift при save failure

**Файл:** `src-tauri/src/commands.rs:29,37,46,56,73`

**Проблема:** Мьютекс мутируется, затем вызывается `save_clients()?`. Если save провалится, in-memory ≠ persisted.

**Исправление:** Сохранять в temp-переменную, а на success — обновлять мьютекс:
```rust
let mut clients = state.clients.lock().unwrap();
// ... мутировать clients ...
let result = state.storage.save_clients(&clients);
if result.is_err() {
    // rollback? или просто вернуть ошибку без изменения состояния
}
result?;
```

---

## Приоритет 3 (желательно)

### 3.1. Rust — Dead code: `add_payment` и `read_file_bytes`

**Файл:** `src-tauri/src/commands.rs:61-75,129-138`

**Проблема:** Зарегистрированы в `main.rs` но не вызываются из TS.

**Исправление:** Удалить функции и их регистрацию из `generate_handler!`.

---

### 3.2. Rust — Dead code: 6 методов `impl Order`

**Файл:** `src-tauri/src/models.rs:62-99`

**Проблема:** `total_received()`, `debt()`, `remaining_debt()` и др. не используются в Rust.

**Исправление:** Удалить `impl Order` блок и `#[allow(dead_code)]`.

---

### 3.3. TS — `formatMoney` падает на NaN

**Файл:** `src/main.ts:97-107`

**Проблема:** `NaN.toFixed(2)` бросает `RangeError`.

**Исправление:** Добавить защиту:
```typescript
function formatMoney(amount: number, currency = "RUB"): string {
  if (isNaN(amount) || !isFinite(amount)) return `0 ${currSym(currency)}`;
  ...
}
```

---

### 3.4. TS — `importFromFolder`: пустое имя клиента

**Файл:** `src/main.ts:1508-1555`

**Проблема:** Пустой `webkitRelativePath` → клиент с пустым именем.

**Исправление:** Валидировать `clientName`:
```typescript
if (!clientName) {
    alert("Не удалось определить имя клиента из папки");
    return;
}
```

---

### 3.5. TS — `openAbout` использует class selector с `!`

**Файл:** `src/main.ts:1738`

**Проблема:** `document.querySelector(".about-dialog")!` — fragile.

**Исправление:** Добавить `id="about-dialog"` в HTML и использовать `el("about-dialog")`.

---

## Итоги

| Приоритет | Багов | Действия |
|-----------|-------|----------|
| 1 (критично) | 5 | Mutex unwrap, path traversal, rename dual-path, listener leak, jsEscape XSS |
| 2 (важно) | 8 | State drift, silent failures, debounce, showConfirm leak, Ctrl+S race, Rust unwraps, save failure |
| 3 (желательно) | 5 | Dead code, NaN guard, empty name, class selector |
