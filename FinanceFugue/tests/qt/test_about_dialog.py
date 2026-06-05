import pytest
from PySide6.QtWidgets import QTabWidget

from src.dialogs.about import AboutDialog


@pytest.mark.qt
def test_about_dialog_has_tabs(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() >= 3
