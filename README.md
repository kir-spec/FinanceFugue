# 💼 FinanceFugue
> **Modern Desktop CRM & Client Management Tool for Professionals**

[![Release](https://img.shields.io/badge/release-25.07.2026-blue.svg?style=flat-square)](https://github.com/kir-spec/FinanceFugue/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/UI-PySide6%20(Qt%206)-green.svg?style=flat-square)](https://pypi.org/project/PySide6/)
[![License](https://img.shields.io/badge/license-Custom-orange.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey.svg?style=flat-square)]()

---

## 🌍 Short Description / Краткое описание / Короткий опис

### 🇺🇸 English
**FinanceFugue** is a professional desktop CRM and client management tool designed for freelancers, creative studios, and small businesses. It provides a robust environment for managing client databases, tracking financial transactions, monitoring deadlines, and organizing local documents—all in a single seamless interface with a premium dark design.

### 🇷🇺 Русский
**FinanceFugue** — это профессиональное десктопное CRM-решение, созданное для фрилансеров, студий и предпринимателей. Приложение предоставляет мощный инструментарий для ведения клиентской базы, финансового учёта сделок, контроля дедлайнов и организации рабочих файлов в едином бесшовном интерфейсе с премиальным темным дизайном.

### 🇺🇦 Українська
**FinanceFugue** — це професійне десктопне CRM-рішення, створене для фрілансерів, студій та підприємців. Додаток надає потужний інструментарій для ведення клієнтської бази, фінансового обліку угод, контролю дедлайнів та організації робочих файлів у єдиному безшовному інтерфейсі з преміальним темним дизайном.

---

## 📖 Detailed Description / Подробное описание / Детальний опис

<details>
<summary>🇺🇸 Click to expand detailed description in English</summary>
<br>

### ✨ Core Features

#### 👤 Client & Order Management
* **Single Registry:** Real-time grouping, smart live search, and filtration of the client database.
* **Smart Sorting:** Automatic ranking of clients by name, last order date, or deadline urgency.
* **Order Lifecycle:** Visual tracking of statuses ("In Progress", "Completed", "Paused").

#### 💰 Financial Accounting & Payment Logs
* **Automated Calculations:** Instant recalculation of advances, received amounts, and remaining debt for each project.
* **Transaction Log:** Comprehensive payment history with categories (Advances, Payments, Adjustments) and text comments.
* **Multi-currency:** Full support for major currencies (RUB, USD, EUR) with proper symbol mapping.
* **Dashboard:** Instant analytics on revenue, total debts, and active orders directly on the main screen.

#### 📁 Smart File Management & Drag-and-Drop
* **Two Storage Modes:** Leave files in place (shortcuts) or completely copy them into the isolated database folder.
* **Integrated File Manager:** Intuitive customer folder tree with the ability to open files in system default apps with a single click.
* **Drag-and-Drop:** Attach files by simply dragging them onto the order widget or file manager tree.

#### 🔒 Safety & Enterprise-grade Resilience
* **Atomic Writes:** All database and settings write operations go through temporary files, preventing corruption during sudden power losses.
* **Data Isolation:** Logs, settings, and backups are stored in the user's `%LOCALAPPDATA%`, preventing permission errors (`Access Denied`).
* **Conflict Prevention (Instance Lock):** File locking prevents running multiple instances of the app to avoid database overwrite conflicts.
* **Built-in Crash Reporter:** A global exception handler catches critical errors, displaying a user-friendly crash dialog and writing stack traces to the log files.

---

### 🎨 UI & Design
The application is styled with a modern **Fusion Dark Material** theme:
* Deep dark palette to reduce eye strain during long working hours.
* Urgency color-coding: deadlines are highlighted in green, yellow, or red depending on the remaining time.
* Responsive layouts that scale cleanly across different screen resolutions.

---

### 🚀 Quick Start (Development)
#### Requirements
* Python 3.11+
* PySide6 >= 6.6.0

#### Run from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/kir-spec/FinanceFugue.git
   cd FinanceFugue
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the application:
   ```bash
   python main_pyside.py
   ```

#### Run Tests
```bash
# Run unit tests
python -m unittest discover -s tests -p "test_*.py" -v

# Run Qt UI tests
pytest tests/qt -v
```

---

### 🛠 Building Executable (EXE/App)
To build a standalone commercial executable via PyInstaller:
```bash
# Install build requirements
pip install -r requirements-build.txt

# Run PyInstaller compilation
pyinstaller build.spec
```
The standalone executable `FinanceFugue.exe` will be generated in `dist/`.

---

### 📁 User Data Structure
To prevent permission conflicts when installed in protected directories (e.g. `Program Files`), the app separates user data:

| User Data | Default Path | Description |
| :--- | :--- | :--- |
| **Client Database** | `%LOCALAPPDATA%/FinanceFugue/pro_database.json` | JSON store containing all customer profiles and orders |
| **Settings** | `%LOCALAPPDATA%/FinanceFugue/crm_settings.json` | User configuration settings |
| **Logs** | `%LOCALAPPDATA%/FinanceFugue/logs/` | Log files with automatic 2MB rotation (up to 5 backups) |
| **Backups** | `%LOCALAPPDATA%/FinanceFugue/settings_backups/` | Automated backups of settings files |

*Note: If upgrading from beta versions, the application will automatically inherit settings and databases located in the root directory.*

---

### ⚖️ License & Legal Info
* All rights reserved by the author.
* Please review [EULA.md](EULA.md) and [PRIVACY.md](PRIVACY.md).
* Third-party licenses are documented in [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

</details>

<details>
<summary>🇷🇺 Нажмите, чтобы развернуть подробное описание на русском</summary>
<br>

### ✨ Основные возможности

#### 👤 Управление клиентами и заказами
* **Единый реестр:** Группировка, умный живой поиск и фильтрация клиентской базы в реальном времени.
* **Сортировка по приоритетам:** Умный алгоритм ранжирования клиентов (по имени, дате последнего заказа или критичности дедлайнов).
* **Жизненный цикл заказа:** Удобный трекинг статусов («В работе», «Выполнен», «Приостановлен»).

#### 💰 Финансовый учёт и логирование платежей
* **Автоматические расчёты:** Мгновенный перерасчёт авансов, полученных сумм и остатка долга по каждому проекту.
* **История транзакций:** Полноценный лог платежей с разбивкой по категориям (Авансы, Платежи, Корректировки) и текстовыми примечаниями.
* **Мультивалютность:** Корректная поддержка различных валют (RUB, USD, EUR) с отображением релевантных символов.
* **Сводный дашборд:** Мгновенная аналитика по выручке, долгам и активным заказам прямо на главном экране.

#### 📁 Умная файловая система и Drag-and-Drop
* **Два режима хранения:** Возможность оставлять файлы на своих местах (ссылки) или полностью копировать их в структуру базы данных.
* **Интегрированный файловый менеджер:** Интуитивное дерево папок клиентов и заказов с возможностью открывать файлы системными приложениями в один клик.
* **Drag-and-Drop:** Прикрепление файлов простым перетаскиванием прямо на виджет заказа или в дерево файлового менеджера.

#### 🔒 Безопасность и отказоустойчивость корпоративного уровня
* **Атомарная запись (Atomic Writes):** Все операции записи базы данных и настроек происходят через временные файлы с последующей заменой. Это гарантирует защиту от повреждения данных при внезапном отключении ПК.
* **Изоляция данных:** Логи, настройки и резервные копии изолированы в системном каталоге `AppData` пользователя, что исключает ошибки доступа (`Access Denied`).
* **Защита от конфликтов (Instance Lock):** Файловая блокировка базы данных исключает запуск нескольких копий программы, предотвращая перезапись данных.
* **Встроенный Crash Reporter:** Любое критическое исключение перехватывается глобальным обработчиком, выводя информативное окно для пользователя и детальный стек вызовов в логи.

---

### 🎨 Интерфейс и дизайн
Приложение оформлено в современном стиле **Fusion Dark Material**:
* Глубокая тёмная палитра для снижения нагрузки на зрение при долгой работе.
* Цветовое кодирование критичности: дедлайны подсвечиваются мягким зелёным, жёлтым или контрастным красным цветом в зависимости от оставшегося времени.
* Адаптивная вёрстка: информационные блоки аккуратно подстраиваются под разрешение экрана.

---

### 🚀 Быстрый старт (Разработка)
#### Требования
* Python 3.11 или выше
* PySide6 >= 6.6.0

#### Запуск из исходного кода
1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/kir-spec/FinanceFugue.git
   cd FinanceFugue
   ```
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Запустите приложение:
   ```bash
   python main_pyside.py
   ```

#### Запуск тестов
```bash
# Запуск unit-тестов
python -m unittest discover -s tests -p "test_*.py" -v

# Запуск UI-тестов Qt
pytest tests/qt -v
```

---

### 🛠 Сборка исполняемого файла (EXE/App)
Сборка автономной коммерческой версии выполняется с помощью PyInstaller:
```bash
# Установка сборочных зависимостей
pip install -r requirements-build.txt

# Сборка исполняемого файла
pyinstaller build.spec
```
Исполняемый файл `.exe` будет создан в папке `dist/FinanceFugue.exe` и будет полностью независим от установленного Python.

---

### 📁 Структура пользовательских данных
Для предотвращения проблем с правами доступа в защищенных папках (например, `Program Files`), FinanceFugue разделяет ресурсы:

| Данные | Расположение по умолчанию | Описание |
| :--- | :--- | :--- |
| **База клиентов** | `%LOCALAPPDATA%/FinanceFugue/pro_database.json` | Хранилище всей информации в формате JSON |
| **Настройки** | `%LOCALAPPDATA%/FinanceFugue/crm_settings.json` | Пользовательская конфигурация приложения |
| **Логи** | `%LOCALAPPDATA%/FinanceFugue/logs/` | Файлы журналов работы приложения (до 5 ротаций по 2МБ) |
| **Бэкапы** | `%LOCALAPPDATA%/FinanceFugue/settings_backups/` | Резервные копии настроек программы |

*Примечание: При обновлении с бета-версий программа автоматически подхватит старые файлы `pro_database.json` и `crm_settings.json` из корневой папки, если они там присутствуют.*

---

### ⚖️ Лицензия и правовая информация
* Все права на приложение принадлежат автору. 
* Ознакомьтесь с условиями использования в [EULA.md](EULA.md) и политикой конфиденциальности в [PRIVACY.md](PRIVACY.md).
* Список сторонних лицензий доступен в [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

</details>

<details>
<summary>🇺🇦 Натисніть, щоб розгорнути детальний опис українською</summary>
<br>

### ✨ Основні можливості

#### 👤 Управління клієнтами та замовленнями
* **Єдиний реєстр:** Групування, розумний швидкий пошук та фільтрація клієнтської бази в реальному часі.
* **Сортування за пріоритетами:** Розумний алгоритм ранжування клієнтів (за ім'ям, датою останнього замовлення або критичністю дедлайнів).
* **Життєвий цикл замовлення:** Зручний трекінг статусів («В роботі», «Виконано», «Призупинено»).

#### 💰 Фінансовий облік та логування платежів
* **Автоматичні розрахунки:** Миттєвий перерахунок авансів, отриманих сум та залишку боргу по кожному проекту.
* **Історія транзакцій:** Повноцінний лог платежів з розбивкою за категоріями (Аванси, Платежі, Коригування) та текстовими примітками.
* **Мультивалютність:** Коректна підтримка основних валют (RUB, USD, EUR) з відображенням відповідних символів.
* **Зведений дашборд:** Миттєва аналітика доходів, загальних боргів та активних замовлень безпосередньо на головному екрані.

#### 📁 Розумна файлова система та Drag-and-Drop
* **Два режими зберігання:** Можливість залишати файли на своїх місцях (посилання) або повністю копіювати їх у структуру бази даних.
* **Інтегрований файловий менеджер:** Інтуїтивне дерево папок клієнтів та замовлень з можливістю відкривати файли системними додатками в один клік.
* **Drag-and-Drop:** Прикріплення файлів простим перетягуванням безпосередньо на віджет замовлення або в дерево файлового менеджера.

#### 🔒 Безпека та відмовостійкість корпоративного рівня
* **Атомарний запис (Atomic Writes):** Всі операції запису бази даних та налаштувань відбуваються через тимчасові файли з подальшою заміною. Це гарантує захист від пошкодження даних при раптовому вимкненні ПК.
* **Ізоляція даних:** Логи, налаштування та резервні копії ізольовані в системному каталозі `AppData` користувача, що виключає помилки доступу (`Access Denied`).
* **Запобігання конфліктам (Instance Lock):** Файлове блокування бази даних виключає запуск кількох копій програми, запобігаючи перезапису даних.
* **Вбудований Crash Reporter:** Будь-яке критичне виключення перехоплюється глобальним обробником, який виводить інформативне вікно для користувача та детальний стек викликів у логи.

---

### 🎨 Інтерфейс та дизайн
Додаток оформлено в сучасному стилі **Fusion Dark Material**:
* Глибока темна палітра для зниження навантаження на зір при тривалій роботі.
* Кольорове кодування критичності: дедлайни підсвічуються м'яким зеленим, жовтим або контрастним червоним кольором залежно від часу, що залишився.
* Адаптивна верстка: інформаційні блоки акуратно підлаштовуються під роздільну здатність екрана.

---

### 🚀 Швидкий старт (Розробка)
#### Вимоги
* Python 3.11 або вище
* PySide6 >= 6.6.0

#### Запуск із вихідного коду
1. Клонуйте репозиторій:
   ```bash
   git clone https://github.com/kir-spec/FinanceFugue.git
   cd FinanceFugue
   ```
2. Встановіть залежності:
   ```bash
   pip install -r requirements.txt
   ```
3. Запустіть додаток:
   ```bash
   python main_pyside.py
   ```

#### Запуск тестів
```bash
# Запуск unit-тестів
python -m unittest discover -s tests -p "test_*.py" -v

# Запуск UI-тестів Qt
pytest tests/qt -v
```

---

### 🛠 Збірка виконуваного файлу (EXE/App)
Збірка автономної комерційної версії виконується за допомогою PyInstaller:
```bash
# Встановлення залежностей збірки
pip install -r requirements-build.txt

# Збірка виконуваного файлу
pyinstaller build.spec
```
Виконуваний файл `.exe` буде створено в папці `dist/FinanceFugue.exe` і він буде повністю незалежним від встановленого Python.

---

### 📁 Структура користувацьких даних
Для запобігання проблемам з правами доступу в захищених папках (наприклад, `Program Files`), FinanceFugue розділяє ресурси:

| Дані | Розташування за замовчуванням | Опис |
| :--- | :--- | :--- |
| **База клієнтів** | `%LOCALAPPDATA%/FinanceFugue/pro_database.json` | Сховище всієї інформації у форматі JSON |
| **Налаштування** | `%LOCALAPPDATA%/FinanceFugue/crm_settings.json` | Користувацька конфігурація додатка |
| **Логи** | `%LOCALAPPDATA%/FinanceFugue/logs/` | Файли журналів роботи додатка (до 5 ротацій по 2МБ) |
| **Бекапи** | `%LOCALAPPDATA%/FinanceFugue/settings_backups/` | Резервні копії налаштувань програми |

*Примітка: При оновленні з бета-версій додаток автоматично підхопить старі файли `pro_database.json` та `crm_settings.json` з кореневої папки, якщо вони там присутні.*

---

### ⚖️ Ліцензія та правова інформація
* Всі права на додаток належать автору.
* Ознайомтеся з умовами використання у [EULA.md](EULA.md) та політикою конфіденційності у [PRIVACY.md](PRIVACY.md).
* Список сторонніх ліцензій доступний у [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

</details>
