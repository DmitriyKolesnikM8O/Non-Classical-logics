"""Тесты вкладки «Генерация и выборка» (Шаг 7c)."""

import pytest

from fuzzy_core import FuzzySet
from gui.app import GenerationTab, FuzzyApp, TAB_GENERATION
from logger import SessionLogger


@pytest.fixture
def messages():
    return []


@pytest.fixture
def samples():
    return []


@pytest.fixture
def tab(tk_window, tmp_path, messages, samples):
    logger = SessionLogger(tmp_path)
    widget = GenerationTab(
        tk_window, logger, on_message=messages.append, on_sample=lambda *args: samples.append(args)
    )
    yield widget
    if not logger.closed:
        logger.close()


def result_text(tab) -> str:
    return tab.result_label.cget("text")


def set_counts(tab, low, high) -> None:
    tab.count_low.set(low)
    tab.count_high.set(high)


def pairs(sample) -> list:
    return [(variable.a, variable.b) for variable in sample]


# ----------------------------------------------------------------------
# Начальное состояние
# ----------------------------------------------------------------------
def test_default_parameters(tab):
    assert (tab.a_low.text, tab.a_high.text) == ("-10", "10")
    assert (tab.w_low.text, tab.w_high.text) == ("0", "4")
    assert (tab.count_low.text, tab.count_high.text) == ("100", "300")
    assert tab.seed_entry.text == ""
    assert tab.table.row_count == 0
    assert tab.sample is None
    assert "не сгенерирована" in result_text(tab)


def test_read_parameters_returns_tuples(tab):
    parameters = tab.read_parameters()
    assert parameters == {
        "a_range": (-10.0, 10.0),
        "width_range": (0.0, 4.0),
        "count_range": (100.0, 300.0),
    }


# ----------------------------------------------------------------------
# Генерация
# ----------------------------------------------------------------------
def test_generate_with_fixed_count_and_seed(tab):
    set_counts(tab, 5, 5)
    tab.seed_entry.set("42")
    sample = tab.generate()

    assert isinstance(sample, FuzzySet)
    assert len(sample) == 5
    assert tab.sample is sample
    assert tab.last_seed == 42
    assert tab.table.row_count == 5
    assert "Сгенерировано величин: 5" in result_text(tab)
    assert "seed = 42" in result_text(tab)


def test_generated_count_is_inside_default_range(tab):
    tab.seed_entry.set("7")
    sample = tab.generate()
    assert 100 <= len(sample) <= 300
    assert tab.table.row_count == len(sample)


def test_same_seed_gives_same_sample(tab):
    set_counts(tab, 8, 8)
    tab.seed_entry.set("123")
    first = tab.generate()
    second = tab.generate()
    assert pairs(first) == pairs(second)


def test_different_seeds_give_different_samples(tab):
    set_counts(tab, 8, 8)
    tab.seed_entry.set("1")
    first = tab.generate()
    tab.seed_entry.set("2")
    second = tab.generate()
    assert pairs(first) != pairs(second)


def test_empty_seed_uses_random_seed_and_reports_it(tab):
    set_counts(tab, 3, 3)
    first = tab.generate()
    first_seed = tab.last_seed
    first_text = result_text(tab)
    second = tab.generate()
    second_seed = tab.last_seed

    assert isinstance(first_seed, int)
    assert 1 <= first_seed < 10**9
    assert first_seed != second_seed
    assert f"seed = {first_seed!r}" in first_text
    assert pairs(first) != pairs(second)


def test_text_seed_is_allowed_and_reproducible(tab):
    set_counts(tab, 4, 4)
    tab.seed_entry.set("опыт")
    first = tab.generate()
    second = tab.generate()
    assert tab.last_seed == "опыт"
    assert pairs(first) == pairs(second)


def test_variables_respect_bounds(tab):
    set_counts(tab, 20, 20)
    tab.a_low.set("-1")
    tab.a_high.set("1")
    tab.w_low.set("0")
    tab.w_high.set("0.5")
    tab.seed_entry.set("5")
    sample = tab.generate()
    for variable in sample:
        assert -1.0 <= variable.a <= 1.0
        assert 0.0 <= variable.width <= 0.5


def test_random_count_varies_inside_range(tab):
    """При случайном зерне объём выборки меняется от запуска к запуску."""
    tab.count_low.set("2")
    tab.count_high.set("10")
    lengths = {len(tab.generate()) for _ in range(8)}
    assert lengths <= set(range(2, 11))
    assert len(lengths) > 1


