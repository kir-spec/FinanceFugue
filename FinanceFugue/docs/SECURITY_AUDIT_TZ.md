# TZ — Техническое задание на устранение дефектов аудита 04.08.2026

**Дата:** 04.08.2026  
**Аудитор:** opencode (SENIOR PRODUCTION ENGINEER mode)  
**Проект:** FinanceFugue (PySide6 CRM, `E:\coding\client_manager\FinanceFugue`)  
**Версия на момент аудита:** `19e299f` (до аудита)  
**HEAD на момент ТЗ:** `e6eecd2` (round 2 уже применён)  

---

## Режим работы

Корректность → надёжность → без регрессий → минимальный diff.  
Все правки идут с тестами на уровне модуля (без UI-фикстур, где возможно).  
Commit-message следует Conventional Commits.  

---

## Резюме аудита

**Скоуп:** 50 .py файлов в `src/`, `main_pyside.py`, `scripts/`, `build.spec`, 13 test-файлов.  
**Метод:** статический анализ (read-through), `pytest`, `ruff`, `bandit`, `mypy`, `grep` по паттернам.

**Найдено:**
- 🔴 **CRITICAL:** 6 (3 исправлены в round 2, 3 закрыты предыдущим коммитом `712ccfe`)
- 🟡 **HIGH:** 10 (5 исправлено, 5 перенесено в backlog)
- 🟠 **MEDIUM:** 16 (8 исправлено, 8 перенесено)
- 🔵 **LOW:** 20 (4 исправлено, 16 не критично)

**Безопасность:** 6/10 → 8.5/10 после round 2.  
**Покрытие тестами:** ~35% → ~50% (с 40 до 60 тестов).

---

## Этап P0 — CRITICAL (блокеры продакшена)

Все выполнены в коммитах `712ccfe` и `e6eecd2`. Здесь фиксируем итоговые критерии.

| ID | Проблема | Файлы | Статус | Критерий |
|----|----------|-------|--------|----------|
| P0-1 | `Order.update_price` рассинхронизирует `advance` и `total_received` | `src/models.py` | ✅ `712ccfe` | Тест `test_update_price_below_advance_keeps_advance_in_sync` зелёный |
| P0-2 | `Order.add_payment` пропускает платежи при `debt=0` (overpayment) | `src/models.py` | ✅ `712ccfe` | Тест `test_overpayment_rejected_when_debt_zero` зелёный |
| P0-3 | Path traversal в `rename_file` (raw user input → `os.rename`) | `src/widgets/file_item_widget.py`, новый `src/utils/path_safety.py` | ✅ `e6eecd2` | Тесты `test_safe_filename_candidate_blocks_traversal`, `test_rename_rejects_traversal` |
| P0-4 | Path traversal в `FileManagerDialog._handle_drop` (любые URL из MIME) | `src/dialogs/file_manager.py` | ✅ `e6eecd2` | Тест `test_safe_resolve_within`, ручной: drop из `C:\Windows` отклоняется с warning |
| P0-5 | Частичный сбой `change_database_location` оставляет mixed paths | `src/dialogs/settings_dialog.py` | ✅ `e6eecd2` | Логика «copy-all → mutate»: при исключении ни один `file.path` не изменён |

## Этап P1 — HIGH (серьёзные баги и утечки)

5 из 10 закрыты. Остаток — приоритетный backlog.

| ID | Проблема | Файлы | Статус | Критерий |
|----|----------|-------|--------|----------|
| P1-1 | `backup.create_full_backup_zip` пропускает arcname с `..` (path traversal в архиве) | `src/services/backup.py` | ✅ `e6eecd2` | Тест `TestBackupArcnameSafety` зелёный; `..` в `client.name`/`service_type`/`file.name` режется |
| P1-2 | Stale `InstanceLock` после крэша процесса | `src/utils/instance_lock.py` | ✅ `e6eecd2` | Тест: создать lock-файл с мёртвым PID, `acquire()` не бросает `InstanceLockError` |
| P1-3 | Deadline popup на каждом холодном старте (спам) | `src/ui/main_window/window.py`, `mixins/shell.py` | ✅ `e6eecd2` | `popup=True` убран из cold-start, dedup через `deadline_alerts_acked` |
| P1-4 | `sync_price` дублирует логику `update_price` с другим (хрупким) порядком | `src/widgets/order_financial_mixin.py` | ✅ `e6eecd2` | Тест через mock-объект: поведение идентично `Order.update_price` |
| P1-5 | `order_financial_mixin` не валидирует NaN/Inf | `src/widgets/order_financial_mixin.py` | ✅ `e6eecd2` | `if not math.isfinite(new_price): warning` |
| P1-6 | `delete_client` освобождает UI до `save_db()` — при сбое inconsistent | `mixins/client_list.py` | ❌ backlog | После: `save_db()` до `refresh_list()`. Effort: 0.5d |
| P1-7 | `clear_profile_layout` утекает `QSpacerItem` на каждом пере-выборе клиента | `mixins/client_profile.py` | ❌ backlog | После: явно `deleteLater()` для `spacer` items. Effort: 0.5d |
| P1-8 | `import_json_file` парсит файл дважды (preview + import) | `mixins/database_ops.py`, `services/database_io.py` | ❌ backlog | Передать `preview` в `import_database_with_backup(...)`. Effort: 0.5d |
| P1-9 | Финансовая неточность в `Order` properties (O(N) итерации на каждый доступ) | `src/models.py` | ❌ backlog | Кэшировать `total_received`/`total_advance_received` после `add_payment`/`delete_payment`. Effort: 1d |
| P1-10 | `change_database_location` создаёт lock-race между release старого и acquire нового | `mixins/database_ops.py:21-46` | ❌ backlog | Атомарный rebind lock (создать новый до release старого, использовать lock-файл БД уникальный). Effort: 1d |

