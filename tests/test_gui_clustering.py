"""Тесты вкладки «Кластерный анализ» (Шаг 7d)."""

import pytest

from fuzzy_core import FuzzySet, UniformFuzzyVariable
from gui.app import (
    METHOD_DENSITY,
    METHOD_KMEANS,
    METHOD_THRESHOLD,
    TAB_CLUSTERING,
    TAB_GENERATION,
    ClusteringTab,
    FuzzyApp,
)
from logger import SessionLogger


def make_sample() -> FuzzySet:
    """Три хорошо разделённые группы по четыре величины (центры −8, 0, 8)."""
    variables = []
    for center in (-8.0, 0.0, 8.0):
        for offset in (-0.3, -0.1, 0.1, 0.3):
            variables.append(
                UniformFuzzyVariable(center + offset - 0.5, center + offset + 0.5)
            )
    return FuzzySet(variables)


@pytest.fixture
def messages():
    return []


@pytest.fixture
def results():
    return []


@pytest.fixture
def sample():
    return make_sample()


@pytest.fixture
def tab(tk_window, tmp_path, messages, results, sample):
    logger = SessionLogger(tmp_path)
    widget = ClusteringTab(
        tk_window,
        logger,
        lambda: sample,
        on_message=messages.append,
        on_result=results.append,
    )
    yield widget
    if not logger.closed:
        logger.close()


def result_text(tab) -> str:
    return tab.result_label.cget("text")


def legend_texts(tab) -> list:
    """Подписи строк панели легенды (например, ``кластер 3``)."""
    return tab.legend_panel.captions


# ----------------------------------------------------------------------
# Начальное состояние
# ----------------------------------------------------------------------
def test_sample_info_when_sample_exists(tab, sample):
    assert f"Доступна выборка: {len(sample)} величин." == tab.sample_label.cget("text")


def test_sample_info_when_no_sample(tk_window, tmp_path):
    widget = ClusteringTab(tk_window, SessionLogger(tmp_path), lambda: None)
    try:
        assert "не сгенерирована" in widget.sample_label.cget("text")
    finally:
        widget.logger.close()


def test_defaults(tab):
    assert tab.method_var.get() == METHOD_KMEANS
    assert tab.metric_var.get() == "hausdorff"
    assert tab.k_entry.text == "3"
    assert tab.threshold_entry.text == "1.0"
    assert tab.eps_entry.text == "0.5"
    assert tab.min_points_entry.text == "2"
    assert tab.seed_entry.text == ""
    assert tab.result is None
    assert "не выполнялся" in result_text(tab)
    assert tab.cluster_table.row_count == 0
    assert tab.point_table.row_count == 0


def test_parameter_fields_switch_with_method(tab):
    def state(entry):
        return str(entry.entry.cget("state"))

    assert state(tab.k_entry) == "normal"
    assert state(tab.threshold_entry) == "disabled"
    assert state(tab.eps_entry) == "disabled"
    assert state(tab.seed_entry) == "normal"

    tab.method_var.set(METHOD_THRESHOLD)
    tab._update_parameter_state()
    assert state(tab.k_entry) == "disabled"
    assert state(tab.threshold_entry) == "normal"
    assert state(tab.seed_entry) == "disabled"

    tab.method_var.set(METHOD_DENSITY)
    tab._update_parameter_state()
    assert state(tab.eps_entry) == "normal"
    assert state(tab.min_points_entry) == "normal"
    assert state(tab.threshold_entry) == "disabled"
    assert state(tab.seed_entry) == "disabled"


def test_read_parameters_per_method(tab):
    parameters = tab.read_parameters(METHOD_KMEANS)
    assert parameters["k"] == 3
    assert isinstance(parameters["seed"], int)
    tab.threshold_entry.set("2,5")
    assert tab.read_parameters(METHOD_THRESHOLD) == {"threshold": 2.5}
    assert tab.read_parameters(METHOD_DENSITY) == {"eps": 0.5, "min_points": 2}


