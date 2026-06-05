# Production Remediation Plan — FinanceFugue

Промпт для поэтапного исправления всех заявленных недостатков (аудит 05.06.2026).

## Режим работы

SENIOR PRODUCTION ENGINEER: корректность → надёжность → без регрессий → минимальный diff.

## Этап P0 — Критические баги (блокеры продакшена)

| ID | Проблема | Файлы | Критерий готовности |
|----|----------|-------|---------------------|
| P0-1 | InstanceLock не переезжает при смене `database_path` | `database_ops.py`, `startup.py`, `settings_dialog.py` | После смены пути lock на `new_db.lock`, второй экземпляр блокируется |
| P0-2 | Дедлайн в «Новый заказ» — свободный текст | `orders.py` | Только `QDateEdit`, невалидная дата невозможна |
| P0-3 | `storage.load()` после first run без обработки ошибок | `startup.py` | `DatabaseLoadError` → диалог + `sys.exit(1)` |
| P0-4 | Copy-mode при ошибке копирования падает в link | `order_widget.py` | При `copy` + ошибка файл не добавляется |

## Этап P1 — Мультивалютность

| ID | Проблема | Файлы | Критерий готовности |
|----|----------|-------|---------------------|
| P1-1 | Суммирование разных валют в дашборде | `client_stats.py`, `dashboard.py` | Суммы группируются по `currency`, UI показывает `1 000 ₽ + 50 $` |
| P1-2 | Жёсткий `₽` в платежах и order_widget | `payments.py`, `order_widget.py` | Символ из `order.currency` |

## Этап P2 — Структура и дубли

| ID | Проблема | Файлы | Критерий готовности |
|----|----------|-------|---------------------|
| P2-1 | Дублирование удаления клиента | `client_deletion.py`, `client_list.py` | Общий сервис для disk cleanup |
| P2-2 | `order_widget.py` ~940 строк | `order_financial_mixin.py`, `order_files_mixin.py` | Финансы и файлы вынесены, поведение идентично |

## Этап P3 — Документация и мёртвый код

| ID | Действие |
|----|----------|
| P3-1 | Удалить `scripts/trim_order_widget.py`, `docs/PROMPT_WIDGET_REFACTOR.md` |
| P3-2 | Исправить `pyproject.toml` (убрать `src/widgets.py`) |
| P3-3 | Реализовать `on_storage_changed` в `first_run.py` |
| P3-4 | Обновить `README.md`, `CHANGELOG.md` |

## Этап P4 — Тесты и CI

| ID | Тест | Файл |
|----|------|------|
| P4-1 | Валюта, группировка | `tests/test_currency.py` |
| P4-2 | `rebind_storage` + lock path | `tests/test_storage_rebind.py` |
| P4-3 | Безопасное удаление файлов | `tests/test_client_deletion.py` |
| P4-4 | Обновить `test_client_stats.py` | мультивалютные кейсы |
| P4-5 | CI: unittest + pytest без регрессий | `.github/workflows/ci.yml` |

## Проверка после каждого этапа

```bash
cd FinanceFugue
ruff check src tests main_pyside.py scripts
python -m unittest discover -s tests -p "test_*.py" -v
pytest tests/qt -v
```

## Вне scope (осознанно)

- Шифрование БД
- Цифровая подпись EXE
- Debounce `save_db` (меняет UX, отдельная задача)
- Конвертация валют по курсу
