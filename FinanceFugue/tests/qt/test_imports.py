def test_main_window_and_widgets_import():
    from src.main_window import FinanceFugueWindow
    from src.widgets import FileItemWidget, OrderWidget

    assert FinanceFugueWindow is not None
    assert OrderWidget is not None
    assert FileItemWidget is not None
