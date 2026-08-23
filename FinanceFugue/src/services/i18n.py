import os
import locale
from typing import Optional, Dict, Any

from PySide6.QtCore import QLocale

# Языковая иерархия: базовый English, Русский, Українська
SUPPORTED_LANGUAGES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "uk": "🇺🇦 Українська",
}

DEFAULT_LANGUAGE = "en"

# Текущий активный язык в памяти
_CURRENT_LANGUAGE = None


def detect_system_language() -> str:
    """
    Автоматически определяет язык операционной системы:
    - Если система на русском (ru_RU, ru_UA, ru_BY и т.д.) -> 'ru'
    - Если система на украинском (uk_UA) -> 'uk'
    - Во всех остальных случаях -> базовый 'en' (English)
    """
    try:
        # 1. Проверяем через QLocale (Qt)
        qt_lang = QLocale.system().name().lower()
        if qt_lang.startswith("ru"):
            return "ru"
        elif qt_lang.startswith("uk"):
            return "uk"

        # 2. Проверяем через модуль locale Python
        loc = locale.getdefaultlocale()[0]
        if loc:
            loc = loc.lower()
            if loc.startswith("ru"):
                return "ru"
            elif loc.startswith("uk"):
                return "uk"

        # 3. Проверяем переменные окружения ОС
        for env_var in ("LANG", "LANGUAGE", "LC_ALL"):
            val = os.environ.get(env_var, "").lower()
            if val.startswith("ru"):
                return "ru"
            elif val.startswith("uk"):
                return "uk"
    except Exception:
        pass

    return DEFAULT_LANGUAGE


def get_current_language(app_settings: Optional[dict] = None) -> str:
    global _CURRENT_LANGUAGE
    if _CURRENT_LANGUAGE is not None:
        return _CURRENT_LANGUAGE

    if app_settings:
        saved_lang = app_settings.get("ui_language")
        if saved_lang and saved_lang in SUPPORTED_LANGUAGES:
            _CURRENT_LANGUAGE = saved_lang
            return _CURRENT_LANGUAGE

    _CURRENT_LANGUAGE = detect_system_language()
    return _CURRENT_LANGUAGE


def set_current_language(lang_code: str):
    global _CURRENT_LANGUAGE
    if lang_code in SUPPORTED_LANGUAGES:
        _CURRENT_LANGUAGE = lang_code
    elif lang_code == "auto":
        _CURRENT_LANGUAGE = detect_system_language()