def test_non_integer_parameters_rejected(tab):
    tab.k_entry.set("3,5")
    with pytest.raises(ValueError):
        tab.read_parameters(METHOD_KMEANS)
    tab.min_points_entry.set("1,5")
    with pytest.raises(ValueError):
        tab.read_parameters(METHOD_DENSITY)


# ----------------------------------------------------------------------
# K-Means
# ----------------------------------------------------------------------
def test_kmeans_finds_three_groups(tab):
    tab.seed_entry.set("1")
    result = tab.run()

    assert result is not None
    assert result.method == "kmeans"
    assert result.metric == "hausdorff"
    assert len(result.clusters) == 3
    assert result.sizes == [4, 4, 4]
    assert result.noise == []
    assert tab.result is result
    assert tab.cluster_table.row_count == 3
    assert tab.point_table.row_count == 12


def test_kmeans_keeps_requested_seed(tab):
    tab.seed_entry.set("42")
    tab.run()
    assert "seed=42" in tab.logger.read()


def test_summary_contains_quality_marks(tab):
    tab.seed_entry.set("2")
    tab.run()
    text = result_text(tab)
    assert "Кластеров: 3" in text
    assert "размеры: 4, 4, 4" in text
    assert "средняя внутрикластерная дисперсия = " in text
    assert "максимальный диаметр = " in text
    assert "silhouette = " in text


def test_cluster_table_rows(tab):
    tab.seed_entry.set("3")
    result = tab.run()
    first = tab.cluster_table.row(0)
    assert first[0] == "1"
    assert first[1] == "4"
    assert float(first[2]) == pytest.approx(result.clusters[0].centroid.center)
    assert float(first[4]) == pytest.approx(result.clusters[0].diameter)
    assert float(first[5]) == pytest.approx(result.clusters[0].center_variance)


def test_point_table_shows_cluster_numbers(tab):
    tab.seed_entry.set("4")
    result = tab.run()
    for index, label in enumerate(result.labels):
        assert tab.point_table.row(index)[5] == str(label)


def test_plot_shows_points_and_centroids(tab):
    tab.seed_entry.set("5")
    tab.run()
    assert tab.plot.point_count == 12
    assert tab.plot.group_count == 3
    assert tab.plot.centroid_count == 3


def test_plot_and_tables_live_in_resizable_pane(tab):
    """График и таблицы — в раздвижной панели, поэтому не уезжают за край окна."""
    panes = [str(pane) for pane in tab.paned.panes()]
    assert len(panes) == 2
    assert str(tab.plot_area) in panes
    assert str(tab.table_notebook) in panes
    assert tab.table_notebook.index("end") == 2


def test_legend_button_is_disabled_before_run(tab):
    assert str(tab.legend_button.cget("state")) == "disabled"
    assert tab.legend_visible is False
    assert tab.plot_area.panes() == (str(tab.plot),)


def test_legend_panel_toggles_by_button(tab):
    """Кнопка показывает полную легенду и снова её скрывает."""
    tab.seed_entry.set("5")
    tab.run()

    assert tab.legend_button.cget("text") == "Показать легенду (3)"
    assert str(tab.legend_button.cget("state")) == "normal"

    assert tab.toggle_legend() is True
    assert tab.legend_visible is True
    assert [str(pane) for pane in tab.plot_area.panes()] == [
        str(tab.plot),
        str(tab.legend_panel),
    ]
    assert tab.legend_button.cget("text") == "Скрыть легенду"

    assert tab.toggle_legend() is False
    assert tab.plot_area.panes() == (str(tab.plot),)
    assert tab.legend_button.cget("text") == "Показать легенду (3)"


def test_legend_lists_every_cluster_with_its_color(tab):
    """В панели — по строке на кластер, цвета совпадают с точками на графике."""
    tab.method_var.set(METHOD_THRESHOLD)
    tab.threshold_entry.set("0.1")
    result = tab.run()

    assert len(result.clusters) > 10
    assert tab.legend_button.cget("text") == f"Показать легенду ({len(result.clusters)})"
    assert tab.legend_panel.item_count == len(result.clusters) + 1  # + центры

    colors = tab.plot.group_colors
    labels = legend_texts(tab)
    assert "кластер 0" in labels
    assert f"кластер {len(result.clusters) - 1}" in labels
    assert "центры кластеров" in labels
    assert len(set(colors.values())) == len(colors)  # цвет у каждого кластера свой


