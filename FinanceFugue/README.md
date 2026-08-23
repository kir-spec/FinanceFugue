<div align="center">

# 💎 FinanceFugue

[![Version](https://img.shields.io/badge/version-23.08.2026-00D1FF.svg?style=for-the-badge)](https://github.com/kir-spec/FinanceFugue)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41CD52.svg?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Free-8E44AD.svg?style=for-the-badge)](EULA.md)
[![Telegram Sync](https://img.shields.io/badge/2--Way%20Sync-Telegram%20Bot-229ED9.svg?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me)

---

### 🌐 Key Mission / Главная цель / Головна мета

> 🇬🇧 **Full control over finances, client management, and orders.**  
> 🇷🇺 **Полный контроль над финансами, учётом клиентов и заказов.**  
> 🇺🇦 **Повний контроль над фінансами, обліком клієнтів та замовлень.**

---

</div>

<br>

<!-- ================================================================= -->
<!-- 1. ENGLISH SECTION -->
<!-- ================================================================= -->
<details open>
<summary><h2>🇬🇧 English — Overview, Features & Documentation</h2></summary>
<br>

### 🚀 What is FinanceFugue?
**FinanceFugue** is a high-performance, local-first CRM and financial accounting ecosystem designed specifically for freelancers, sound engineers, creative studios, designers, and independent contractors. 

It bridges the gap between a robust **Desktop Application (PC)** and a smart **Mobile Telegram Bot**, ensuring seamless 2-way real-time data synchronization with absolute local data privacy.

---

### ✨ Key Capabilities & Highlights

* **🔒 Local-First Absolute Privacy:** Your data belongs entirely to you. All records and project files are stored locally on your machine in `pro_database.json` without vendor lock-in or hidden third-party tracking.
* **🧮 Mathematical Financial Rigor:**
  * Strict linking of `Price ➔ Advance (Prepayment) ➔ Remaining Debt`.
  * **Overpayment Protection:** Prevents entering transactions exceeding the remaining balance.
  * **Automated Refund Adjustments:** Modifying an order price after payments automatically creates compensating balancing entries, ensuring 100% financial integrity.
  * Native multi-currency support (`RUB`, `USD`, `EUR`, `USDT`, etc.) with zero floating-point rounding errors (`math.isfinite` validation).
* **📁 Smart Portable File Manager:**
  * Attach project briefs, stems, masters, and contracts directly to orders via Drag & Drop.
  * **Portable Copy Mode:** Bundles files inside the database folder so you can move the app to a USB drive or cloud folder (Dropbox, Google Drive).
  * **Auto-Healing Paths:** Automatically relocates and reconnects moved project assets.
  * **1-Click ZIP Archive Export:** Compresses all project deliverables with an auto-generated `PROJECT_MANIFEST.txt`.
* **🔄 Seamless 2-Way Telegram Bot Synchronization:**
  * Synchronize all clients, orders, payments, and files between PC and Telegram in real-time.
  * Background auto-sync upon saving changes on PC.
  * Manual Push and Pull with instant UI refresh.
* **🧊 Cold Storage Archive:**
  * Archive completed orders into a high-speed read-only hierarchical tree (`Year ➔ Month`) to keep the primary workspace lightning fast even after 10+ years of active use.
* **📊 Analytics Dashboard & PDF Invoices:**
  * Real-time cashflow metrics, debt tracking, period filters (Current Year, Previous Year, Custom Months).
  * Generate printable official PDF invoices with custom banking requisites.

---

### ⚡️ Quick Start & Installation

#### Running from Source:
```bash
# 1. Clone repository
git clone https://github.com/kir-spec/FinanceFugue.git
cd FinanceFugue

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch application
python main_pyside.py
```

#### Building Standalone Windows EXE:
```bash
pip install -r requirements-build.txt
pyinstaller build.spec
# Executable will be generated at dist/FinanceFugue.exe
```

---

### ⌨️ Useful Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + N` | Create a new client |
| `Ctrl + S` | Force save database & trigger background auto-sync |
| `Ctrl + F` | Focus search bar |
| `Ctrl + O` | Open Global File Manager |
| `Ctrl + Shift + S` | Open Preferences & Settings |
| `F5` | Refresh view and recalculate analytics |
| `Delete` | Move selected client/order to Trash |

</details>

<br>

<!-- ================================================================= -->
<!-- 2. RUSSIAN SECTION -->
<!-- ================================================================= -->
<details>
<summary><h2>🇷🇺 Русский — Описание, возможности и документация</h2></summary>
<br>

### 🚀 Что такое FinanceFugue?
**FinanceFugue** — это профессиональная настольная CRM-система и экосистема финансового учета, созданная для фрилансеров, звукорежиссеров, студий звукозаписи, дизайнеров, разработчиков и агентств.

Система объединяет мощную **десктопную программу на ПК** и умного **мобильного Telegram-бота**, обеспечивая полную двустороннюю синхронизацию в реальном времени при сохранении 100% приватности локальных данных.

---

### ✨ Ключевые возможности программы

* **🔒 Локальная приватность (Local-First):** База данных принадлежит только вам. Все записи хранятся локально в файле `pro_database.json`. Никаких скрытых облачных серверов третьих лиц.
* **🧮 Строгая финансовая математика:**
  * Автоматический расчет баланса: `Стоимость ➔ Аванс (Предоплата) ➔ Остаток долга`.
  * **Защита от переплат:** Программа блокирует внесение сумм, превышающих текущий долг по сделке.
  * **Автоматические возвраты:** Если стоимость заказа уменьшена после оплаты, программа автоматически создает корректировочный платеж возврата, сохраняя кассу безупречной.
  * Поддержка любых валют (`RUB`, `USD`, `EUR`, `USDT` и др.) с проверкой чисел на валидность (`math.isfinite`).
* **📁 Умный файловый менеджер (Portable Mode):**
  * Прикрепление любых рабочих файлов (брифы, дорожки, архивы исходников, договоры) через Drag & Drop.
  * **Режим копирования в базу:** Позволяет переносить папку программы на флешку или в облачный диск (Яндекс.Диск, Google Drive) без потери файлов.
  * **Авто-лечение путей (Auto-heal):** Программа автоматически находит и восстанавливает перемещенные файлы.
  * **Экспорт проекта в ZIP за 1 клик:** Асинхронная упаковка файлов проекта в единый архив с манифестом `PROJECT_MANIFEST.txt`.
* **🔄 Двусторонняя синхронизация с Telegram-ботом:**
  * Управление проектами и клиентами как с ПК, так и со смартфона через Telegram.
  * Фоновая автосинхронизация при сохранении на компьютере.
  * Ручной Push (отправка в бота) и Pull (загрузка в программу) с моментальным обновлением интерфейса.
* **🧊 «Холодное хранилище» (Архив):**
  * Отправка выполненных заказов в иерархический архив (`Год ➔ Месяц`) для сохранения максимальной скорости работы интерфейса на протяжении многих лет.
* **📊 Аналитический дашборд и печать PDF-инвойсов:**
  * Сводная касса, учет авансов и долгов, фильтрация по периодам (текущий год, прошлый год, месяцы).
  * Генерация официальных счетов и актов в PDF с реквизитами исполнителя.

---

### ⚡️ Быстрый запуск и установка

#### Запуск из исходного кода:
```bash
# 1. Клонирование репозитория
git clone https://github.com/kir-spec/FinanceFugue.git
cd FinanceFugue

# 2. Установка зависимостей
pip install -r requirements.txt

# 3. Запуск приложения
python main_pyside.py
```

#### Сборка автономного EXE для Windows:
```bash
pip install -r requirements-build.txt
pyinstaller build.spec
# Готовый файл появится в dist/FinanceFugue.exe
```

---

### ⌨️ Горячие клавиши

| Сочетание | Действие |
| :--- | :--- |
| `Ctrl + N` | Создать нового клиента |
| `Ctrl + S` | Сохранить базу и запустить автосинхронизацию |
| `Ctrl + F` | Фокус на строку поиска клиентов |
| `Ctrl + O` | Открыть глобальный файловый менеджер |
| `Ctrl + Shift + S` | Открыть окно настроек программы |
| `F5` | Обновить списки и пересчитать дашборд |
| `Delete` | Удалить выбранного клиента или заказ (в корзину) |

</details>

<br>

<!-- ================================================================= -->
<!-- 3. UKRAINIAN SECTION -->
<!-- ================================================================= -->
<details>
<summary><h2>🇺🇦 Українська — Опис, можливості та документація</h2></summary>
<br>

### 🚀 Що таке FinanceFugue?
**FinanceFugue** — це професійна настільна CRM-система та екосистема фінансового обліку, створена спеціально для фрілансерів, звукорежисерів, музичних студій, дизайнерів, розробників та креативних команд.

Система об'єднує надійну **десктопну програму на ПК** та розумного **мобільного Telegram-бота**, забезпечуючи повноцінну двосторонню синхронізацію в реальному часі зі 100% збереженням приватності локальних даних.

---

### ✨ Ключові можливості програми

* **🔒 Локальна приватність (Local-First):** База даних належить виключно вам. Всі записи зберігаються локально у файлі `pro_database.json` без прив'язки до сторонніх хмарних серверів.
* **🧮 Точна фінансова математика:**
  * Автоматичний розрахунок балансу: `Вартість ➔ Аванс (Передплата) ➔ Залишок боргу`.
  * **Захист від переплат:** Програма блокує внесення сум, які перевищують поточний борг клієнта за замовленням.
  * **Автоматичні повернення:** Зниження вартості замовлення після отримання оплати автоматично формує коригувальний платіж повернення.
  * Підтримка будь-яких валют (`UAH`, `USD`, `EUR`, `USDT`, `PLN` тощо) з валідацією чисел (`math.isfinite`).
* **📁 Розумний менеджер файлів (Portable Mode):**
  * Прикріплення будь-яких робочих файлів (брифи, доріжки, вихідні матеріали, договори) за допомогою Drag & Drop.
  * **Режим копіювання до бази:** Дозволяє переносити теку програми на флешку або у хмарне сховище (Google Drive, Dropbox) без втрати прив'язки файлів.
  * **Авто-відновлення шляхів (Auto-heal):** Автоматичний пошук переміщених файлів у структурі проєкту.
  * **Експорт проєкту в ZIP за 1 клік:** Асинхронне пакування матеріалів у єдиний архів із маніфестом `PROJECT_MANIFEST.txt`.
* **🔄 Двостороння синхронізація з Telegram-ботом:**
  * Управління проєктами та клієнтами як з комп'ютера, так і зі смартфона через Telegram.
  * Фоновий автосинхрон під час збереження бази на ПК.
  * Ручний Push (відправка до бота) та Pull (завантаження з бота) з миттєвим оновленням інтерфейсу.
* **🧊 «Холодне сховище» (Архів):**
  * Переміщення завершених замовлень до ієрархічного архіву (`Рік ➔ Місяць`) для блискавичної роботи інтерфейсу навіть через роки використання.
* **📊 Аналітичний дашборд та друк PDF-рахунків:**
  * Зведена каса, облік авансів та боргів, фільтри за періодами (поточний рік, минулий рік, місяці).
  * Генерація офіційних рахунків та актів у форматі PDF із реквізитами виконавця.

---

### ⚡️ Швидкий запуск та встановлення

#### Запуск із вихідного коду:
```bash
# 1. Клонування репозиторію
git clone https://github.com/kir-spec/FinanceFugue.git
cd FinanceFugue

# 2. Встановлення залежностей
pip install -r requirements.txt

# 3. Запуск програми
python main_pyside.py
```

#### Збірка автономного EXE для Windows:
```bash
pip install -r requirements-build.txt
pyinstaller build.spec
# Готовий файл буде у dist/FinanceFugue.exe
```

---

### ⌨️ Гарячі клавіші

| Сполучення | Дія |
| :--- | :--- |
| `Ctrl + N` | Створити нового клієнта |
| `Ctrl + S` | Зберегти базу та запустити автосинхронізацію |
| `Ctrl + F` | Фокус на поле пошуку клієнтів |
| `Ctrl + O` | Відкрити глобальний менеджер файлів |
| `Ctrl + Shift + S` | Відкрити налаштування програми |
| `F5` | Оновити списки та перерахувати статистику |
| `Delete` | Видалити вибраного клієнта або замовлення (у кошик) |

</details>

<br>

---

<div align="center">

### 🛡 Security & Legal Information / Юридическая информация

Developed by **KVF SOFT** • Author: **Kirill V. Fandeev**  
© 2026 Kirill Fandeev. All rights reserved.

[EULA.md](EULA.md) • [PRIVACY.md](PRIVACY.md) • [DOCUMENTATION.md](DOCUMENTATION.md)

</div>
