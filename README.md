# FinanceFugue

Desktop CRM для управления клиентами и заказами.

## Актуальная версия

**FinanceFugue** — папка `FinanceFugue/` (версия 05.06.2026)

```bash
cd FinanceFugue
pip install -r requirements.txt
python main_pyside.py
```

## История версий

Старые версии (01–24) хранятся на GitHub в ветках `v01` … `v24` и в ветке `main`.

## Тесты

```bash
cd FinanceFugue
python -m unittest discover -s tests -v
```

## Сборка

```bash
cd FinanceFugue
pip install -r requirements-build.txt
pyinstaller build.spec
```
