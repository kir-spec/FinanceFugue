# Changelog

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