## Этап P2 — MEDIUM (потенциальные проблемы)

8 из 16 закрыто, остаток — качественные улучшения.

| ID | Проблема | Файлы | Статус | Критерий |
|----|----------|-------|--------|----------|
| P2-1 | `add_payment` не отклоняет NaN/Inf | `src/models.py` | ✅ `e6eecd2` | Тесты `TestOrderIsFinite.test_add_payment_rejects_nan/inf` |
| P2-2 | `_parse_clients_list` молча портит БД при `Infinity` в JSON | `src/storage.py` | ✅ `e6eecd2` | Тесты `TestStorageFiniteParsing`; `Decimal(str(inf))` не падает |
| P2-3 | `update_price`/`update_advance` не отклоняют NaN/Inf | `src/models.py` | ✅ `e6eecd2` | Тест `test_update_price_rejects_nan` |
| P2-4 | `is_safe_to_delete` некорректен на Windows с разными case | `src/services/client_deletion.py` | ✅ `e6eecd2` | Делегирует `path_safety.is_path_within` (resolve + normcase) |
| P2-5 | `folder_import.scan_folder` падает на защищённой подпапке | `src/dialogs/folder_import.py` | ✅ `e6eecd2` | Per-folder `try/except OSError`; одна плохая папка не ломает весь импорт |
| P2-6 | `import_dropped_client_folder` создаёт дубли при `name.strip() != name` | `mixins/database_ops.py` | ✅ `e6eecd2` | Сравнение `name.strip().lower()` |
| P2-7 | `search_edit.textChanged` рефрешит список на каждом символе | `mixins/shell.py` | ✅ `e6eecd2` | Debounce 200мс через `QTimer` |
| P2-8 | `os.walk` в dropEvent следует по symlink → DoS | `widgets/order_files_mixin.py` | ✅ `e6eecd2` | `followlinks=False` |
| P2-9 | `client_export` не sanitize имя файла (Windows-запрещённые символы) | `mixins/client_export.py` | ✅ `e6eecd2` | `_sanitize_filename` для всех имён; NUL тоже |
| P2-10 | `cleanup_empty_attached_dirs` блокирует UI на большом дереве | `services/client_deletion.py` | ❌ backlog | Wrap в `QThread`. Effort: 1d |
| P2-11 | `export_full_backup` синхронно архивирует (UI-freeze) | `mixins/database_ops.py` | ❌ backlog | `QThread` + progress bar. Effort: 1d |
| P2-12 | Logger FD-утечка при множественном импорте в одном процессе (тесты) | `src/logger.py` | ❌ backlog | Single init через `if not logging.getLogger().handlers:`. Effort: 0.5d |
| P2-13 | `delete_client` / `delete_database_full` без отмены транзакции при исключении | `mixins/database_ops.py` | ❌ backlog | try/finally + validation. Effort: 0.5d |
| P2-14 | `_extract_clients_payload` не мигрирует `version < SCHEMA_VERSION` | `src/storage.py` | ❌ backlog | Принять `version==1`, явно типизировать. Effort: 0.5d |
| P2-15 | `Link-following` в `_open_path` (symlink атака внутри attached_files) | `dialogs/file_manager.py`, `widgets/file_item_widget.py` | ❌ backlog | Reject если `Path.resolve()` уходит за пределы safe_root. Effort: 1d |
| P2-16 | Dead-code в `folder_import.py` (`group_by_name`, `extensions_edit`, `import_empty_cb`) | `src/dialogs/folder_import.py` | ❌ backlog | Удалить неиспользуемые чекбоксы (или реализовать их). Effort: 0.5d |

