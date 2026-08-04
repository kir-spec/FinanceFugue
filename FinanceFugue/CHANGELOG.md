# Changelog

## 04.08.2026 — bugfix release

### Исправлено (критические)
- `Order.update_price` — устранён рассинхрон `advance` ↔ `total_received`
  при уменьшении цены ниже аванса. Сначала создаётся возврат (negative
  payment), затем обновляется `advance` и `price`. Раньше `add_payment`
  откатывал `advance` через `max(advance, total_advance_received)`.
- `Order.add_payment` — при переплате `debt == 0` и ранее любой
  положительный платёж проходил валидацию. Теперь блокируется.
- `services/currency.py` — `format_amount` использует `Decimal`+`ROUND_HALF_UP`
  (финансовое), а не банковское HALF_EVEN; добавлен `has_outstanding_debt()`.
- `services/client_stats.calculate_global_dashboard` — больше не сравниваем
  `sum(debt_by_currency.values())` с нулём (смешивало валюты).

### Исправлено (прочие)
- `widgets/file_item_widget.py` — `mouseReleaseEvent` больше не открывает
  файл при клике по кнопкам «Открыть»/«Удалить» (двойное открытие).
- `widgets/order_financial_mixin.format_number` — больше не теряет дробную
  часть (`0.5 → "0"` заменено на `0.5 → "0.5"`, `1.5 → "2"` → `"1.5"`).
- `widgets/order_financial_mixin.sync_price` — тот же баг-паттерн
  рассинхрона, что и в `update_price` — исправлено.
- `utils/instance_lock.py` — `release()` теперь закрывает файл через
  `try/finally`, устраняя утечку FD при исключении.
- `dialogs/folder_import.py` — `os.listdir(folder)` обёрнут в `try/except`,
  иначе краш на защищённой корневой папке.
- `dialogs/file_manager._resolve_drop_target` — drop файла на top-level
  теперь возвращает информативное сообщение вместо `AttributeError`.
- `services/backup.py` (через fix `logger.py`) — убран неиспользуемый
  `pathlib.Path` (ruff F401).

### Добавлено
- `tests/test_bugfixes.py` — 6 тестов на новые инварианты (46 passed в сумме).
- `services/currency.has_outstanding_debt()` — корректная проверка долгов.

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
