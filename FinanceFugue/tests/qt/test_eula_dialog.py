import pytest
from PySide6.QtWidgets import QCheckBox, QPushButton, QTextBrowser

from src import EULA_VERSION
from src.dialogs.eula import EulaDialog


@pytest.mark.qt
def test_eula_dialog_creates_widgets(qtbot):
    dialog = EulaDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle()
    assert dialog.findChild(QCheckBox) is not None
    assert dialog.findChild(QTextBrowser) is not None

    accept_btn = dialog.findChild(QPushButton, "acceptBtn")
    assert accept_btn is not None

    # Принятие должно быть заблокировано, пока пользователь не дочитал
    # до конца и не поставил флажок (KoshaDrive UX pattern).
    assert not accept_btn.isEnabled(), (
        "Кнопка 'Принять' должна быть отключена до прокрутки + флажка"
    )

    # Прокручиваем до конца
    sb = dialog.text.verticalScrollBar()
    sb.setValue(sb.maximum())
    dialog._on_scroll(sb.maximum())
    assert dialog._scrolled_to_end

    # Ставим флажок → кнопка активна
    dialog.accept_cb.setChecked(True)
    assert accept_btn.isEnabled()


@pytest.mark.qt
def test_eula_dialog_html_contains_revision(qtbot):
    dialog = EulaDialog()
    qtbot.addWidget(dialog)
    html = dialog.text.toPlainText()
    # toPlainText стирает HTML, проверяем через html()
    raw_html = dialog.text.toHtml()
    assert EULA_VERSION in raw_html, (
        f"EULA_VERSION={EULA_VERSION} должен быть в HTML диалога"
    )
