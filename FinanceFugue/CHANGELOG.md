# Changelog

## 04.08.2026 — security audit & bugfixes (round 2)

### Исправлено (🔴 критические)
- **Path traversal в `widgets/file_item_widget.rename_file`** — пользовательский
  ввод больше не проходит в `os.rename` напрямую. Добавлен
  `safe_filename_candidate` (удаляет `..` и `/\\`).
- **Path traversal в `dialogs/file_manager._handle_drop`** — drop файлов
  вне `attached_files` отклоняется через `safe_resolve_within` (ранее
  принимались любые пути из MIME).
- **Inconsistent state в `dialogs/settings_dialog.change_database_location`** —
  теперь копируем все файлы, и только при полном успехе мутируем
  `file.path` (ранее мутация происходила в цикле копирования, и при
  исключении половина файлов указывала на новое место, половина на старое).

### Исправлено (🟡 серьёзные)
- **`services/backup.create_full_backup_zip`** — каждый arcname проходит
  проверку на отсутствие `..` и абсолютный префикс; файлы с
  path-traversal в `Path.parts` отклоняются.
- **`utils/instance_lock`** — stale lock detection: проверка PID в lock-файле;
  если процесс не существует — lock удаляется автоматически (msvcrt через
  `OpenProcess`/`GetExitCodeProcess`, POSIX через `os.kill(pid, 0)`).
- **`ui/main_window/window`** — `QTimer.singleShot(800)` с popup=True
  заменён на parented QTimer + status bar (popup=True спамил дедлайнами
  на каждом запуске).
- **`ui/main_window/mixins/shell.check_deadline_notifications`** — дедуп
  через `app_settings["deadline_alerts_acked"]`; повторный показ только
  для новых алертов.

### Исправлено (🟠 умеренные)
- **`Order.add_payment` / `update_price` / `update_advance`** — все три
  отклоняют NaN/Inf через `math.isfinite`.
- **`storage._parse_clients_list`** — NaN/Inf в `price`/`advance`/`amount`
  заменяются на default через `_finite_float` (ранее `debt = max(0, price - inf)
  = 0` → «долг 0» при технической ошибке, плюс `Decimal(str(NaN))` крашил
  дашборд).
- **`services/client_deletion.is_safe_to_delete`** — теперь через
  `path_safety.is_path_within` (resolve + commonpath с учётом case Windows).
- **`dialogs/folder_import.scan_folder`** — каждая `os.listdir` обёрнута в
  `try/except OSError`; одна защищённая папка больше не ломает весь импорт.
- **`database_ops.import_dropped_client_folder`** — сравнение имён
  клиентов через `name.strip().lower()` (устраняет дубликаты с пробелами).
- **`ui/main_window/mixins/shell`** — debounce 200мс для
  `search_edit.textChanged` (ранее полный пересчёт списка на каждом
  символе).
- **`widgets/order_files_mixin.dropEvent`** — `os.walk(followlinks=False)`
  (защита от symlink-циклов).
- **`mixins/client_export`** — sanitize имён файлов и папок (удаление
  `<>:"/\\|?*\x00-\x1f`, защита от path-traversal в названиях экспортируемых
  заказов/клиентов).
- **`dialogs/settings_dialog.restore_settings_dialog`** — `backup_dir`
  теперь идёт через `user_data_path()`, не от CWD.

### Добавлено
- **`utils/path_safety.py`** — единая точка валидации путей:
  `sanitize_path_component`, `is_path_within`, `safe_filename_candidate`,
  `safe_resolve_within`. Используется во всех местах с пользовательским
  вводом файлов.
- **`tests/test_audit_fixes.py`** — 14 новых тестов на защиты от
  path traversal, NaN/Inf в финансах, backup arcname.

### Итого
- pytest: **60 passed** (было 46)
- ruff: All checks passed
- bandit: 15 known false-positives (subprocess без shell для открытия файлов)

## 04.08.2026 — bugfix release (round 1)

### Исправлено (критические)
- `Order.update_price` — устранён рассинхрон `advance` ↔ `total_received`
  при уменьшении цены ниже аванса.
- `Order.add_payment` — при переплате `debt == 0` блокирует любой
  положительный платёж.
- `services/currency.py` — `format_amount` использует `Decimal`+`ROUND_HALF_UP`;
  добавлен `has_outstanding_debt()`.

### Исправлено (прочие)
- `widgets/file_item_widget.mouseReleaseEvent` — больше не открывает файл
  при клике по кнопкам «Открыть»/«Удалить».
- `order_financial_mixin.format_number` — больше не теряет дробную часть.
- `order_financial_mixin.sync_price` — тот же баг-паттерн исправлен.
- `utils/instance_lock.release` — FD закрывается через `try/finally`.
- `dialogs/folder_import` — `os.listdir(folder)` обёрнут в `try/except`.
- `dialogs/file_manager._resolve_drop_target` — AttributeError → info.
- `logger.py` — убран неиспользуемый `pathlib.Path`.

## 05.06.2026 18:28

Релиз FinanceFugue: production remediation (InstanceLock, мультивалютность, модульная структура, 40 тестов, CI).

## 05.06.2026 (remediation)

### Добавлено
- `rebind_storage()` — переназначение БД с переносом InstanceLock
- `services/currency.py` — суммы по валютам без смешивания
- `services/client_deletion.py` — общая логика удаления файлов
- Разбиение `OrderWidget` на `order_files_mixin` / `order_financial_mixin`
- Тесты: валюта, удаление файлов, rebind storage
- `docs/PRODUCTION_REMEDIATION_PLAN.md`

### Исправлено
- Дедлайн в диалоге «Новый заказ» — только QDateEdit
- Copy-mode: при ошибке копирования файл не добавляется
- DatabaseLoadError после первого запуска
- Мультивалютный дашборд (без суммирования RUB+USD)
- `on_storage_changed` в FirstRunDialog

### Удалено
- `scripts/trim_order_widget.py`, `docs/PROMPT_WIDGET_REFACTOR.md`

## 05.06.2026

### Добавлено
- Поиск клиентов, менеджер файлов, DnD папок, горячие клавиши
- Уведомления о дедлайнах (при запуске + статус-бар каждые 30 мин)
- EULA, Privacy, диалог «О программе»
- Версия схемы JSON (`schema_version`)
- Блокировка второго экземпляра на одну базу
- CI: ruff + сборка EXE

### Исправлено
- Дублирование логики импорта из папки
- Создание `LINK_*.txt` на диске пользователя
- Неполный перенос папок при смене места базы
- Санитизация имён в ZIP-бэкапе
- `delete_all_files` — отсутствующие кнопки диалога
- Загрузка битых настроек (теперь явная ошибка)

### Удалено
- Неиспользуемый код `src/legacy/`
