# Client Manager

История версий desktop-приложения **Client Manager** (CRM для клиентов).

## Структура репозитория

| Ветка | Содержимое |
|-------|------------|
| `main` | Все версии в папках `client manager 01` … `client manager 24` |
| `v01` … `v24` | Каждая ветка — снимок одной версии в корне репозитория (готово к запуску) |

**Актуальная версия:** `v24` / папка `client manager 24`

## Вехи

| Версии | Описание |
|--------|----------|
| 01–04 | Ранние прототипы (`main.py`) |
| 05–08 | Модульная структура, tkinter |
| 09–22 | PySide6 |
| 23–24 | SQLite, шифрование |

## Запуск

```bash
git checkout v24
pip install PySide6
python main_pyside.py
```

Или из архива на `main`:

```bash
cd "client manager 24"
pip install PySide6
python main_pyside.py
```
