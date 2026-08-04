# Changelog

## 04.08.2026 — security audit & bugfixes (round 3)

### Исправлено (HIGH из TZ)
- **P1-6 `delete_client`**: `save_db()` теперь идёт до `refresh_list()`.
  При исключении на диске остаётся согласованное состояние, UI просто
  перестаёт показывать. Добавлен graceful `QMessageBox.critical` при сбое.
- **P1-7 `clear_profile_layout`**: корректно удаляет `QSpacerItem` и
  nested layouts. Раньше `item.widget()` для spacer'а возвращал `None`,
  и они утекали на каждом пере-выборе клиента.
- **P1-8 `import_json_file`**: двойной парсинг JSON устранён через
  `import_database_with_backup(preloaded_clients=...)`.
- **P2-15 Symlink-атака**: `file_item_widget.open_file` и
  `file_manager._open_path` теперь проверяют, что symlink указывает
  внутрь ожидаемой директории (`is_path_within`).

### Исправлено (MEDIUM из TZ)
- **P2-10 `cleanup_empty_attached_dirs`** теперь выполняется через
  `QThreadPool.globalInstance()` (класс `_CleanupTask`) — UI не блокируется
  на глубоких деревьях.
- **P2-11 `export_full_backup`** для баз с >5 клиентами работает в
  `QThreadPool` через `BackupWorker` (с `BackupSignals`), с прогресс-баром.
  Маленькие базы остались синхронными (overhead ниже).
- **P1-9 Кэш running totals в `Order`**: `_recalculate_totals()` после
  `add_payment`/`delete_payment`. Сложность `debt`/`advance_debt` с O(N²)
  до O(1). `__post_init__` прогревает кэш и поднимает `advance` при
  загрузке из БД.

### Tooling (P3-1..P3-3, P3-7)
- **`pyproject.toml`**: добавлены `[tool.mypy]` и `[tool.bandit]`.
  `mypy --disable-error-code=attr-defined` для mixin-паттерна.
  `bandit --skips=B404,B603,B606,B607` (subprocess для file-open —
  основная фича desktop).
- **`testpaths`**: `["tests/qt"]` → `["tests"]` — все unit-тесты
  собираются автоматически.
- **`.pre-commit-config.yaml`**: ruff + ruff-format + базовые hooks.
  pytest и bandit на `manual` stage (для CI запуска).
- **`README.md`**: обновлён (новая версия, схема тестов, упоминание
  `path_safety.py`, удаление Tauri-порта).

### Новые тесты
- `tests/test_round3_fixes.py` — 10 тестов:
  - кэш total_* (4 теста: post_init, add_payment, delete_payment, advance-from-payments)
  - контракт `delete_client.save_db-before-refresh` (через inspect)
  - `import_database_with_backup(preloaded=)` (2 теста)
  - сигналы `BackupWorker` (через QApplication)
  - symlink+is_path_within (skip на Windows без admin)
  - arcname итератор бэкапа

### Итого
- pytest: **70 passed in 0.31s** (было 60 в round 2)
- ruff: All checks passed
- bandit: **0 issues** (было 15 known FP)
- mypy: 15 expected attr-defined (mixins), без критики runtime

**Security score:** 8.5/10 → **9/10** (закрыта symlink-атака).

---

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
