"""Тесты вкладки «Арифметика» (Шаг 7b)."""

import math

import pytest
from tkinter import ttk

from fuzzy_core import UniformFuzzyVariable
from gui.app import TAB_ARITHMETIC, ArithmeticTab, FuzzyApp
from logger import SessionLogger


@pytest.fixture
def messages():
    return []


@pytest.fixture
def tab(tk_window, tmp_path, messages):
    logger = SessionLogger(tmp_path)
    widget = ArithmeticTab(tk_window, logger, on_message=messages.append)
    yield widget
    if not logger.closed:
        logger.close()


def result_text(tab) -> str:
    return tab.result_label.cget("text")


def set_inputs(tab, a_low, a_high, b_low, b_high) -> None:
    tab.a_low.set(a_low)
    tab.a_high.set(a_high)
    tab.b_low.set(b_low)
    tab.b_high.set(b_high)


# ----------------------------------------------------------------------
# Начальное состояние
# ----------------------------------------------------------------------
def test_default_values_and_plot(tab):
    assert (tab.a_low.text, tab.a_high.text) == ("1", "3")
    assert (tab.b_low.text, tab.b_high.text) == ("2", "5")
    assert tab.variable_a() == UniformFuzzyVariable(1, 3)
    assert tab.variable_b() == UniformFuzzyVariable(2, 5)
    assert tab.plot.curve_count == 2
    assert tab.plot.labels == ("A", "B")


def test_operation_buttons_exist(tab):
    assert set(tab.operation_buttons) == {"+", "-", "*", "/"}
    assert tab.compare_button is not None
    assert tab.metric_var.get() == "hausdorff"


def test_protocol_has_initial_hint(tab):
    assert "Введите границы" in tab.protocol.content


# ----------------------------------------------------------------------
# Арифметика
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "operation, expected",
    [
        ("+", (3.0, 8.0)),
        ("-", (-4.0, 1.0)),
        ("*", (2.0, 15.0)),
        ("/", (0.2, 1.5)),
    ],
)
def test_operations_give_interval_results(tab, operation, expected):
    result = tab.compute(operation)
    assert result is not None
    assert (result.a, result.b) == pytest.approx(expected)
    assert tab.last_result is result
    assert tab.last_operation == operation


def test_result_label_and_plot_after_operation(tab):
    tab.compute("+")
    text = result_text(tab)
    assert "A + B = [3.000, 8.000]" in text
    assert "центр c = 5.500" in text
    assert "ширина w = 5.000" in text
    assert tab.plot.curve_count == 3
    assert "= [3.000, 8.000]" in tab.plot.labels[2]


def test_operation_goes_to_protocol_and_log(tab):
    tab.compute("*")
    assert "Умножение" in tab.protocol.content
    assert "Операция Умножение (×): [1.000, 3.000]" in tab.protocol.content
    assert "= [2.000, 15.000]" in tab.protocol.content
    log_text = tab.logger.read()
    assert "Операция *" in log_text


def test_status_bar_message_after_operation(tab, messages):
    tab.compute("+")
    assert messages[-1] == "Выполнено: A + B = [3.000, 8.000]"


def test_negative_operands(tab):
    """Произведение отрицательного и положительного интервалов: min/max по всем парам."""
    set_inputs(tab, -5, -3, 1, 2)
    result = tab.compute("*")
    assert (result.a, result.b) == (-10.0, -3.0)


def test_comma_as_decimal_separator(tab):
    set_inputs(tab, "1,5", "2", "1", "1,5")
    result = tab.compute("+")
    assert (result.a, result.b) == (2.5, 3.5)


# ----------------------------------------------------------------------
# Ошибки ввода
# ----------------------------------------------------------------------
def test_division_by_interval_containing_zero_reports_error(tab):
    set_inputs(tab, 1, 3, -1, 1)
    assert tab.compute("/") is None
    assert result_text(tab).startswith("Ошибка")
    assert tab.last_result is None
    assert "ОШИБКА" in tab.protocol.content
    log_text = tab.logger.read()
    assert "ERROR" in log_text
    assert "Деление невозможно" in log_text


def test_reversed_bounds_report_error(tab):
    set_inputs(tab, 5, 1, 2, 5)
    assert tab.compute("+") is None
    assert "величина A" in result_text(tab)


def test_non_numeric_input_reports_error(tab):
    set_inputs(tab, "abc", 3, 2, 5)
    assert tab.compute("+") is None
    assert "Ошибка" in result_text(tab)
    assert "abc" in result_text(tab)


def test_empty_input_reports_error(tab):
    set_inputs(tab, "", 3, 2, 5)
    assert tab.compute("+") is None
    assert "не задано" in result_text(tab)


def test_error_after_success_resets_last_result(tab):
    assert tab.compute("+") is not None
    set_inputs(tab, 5, 1, 2, 5)
    assert tab.compute("+") is None
    assert tab.last_result is None


def test_unknown_operation_is_programming_error(tab):
    with pytest.raises(ValueError):
        tab.compute("^")


# ----------------------------------------------------------------------
# Сравнение
# ----------------------------------------------------------------------
def test_comparison_returns_metrics(tab):
    info = tab.compare()
    assert info is not None
    assert info["relation"] == -1
    assert info["hausdorff"] == pytest.approx(2.0)
    assert info["euclidean"] == pytest.approx(math.sqrt(2.5))
    assert info["selected"] == pytest.approx(2.0)
    for key in ("possibility", "necessity", "dominance"):
        assert 0.0 <= info[key] <= 1.0


def test_comparison_label_and_protocol(tab):
    tab.compare()
    text = result_text(tab)
    assert "A < B" in text
    assert "дом" in text.lower()
    assert "итог ранжирования: A < B" in tab.protocol.content
    assert tab.plot.curve_count == 2


def test_comparison_writes_log(tab):
    tab.compare()
    log_text = tab.logger.read()
    assert "Сравнение" in log_text
    assert "Сравнение индексов" in log_text


def test_metric_can_be_switched(tab):
    tab.metric_var.set("euclidean")
    info = tab.compare()
    assert info["selected"] == pytest.approx(math.sqrt(2.5))
    assert "евклидово расстояние" in tab.protocol.content


def test_unknown_metric_reports_error(tab):
    tab.metric_var.set("манхэттен")
    assert tab.compare() is None
    assert "Ошибка" in result_text(tab)


def test_comparison_of_equal_variables(tab):
    set_inputs(tab, 2, 4, 2, 4)
    info = tab.compare()
    assert info["relation"] == 0
    assert info["hausdorff"] == pytest.approx(0.0)
    assert "A = B" in result_text(tab)


# ----------------------------------------------------------------------
# Протокол
# ----------------------------------------------------------------------
def test_clear_protocol(tab):
    tab.compute("+")
    tab.clear_protocol()
    assert tab.protocol.content == "Протокол очищен."


# ----------------------------------------------------------------------
# Встраивание в главное окно
# ----------------------------------------------------------------------
def test_app_uses_arithmetic_tab(tk_window, tmp_path):
    application = FuzzyApp(master=tk_window, logger=SessionLogger(tmp_path))
    try:
        widget = application.tabs[TAB_ARITHMETIC]
        assert isinstance(widget, ArithmeticTab)
        assert isinstance(widget, ttk.Frame)
        assert widget.logger is application.logger

        widget.compute("+")
        assert "Выполнено" in application.status_bar.message
    finally:
        application.close()
