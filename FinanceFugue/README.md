<div align="center">

# 💎 FinanceFugue

### ⚡️ The Next-Generation Local-First CRM & Financial Accounting Ecosystem  
### ⚡️ Экосистема финансового учета и CRM нового поколения с синхронизацией в Telegram

[![Version](https://img.shields.io/badge/version-23.08.2026-00D1FF.svg?style=for-the-badge)](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41CD52.svg?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Free-8E44AD.svg?style=for-the-badge)](EULA.md)
[![Telegram Sync](https://img.shields.io/badge/2--Way%20Sync-Telegram%20Bot-229ED9.svg?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/FinanceFugue_bot)
[![Download EXE](https://img.shields.io/badge/Download-Windows%20EXE%20(v23.08.2026)-green.svg?style=for-the-badge&logo=windows)](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026)

---

### 🌐 Key Mission / Главная цель / Головна мета

> 🇬🇧 **Full control over finances, client management, and orders.**  
> 🇷🇺 **Полный контроль над финансами, учётом клиентов и заказов.**  
> 🇺🇦 **Повний контроль над фінансами, обліком клієнтів та замовлень.**

---

</div>

## 🌟 Уникальная суперсила: Бесшовная 2-сторонняя синхронизация с Telegram-ботом
## 🌟 Unique Killer Feature: Seamless 2-Way Real-time Sync with Telegram Bot

```
 ┌────────────────────────────────────────┐          2-Way Real-time Sync          ┌────────────────────────────────────────┐
 │          🖥 DESKTOP APP (PC)           │  ◄──────────────────────────────────►  │       📱 TELEGRAM BOT COMPANION        │
 │  • Local-first private database        │       (Chat ID & Secure Bot API)       │  • Voice & text NLP transactions       │
 │  • Drag & Drop project files & stems   │                                        │  • Mobile CRM in your pocket           │
 │  • Multi-currency cashflow dashboard   │                                        │  • Deadline push notifications         │
 │  • Official PDF invoices & receipts    │                                        │  • Multi-Account Shared DB Linking     │
 └────────────────────────────────────────┘                                        └────────────────────────────────────────┘
```

* 🚀 **Управление отовсюду:** Вносите платежи и заказы со смартфона в Telegram на ходу или работайте за большим монитором на ПК — все изменения синхронизируются мгновенно.
* 🔒 **100% Локальная приватность:** Никаких сторонних закрытых облаков. База данных принадлежит только вам.
* ☁️ **0 байт нагрузки на сервер (Telegram Cloud CDN):** Файлы проектов хранятся в защищенном облаке Telegram бесплатно и бессрочно.
* 👥 **Мультиаккаунтная общая база:** Возможность привязать несколько Telegram-аккаунтов (второй телефон, партнер, коллега) к единой базе данных.
* 🎯 **3 Режима работы:** «👤 Личные финансы» ⇄ «💼 CRM клиентов и заказов» ⇄ «✨ Полный гибридный режим».

---

<br>

<!-- ================================================================= -->
<!-- 1. ENGLISH SECTION -->
<!-- ================================================================= -->
<details open>
<summary><h2>🇬🇧 English — Complete Overview, Bot Synergy & Documentation</h2></summary>
<br>

### 🚀 What is FinanceFugue?
**FinanceFugue** is a modern, high-performance CRM and financial accounting ecosystem built for freelancers, sound engineers, music producers, creative studios, designers, and independent contractors.

It bridges the gap between a robust **Desktop Application (PC)** and a smart **Mobile Telegram Bot Companion**, allowing real-time 2-way database synchronization while maintaining absolute data privacy and zero vendor lock-in.

---

### 📱 How the Telegram Bot Synergy Works:
1. **Connect in 10 Seconds:** Open the bot in Telegram (`@FinanceFugue_bot`) and type `/sync`. Copy your personal **Telegram Chat ID**.
2. **Pair with PC:** In the desktop app, click **«📱 Bot / Sync»** on the sidebar, enter your Chat ID, and click **«⚡️ Test Connection»**.
3. **Automated Workflows:**
   * **Auto-Sync:** Every time you save changes on PC (`Ctrl+S`), the database automatically synchronizes with your bot in the background.
   * **Manual Push / Pull:** Send the PC database to the bot with 1 click, or load the latest changes made in Telegram back into your PC app.
   * **Multi-Account Linking:** Link multiple Telegram accounts to a single shared database via `/admin` pairing codes.

#### 📁 Smart File Architecture & Zero Server Disk Usage:
* **Telegram Cloud CDN:** Files and audio deliverables attached to orders via Telegram are stored directly in Telegram's distributed Cloud CDN via `tg_file_id`, consuming **0 bytes of VPS host server disk**.
* **Local PC Storage:** On your PC, files are stored locally with auto-healing path relocation and 1-click ZIP archive packaging (`PROJECT_MANIFEST.txt`).

---

### ✨ Core Features & Mathematical Precision

* **🔒 Local-First Absolute Privacy:** Your data belongs entirely to you. All records and project files are stored locally on your machine in `pro_database.json` without vendor lock-in.
* **🧮 Mathematical Financial Rigor:**
  * Strict linking of `Price ➔ Advance (Prepayment) ➔ Remaining Debt`.
  * **Overpayment Protection:** Prevents entering transactions exceeding the remaining balance.
  * **Automated Refund Adjustments:** Modifying an order price after payments automatically creates compensating balancing entries.
  * Native multi-currency support (`RUB`, `USD`, `EUR`, `USDT`, `UAH`, `KZT`, `BYN`, etc.) with zero floating-point rounding errors (`math.isfinite` validation).
* **🧊 Cold Storage Archive:**
  * Archive completed orders into a high-speed read-only hierarchical tree (`Year ➔ Month`) to keep the primary workspace lightning fast.
* **📊 Analytics Dashboard & PDF Invoices:**
  * Real-time cashflow metrics, debt tracking, period filters (Current Year, Previous Year, Custom Months).
  * Generate printable official PDF invoices with custom banking requisites.

---

### 📥 Download & Quick Start

* 🚀 **Standalone Executable:** Download the latest [**FinanceFugue.exe (v23.08.2026)**](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026) — no installation required!
* 📦 **ZIP Package:** [FinanceFugue-Windows-v23.08.2026.zip](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026)

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
<summary><h2>🇷🇺 Русский — Полное описание, синхронизация с ботом и документация</h2></summary>
<br>

### 🚀 Что такое FinanceFugue?
**FinanceFugue** — это профессиональная экосистема финансового учета и управления клиентами, созданная специально для фрилансеров, звукорежиссеров, студий звукозаписи, дизайнеров, разработчиков и агентств.

Система объединяет мощную **десктопную программу на ПК** и умного **мобильного Telegram-бота**, обеспечивая полную двустороннюю синхронизацию в реальном времени при сохранении 100% приватности локальных данных.

---

### 📱 Подробно о связке с Telegram-ботом:
1. **Подключение за 10 секунд:** Откройте финансового бота в Telegram (`@FinanceFugue_bot`) и отправьте команду `/sync`. Бот покажет ваш персональный **Telegram Chat ID**.
2. **Привязка к программе:** В программе на ПК нажмите кнопку **«📱 Бот / Синхронизация»** на левой панели, вставьте ваш Chat ID и нажмите **«⚡️ Проверить связь»**.
3. **Единая база везде:**
   * **Автосинхронизация:** При каждом сохранении на ПК (`Ctrl+S`) база автоматически и незаметно отправляется в бота в фоновом потоке.
   * **Ручной Push / Pull:** Выгружайте актуальные данные из бота в программу или отправляйте базу с ПК в бота в 1 клик.
   * **Мультиаккаунтное связывание:** Администратор может объединить несколько Telegram-аккаунтов для совместной работы в одной базе данных.

#### 📁 Файлы проектов и защита диска сервера:
* **Облако Telegram CDN (0 байт расхода диска сервера):**  
  Все файлы, аудиодорожки, брифы и материалы, прикрепляемые к заказам в Telegram, сохраняются напрямую в распределенном облаке Telegram CDN через дескрипторы `tg_file_id`. Диск вашего сервера VPS **никогда не переполнится**.
* **Локальное хранение на ПК (Portable Mode):**  
  На компьютере файлы хранятся в рабочей директории с поддержкой умного авто-лечения путей и упаковки проекта в ZIP-архив за 1 клик (`PROJECT_MANIFEST.txt`).

---

### ✨ Ключевые возможности программы

* **🔒 Локальная приватность (Local-First):** База данных принадлежит только вам. Все записи хранятся локально в файле `pro_database.json`. Никаких скрытых облачных серверов третьих лиц.
* **🧮 Строгая финансовая математика:**
  * Автоматический расчет баланса: `Стоимость ➔ Аванс (Предоплата) ➔ Остаток долга`.
  * **Защита от переплат:** Программа блокирует внесение сумм, превышающих текущий долг по сделке.
  * **Автоматические возвраты:** Если стоимость заказа уменьшена после оплаты, программа автоматически создает корректировочный платеж возврата, сохраняя кассу безупречной.
  * Поддержка любых валют (`RUB`, `USD`, `EUR`, `USDT`, `UAH`, `KZT`, `BYN` и др.) с проверкой чисел на валидность (`math.isfinite`).
* **📁 Умный файловый менеджер:**
  * Прикрепление любых рабочих файлов через Drag & Drop.
  * **Режим копирования в базу:** Позволяет переносить папку программы на флешку или в облачный диск (Яндекс.Диск, Google Drive) без потери файлов.
  * **Экспорт проекта в ZIP за 1 клик:** Асинхронная упаковка файлов проекта в единый архив с манифестом `PROJECT_MANIFEST.txt`.
* **🧊 «Холодное хранилище» (Архив):**
  * Отправка выполненных заказов в иерархический архив (`Год ➔ Месяц`) для сохранения максимальной скорости работы интерфейса на протяжении многих лет.
* **📊 Аналитический дашборд и печать PDF-инвойсов:**
  * Сводная касса, учет авансов и долгов, фильтрация по периодам.
  * Генерация официальных счетов и актов в PDF с реквизитами исполнителя.

---

### 📥 Скачивание и быстрый старт

* 🚀 **Готовый EXE-файл:** Скачайте последний релиз [**FinanceFugue.exe (v23.08.2026)**](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026) — установка не требуется!
* 📦 **ZIP-архив с документацией:** [FinanceFugue-Windows-v23.08.2026.zip](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026)

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
<summary><h2>🇺🇦 Українська — Повний опис, синхронізація з ботом та документація</h2></summary>
<br>

### 🚀 Що таке FinanceFugue?
**FinanceFugue** — це професійна екосистема фінансового обліку та управління клієнтами, створена спеціально для фрілансерів, звукорежисерів, музичних студій, дизайнерів, розробників та креативних команд.

Система об'єднує надійну **десктопну програму на ПК** та розумного **мобільного Telegram-бота**, забезпечуючи повноцінну двосторонню синхронізацію в реальному часі зі 100% збереженням приватності локальних даних.

---

### 📱 Детально про зв'язку з Telegram-ботом:
1. **Підключення за 10 секунд:** Відкрийте фінансового бота в Telegram (`@FinanceFugue_bot`) та надішліть команду `/sync`. Бот покаже ваш персональний **Telegram Chat ID**.
2. **Прив'язка до програми:** У програмі на ПК натисніть кнопку **«📱 Бот / Синхронізація»** на лівій панелі, вставте ваш Chat ID та натисніть **«⚡️ Перевірити зв'язок»**.
3. **Спільна база всюди:**
   * **Автосинхронізація:** Під час кожного збереження на ПК (`Ctrl+S`) база автоматично та непомітно надсилається до бота у фоновому потоці.
   * **Ручний Push / Pull:** Вивантажуйте актуальні дані з бота у програму або надсилайте базу з ПК до бота в 1 клік.
   * **Мультиакаунтне зв'язування:** Адміністратор може об'єднати кілька Telegram-акаунтів для спільної роботи в єдиній базі даних.

#### 📁 Файли проєктів та захист диска сервера:
* **Хмарне сховище Telegram CDN (0 байт навантаження на сервер):**  
  Усі файли, аудіодоріжки, брифи та матеріали, прикріплені до замовлень у Telegram, зберігаються безпосередньо в розподіленій хмарі Telegram CDN через дескриптори `tg_file_id`. Сервер VPS **ніколи не переповниться**.
* **Локальне зберігання на ПК (Portable Mode):**  
  На комп'ютері файли зберігаються в робочій директорії з підтримкою розумного авто-відновлення шляхів та пакування проєкту в ZIP-архів за 1 клік (`PROJECT_MANIFEST.txt`).

---

### ✨ Ключові можливості програми

* **🔒 Локальна приватність (Local-First):** База даних належить виключно вам. Всі записи зберігаються локально у файлі `pro_database.json`.
* **🧮 Точна фінансова математика:**
  * Автоматичний розрахунок балансу: `Вартість ➔ Аванс (Передплата) ➔ Залишок боргу`.
  * **Захист від переплат:** Блокування сум, що перевищують поточний борг.
  * **Автоматичні повернення:** Зниження вартості замовлення автоматично формує коригувальний платіж повернення.
  * Підтримка будь-яких валют (`UAH`, `USD`, `EUR`, `USDT`, `RUB`, `PLN` тощо) з валідацією чисел (`math.isfinite`).
* **📁 Розумний менеджер файлів (Portable Mode):**
  * Прикріплення будь-яких робочих файлів за допомогою Drag & Drop.
  * **Режим копіювання до бази:** Перенесення теки програми на флешку або хмарне сховище без втрати прив'язки файлів.
  * **Експорт проєкту в ZIP за 1 клік:** Асинхронне пакування матеріалів у єдиний архів із маніфестом `PROJECT_MANIFEST.txt`.
* **🧊 «Холодне сховище» (Архів):**
  * Переміщення завершених замовлень до ієрархічного архіву (`Рік ➔ Місяць`).
* **📊 Аналітичний дашборд та друк PDF-рахунків:**
  * Зведена каса, облік авансів та боргів, фільтри за періодами.
  * Генерація офіційних рахунків та актів у форматі PDF із реквізитами виконавця.

---

### 📥 Завантаження та швидкий старт

* 🚀 **Готовий EXE-файл:** Завантажте останній реліз [**FinanceFugue.exe (v23.08.2026)**](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026) — встановлення не потрібне!
* 📦 **ZIP-архів з документацією:** [FinanceFugue-Windows-v23.08.2026.zip](https://github.com/kir-spec/FinanceFugue/releases/tag/v23.08.2026)

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

[EULA.md](EULA.md) • [PRIVACY.md](PRIVACY.md) • [DOCUMENTATION.md](DOCUMENTATION.md) • [Releases](https://github.com/kir-spec/FinanceFugue/releases)

</div>
