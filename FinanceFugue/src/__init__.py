APP_NAME = "FinanceFugue"

# Версии для отображения (в UI, диалогах, About, логах).
# Формат ДД.ММ.ГГГГ для соответствия пользовательскому формату и
# привычке KoshaDrive. Используется в Inno Setup, About, install folder.
__version_date__ = "04.08.2026"
VERSION = __version_date__           # публичное имя релиза (displayed)
VERSION_DATE = __version_date__      # алиас для единообразия с KoshaDrive

# EULA_REVISION — редакция пользовательского соглашения.
# Меняется при изменении условий; хранится в crm_settings.json
# для повторного показа при апгрейде.
EULA_VERSION = "FF-EULA-04.08.2026-1"

# Семантическое версионирование (только для pyproject / pip / CI).
# Всегда совпадает с датой релиза в формате MAJOR.MINOR.PATCH.
__version_semver__ = "1.0.0"

COMPANY = "KVF SOFT"
COPYRIGHT_HOLDER = "Kirill Fandeev"
SUPPORT_EMAIL = "KVF_SOFT@mail.ru"