# --- СЛОВАРЬ ПЕРЕВОДОВ (EN / RU / UK) ---
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # Главная боковая панель и навигация
    "app_title": {
        "en": "FinanceFugue",
        "ru": "FinanceFugue",
        "uk": "FinanceFugue",
    },
    "sidebar_new_client": {
        "en": "➕ New Client",
        "ru": "➕ Новый клиент",
        "uk": "➕ Новий клієнт",
    },
    "sidebar_new_client_tooltip": {
        "en": "Add a new client (Ctrl+N)",
        "ru": "Добавить нового клиента (Ctrl+N)",
        "uk": "Додати нового клієнта (Ctrl+N)",
    },
    "sidebar_file_manager": {
        "en": "📁 File Manager",
        "ru": "📁 Менеджер файлов",
        "uk": "📁 Менеджер файлів",
    },
    "sidebar_file_manager_tooltip": {
        "en": "Open global project file manager (Ctrl+O)",
        "ru": "Открыть глобальный менеджер файлов (Ctrl+O)",
        "uk": "Відкрити глобальний менеджер файлів (Ctrl+O)",
    },
    "sidebar_bot_sync": {
        "en": "📱 Bot / Sync",
        "ru": "📱 Бот / Синхронизация",
        "uk": "📱 Бот / Синхронізація",
    },
    "sidebar_bot_sync_tooltip": {
        "en": "2-Way sync with Telegram Bot",
        "ru": "Двусторонняя синхронизация с Telegram-ботом",
        "uk": "Двостороння синхронізація з Telegram-ботом",
    },
    "sidebar_settings": {
        "en": "⚙ Settings",
        "ru": "⚙ Настройки",
        "uk": "⚙ Налаштування",
    },
    "sidebar_settings_tooltip": {
        "en": "Application settings (Ctrl+Shift+S)",
        "ru": "Глобальные настройки программы (Ctrl+Shift+S)",
        "uk": "Загальні налаштування програми (Ctrl+Shift+S)",
    },
    "sidebar_help": {
        "en": "❓ Help & Guide",
        "ru": "❓ Справка",
        "uk": "❓ Довідка",
    },
    "sidebar_help_tooltip": {
        "en": "Open user documentation and guide",
        "ru": "Открыть руководство пользователя",
        "uk": "Відкрити посібник користувача",
    },
    "sidebar_clients_count": {
        "en": "Clients: {count}",
        "ru": "Клиентов: {count}",
        "uk": "Клієнтів: {count}",
    },
    "search_placeholder": {
        "en": "Search clients...",
        "ru": "Поиск клиентов...",
        "uk": "Пошук клієнтів...",
    },
    "trash_button": {
        "en": "🗑 Trash",
        "ru": "🗑 Корзина",
        "uk": "🗑 Кошик",
    },
    "archive_button": {
        "en": "🗄 Archive",
        "ru": "🗄 Архив",
        "uk": "🗄 Архів",
    },

    # Дашборд аналитики
    "dash_total_cash": {
        "en": "Total Revenue",
        "ru": "Общая касса",
        "uk": "Загальна каса",
    },
    "dash_expected_profit": {
        "en": "Expected Profit",
        "ru": "Ожидаемая прибыль",
        "uk": "Очікуваний прибуток",
    },
    "dash_advance": {
        "en": "Advances (Prepaid)",
        "ru": "Авансы",
        "uk": "Аванси",
    },
    "dash_completed_orders": {
        "en": "Completed Orders",
        "ru": "Выполнено заказов",
        "uk": "Виконано замовлень",
    },
    "filter_current_year": {
        "en": "Current Year",
        "ru": "Текущий год",
        "uk": "Поточний рік",
    },
    "filter_prev_year": {
        "en": "Previous Year",
        "ru": "Прошлый год",
        "uk": "Минулий рік",
    },
    "filter_all_time": {
        "en": "All Time",
        "ru": "Всё время",
        "uk": "Весь час",
    },

    # Профиль клиента
    "client_no_selection": {
        "en": "Select a client from the list or create a new one",
        "ru": "Выберите клиента из списка или создайте нового",
        "uk": "Виберіть клієнта зі списку або створіть нового",
    },
    "client_settings_btn": {
        "en": "⚙ Client Settings",
        "ru": "⚙ Настройки клиента",
        "uk": "⚙ Налаштування клієнта",
    },
    "client_add_order_btn": {
        "en": "➕ Add Order",
        "ru": "➕ Добавить заказ",
        "uk": "➕ Додати замовлення",
    },
    "client_email_label": {
        "en": "Email:",
        "ru": "Email:",
        "uk": "Email:",
    },
    "client_social_label": {
        "en": "Social / Links:",
        "ru": "Соцсети / Связь:",
        "uk": "Соцмережі / Зв'язок:",
    },
    "client_notes_label": {
        "en": "Notes:",
        "ru": "Заметки:",
        "uk": "Нотатки:",
    },
    "client_total_stat": {
        "en": "Orders: {orders} | Done: {done} | Paid: {paid} | Debt: {debt}",
        "ru": "Заказов: {orders} | Готово: {done} | Внесено: {paid} | Долг: {debt}",
        "uk": "Замовлень: {orders} | Готово: {done} | Сплачено: {paid} | Борг: {debt}",
    },

    # Карточка заказа
    "order_service_label": {
        "en": "Service:",
        "ru": "Услуга:",
        "uk": "Послуга:",
    },
    "order_price_label": {
        "en": "Price:",
        "ru": "Стоимость:",
        "uk": "Вартість:",
    },
    "order_advance_label": {
        "en": "Advance (Prepaid):",
        "ru": "Аванс:",
        "uk": "Аванс:",
    },
    "order_debt_label": {
        "en": "Remaining Debt:",
        "ru": "Остаток долга:",
        "uk": "Залишок боргу:",
    },
    "order_deadline_label": {
        "en": "Deadline:",
        "ru": "Дедлайн:",
        "uk": "Дедлайн:",
    },
    "order_status_label": {
        "en": "Status:",
        "ru": "Статус:",
        "uk": "Статус:",
    },
    "status_in_progress": {
        "en": "In Progress",
        "ru": "В работе",
        "uk": "В роботі",
    },
    "status_completed": {
        "en": "Completed",
        "ru": "Завершен",
        "uk": "Завершено",
    },
    "status_cancelled": {
        "en": "Cancelled",
        "ru": "Отменен",
        "uk": "Скасовано",
    },
    "btn_add_payment": {
        "en": "✚ Add Payment",
        "ru": "✚ добавить платеж",
        "uk": "✚ додати платіж",
    },
    "btn_pay_all": {
        "en": "✅ Fully Paid",
        "ru": "✅ ОПЛАЧЕНО",
        "uk": "✅ СПЛАЧЕНО",
    },
    "btn_unpaid": {
        "en": "❌ UNPAID",
        "ru": "❌ НЕ ОПЛАЧЕНО",
        "uk": "❌ НЕ СПЛАЧЕНО",
    },
    "btn_payment_history": {
        "en": "📋 History",
        "ru": "📋 история",
        "uk": "📋 історія",
    },
    "btn_archive_order": {
        "en": "📦 To Archive",
        "ru": "📦 В архив",
        "uk": "📦 До архіву",
    },
    "btn_export_zip": {
        "en": "📦 Export ZIP",
        "ru": "📦 Экспорт ZIP",
        "uk": "📦 Експорт ZIP",
    },
    "btn_add_files": {
        "en": "➕ Add Files",
        "ru": "➕ Добавить файлы",
        "uk": "➕ Додати файли",
    },

    # Настройки программы
    "settings_title": {
        "en": "Global Settings",
        "ru": "Глобальные настройки",
        "uk": "Загальні налаштування",
    },
    "settings_tab_general": {
        "en": "General",
        "ru": "Основные",
        "uk": "Основні",
    },
    "settings_tab_database": {
        "en": "Database",
        "ru": "База данных",
        "uk": "База даних",
    },
    "settings_tab_cloud": {
        "en": "Cloud & Sync",
        "ru": "Облако и Бот",
        "uk": "Хмара та Бот",
    },
    "settings_tab_notifications": {
        "en": "Notifications",
        "ru": "Уведомления",
        "uk": "Сповіщення",
    },
    "settings_language": {
        "en": "Interface Language:",
        "ru": "Язык интерфейса:",
        "uk": "Мова інтерфейсу:",
    },
    "settings_lang_auto": {
        "en": "🌐 Auto (System Language)",
        "ru": "🌐 Авто (Язык системы)",
        "uk": "🌐 Авто (Мова системи)",
    },
    "settings_app_mode": {
        "en": "Application Mode:",
        "ru": "Режим работы программы:",
        "uk": "Режим роботи програми:",
    },
    "mode_personal": {
        "en": "👤 Personal Finance (Home Budget)",
        "ru": "👤 Личные финансы (Домашняя бухгалтерия)",
        "uk": "👤 Особисті фінанси (Домашній бюджет)",
    },
    "mode_crm": {
        "en": "💼 Client Manager & Orders (Studio CRM)",
        "ru": "💼 Клиенты и заказы (CRM студии / фриланса)",
        "uk": "💼 Клієнти та замовлення (CRM студії / фрілансу)",
    },
    "mode_full": {
        "en": "✨ Full Hybrid Mode (CRM + Finance)",
        "ru": "✨ Полный гибридный режим (CRM + Финансы)",
        "uk": "✨ Повний гібридний режим (CRM + Фінанси)",
    },
    "settings_theme": {
        "en": "Color Theme:",
        "ru": "Тема оформления:",
        "uk": "Тема оформлення:",
    },
    "settings_file_storage": {
        "en": "File Storage Mode:",
        "ru": "Режим хранения файлов:",
        "uk": "Режим зберігання файлів:",
    },
    "settings_storage_copy": {
        "en": "Copy to database folder (Portable)",
        "ru": "Копировать в базу (Портативный)",
        "uk": "Копіювати до бази (Портативний)",
    },
    "settings_storage_links": {
        "en": "Store as links to originals",
        "ru": "Оставлять ссылки на оригиналы",
        "uk": "Залишати посилання на оригінали",
    },
    "settings_deadline_notify": {
        "en": "Show deadline reminders on startup",
        "ru": "Показывать напоминания о дедлайнах при запуске",
        "uk": "Показувати нагадування про дедлайни під час запуску",
    },
    "settings_save_btn": {
        "en": "Save & Apply",
        "ru": "Сохранить и применить",
        "uk": "Зберегти та застосувати",
    },
    "settings_cancel_btn": {
        "en": "Cancel",
        "ru": "Отмена",
        "uk": "Скасувати",
    },

    # Синхронизация Telegram
    "tg_sync_title": {
        "en": "Telegram Bot Synchronization",
        "ru": "Синхронизация с Telegram-ботом",
        "uk": "Синхронізація з Telegram-ботом",
    },
    "tg_sync_chat_id": {
        "en": "Your Telegram Chat ID:",
        "ru": "Ваш Telegram Chat ID:",
        "uk": "Ваш Telegram Chat ID:",
    },
    "tg_sync_token": {
        "en": "Bot Token (Optional):",
        "ru": "Токен бота (Необязательно):",
        "uk": "Токен бота (Необов'язково):",
    },
    "tg_sync_test_btn": {
        "en": "⚡️ Test Connection",
        "ru": "⚡️ Проверить связь с ботом",
        "uk": "⚡️ Перевірити зв'язок з ботом",
    },
    "tg_sync_auto_cb": {
        "en": "Automatically sync with Telegram Bot on save",
        "ru": "Автоматически синхронизировать с ботом при сохранении на ПК",
        "uk": "Автоматично синхронізувати з ботом під час збереження на ПК",
    },
    "tg_sync_push_btn": {
        "en": "⬆️ Push Database to Bot",
        "ru": "⬆️ Отправить базу в бота (Push)",
        "uk": "⬆️ Надіслати базу до бота (Push)",
    },
    "tg_sync_pull_btn": {
        "en": "⬇️ Pull Database from Bot",
        "ru": "⬇️ Загрузить базу из бота (Pull)",
        "uk": "⬇️ Завантажити базу з бота (Pull)",
    },
    "tg_sync_now_btn": {
        "en": "🔄 Sync Now (2-Way)",
        "ru": "🔄 Синхронизировать сейчас (2-сторонняя)",
        "uk": "🔄 Синхронізувати зараз (2-стороння)",
    },

    # Сообщения и статусбар
    "status_saved": {
        "en": "Saved",
        "ru": "Сохранено",
        "uk": "Збережено",
    },
    "status_sync_ok": {
        "en": "☁️ Synchronized with Telegram Bot",
        "ru": "☁️ Синхронизировано с Telegram-ботом",
        "uk": "☁️ Синхронізовано з Telegram-ботом",
    },
    "confirm_delete_client": {
        "en": "Are you sure you want to delete client «{name}» and all associated data?",
        "ru": "Вы уверены, что хотите удалить клиента «{name}» и все связанные данные?",
        "uk": "Ви впевнені, що хочете видалити клієнта «{name}» та всі пов'язані дані?",
    },
}


def t(key: str, lang: Optional[str] = None, **kwargs) -> str:
    """
    Возвращает локализованную строку по ключу.
    Иерархия разрешения:
    1. Переданный `lang` (или текущий активный язык).
    2. Базовый English (`en`).
    3. Исходный ключ (fallback).
    """
    target_lang = lang or _CURRENT_LANGUAGE or DEFAULT_LANGUAGE
    
    val = None
    if key in TRANSLATIONS:
        val = TRANSLATIONS[key].get(target_lang) or TRANSLATIONS[key].get(DEFAULT_LANGUAGE)
    
    if val is None:
        val = key

    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
            
    return val