def test_legend_mentions_noise(tab):
    """Плотностной метод может помечать шум — он тоже должен быть в легенде."""
    tab.method_var.set(METHOD_DENSITY)
    tab.eps_entry.set("0.05")
    result = tab.run()

    assert len(result.clusters) == 0
    assert tab.plot.group_colors == {-1: "#7f7f7f"}
    assert tab.legend_button.cget("text") == "Показать легенду (1)"
    texts = legend_texts(tab)
    assert "шум" in texts


def test_legend_stays_open_after_new_run(tab):
    """Если легенда открыта, новый расчёт просто обновляет её содержимое."""
    tab.seed_entry.set("5")
    tab.run()
    tab.toggle_legend()
    assert tab.legend_panel.item_count == 4

    tab.k_entry.set("2")
    tab.run()
    assert tab.legend_visible is True
    assert tab.legend_panel.item_count == 3
    assert tab.legend_button.cget("text") == "Скрыть легенду"


def test_many_clusters_do_not_grow_the_legend(tab):
    """Пороговый метод даёт десятки кластеров — подписи уходят в панель легенды."""
    tab.method_var.set(METHOD_THRESHOLD)
    tab.threshold_entry.set("0.1")
    result = tab.run()

    assert len(result.clusters) > 10
    assert tab.cluster_table.row_count == len(result.clusters)
    assert tab.plot.axes.get_legend() is None
    assert len(tab.plot.axes.texts) == 0


def test_summary_limits_the_list_of_sizes(tk_window, tmp_path):
    """Список размеров обрезается, иначе сводка не влезает в панель."""
    sample = FuzzySet(
        [UniformFuzzyVariable(index * 3.0, index * 3.0 + 1.0) for index in range(20)]
    )
    widget = ClusteringTab(tk_window, SessionLogger(tmp_path), lambda: sample)
    try:
        widget.method_var.set(METHOD_THRESHOLD)
        widget.threshold_entry.set("0.1")
        result = widget.run()

        text = widget.result_label.cget("text")
        assert len(result.clusters) == 20
        assert "(всего 20)" in text
        assert len(text.splitlines()[1]) < 120
        assert "средняя внутрикластерная дисперсия" in text
        assert "silhouette" in text
    finally:
        widget.logger.close()


def test_log_and_status_message(tab, messages, results):
    tab.seed_entry.set("6")
    result = tab.run()

    assert results == [result]
    assert messages[-1] == "Кластеризация (K-Means: на K кластеров): кластеров 3, seed=6"
    log_text = tab.logger.read()
    assert "Кластеризация: метод=kmeans" in log_text
    assert "Кластер 1" in log_text


def test_second_run_replaces_previous_result(tab):
    tab.seed_entry.set("7")
    tab.run()
    tab.k_entry.set("2")
    second = tab.run()
    assert len(second.clusters) == 2
    assert tab.cluster_table.row_count == 2


# ----------------------------------------------------------------------
# Порог и плотность
# ----------------------------------------------------------------------
def test_threshold_clustering(tab):
    tab.method_var.set(METHOD_THRESHOLD)
    tab.threshold_entry.set("2.0")
    result = tab.run()

    assert result.method == "threshold"
    assert len(result.clusters) == 3
    assert sorted(result.sizes) == [4, 4, 4]
    assert tab.plot.group_count == 3


def test_threshold_too_small_gives_singletons(tab):
    tab.method_var.set(METHOD_THRESHOLD)
    tab.threshold_entry.set("0.01")
    result = tab.run()
    assert len(result.clusters) == 12
    assert result.sizes == [1] * 12


