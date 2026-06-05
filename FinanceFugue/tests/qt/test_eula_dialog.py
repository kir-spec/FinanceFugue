import pytest
from PySide6.QtWidgets import QCheckBox, QPushButton

from src.dialogs.eula import EulaDialog


@pytest.mark.qt
def test_eula_dialog_creates_widgets(qtbot):
    dialog = EulaDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle()
    assert dialog.findChild(QCheckBox) is not None
    accept_btn = dialog.findChild(QPushButton, "acceptBtn")
    if accept_btn is None:
        buttons = dialog.findChildren(QPushButton)
        assert any("Принять" in b.text() for b in buttons)
    else:
        assert accept_btn.isEnabled()
