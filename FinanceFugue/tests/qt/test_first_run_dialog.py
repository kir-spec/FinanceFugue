import pytest
from PySide6.QtWidgets import QPushButton

from src.dialogs.first_run import FirstRunDialog


@pytest.mark.qt
def test_first_run_dialog_db_path_field(qtbot):
    dialog = FirstRunDialog()
    qtbot.addWidget(dialog)

    assert dialog.db_path_edit.text()

    buttons = dialog.findChildren(QPushButton)
    assert any("папк" in b.text().lower() for b in buttons)
