"""Тесты модуля графиков (Шаг 7b)."""

import math

import pytest

from fuzzy_core import UniformFuzzyVariable
from gui.plotter import COLORS, MembershipPlot, distinct_colors, membership_points


# ----------------------------------------------------------------------
# Набор цветов для групп
# ----------------------------------------------------------------------
def test_distinct_colors_uses_fixed_palette_first():
    assert distinct_colors(0) == []
    assert distinct_colors(3) == list(COLORS[:3])


def test_distinct_colors_unique_for_many_groups():
    """Хватает и на 36 кластеров, и на максимальную выборку в 300 величин."""
    for count in (9, 36, 92, 300):
        colors = distinct_colors(count)
        assert len(colors) == count
        assert len(set(colors)) == count
        assert all(color.startswith("#") for color in colors)


def test_neighbouring_groups_get_distant_colors():
    """Кластеры 0 и 1 стоят на графике рядом — цвета не должны быть похожими."""
    colors = distinct_colors(36)

    def rgb(color: str) -> tuple:
        return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))

    distances = [
        math.dist(rgb(first), rgb(second)) for first, second in zip(colors, colors[1:])
    ]
    assert min(distances) > 200  # в 8-битных каналах, максимум ~441


def test_distinct_colors_are_pale_enough_for_white_background():
    """Все цвета темнее белого фона: ни один не сливается с подложкой."""

    def brightness(color: str) -> float:
        red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
        return 0.299 * red + 0.587 * green + 0.114 * blue

    assert max(brightness(color) for color in distinct_colors(300)) < 220


# ----------------------------------------------------------------------
# Точки функции принадлежности
# ----------------------------------------------------------------------
def test_membership_points_form_trapezoid():
    variable = UniformFuzzyVariable(2.0, 5.0)
    xs, ys = membership_points(variable, pad=1.0)
    assert xs == [1.0, 2.0, 5.0, 6.0]
    assert ys == [0.0, 1.0, 1.0, 0.0]


def test_membership_points_negative_interval():
    variable = UniformFuzzyVariable(-3.0, -1.0)
    xs, ys = membership_points(variable, pad=0.5)
    assert xs == [-3.5, -3.0, -1.0, -0.5]
    assert ys == [0.0, 1.0, 1.0, 0.0]


def test_membership_points_crisp_variable():
    xs, ys = membership_points(UniformFuzzyVariable(1.0, 1.0))
    assert xs == [0.0, 1.0, 1.0, 2.0]
    assert ys == [0.0, 1.0, 1.0, 0.0]


# ----------------------------------------------------------------------
# Виджет графика
# ----------------------------------------------------------------------
def test_plot_starts_empty(tk_window):
    plot = MembershipPlot(tk_window)
    assert plot.curve_count == 0
    assert plot.labels == ()
    assert plot.axes.get_xlabel() == "x"
    assert plot.axes.get_ylabel() == "μ(x)"


def test_show_variables_draws_curves_with_labels(tk_window):
    plot = MembershipPlot(tk_window)
    plot.show_variables(
        [UniformFuzzyVariable(1, 3), UniformFuzzyVariable(2, 5)],
        ["A = [1; 3]", "B = [2; 5]"],
    )
    assert plot.curve_count == 2
    assert plot.labels == ("A = [1; 3]", "B = [2; 5]")


def test_show_variables_without_labels_uses_bounds(tk_window):
    plot = MembershipPlot(tk_window)
    plot.show_variables([UniformFuzzyVariable(1.5, 2.5)])
    assert plot.curve_count == 1
    assert plot.labels == ("[1.5; 2.5]",)


def test_second_show_replaces_previous_curves(tk_window):
    plot = MembershipPlot(tk_window)
    plot.show_variables([UniformFuzzyVariable(1, 2)])
    plot.show_variables([UniformFuzzyVariable(1, 2), UniformFuzzyVariable(3, 4)])
    assert plot.curve_count == 2


def test_reset_clears_curves(tk_window):
    plot = MembershipPlot(tk_window)
    plot.show_variables([UniformFuzzyVariable(1, 2)])
    plot.reset()
    assert plot.curve_count == 0
    assert plot.labels == ()


def test_curve_points_match_membership(tk_window):
    plot = MembershipPlot(tk_window)
    variable = UniformFuzzyVariable(2.0, 5.0)
    plot.show_variables([variable])
    xs, ys = plot.curve_points(0)
    assert xs == [1.0, 2.0, 5.0, 6.0]
    assert ys == [0.0, 1.0, 1.0, 0.0]


def test_x_limits_cover_the_variables(tk_window):
    plot = MembershipPlot(tk_window)
    plot.show_variables([UniformFuzzyVariable(0, 4), UniformFuzzyVariable(-2, 7)])
    low, high = plot.x_limits
    assert low <= -3.0
    assert high >= 8.0


