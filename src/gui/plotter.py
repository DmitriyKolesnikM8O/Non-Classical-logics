"""Построение графиков: функции принадлежности величин и диаграммы рассеяния.

Matplotlib встраивается в окно Tkinter через ``FigureCanvasTkAgg``; модуль
``pyplot`` не используется, поэтому графики строятся и в невизуальном режиме
(это важно для автотестов).

Рисуются любые объекты с атрибутами ``a``, ``b`` и ``center`` — то есть
экземпляры :class:`fuzzy_core.UniformFuzzyVariable`.
"""

from __future__ import annotations

import colorsys
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import to_hex
from matplotlib.figure import Figure

from fuzzy_core import NOISE_LABEL

__all__ = [
    "COLORS",
    "NOISE_COLOR",
    "MembershipPlot",
    "distinct_colors",
    "membership_points",
]

#: Набор цветов для кривых и кластеров.
COLORS: Tuple[str, ...] = (
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#ff7f0e",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#bcbd22",
)

#: Цвет точек шума (метка кластера -1).
NOISE_COLOR = "#7f7f7f"

#: Насыщенность и яркость цветов, полученных шагом по кругу оттенков.
HUE_SATURATION = 0.9
HUE_VALUE = 0.85

#: Шаг по кругу оттенков (золотое сечение) для больших наборов цветов.
HUE_STEP = 0.6180339887498949


def distinct_colors(count: int) -> List[str]:
    """Список различимых цветов заданной длины.

    До восьми групп берётся фиксированная палитра :data:`COLORS` (привычные
    цвета). Дальше цвета идут по кругу оттенков с шагом :data:`HUE_STEP`
    («золотое сечение»): соседние по номеру кластеры получают далёкие друг от
    друга цвета, а не два похожих оттенка рядом. Кластеры пронумерованы по
    расположению, поэтому на графике рядом стоят именно соседние номера.
    Насыщенность и яркость слегка уменьшены, чтобы жёлтые и голубые точки не
    сливались с белым фоном.
    """
    if count <= 0:
        return []
    if count <= len(COLORS):
        return list(COLORS[:count])
    return [
        to_hex(colorsys.hsv_to_rgb((index * HUE_STEP) % 1.0, HUE_SATURATION, HUE_VALUE))
        for index in range(count)
    ]


def membership_points(variable: Any, pad: float = 1.0) -> Tuple[List[float], List[float]]:
    """Точки ломаной μ(x) для равномерной величины: 0 → 1 на [a, b] → 0.

    Возвращает пару списков ``(x, y)``: слева от ``a`` и справа от ``b``
    функция принадлежности равна нулю, внутри отрезка — единице.
    """
    a = float(variable.a)
    b = float(variable.b)
    left = a - abs(pad)
    right = b + abs(pad)
    return [left, a, b, right], [0.0, 1.0, 1.0, 0.0]


