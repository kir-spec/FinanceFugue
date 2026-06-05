# FinanceFugue



CRM для управления клиентами и заказами.



**Версия:** 05.06.2026 18:28



## Запуск



```bash

pip install -r requirements.txt

python main_pyside.py

```



## Тесты



```bash

python -m unittest discover -s tests -p "test_*.py" -v

pytest tests/qt -v

```



## Сборка EXE (Windows)



```bash

pip install Pillow

python scripts/create_icon.py

pip install -r requirements-build.txt

pyinstaller build.spec

```



Результат: `dist/FinanceFugue.exe`



## Безопасность и правовая информация



- Данные в `pro_database.json` хранятся локально в открытом виде (без шифрования в программе).

- Рекомендуется BitLocker и регулярные бэкапы (Настройки → Полный бэкап ZIP).

- Документы: `EULA.md`, `PRIVACY.md`, `LICENSE`, `THIRD_PARTY_LICENSES.txt`.

- В приложении: Настройки → «О программе и лицензии».



## Отладка



```bash

set FINANCEFUGUE_DEBUG=1

python main_pyside.py

```



## Структура



```

src/

  models.py              — бизнес-модели

  storage.py             — JSON-хранилище

  theme.py               — единый источник QSS-стилей

  services/              — настройки, статистика, валюта, удаление, импорт, бэкапы

  ui/

    main_window/         — главное окно (mixins)

    dashboard.py         — панель статистики

  widgets/               — OrderWidget, FileItemWidget (+ mixins)

  dialogs/               — диалоги

  utils/                 — пути, блокировка экземпляра

```



См. также `CHANGELOG.md`, `docs/PRODUCTION_REMEDIATION_PLAN.md`.



## Данные



| Файл | Назначение |

|------|------------|

| `pro_database.json` | База клиентов |

| `crm_settings.json` | Настройки приложения |

| `settings_backups/` | Резервные копии настроек |

| `logs/` | Логи работы |