def test_save_writes_image_file(tk_window, tmp_path):
    plot = MembershipPlot(tk_window)
    plot.show_variables([UniformFuzzyVariable(1, 3)])
    target = tmp_path / "график.png"
    plot.save(target)
    assert target.exists()
    assert target.stat().st_size > 0
    assert target.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_toolbar_can_be_disabled(tk_window):
    assert MembershipPlot(tk_window).toolbar is not None
    assert MembershipPlot(tk_window, toolbar=False).toolbar is None


def test_many_variables_cycle_colors(tk_window):
    plot = MembershipPlot(tk_window)
    variables = [UniformFuzzyVariable(index, index + 1) for index in range(10)]
    plot.show_variables(variables)
    assert plot.curve_count == 10
    colors = [line.get_color() for line in plot.axes.get_lines()]
    assert len(colors) >= 10
    assert len(set(colors)) > 1


def test_invalid_variable_like_object_raises(tk_window):
    plot = MembershipPlot(tk_window)
    with pytest.raises(AttributeError):
        plot.show_variables(["не величина"])


# ----------------------------------------------------------------------
# Диаграмма рассеяния (кластеры)
# ----------------------------------------------------------------------
def test_show_scatter_draws_points_and_groups(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    points = [(0.0, 1.0), (0.1, 1.0), (8.0, 2.0)]
    plot.show_scatter(points, [0, 0, 1], centroids=[(0.05, 1.0), (8.0, 2.0)])

    assert plot.point_count == 3
    assert plot.group_count == 2
    assert plot.centroid_count == 2
    assert plot.labels == ("кластер 0", "кластер 1", "центры кластеров")
    assert plot.axes.get_xlabel() == "центр c"
    assert plot.axes.get_ylabel() == "ширина w"


def test_show_scatter_marks_noise(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    plot.show_scatter([(0.0, 0.0), (5.0, 5.0)], [-1, -1])
    assert plot.group_count == 1
    assert plot.labels == ("шум",)
    assert plot.axes.collections[0].get_facecolor()[0][:3] == pytest.approx(
        (0.4980392156862745, 0.4980392156862745, 0.4980392156862745)
    )


def test_show_scatter_requires_matching_sizes(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    with pytest.raises(ValueError):
        plot.show_scatter([(0.0, 0.0)], [0, 1])


def test_scatter_replaces_membership_curves(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    plot.show_variables([UniformFuzzyVariable(1, 2)])
    plot.show_scatter([(1.0, 1.0)], [0])
    assert plot.curve_count == 0
    assert plot.point_count == 1


def test_reset_clears_scatter(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    plot.show_scatter([(1.0, 1.0)], [0], centroids=[(1.0, 1.0)])
    plot.reset()
    assert plot.point_count == 0
    assert plot.group_count == 0
    assert plot.centroid_count == 0


# ----------------------------------------------------------------------
# Поведение при большом числе групп: легенда не должна закрывать график
# ----------------------------------------------------------------------
def test_scatter_legend_hidden_for_many_groups(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    groups = [index // 4 for index in range(4 * 25)]

    assert not plot.axes.get_legend()  # до отрисовки легенды нет
    plot.show_scatter([(float(i), float(i % 7)) for i in range(len(groups))], groups)

    assert plot.axes.get_legend() is None
    assert len(plot.axes.texts) == 0  # никаких надписей поверх графика
    assert len(plot.group_colors) == 25


def test_scatter_shows_legend_for_few_groups(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    plot.show_scatter([(0.0, 1.0), (1.0, 1.0), (9.0, 1.0)], [0, 0, 1])
    legend = plot.axes.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["кластер 0", "кластер 1"]
    assert len(plot.axes.texts) == 0


def test_every_group_gets_its_own_color(tk_window):
    """36 кластеров — 36 разных цветов, а не 8 повторяющихся."""
    plot = MembershipPlot(tk_window, toolbar=False)
    groups = [index // 2 for index in range(72)]
    plot.show_scatter([(float(index), 1.0) for index in range(len(groups))], groups)

    colors = plot.group_colors
    assert len(colors) == 36
    assert len(set(colors.values())) == 36


def test_noise_keeps_grey_color(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    groups = [-1] + [index for index in range(11)]  # первая точка — шум
    plot.show_scatter([(float(index), 1.0) for index in range(len(groups))], groups)

    colors = plot.group_colors
    assert colors[-1] == "#7f7f7f"
    assert "#7f7f7f" not in [color for label, color in colors.items() if label >= 0]
    assert plot.group_sizes[-1] == 1


def test_curves_legend_hidden_when_too_many(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    variables = [UniformFuzzyVariable(index, index + 1) for index in range(12)]
    plot.show_variables(variables, [f"№{index + 1}" for index in range(12)])
    assert plot.axes.get_legend() is None
    assert any("легенда скрыта" in text.get_text() for text in plot.axes.texts)


def test_curves_legend_shown_normally(tk_window):
    plot = MembershipPlot(tk_window, toolbar=False)
    plot.show_variables([UniformFuzzyVariable(1, 2), UniformFuzzyVariable(3, 4)], ["A", "B"])
    legend = plot.axes.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["A", "B"]
