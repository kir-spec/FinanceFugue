# FinanceFugue

CRM для управления клиентами и заказами.

**Версия:** 04.08.2026 (security audit round 3)

## Что это

Десктопное PySide6-приложение для управления клиентской базой: заказы,
платежи (включая мультивалютные), прикреплённые файлы с возможностью
копирования или хранения по ссылке, отслеживание дедлайнов, заметки,
бэкапы.

## Запуск

```bash
pip install -r requirements.txt
python main_pyside.py
```

## Тесты

```bash
# Unit-тесты (все, без UI-фикстур)
python -m pytest tests/ -q

# Конкретные подмножества
python -m pytest tests/ -q -k "model"           # только модели
python -m pytest tests/qt/ -q                   # только Qt-smoke

# Линтеры
ruff check src/ tests/
bandit -c pyproject.toml -r src/
mypy src/
```

На текущий момент: **60 passed**, ruff clean, bandit 0 (1 fixed FP).

## Сборка EXE (Windows)

```bash
pip install -r requirements-build.txt
pyinstaller build.spec
```

Результат: `dist/FinanceFugue.exe`.

## Безопасность и правовая информация

- Данные в `pro_database.json` хранятся локально в открытом виде
  (без шифрования в программе).
- Рекомендуется BitLocker и регулярные бэкапы
  (Настройки → Полный бэкап ZIP).
- Защита от path traversal в пользовательском вводе:
  `src/utils/path_safety.py` (`safe_filename_candidate`,
  `is_path_within`, `safe_resolve_within`).
- Symlink-атака на `_open_path` блокируется.
- Платёжные данные валидируются через `math.isfinite()` —
  NaN/Inf в финансах теперь невозможен.
- Документы: `EULA.md`, `PRIVACY.md`, `LICENSE`, `THIRD_PARTY_LICENSES.txt`.

## Отладка

```bash
set FINANCEFUGUE_DEBUG=1
python main_pyside.py
```

Подробный security-аудит и план устранения — в
[`docs/SECURITY_AUDIT_TZ.md`](docs/SECURITY_AUDIT_TZ.md).

## Структура

```
src/
  models.py              — бизнес-модели (Client, Order, Payment, ProjectFile)
  storage.py             — JSON-хранилище (atomic write, finite-float parsing)
  theme.py               — единый источник QSS-стилей
  services/              — settings, stats, currency, deletion, import, backup
                          |  └─ backup.py — есть BackupWorker (QThreadPool)
  ui/
    main_window/         — главное окно (mixins)
      mixins/shell.py    — debounce search (200мс)
      mixins/database_ops.py — async backup через QThreadPool
    dashboard.py         — панель статистики
  widgets/               — OrderWidget, FileItemWidget (+ mixins)
  dialogs/               — диалоги
  utils/
    path_safety.py       — валидация файловых путей (★ единая точка)
    instance_lock.py     — блокировка экземпляра + stale-PID detection
    paths.py             — user-data пути через QStandardPaths
tests/
  test_bugfixes.py       — регресс-тесты round 1
  test_audit_fixes.py    — регресс-тесты round 2/3 (path safety, NaN/Inf)
  test_models.py         — Order/Payment логика
  test_storage.py        — roundtrip, atomic replace, legacy, corrupt
  test_settings.py       — settings roundtrip
  test_backup.py         — sanitize, full zip
  test_client_deletion.py — safe_to_delete, disk removal
  test_client_stats.py   — multi-currency display
  test_currency.py       — formatting, no mixing
  test_deadline_notifier.py — alerts formatting
  test_folder_import_service.py — folder scan/apply
  test_app_bridge.py     — bridge signal contract
  test_storage_rebind.py — lock rebind
```

## Данные

| Файл | Назначение |
|------|------------|
| `pro_database.json` | База клиентов |
| `crm_settings.json` | Настройки приложения |
| `settings_backups/` | Резервные копии настроек |
| `logs/` | Логи работы |

## Tauri-версия

Удалена в коммите `712ccfe`. Разработка ведётся только на PySide6.
Бывший Tauri-порт содержал 18 известных багов (см. историю) и был
сложнее в поддержке (Rust + TypeScript mixin), при этом не давал
преимуществ для desktop-CRM.
