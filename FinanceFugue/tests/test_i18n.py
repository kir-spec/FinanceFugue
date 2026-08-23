import unittest
from src.services.i18n import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    detect_system_language,
    get_current_language,
    set_current_language,
    t,
)


class TestI18n(unittest.TestCase):
    def setUp(self):
        set_current_language("en")

    def test_supported_languages(self):
        self.assertIn("en", SUPPORTED_LANGUAGES)
        self.assertIn("ru", SUPPORTED_LANGUAGES)
        self.assertIn("uk", SUPPORTED_LANGUAGES)

    def test_default_language(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")

    def test_translations_en(self):
        set_current_language("en")
        self.assertEqual(t("sidebar_new_client"), "➕ New Client")
        self.assertEqual(t("sidebar_bot_sync"), "📱 Bot / Sync")
        self.assertEqual(t("status_in_progress"), "In Progress")

    def test_translations_ru(self):
        set_current_language("ru")
        self.assertEqual(t("sidebar_new_client"), "➕ Новый клиент")
        self.assertEqual(t("sidebar_bot_sync"), "📱 Бот / Синхронизация")
        self.assertEqual(t("status_in_progress"), "В работе")

    def test_translations_uk(self):
        set_current_language("uk")
        self.assertEqual(t("sidebar_new_client"), "➕ Новий клієнт")
        self.assertEqual(t("sidebar_bot_sync"), "📱 Бот / Синхронізація")
        self.assertEqual(t("status_in_progress"), "В роботі")

    def test_translation_formatting(self):
        set_current_language("en")
        self.assertEqual(t("sidebar_clients_count", count=5), "Clients: 5")
        set_current_language("ru")
        self.assertEqual(t("sidebar_clients_count", count=10), "Клиентов: 10")
        set_current_language("uk")
        self.assertEqual(t("sidebar_clients_count", count=15), "Клієнтів: 15")

    def test_fallback_to_key(self):
        self.assertEqual(t("non_existent_key_12345"), "non_existent_key_12345")


if __name__ == "__main__":
    unittest.main()