# ----------------------------------------------------------------------
# Таблица и итоги
# ----------------------------------------------------------------------
def test_table_rows_match_sample(tab):
    set_counts(tab, 3, 3)
    tab.seed_entry.set("9")
    sample = tab.generate()

    assert tab.table.keys == ("index", "a", "b", "center", "width")
    first = tab.table.row(0)
    variable = sample[0]
    assert first == (
        "1",
        f"{variable.a:.3f}",
        f"{variable.b:.3f}",
        f"{variable.center:.3f}",
        f"{variable.width:.3f}",
    )
    assert tab.table.row(2)[0] == "3"


def test_summary_contains_statistics(tab):
    set_counts(tab, 5, 5)
    tab.seed_entry.set("3")
    sample = tab.generate()
    text = result_text(tab)
    assert f"{sample.mean_center():.3f}" in text
    assert f"{sample.mean_width():.3f}" in text
    assert "охватывающий интервал" in text
    assert "a ∈ [-10, 10]" in text


def test_generation_is_written_to_log(tab):
    set_counts(tab, 4, 4)
    tab.seed_entry.set("77")
    tab.generate()
    log_text = tab.logger.read()
    assert "Выборка (генератор (GUI)): элементов=4" in log_text
    assert "seed=77" in log_text
    assert "средний центр=" in log_text


def test_on_sample_callback_receives_data(tab, samples):
    set_counts(tab, 6, 6)
    tab.seed_entry.set("11")
    sample = tab.generate()

    assert len(samples) == 1
    received, seed, parameters = samples[0]
    assert received is sample
    assert seed == 11
    assert parameters["a_range"] == (-10.0, 10.0)
    assert parameters["count_range"] == (6.0, 6.0)


def test_status_message_after_generation(tab, messages):
    set_counts(tab, 2, 2)
    tab.seed_entry.set("1")
    tab.generate()
    assert messages[-1] == "Сгенерировано величин: 2 (seed=1)"


# ----------------------------------------------------------------------
# Ошибки ввода
# ----------------------------------------------------------------------
def test_reversed_a_range_reports_error(tab):
    tab.a_low.set("10")
    tab.a_high.set("-10")
    assert tab.generate() is None
    assert result_text(tab).startswith("Ошибка")
    assert "a_range" in result_text(tab)
    assert "ERROR" in tab.logger.read()


def test_negative_width_reports_error(tab):
    tab.w_low.set("-1")
    tab.w_high.set("1")
    assert tab.generate() is None
    assert "ширина" in result_text(tab).lower()


def test_count_must_be_integer(tab):
    set_counts(tab, "5,5", 10)
    assert tab.generate() is None
    assert "целым числом" in result_text(tab)


def test_reversed_count_range_reports_error(tab):
    set_counts(tab, 300, 100)
    assert tab.generate() is None
    assert "count_range" in result_text(tab)


def test_non_numeric_parameter_reports_error(tab):
    tab.a_low.set("abc")
    assert tab.generate() is None
    assert "Ошибка" in result_text(tab)
    assert "abc" in result_text(tab)


def test_error_clears_sample_and_table(tab):
    set_counts(tab, 3, 3)
    tab.seed_entry.set("1")
    assert tab.generate() is not None

    tab.a_low.set("10")
    tab.a_high.set("-10")
    assert tab.generate() is None
    assert tab.sample is None
    assert tab.table.row_count == 0


# ----------------------------------------------------------------------
# Очистка
# ----------------------------------------------------------------------
def test_clear_resets_everything(tab, samples):
    set_counts(tab, 3, 3)
    tab.seed_entry.set("1")
    tab.generate()

    tab.clear()
    assert tab.sample is None
    assert tab.last_seed is None
    assert tab.last_parameters == {}
    assert tab.table.row_count == 0
    assert "не сгенерирована" in result_text(tab)
    assert samples[-1] == (None, None, {})


# ----------------------------------------------------------------------
# Встраивание в главное окно
# ----------------------------------------------------------------------
def test_app_shares_sample_with_other_tabs(tk_window, tmp_path):
    application = FuzzyApp(master=tk_window, logger=SessionLogger(tmp_path))
    try:
        widget = application.tabs[TAB_GENERATION]
        assert isinstance(widget, GenerationTab)
        assert application.sample is None

        widget.count_low.set("3")
        widget.count_high.set("3")
        widget.seed_entry.set("5")
        sample = widget.generate()

        assert application.sample is sample
        assert application.sample_seed == 5
        assert application.sample_parameters["count_range"] == (3.0, 3.0)
        assert "Сгенерировано" in application.status_bar.message

        widget.clear()
        assert application.sample is None
        assert application.sample_seed is None
    finally:
        application.close()