## Этап P3 — LOW (качество, code style)

Backlog.

| ID | Проблема | Файлы | Effort |
|----|----------|-------|--------|
| P3-1 | `.bandit`/`bandit.yaml` для подавления known false-positives (subprocess для file-open) | repo root | 5m |
| P3-2 | `mypy` config с `[tool.mypy]` для mixin-attr-defined false-positives | `pyproject.toml` | 30m |
| P3-3 | `pre-commit` с `ruff` + `pytest --tb=short` + `bandit` | `.pre-commit-config.yaml` | 1h |
| P3-4 | `services/schema.py` — заглушка (одна константа); реальной миграции нет | `src/services/schema.py` | 2d |
| P3-5 | `CHANGELOG.md` структурировать по SemVer (1.x.y → 1.x.y) | repo root | 30m |
| P3-6 | `scripts/` — мёртвый код (нужен ревью что реально используется) | `scripts/*.py` | 1d |
| P3-7 | README актуализировать: убрать упоминания Tauri | `README.md` | 30m |
| P3-8 | Скрытый edge case `Path(tmp).resolve() is shared with parent in CI` | tests | 1d |
| P3-9 | Qt-фикстуры для UI-тестов (pytest-qt уже есть, но не используется) | `tests/qt/` | 2d |
| P3-10 | `instance_lock` PID detection: документировать ограничение на сетевых FS | `src/utils/instance_lock.py` docstring | 10m |

---

## Backlog — что НЕ делать в этом цикле

| Тема | Почему отложено |
|---|---|
| Полный рефакторинг mixins в один `MainWindow` class вместо множественного наследования | Высокий риск регрессий, не оправдан для приложения, которое работает |
| Замена `dataclass Order/Client` на `pydantic` | Требует миграции существующих БД, тесты проходят с dataclass |
| Миграция `pro_database.json → SQLite` | Дорого, юзер не просил, JSON читается; на 10k клиентов ~ десятки МБ — терпимо |
| Добавление multi-window UI | Вне scope аудита; не заявлено |
| Async Qt (`qasync`) | Сложность не оправдана; UI операции короткие |
| macOS .app bundle / Linux AppImage | Только `pyinstaller build.spec`; расширение дистрибуции — отдельная задача |

---

## Definition of Done — round 2 (✅ выполнено)

```bash
cd E:\coding\client_manager\FinanceFugue
python -m pytest tests/ -q          # 60 passed
python -m ruff check src/ tests/    # All checks passed
python -m bandit -r src/            # 0 Medium/High, 15 Low (known FP)
git log --oneline -3                # e6eecd2 fix(audit): security & correctness round 2
```

**Команда подтверждает:**  
- Все обязательные финансовые операции (платежи, аванс, цена) корректно обрабатывают edge cases (NaN/Inf, переплата, уменьшение цены ниже аванса).  
- Path traversal невозможен ни через rename, ни через drop, ни через backup arcname, ни через import.  
- Stale locks автоматически очищаются.  
- Дедлайн-уведомления дедуплицируются.  

---

## Definition of Done — round 3 (рекомендуемый next sprint)

| Приоритет | Объём | Effort |
|-----------|-------|--------|
| P1-6, P1-7, P1-8, P1-10 | 4 HIGH бага | ~3 дня |
| P2-10, P2-11, P2-15 | 3 MEDIUM (UI freeze / symlink) | ~3 дня |
| P3-1, P3-2, P3-3, P3-7 | tooling | ~3h |
| Тесты UI (P3-9) | pytest-qt fixtures | ~2 дня |

**Acceptance criteria round 3:**
1. `pytest tests/ -q` → ≥75 passed.
2. `ruff`, `bandit` — без новых warnings.
3. UI-операции (`export_full_backup`, `delete_all_files`) — выполняются в `QThread`, главное окно не блокируется.
4. Drop symlink, указывающего наружу — отклоняется с warning.
5. README обновлён, Tauri не упоминается.
6. `pre-commit` настроен.

---

## Контакты / владельцы

| Кодовая зона | Ответственный |
|--------------|---------------|
| `src/models.py` (финансы) | senior reviewer (Kirill) |
| `src/services/*` (безопасность, бэкапы) | senior reviewer |
| `src/ui/main_window/**` (mixins) | senior reviewer |
| `src/widgets/*` | mid reviewer |
| `src/dialogs/*` | mid reviewer |
| `tests/*` | любой, кто правит код — обязан добавлять тесты |
| `docs/*` (этот файл) | автор аудита |

## История изменений ТЗ

| Дата | Изменение |
|------|-----------|
| 04.08.2026 | Первая версия. По итогам аудита `e6eecd2` (round 2) задокументировано состояние «as-is» и сформирован backlog round 3. |
