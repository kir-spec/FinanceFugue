from src.theme import (
    DIALOG_STYLESHEET,
    MAIN_WINDOW_STYLESHEET,
    NEW_ORDER_DIALOG_STYLESHEET,
    deadline_date_edit_style,
    money_input_style,
    payment_status_style,
)


def test_dialog_stylesheets_are_non_empty():
    assert "QDialog" in DIALOG_STYLESHEET
    assert "QMainWindow" in MAIN_WINDOW_STYLESHEET
    assert "QFormLayout" in NEW_ORDER_DIALOG_STYLESHEET


def test_dynamic_style_helpers():
    assert "#00D1FF" in money_input_style("#00D1FF")
    assert "#28A745" in payment_status_style("#28A745")
    assert "#FF4B2B" in deadline_date_edit_style("#FF4B2B", "#FF4B2B")