def test_density_clustering(tab):
    tab.method_var.set(METHOD_DENSITY)
    tab.eps_entry.set("1.0")
    tab.min_points_entry.set("2")
    result = tab.run()

    assert result.method == "density"
    assert len(result.clusters) == 3
    assert sorted(result.sizes) == [4, 4, 4]
    assert result.noise == []


def test_density_marks_noise_and_shows_it_in_table(tab):
    tab.method_var.set(METHOD_DENSITY)
    tab.eps_entry.set("0.05")
    result = tab.run()

    assert len(result.clusters) == 0
    assert len(result.noise) == 12
    assert "шумовых точек: 12" in result_text(tab)
    assert tab.point_table.row(0)[5] == "шум"
    assert tab.plot.group_count == 1
    assert tab.plot.centroid_count == 0


# ----------------------------------------------------------------------
# Метрика
# ----------------------------------------------------------------------
def test_euclidean_metric_can_be_used(tab):
    tab.metric_var.set("euclidean")
    tab.seed_entry.set("8")
    result = tab.run()
    assert result.metric == "euclidean"
    assert len(result.clusters) == 3
    assert "метрика euclidean" in tab.plot.axes.get_title()


def test_unknown_metric_reports_error(tab):
    tab.metric_var.set("манхэттен")
    assert tab.run() is None
    assert "Ошибка" in result_text(tab)


# ----------------------------------------------------------------------
# Ошибки
# ----------------------------------------------------------------------
def test_empty_sample_reports_error(tk_window, tmp_path):
    widget = ClusteringTab(tk_window, SessionLogger(tmp_path), lambda: FuzzySet())
    try:
        assert widget.run() is None
        assert "выборка пуста" in widget.result_label.cget("text")
        assert "ERROR" in widget.logger.read()
    finally:
        widget.logger.close()


def test_too_many_clusters_reports_error(tab):
    tab.k_entry.set("99")
    assert tab.run() is None
    assert "Ошибка" in result_text(tab)
    assert tab.cluster_table.row_count == 0
    assert tab.result is None


def test_zero_clusters_reports_error(tab):
    tab.k_entry.set("0")
    assert tab.run() is None
    assert "k" in result_text(tab)


def test_negative_threshold_reports_error(tab):
    tab.method_var.set(METHOD_THRESHOLD)
    tab.threshold_entry.set("-1")
    assert tab.run() is None
    assert "порог" in result_text(tab) or "threshold" in result_text(tab)


def test_zero_eps_reports_error(tab):
    tab.method_var.set(METHOD_DENSITY)
    tab.eps_entry.set("0")
    assert tab.run() is None
    assert "eps" in result_text(tab)


def test_error_after_success_clears_tables(tab):
    tab.seed_entry.set("9")
    assert tab.run() is not None

    tab.k_entry.set("99")
    assert tab.run() is None
    assert tab.result is None
    assert tab.cluster_table.row_count == 0
    assert tab.point_table.row_count == 0


# ----------------------------------------------------------------------
# Встраивание в главное окно
# ----------------------------------------------------------------------
def test_app_generates_sample_and_clusters_it(tk_window, tmp_path):
    application = FuzzyApp(master=tk_window, logger=SessionLogger(tmp_path))
    try:
        generation = application.tabs[TAB_GENERATION]
        generation.count_low.set("3")
        generation.count_high.set("3")
        generation.seed_entry.set("1")
        sample = generation.generate()

        widget = application.tabs[TAB_CLUSTERING]
        assert isinstance(widget, ClusteringTab)
        assert widget.current_sample() is sample

        application.notebook.select(application.tabs[TAB_CLUSTERING])
        application._on_tab_changed()
        assert f"{len(sample)} величин" in widget.sample_label.cget("text")

        widget.k_entry.set("2")
        widget.seed_entry.set("1")
        result = widget.run()

        assert application.clustering_result is result
        assert len(result.clusters) == 2
        assert "Кластеризация" in application.status_bar.message

        generation.clear()
        application.notebook.select(application.tabs[TAB_CLUSTERING])
        application._on_tab_changed()
        assert "не сгенерирована" in widget.sample_label.cget("text")
        assert widget.run() is None
    finally:
        application.close()
