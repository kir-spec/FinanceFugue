import unittest
from pathlib import Path

from src import (
    APP_NAME,
    COMPANY,
    COPYRIGHT_HOLDER,
    EULA_VERSION,
    SUPPORT_EMAIL,
    VERSION,
    VERSION_DATE,
    __version_date__,
    __version_semver__,
)
from src.services.eula_renderer import (
    _PLACEHOLDER_RE,
    _render_with_placeholders,
    load_eula_html,
)


class TestVersionConstants(unittest.TestCase):
    """Проверка, что 04.08.2026 правильно пробрасывается во все константы."""

    def test_version_display(self):
        self.assertEqual(VERSION, "04.08.2026")
        self.assertEqual(VERSION_DATE, "04.08.2026")
        self.assertEqual(__version_date__, "04.08.2026")

    def test_semver_matches_date_release(self):
        # SemVer увеличивается вместе с датой релиза
        self.assertEqual(__version_semver__, "1.0.0")

    def test_eula_revision_format(self):
        # FF-EULA-ДД.ММ.ГГГГ-N — стабильный формат
        self.assertRegex(
            EULA_VERSION,
            r"^FF-EULA-\d{2}\.\d{2}\.\d{4}-\d+$",
        )

    def test_app_metadata(self):
        self.assertEqual(APP_NAME, "FinanceFugue")
        self.assertEqual(COMPANY, "KVF SOFT")
        self.assertEqual(COPYRIGHT_HOLDER, "Kirill Fandeev")
        self.assertEqual(SUPPORT_EMAIL, "KVF_SOFT@mail.ru")


class TestEULARenderer(unittest.TestCase):
    def test_placeholder_regex(self):
        ms = _PLACEHOLDER_RE.findall("test {{REVISION}} and {{DATE}}")
        self.assertEqual(ms, ["REVISION", "DATE"])

    def test_render_substitutes(self):
        out = _render_with_placeholders(
            "Rev={{REVISION}} Date={{DATE}}",
            {"REVISION": "r1", "DATE": "2026-08-04"},
        )
        self.assertEqual(out, "Rev=r1 Date=2026-08-04")

    def test_render_missing_marks_visible(self):
        out = _render_with_placeholders("{{UNKNOWN}}", {})
        self.assertIn("[?UNKNOWN?]", out)
        self.assertNotIn("{{UNKNOWN}}", out)

    def test_load_eula_html_real_file(self):
        # Если resources/eula.html существует — рендерим реальный.
        # Если нет (CI на Linux без файла) — fallback.
        html = load_eula_html(revision="r-test", date="2026-08-04")
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 100)
        # Когда файл существует — должна содержать подставленные маркеры.
        if Path("resources/eula.html").exists():
            self.assertIn("r-test", html)
            self.assertIn("2026-08-04", html)
            self.assertNotIn("{{REVISION}}", html)
            self.assertNotIn("{{DATE}}", html)

    def test_load_eula_html_fallback_when_no_resource(self):
        """Fallback-когда resources/eula.html отсутствует."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            empty_dir = Path(tmp)
            html = load_eula_html(
                resources_dir=empty_dir,
                revision="x",
                date="01.01.0001",
            )
            self.assertIn("x", html)
            self.assertIn("01.01.0001", html)

    def test_render_for_real_template(self):
        """Если ресурс существует — проверить все маркеры заменены."""
        if not Path("resources/eula.html").exists():
            self.skipTest("resources/eula.html не найден")
        html = load_eula_html(
            revision="FF-EULA-04.08.2026-1",
            date="04.08.2026",
        )
        # Не должно быть неподставленных {{ }} маркеров
        remaining = _PLACEHOLDER_RE.findall(html)
        self.assertEqual(remaining, [], f"Найдены неподставленные: {remaining}")


class TestEULAFile(unittest.TestCase):
    """Проверка структуры EULA.md и resources/eula.html."""

    def test_eula_md_exists_and_has_section(self):
        path = Path("EULA.md")
        if not path.exists():
            self.skipTest("EULA.md не найден")
        text = path.read_text(encoding="utf-8")
        # Обязательные разделы
        for marker in (
            "## 1. Предмет",
            "## 2. Отказ от облачных функций",
            "## 3. Лицензия",
            "## 4. Политика отсутствия возвратов",
            "## 5. Данные",
            "## 6. Интеллектуальная собственность",
            "## 7. Гарантии",
            "## 8. Реквизиты",
        ):
            self.assertIn(marker, text, f"EULA.md отсутствует раздел: {marker}")

    def test_eula_md_has_revision_header(self):
        text = Path("EULA.md").read_text(encoding="utf-8")
        self.assertIn(EULA_VERSION, text, (
            "EULA.md должен содержать текущий EULA_VERSION "
            f"({EULA_VERSION}) в заголовке"
        ))

    def test_eula_html_has_placeholders(self):
        path = Path("resources/eula.html")
        if not path.exists():
            self.skipTest("resources/eula.html не найден")
        text = path.read_text(encoding="utf-8")
        self.assertIn("{{REVISION}}", text)
        self.assertIn("{{DATE}}", text)


if __name__ == "__main__":
    unittest.main()