class MembershipPlot(ttk.Frame):
    """Встраиваемый график функций принадлежности.

    Параметры
    ---------
    master:
        Родительский контейнер Tkinter.
    width, height:
        Размер области построения в дюймах.
    dpi:
        Разрешение рисунка.
    toolbar:
        Показывать ли панель инструментов matplotlib (масштаб, сохранение).
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        width: float = 6.4,
        height: float = 4.4,
        dpi: int = 100,
        toolbar: bool = True,
        title: str = "Функции принадлежности μ(x)",
    ) -> None:
        super().__init__(master)
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.toolbar: Optional[NavigationToolbar2Tk] = None
        if toolbar:
            self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            self.toolbar.update()
            self.toolbar.pack(side="bottom", fill="x")

        self.default_title = title
        self._labels: List[str] = []
        self._curves: List[Tuple[List[float], List[float]]] = []
        self._points: List[Tuple[float, float]] = []
        self._groups: List[int] = []
        self._centroids: List[Tuple[float, float]] = []
        self._group_colors: Dict[int, str] = {}
        self.reset()

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def reset(self, title: Optional[str] = None) -> None:
        """Очистить график и вернуть оси в исходное состояние."""
        self._prepare(title or self.default_title, "x", "μ(x)", ylim=(-0.08, 1.3))
        self.redraw()

    def _prepare(
        self,
        title: str,
        xlabel: str,
        ylabel: str,
        *,
        ylim: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Общая подготовка осей для любого вида графика."""
        self.axes.clear()
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        if ylim is not None:
            self.axes.set_ylim(*ylim)
        self.axes.set_title(title)
        self.axes.grid(True, linestyle=":", alpha=0.6)
        self._labels = []
        self._curves = []
        self._points = []
        self._groups = []
        self._centroids = []
        self._group_colors = {}
        self._profile: List[Tuple[float, int]] = []
        self._profile_current: Optional[float] = None
        self._matrix_size = 0
        self._matrix_alpha: Optional[float] = None
        self._matrix_order: Tuple[int, ...] = ()
        self._matrix_values: List[List[float]] = []

    def show_variables(
        self,
        variables: Iterable[Any],
        labels: Optional[Sequence[str]] = None,
        *,
        title: Optional[str] = None,
        pad: float = 1.0,
        show_center: bool = True,
        max_legend_items: int = 10,
    ) -> None:
        """Нарисовать функции принадлежности набора величин.

        ``labels`` — подписи для легенды; при нехватке подписей используется
        запись вида ``[a; b]``. Если кривых больше ``max_legend_items``,
        легенда не рисуется (она перекрыла бы график) — вместо неё выводится
        короткая пометка.
        """
        items = list(variables)
        captions = list(labels) if labels is not None else []
        self.reset(title)

        for index, variable in enumerate(items):
            color = COLORS[index % len(COLORS)]
            xs, ys = membership_points(variable, pad)
            caption = captions[index] if index < len(captions) else f"[{variable.a:g}; {variable.b:g}]"
            self.axes.fill(xs, ys, color=color, alpha=0.15)
            self.axes.plot(xs, ys, color=color, linewidth=2.0, label=caption)
            if show_center:
                self.axes.vlines(
                    float(variable.center),
                    0.0,
                    1.0,
                    color=color,
                    linestyle=":",
                    linewidth=1.0,
                    alpha=0.8,
                )
            self._curves.append((xs, ys))
            self._labels.append(caption)

        if items:
            if len(self._labels) <= max_legend_items:
                self.axes.legend(loc="upper right", fontsize=8)
            else:
                self._legend_note(
                    f"кривых: {len(self._labels)} — легенда скрыта, подписи в протоколе"
                )
            self.redraw()

    def show_scatter(
        self,
        points: Iterable[Tuple[float, float]],
        groups: Iterable[int],
        *,
        centroids: Iterable[Tuple[float, float]] = (),
        title: Optional[str] = None,
        xlabel: str = "центр c",
        ylabel: str = "ширина w",
        max_legend_items: int = 10,
    ) -> None:
        """Диаграмма рассеяния точек, раскрашенных по номерам кластеров.

        Точки с отрицательным номером кластера (``NOISE_LABEL``) считаются
        шумом и рисуются серым. Центры кластеров отмечаются ромбами. Каждая
        группа получает свой цвет (см. :func:`distinct_colors`); если групп
        больше ``max_legend_items``, подписи в угол графика не выводятся —
        полная легенда показывается отдельной панелью в интерфейсе.
        """
        items = [(float(x), float(y)) for x, y in points]
        labels = [int(group) for group in groups]
        if len(items) != len(labels):
            raise ValueError(
                f"точек {len(items)}, а меток кластеров {len(labels)} — размеры должны совпадать"
            )

        self._prepare(title or "Диаграмма рассеяния", xlabel, ylabel)
        self._points = items
        self._groups = labels
        self._centroids = [(float(x), float(y)) for x, y in centroids]

        ordered = sorted(set(labels))
        colored = [group for group in ordered if group >= 0]
        palette = distinct_colors(len(colored))
        self._group_colors = {
            group: palette[index] for index, group in enumerate(colored)
        }
        if NOISE_LABEL in ordered:
            self._group_colors[NOISE_LABEL] = NOISE_COLOR

        if len(ordered) > max_legend_items:
            # Много групп: одна коллекция точек с цветом на каждую точку вместо
            # сотен отдельных вызовов scatter. Иначе перерисовка при десятках
            # кластеров (и особенно пошаговая анимация) занимает секунды.
            show_legend = False
            self.axes.scatter(
                [x for x, _ in items],
                [y for _, y in items],
                s=26,
                alpha=0.8,
                edgecolors="none",
                c=[self._group_colors[label] for label in labels],
            )
        else:
            show_legend = True
            for group in ordered:
                pair = [
                    (x, y) for (x, y), label in zip(items, labels) if label == group
                ]
                caption = "шум" if group < 0 else f"кластер {group}"
                self.axes.scatter(
                    [x for x, _ in pair],
                    [y for _, y in pair],
                    s=26,
                    alpha=0.8,
                    edgecolors="none",
                    label=caption,
                    color=self._group_colors[group],
                )
                self._labels.append(caption)

        if self._centroids:
            self.axes.scatter(
                [x for x, _ in self._centroids],
                [y for _, y in self._centroids],
                marker="D",
                s=48,
                color="black",
                label="центры кластеров",
                zorder=3,
            )
            self._labels.append("центры кластеров")

        if items:
            if show_legend and self._labels:
                self.axes.legend(loc="upper right", fontsize=8)
            self.redraw()

    def show_alpha_profile(
        self,
        profile: Iterable[Any],
        *,
        current: Optional[float] = None,
        title: Optional[str] = None,
        xlabel: str = "уровень отбора α",
        ylabel: str = "число кластеров k(α)",
    ) -> None:
        """Кривая-ступенька ``k(α)``: как уровень отбора влияет на число кластеров.

        ``profile`` — последовательность словарей ``{"alpha": .., "cluster_count": ..}``
        (как их отдаёт :func:`fuzzy_core.alpha_cut_profile`). Ступеньки
        подчёркивают, что при изменении α число кластеров меняется скачками;
        ``current`` (если задан) отмечает текущий уровень вертикальной линией.
        """
        points = sorted(
            (float(point["alpha"]), int(point["cluster_count"])) for point in profile
        )
        self._prepare(
            title or "Профиль k(α): число кластеров от уровня отбора", xlabel, ylabel
        )
        self._profile = points
        self._profile_current = None if current is None else float(current)

        if points:
            xs = [alpha for alpha, _ in points]
            ys = [count for _, count in points]
            self.axes.step(
                xs,
                ys,
                where="post",
                color=COLORS[0],
                linewidth=2.0,
                marker="o",
                markersize=4,
                label="k(α)",
            )
            self.axes.set_ylim(0.0, max(ys) * 1.15 + 1.0)
            if self._profile_current is not None:
                self.axes.axvline(
                    self._profile_current,
                    color=COLORS[1],
                    linestyle="--",
                    linewidth=1.5,
                    label=f"текущий α = {self._profile_current:.2f}",
                )
            self.axes.legend(loc="upper right", fontsize=8)
        self.redraw()

    def show_similarity_matrix(
        self,
        matrix: Sequence[Sequence[float]],
        *,
        alpha: Optional[float] = None,
        order: Optional[Sequence[int]] = None,
        labels: Optional[Sequence[int]] = None,
        title: Optional[str] = None,
    ) -> None:
        """Тепловая карта матрицы сходства с подсветкой α-среза.

        ``order`` — перестановка индексов (например, «сначала кластер 0, потом
        кластер 1...»): строки и столбцы переставляются так, чтобы кластеры
        лежали блоками на диагонали. ``labels`` — метки кластеров в исходном
        порядке; по ним рисуются границы блоков. Клетки со сходством
        ``r_ij ≥ alpha`` подсвечиваются отдельным слоем поверх карты. Шкала
        сходства — от 0 до 1 (полоса цветов не рисуется, значение указано в
        пометке).
        """
        rows = [[float(value) for value in row] for row in matrix]
        size = len(rows)
        if any(len(row) != size for row in rows):
            raise ValueError("матрица сходства должна быть квадратной")

        if order is None:
            sequence = list(range(size))
        else:
            sequence = [int(index) for index in order]
            if sorted(sequence) != list(range(size)):
                raise ValueError("order должен быть перестановкой индексов 0..n-1")

        self._prepare(
            title or "Матрица сходства R (блоки = кластеры)",
            "индекс (упорядочено по кластерам)",
            "индекс (упорядочено по кластерам)",
        )
        self._matrix_size = size
        self._matrix_alpha = None if alpha is None else float(alpha)
        self._matrix_order = tuple(sequence)
        self._matrix_values = [[rows[i][j] for j in sequence] for i in sequence]
        # Тепловая карта: сетка осей и легенда здесь только мешают.
        self.axes.grid(False)
        if size == 0:
            self.redraw()
            return

        data = np.array(self._matrix_values)
        self.axes.imshow(
            data,
            vmin=0.0,
            vmax=1.0,
            cmap="viridis",
            interpolation="nearest",
            aspect="auto",
        )

        note = "шкала сходства r: 0 … 1"
        if self._matrix_alpha is not None:
            highlight = np.ma.masked_where(data < self._matrix_alpha, data)
            self.axes.imshow(
                highlight,
                vmin=0.0,
                vmax=1.0,
                cmap="autumn",
                interpolation="nearest",
                aspect="auto",
                alpha=0.45,
            )
            note += f"; подсвечено r ≥ α = {self._matrix_alpha:.2f}"

        if labels is not None:
            ordered_labels = [int(labels[i]) for i in sequence]
            for position in range(1, size):
                if ordered_labels[position] != ordered_labels[position - 1]:
                    boundary = position - 0.5
                    self.axes.axhline(boundary, color="white", linewidth=1.2)
                    self.axes.axvline(boundary, color="white", linewidth=1.2)

        self._legend_note(note)
        self.redraw()

    def _legend_note(self, text: str) -> None:
        """Короткая пометка вместо слишком большой легенды."""
        self.axes.text(
            0.99,
            0.98,
            text,
            transform=self.axes.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="#333333",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.85,
                  "edgecolor": "#bbbbbb"},
        )

    def redraw(self) -> None:
        """Перерисовать график."""
        try:
            self.canvas.draw_idle()
        except Exception:  # pragma: no cover - защита от состояний окна
            self.canvas.draw()

    def save(self, path: object, *, dpi: int = 150) -> object:
        """Сохранить текущий график в файл (PNG, PDF и т. п.)."""
        self.figure.savefig(path, dpi=dpi, bbox_inches="tight")
        return path

    # ------------------------------------------------------------------
    # Состояние (используется в тестах и других вкладках)
    # ------------------------------------------------------------------
    @property
    def curve_count(self) -> int:
        """Сколько кривых сейчас на графике."""
        return len(self._curves)

    @property
    def labels(self) -> Tuple[str, ...]:
        """Подписи нарисованных кривых."""
        return tuple(self._labels)

    def curve_points(self, index: int) -> Tuple[List[float], List[float]]:
        """Точки кривой по её номеру."""
        return self._curves[index]

    @property
    def x_limits(self) -> Tuple[float, float]:
        """Текущие границы оси абсцисс."""
        return tuple(self.axes.get_xlim())  # type: ignore[return-value]

    @property
    def point_count(self) -> int:
        """Число точек на диаграмме рассеяния."""
        return len(self._points)

    @property
    def group_count(self) -> int:
        """Число различных меток кластеров (с учётом шума)."""
        return len(set(self._groups))

    @property
    def centroid_count(self) -> int:
        """Число отмеченных центров кластеров."""
        return len(self._centroids)

    @property
    def group_colors(self) -> Dict[int, str]:
        """Соответствие «номер кластера → цвет точек» на текущей диаграмме."""
        return dict(self._group_colors)

    @property
    def group_sizes(self) -> Dict[int, int]:
        """Сколько точек нарисовано для каждого кластера."""
        sizes: Dict[int, int] = {}
        for group in self._groups:
            sizes[group] = sizes.get(group, 0) + 1
        return sizes

    @property
    def profile_points(self) -> Tuple[Tuple[float, int], ...]:
        """Точки кривой k(α) в порядке возрастания уровня."""
        return tuple(self._profile)

    @property
    def current_alpha(self) -> Optional[float]:
        """Отмеченный на профиле текущий уровень α (или ``None``)."""
        return self._profile_current

    @property
    def matrix_size(self) -> int:
        """Размер показанной матрицы сходства."""
        return self._matrix_size

    @property
    def matrix_alpha(self) -> Optional[float]:
        """Уровень α, которым подсвечена матрица (или ``None``)."""
        return self._matrix_alpha

    @property
    def matrix_order(self) -> Tuple[int, ...]:
        """Порядок индексов, в котором показана матрица."""
        return self._matrix_order

    @property
    def matrix_values(self) -> List[List[float]]:
        """Матрица сходства в показанном (переупорядоченном) виде."""
        return [list(row) for row in self._matrix_values]
