
from PySide6.QtGui import QIcon

from ..utils.paths import resource_path


def load_app_icon() -> QIcon:
    for name in ("images/FinanceFugue.ico", "images/FinanceFugue.png"):
        path = resource_path(name)
        if path.exists():
            return QIcon(str(path))
    return QIcon()
