"""Тесты вкладки «Кластерный анализ» (Шаг 7d)."""

import pytest

from fuzzy_core import FuzzySet, UniformFuzzyVariable
from gui.app import (
    LINKAGE_LABELS,
    METHOD_ALPHA,
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


def test_all_methods_have_radio_buttons(tab):
    assert set(tab.method_buttons) == {
        METHOD_KMEANS,
        METHOD_THRESHOLD,
        METHOD_ALPHA,
        METHOD_DENSITY,
    }


def test_alpha_method_parameters(tab):
    tab.alpha_entry.set("0,8")
    assert tab.read_parameters(METHOD_ALPHA) == {"alpha": 0.8, "linkage": "complete"}
    tab.linkage_var.set(LINKAGE_LABELS["single"])
    assert tab.read_parameters(METHOD_ALPHA)["linkage"] == "single"


def test_alpha_parameter_fields_switch_with_method(tab):
    def state(entry):
        return str(entry.entry.cget("state"))

    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    assert state(tab.alpha_entry) == "normal"
    assert str(tab.linkage_box.cget("state")) == "readonly"
    assert state(tab.k_entry) == "disabled"
    assert state(tab.threshold_entry) == "disabled"
    assert state(tab.eps_entry) == "disabled"

    tab.method_var.set(METHOD_KMEANS)
    tab._update_parameter_state()
    assert state(tab.alpha_entry) == "disabled"
    assert str(tab.linkage_box.cget("state")) == "disabled"


def test_run_alpha_method_shows_level_profile(tab):
    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    result = tab.run()
    assert result is not None
    assert result.method == "alpha"
    assert len(result.clusters) >= 1
    text = result_text(tab)
    assert "k(α)" in text
    assert tab.profile and len(tab.profile) == 10


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
    assert tab.plot_area.panes() == (str(tab.view_notebook),)


def test_legend_panel_toggles_by_button(tab):
    """Кнопка показывает полную легенду и снова её скрывает."""
    tab.seed_entry.set("5")
    tab.run()

    assert tab.legend_button.cget("text") == "Показать легенду (3)"
    assert str(tab.legend_button.cget("state")) == "normal"

    assert tab.toggle_legend() is True
    assert tab.legend_visible is True
    assert [str(pane) for pane in tab.plot_area.panes()] == [
        str(tab.view_notebook),
        str(tab.legend_panel),
    ]
    assert tab.legend_button.cget("text") == "Скрыть легенду"

    assert tab.toggle_legend() is False
    assert tab.plot_area.panes() == (str(tab.view_notebook),)
    assert tab.legend_button.cget("text") == "Показать легенду (3)"


def test_legend_lists_every_cluster_with_its_color(tab):
    """В панели — по строке на кластер, цвета совпадают с точками на графике."""
    tab.method_var.set(METHOD_THRESHOLD)
    tab.threshold_entry.set("0.1")
    result = tab.run()

    assert len(result.clusters) > 10
    assert tab.legend_button.cget("text") == f"Показать легенду ({len(result.clusters)})"
    # Пока панель скрыта, строки не строятся (экономия на перерисовке).
    assert tab.legend_panel.item_count == 0

    tab.toggle_legend()
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
    tab.toggle_legend()
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


# ----------------------------------------------------------------------
# Интерактивный α-уровень: ползунок, профиль k(α), матрица сходства
# ----------------------------------------------------------------------
def run_alpha(tab, alpha="0.7"):
    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    tab.alpha_entry.set(alpha)
    return tab.run()


def test_alpha_slider_is_disabled_for_other_methods(tab):
    assert str(tab.alpha_scale.cget("state")) == "disabled"
    assert str(tab.play_button.cget("state")) == "disabled"
    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    assert str(tab.alpha_scale.cget("state")) == "normal"
    assert str(tab.play_button.cget("state")) == "normal"


def tab_state(tab, index):
    return str(tab.view_notebook.tab(index, "state"))


def test_alpha_only_tabs_are_disabled_for_other_methods(tab):
    assert tab_state(tab, 0) == "normal"
    assert tab_state(tab, 1) == "disabled"
    assert tab_state(tab, 2) == "disabled"


def test_alpha_tabs_enabled_for_alpha_method(tab):
    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    assert tab_state(tab, 0) == "normal"
    assert tab_state(tab, 1) == "normal"
    assert tab_state(tab, 2) == "normal"


def test_switching_away_from_alpha_disables_tabs_and_returns_to_diagram(tab):
    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    tab.view_notebook.select(2)  # открыта «Матрица сходства»

    tab.method_var.set(METHOD_THRESHOLD)
    tab._update_parameter_state()
    assert tab_state(tab, 1) == "disabled"
    assert tab_state(tab, 2) == "disabled"
    assert tab.view_notebook.index("current") == 0


def test_non_alpha_run_keeps_alpha_tabs_disabled(tab):
    tab.method_var.set(METHOD_DENSITY)
    tab._update_parameter_state()
    tab.eps_entry.set("1.0")
    tab.run()
    assert tab_state(tab, 1) == "disabled"
    assert tab_state(tab, 2) == "disabled"


def test_alpha_slider_syncs_entry_and_label(tab):
    tab.method_var.set(METHOD_ALPHA)
    tab._update_parameter_state()
    assert float(tab.alpha_scale.get()) == pytest.approx(0.7)
    tab.set_alpha_value(0.5)
    assert tab.alpha_entry.text == "0.50"
    assert tab.alpha_value_label.cget("text") == "α = 0.50"
    assert float(tab.alpha_scale.get()) == pytest.approx(0.5)


def test_alpha_scale_schedules_coalesced_recompute(tab):
    run_alpha(tab)
    tab._on_alpha_scale("0.5")
    assert tab.alpha_entry.text == "0.50"
    assert tab._alpha_job is not None
    # Повторное движение отменяет прежнюю задачу — пересчёт один.
    first_job = tab._alpha_job
    tab._on_alpha_scale("0.4")
    assert tab._alpha_job != first_job
    tab.after_cancel(tab._alpha_job)
    tab._alpha_job = None


def test_alpha_live_change_reclusters_without_logging(tab):
    result = run_alpha(tab)
    log_after_run = tab.logger.read()
    moved = tab.set_alpha_value(0.5)
    assert moved == pytest.approx(0.5)
    assert tab.result is not None
    assert tab.result.parameters["alpha"] == pytest.approx(0.5)
    # Живая перестройка не пишется в журнал заново.
    assert tab.logger.read() == log_after_run
    assert result is not tab.result


def test_alpha_live_change_uses_cached_engine(tab):
    run_alpha(tab)
    engine = tab.engine
    tab.set_alpha_value(0.6)
    assert tab.engine is engine  # матрицы не пересчитываются


def test_run_alpha_fills_profile_and_matrix_views(tab, sample):
    result = run_alpha(tab, "0.6")
    assert tab.profile_plot.profile_points
    assert len(tab.profile_plot.profile_points) == 10
    assert tab.profile_plot.current_alpha == pytest.approx(0.6)
    assert tab.matrix_plot.matrix_size == len(sample)
    assert tab.matrix_plot.matrix_alpha == pytest.approx(0.6)


def test_matrix_view_is_ordered_by_clusters(tab, sample):
    result = run_alpha(tab, "0.5")
    expected = [
        index
        for label in sorted(set(result.labels))
        for index, value in enumerate(result.labels)
        if value == label
    ]
    assert list(tab.matrix_plot.matrix_order) == expected
    assert sorted(tab.matrix_plot.matrix_order) == list(range(len(sample)))


def test_explicit_run_draws_all_views_regardless_of_active_tab(tab):
    tab.view_notebook.select(1)  # активна вкладка «Профиль k(α)»
    tab._update_parameter_state()
    run_alpha(tab, "0.6")
    assert tab._stale_views == set()
    assert tab.profile_plot.current_alpha == pytest.approx(0.6)
    assert tab.matrix_plot.matrix_alpha == pytest.approx(0.6)


def test_live_change_defers_hidden_views_until_tab_switch(tab):
    run_alpha(tab, "0.6")  # активна закладка «Диаграмма»
    tab.view_notebook.select(1)  # переключаемся на «Профиль k(α)»
    tab._on_view_changed()

    tab.set_alpha_value(0.5)  # живой пересчёт
    assert "matrix" in tab._stale_views
    assert "scatter" in tab._stale_views
    assert "profile" not in tab._stale_views
    assert tab.profile_plot.current_alpha == pytest.approx(0.5)
    assert tab.matrix_plot.matrix_alpha == pytest.approx(0.6)  # ещё старое

    tab.view_notebook.select(2)  # открываем «Матрицу сходства»
    tab._on_view_changed()
    assert "matrix" not in tab._stale_views
    assert tab.matrix_plot.matrix_alpha == pytest.approx(0.5)


def test_live_change_summary_skips_silhouette(tab):
    run_alpha(tab, "0.7")
    assert "silhouette = " in tab.result_label.cget("text")
    tab.set_alpha_value(0.5)
    assert "нажмите «Кластеризовать»" in tab.result_label.cget("text")


def test_non_alpha_run_clears_alpha_views(tab):
    run_alpha(tab)
    assert tab.profile_plot.profile_points
    tab.method_var.set(METHOD_THRESHOLD)
    tab._update_parameter_state()
    tab.threshold_entry.set("0.1")
    tab.run()
    assert tab.profile == []
    assert tab.profile_plot.profile_points == ()
    assert tab.matrix_plot.matrix_size == 0


def test_alpha_play_steps_through_levels(tab):
    run_alpha(tab)
    tab.start_alpha_play()
    assert tab._playing is True
    assert tab.play_button.cget("text") == "■"
    # start уже сделал первый шаг: α = 1.0.
    assert float(tab.alpha_entry.number()) == pytest.approx(1.0)
    assert tab.advance_alpha_play() == pytest.approx(0.9)
    assert float(tab.alpha_entry.number()) == pytest.approx(0.9)
    tab.stop_alpha_play()
    assert tab._playing is False
    assert tab.play_button.cget("text") == "▶"
    assert tab.advance_alpha_play() is None  # после остановки шаги не идут


def test_alpha_play_toggle_runs_and_stops(tab):
    run_alpha(tab)
    assert tab.toggle_alpha_play() is True
    assert tab._playing is True
    assert tab.toggle_alpha_play() is False
    assert tab._playing is False


def test_alpha_play_finishes_and_resets_button(tab):
    run_alpha(tab)
    tab.start_alpha_play()
    for _ in range(len(tab._play_levels)):
        tab.advance_alpha_play()
    assert tab.advance_alpha_play() is None
    tab.stop_alpha_play()
    assert tab.play_button.cget("text") == "▶"


def test_alpha_play_stops_when_switching_method(tab):
    run_alpha(tab)
    tab.start_alpha_play()
    assert tab._playing is True
    tab.method_var.set(METHOD_KMEANS)
    tab._update_parameter_state()
    assert tab._playing is False


# ----------------------------------------------------------------------
# Пошаговая агломерация
# ----------------------------------------------------------------------
def select_threshold(tab):
    tab.method_var.set(METHOD_THRESHOLD)
    tab._update_parameter_state()


def test_step_controls_disabled_for_non_threshold(tab):
    assert str(tab.step_button.cget("state")) == "disabled"
    assert str(tab.step_play_button.cget("state")) == "disabled"
    assert str(tab.step_reset_button.cget("state")) == "disabled"
    assert tab.step_agglomeration() is None


def test_step_controls_enabled_for_threshold(tab):
    select_threshold(tab)
    for widget in (tab.step_button, tab.step_play_button, tab.step_reset_button):
        assert str(widget.cget("state")) == "normal"


def test_reset_shows_initial_state(tab, sample):
    select_threshold(tab)
    # С галочкой «на пороге» предел = cut_step, но при шаге 0 текст = 0/limit.
    tab.step_stop_var.set(False)  # тестируем полный процесс, как раньше
    trace = tab.reset_agglomeration()
    assert tab.trace is trace
    assert tab.step_index == 0
    assert tab.step_label.cget("text") == f"шаг 0/{len(trace.merges)}"
    # шагов не выполнено: кластеров нет, все точки отмечены как шум
    assert tab.result is not None
    assert len(tab.result.clusters) == 0
    assert tab.result.noise == list(range(len(sample)))


def test_step_agglomeration_decreases_cluster_count(tab, sample):
    select_threshold(tab)
    # Отключаем галочку «на пороге», чтобы тест проверял полный процесс.
    tab.step_stop_var.set(False)
    total = len(tab.get_trace(sample, "hausdorff").merges)
    assert tab.step_agglomeration() == 1
    assert tab.step_label.cget("text") == f"шаг 1/{total}"
    counts = [len(tab.result.clusters)]
    for _ in range(3):
        tab.step_agglomeration()
        counts.append(len(tab.result.clusters))
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == len(sample) - 1


def test_step_agglomeration_runs_to_single_cluster(tab, sample):
    select_threshold(tab)
    # Отключаем ограничение порогом, чтобы дойти до 1 кластера.
    tab.step_stop_var.set(False)
    trace = tab.get_trace(sample, "hausdorff")
    for _ in range(len(trace.merges)):
        assert tab.step_agglomeration() is not None
    assert len(tab.result.clusters) == 1
    assert tab.step_agglomeration() is None  # шагов больше нет


def test_step_agglomeration_logs_each_merge(tab):
    select_threshold(tab)
    tab.step_agglomeration()
    content = tab.logger.read()
    assert "Агломерация" in content
    assert "шаг 1" in content


def test_step_agglomeration_requires_sample(tk_window, tmp_path):
    logger = SessionLogger(tmp_path)
    try:
        widget = ClusteringTab(tk_window, logger, lambda: None)
        widget.method_var.set(METHOD_THRESHOLD)
        widget._update_parameter_state()
        assert widget.step_agglomeration() is None
        assert "Ошибка" in result_text(widget)
    finally:
        logger.close()


def test_step_play_toggles_and_steps(tab):
    select_threshold(tab)
    tab.reset_agglomeration()
    assert tab.toggle_step_play() is True
    assert tab._step_playing is True
    assert tab.step_play_button.cget("text") == "■"
    assert tab.step_index == 1  # start уже сделал первый шаг
    assert tab.toggle_step_play() is False
    assert tab._step_playing is False
    assert tab.step_play_button.cget("text") == "▶"


def test_step_play_stops_when_switching_method(tab):
    select_threshold(tab)
    tab.start_step_play()
    assert tab._step_playing is True
    tab.method_var.set(METHOD_KMEANS)
    tab._update_parameter_state()
    assert tab._step_playing is False
    assert tab.step_play_button.cget("text") == "▶"


def test_step_play_restarts_after_finishing(tab, sample):
    select_threshold(tab)
    # Без ограничения порогом проигрывание доходит до конца и перезапускается.
    tab.step_stop_var.set(False)
    trace = tab.get_trace(sample, "hausdorff")
    for _ in range(len(trace.merges)):
        tab.step_agglomeration()
    assert tab.step_index == len(trace.merges)
    tab.start_step_play()
    assert tab.step_index == 1  # дошли до конца — начали заново
    tab.stop_step_play()


def test_step_trace_cached_per_sample_and_metric(tab, sample):
    select_threshold(tab)
    first = tab.get_trace(sample, "hausdorff")
    assert tab.get_trace(sample, "hausdorff") is first
    assert tab.get_trace(sample, "euclidean") is not first


def test_step_run_uses_threshold_result_and_keeps_steps(tab, sample):
    select_threshold(tab)
    tab.step_agglomeration()
    assert tab.result is not None
    assert tab.result.method == METHOD_THRESHOLD
    assert tab.result.parameters["step"] == 1
    assert tab.result.parameters["steps_total"] == len(sample) - 1


def test_step_play_defers_tables_until_stop(tab, sample):
    """Во время проигрывания таблицы не пересобираются — это дорого."""
    select_threshold(tab)
    tab.reset_agglomeration()
    assert tab.cluster_table.row_count == 0  # шагов ещё нет

    tab.start_step_play()
    tab.step_agglomeration(update_tables=False)
    tab.step_agglomeration(update_tables=False)

    assert tab._step_playing is True
    assert tab._step_ui_stale is True
    assert len(tab.result.clusters) == len(sample) - 3
    assert tab.cluster_table.row_count == 0  # таблица ждёт остановки

    tab.stop_step_play()
    assert tab._step_ui_stale is False
    assert tab.cluster_table.row_count == len(sample) - 3
    assert tab.point_table.row_count == len(sample)


def test_step_play_refreshes_open_legend_on_stop(tab, sample):
    select_threshold(tab)
    tab.reset_agglomeration()
    assert tab.toggle_legend() is True
    assert tab.legend_panel.item_count == 2  # шум + центры

    tab.start_step_play()
    tab.step_agglomeration(update_tables=False)
    assert tab.legend_panel.item_count == 2  # пока проигрываем — старая

    tab.stop_step_play()
    assert tab.legend_panel.item_count == len(sample) - 2 + 1  # кластеры + центры


# ----------------------------------------------------------------------
# Скорость пошагового проигрывания
# ----------------------------------------------------------------------
def test_step_speed_default(tab):
    select_threshold(tab)
    assert tab.step_speed_label.cget("text") == "2.5/с"
    assert tab.step_interval_ms() == 400


def test_step_speed_sets_interval(tab):
    select_threshold(tab)
    assert tab.set_step_speed(20) == pytest.approx(20.0)
    assert tab.step_interval_ms() == 50
    assert tab.step_speed_label.cget("text") == "20.0/с"
    assert tab.set_step_speed(1) == pytest.approx(1.0)
    assert tab.step_interval_ms() == 1000


def test_step_speed_is_clamped(tab):
    select_threshold(tab)
    assert tab.set_step_speed(100) == pytest.approx(20.0)
    assert tab.set_step_speed(0.1) == pytest.approx(1.0)


def test_step_speed_disabled_for_non_threshold(tab):
    assert str(tab.step_speed_scale.cget("state")) == "disabled"
    select_threshold(tab)
    assert str(tab.step_speed_scale.cget("state")) == "normal"


def test_step_speed_reschedules_while_playing(tab):
    select_threshold(tab)
    tab.start_step_play()
    assert tab._step_playing is True
    assert tab._step_job is not None
    tab.set_step_speed(20)
    assert tab._step_playing is True
    assert tab.step_interval_ms() == 50
    tab.stop_step_play()


def test_step_speed_does_not_schedule_when_idle(tab):
    select_threshold(tab)
    tab.set_step_speed(20)
    assert tab._step_playing is False
    assert tab._step_job is None


def test_clustering_tab_left_panel_mousewheel(tab):
    from types import SimpleNamespace
    import tkinter as tk

    assert isinstance(tab.panel_outer, tk.Canvas)
    assert tab.panel_outer.bind("<MouseWheel>")
    assert tab.panel_frame.bind("<MouseWheel>")
    assert tab.run_button.bind("<MouseWheel>")
    assert tab.sample_label.bind("<MouseWheel>")

    assert tab._on_panel_mousewheel(SimpleNamespace(delta=-120)) == "break"
    assert tab._on_panel_mousewheel(SimpleNamespace(delta=120)) == "break"
    assert tab._on_panel_mousewheel(SimpleNamespace(num=4, delta=0)) == "break"
    assert tab._on_panel_mousewheel(SimpleNamespace(num=5, delta=0)) == "break"
    assert tab._on_panel_mousewheel(SimpleNamespace(num=0, delta=0)) == "break"

