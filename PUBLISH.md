# Публикация: client_manager

> **Для ИИ-агента:** при любом запросе «залить / опубликовать / push на GitHub или Cursor»
> **сначала прочитай этот файл целиком** и `E:\coding\CURSOR_ORIGIN.md`.
> Не выполняй `git push`, пока не проверена авторизация.

## Этот репозиторий

| | |
|---|---|
| Папка | `E:\coding\client_manager` |
| GitHub | remote `origin` — см. `git remote -v` |
| Cursor Origin | `amalan/FinanceFugue` |
| Remote Cursor | `cursor` → `https://origin.cursor.com/amalan/FinanceFugue.git` |
| Ветка по умолчанию | `main` |

## 1. Проверка авторизации Cursor (обязательно на Windows)

```powershell
wsl -d Ubuntu -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; origin auth status'
```

- `Token: valid` — можно пушить.
- `expired` / не авторизован → веб-вход:

```powershell
wsl -d Ubuntu -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; origin auth login'
```

Если браузер не открылся — скопируй URL из вывода и открой вручную. Дождись `Logged in successfully`.

**AmneziaVPN:** если WSL без сети → от администратора:
`& "$env:USERPROFILE\fix-wsl-amnezia.ps1"`

## 2. Push на GitHub

```powershell
git push -u origin main
```

Проверка: `gh auth status`

## 3. Push на Cursor Origin (только через WSL на Windows)

```powershell
wsl -d Ubuntu -e bash -lc 'cd /mnt/e/coding/client_manager && git push -u cursor main'
```

Первичная настройка remote (один раз):

```bash
git remote add cursor https://origin.cursor.com/amalan/FinanceFugue.git
```

## 4. Тег / релиз

```powershell
git tag -a vДАТА -m "описание"
git push origin vДАТА
wsl -d Ubuntu -e bash -lc 'cd /mnt/e/coding/client_manager && git push cursor vДАТА'
gh release create vДАТА --title "..." --notes "..."
```

Полная таблица всех проектов: `E:\coding\CURSOR_ORIGIN.md`
