"""Главное окно приложения и вкладки.

Каркас интерфейса: меню, вкладки, строка состояния и журнал сессии.
Содержимое вкладок наполняется на последующих шагах разработки.
"""

from __future__ import annotations

import argparse
import operator
import random
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import fuzzy_core
from fuzzy_core import (
    DEFAULT_ALPHA_GRID,
    DISTANCE_METRICS,
    MAX_COUNT,
    MIN_COUNT,
    NOISE_LABEL,
    Agglomeration,
    AlphaClusterer,
    ClusterResult,
    FuzzySet,
    UniformFuzzyVariable,
    agglomerate,
    cluster,
    generate_sample,
    get_distance_function,
    grouped_result,
)
from logger import SessionLogger, describe_variable, format_variable

from .plotter import MembershipPlot
from .widgets import (
    HINT_COLOR,
    TEXT_FONT,
    LabeledEntry,
    LegendPanel,
    PlaceholderTab,
    ProtocolView,
    StatusBar,
    Table,
    center_window,
)

__all__ = [
    "FuzzyApp",
    "ArithmeticTab",
    "GenerationTab",
    "ClusteringTab",
    "LogTab",
    "main",
    "APP_TITLE",
    "TAB_TITLES",
    "WINDOW_SIZE",
]

APP_TITLE = "Неклассические логики — нечеткие величины (вариант 1: равномерное распределение)"
WINDOW_SIZE = (1180, 780)
MIN_SIZE = (900, 600)

TAB_ARITHMETIC = "Арифметика"
TAB_GENERATION = "Генерация и выборка"
TAB_CLUSTERING = "Кластерный анализ"
TAB_LOG = "Журнал"

TAB_TITLES: Sequence[str] = (TAB_ARITHMETIC, TAB_GENERATION, TAB_CLUSTERING, TAB_LOG)

TAB_DESCRIPTIONS: Dict[str, str] = {
    TAB_ARITHMETIC: (
        "Интерактивный калькулятор нечетких величин: ввод величин A и B, выбор операции, "
        "протокол вычислений и графики функций принадлежности."
    ),
    TAB_GENERATION: (
        "Генерация случайной выборки нечетких величин (100–300 элементов) с настраиваемыми "
        "диапазонами и зерном генератора; просмотр выборки в таблице."
    ),
    TAB_CLUSTERING: (
        "Кластерный анализ множества величин: на заданное число кластеров, по порогу "
        "внутрикластерного расстояния, по α-уровню или по плотности; таблица результатов "
        "и диаграмма."
    ),
    TAB_LOG: (
        "Журнал текущей сессии с метками времени: просмотр и сохранение в отдельный файл."
    ),
}

TAB_HINTS: Dict[str, Sequence[str]] = {
    TAB_ARITHMETIC: ("Операции: сложение, вычитание, умножение, деление, сравнение",),
    TAB_GENERATION: ("Параметры: a ~ U(-10, 10), w ~ U(0, 4), объём 100…300, seed",),
    TAB_CLUSTERING: (
        "Методы: K-Means, пороговый (полная связь), по α-уровню, плотностной (DBSCAN)",
    ),
    TAB_LOG: ("Все действия записываются в файл logs/session_<дата>_<время>.log",),
}


class FuzzyApp:
    """Главное окно приложения.

    Параметры
    ---------
    master:
        Родительское окно; если не задано, создаётся новое ``tk.Tk()``.
    logger:
        Готовый журнал сессии; если не задан, создаётся :class:`SessionLogger`.
    log_dir:
        Каталог журналов (используется, только если ``logger`` не задан).
    """

    def __init__(
        self,
        master: Optional[tk.Misc] = None,
        *,
        logger: Optional[SessionLogger] = None,
        log_dir: Optional[object] = None,
    ) -> None:
        self.root: tk.Misc = master if master is not None else tk.Tk()
        self.logger = logger if logger is not None else SessionLogger(log_dir)
        self._closed = False
        self.tabs: Dict[str, ttk.Frame] = {}

        #: Последняя сгенерированная выборка — общие данные для вкладок.
        self.sample: Optional[FuzzySet] = None
        self.sample_seed: Optional[object] = None
        self.sample_parameters: Dict[str, object] = {}
        #: Последний результат кластерного анализа.
        self.clustering_result: Optional[ClusterResult] = None

        self._configure_window()
        self._build_menu()
        self._build_status_bar()
        self._build_tabs()

        self.logger.session_started(f"версия ядра {fuzzy_core.__version__}")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _configure_window(self) -> None:
        self.root.title(APP_TITLE)
        width, height = WINDOW_SIZE
        center_window(self.root, width, height)
        try:
            self.root.minsize(*MIN_SIZE)
        except tk.TclError:
            pass

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Открыть папку журналов", command=self.open_log_dir)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.close)
        menu_bar.add_cascade(label="Файл", menu=file_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.show_about)
        menu_bar.add_cascade(label="Справка", menu=help_menu)

        self.main_menu = menu_bar
        self.file_menu = file_menu
        self.help_menu = help_menu
        self.root["menu"] = menu_bar

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        for title in TAB_TITLES:
            if title == TAB_ARITHMETIC:
                tab: ttk.Frame = ArithmeticTab(
                    self.notebook, self.logger, on_message=self.set_status
                )
            elif title == TAB_GENERATION:
                tab = GenerationTab(
                    self.notebook,
                    self.logger,
                    on_message=self.set_status,
                    on_sample=self.remember_sample,
                )
            elif title == TAB_CLUSTERING:
                tab = ClusteringTab(
                    self.notebook,
                    self.logger,
                    self.get_sample,
                    on_message=self.set_status,
                    on_result=self.remember_clustering,
                )
            elif title == TAB_LOG:
                tab = LogTab(self.notebook, self.logger, on_message=self.set_status)
            else:
                tab = PlaceholderTab(
                    self.notebook,
                    title,
                    description=TAB_DESCRIPTIONS[title],
                    hints=TAB_HINTS[title],
                )
            self.notebook.add(tab, text=title)
            self.tabs[title] = tab

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_status_bar(self) -> None:
        self.status_bar = StatusBar(self.root, "Готово", self.logger.log_path)
        self.status_bar.pack(side="bottom", fill="x")

    def set_status(self, text: str) -> None:
        """Показать сообщение в строке состояния."""
        self.status_bar.set_message(text)

    def remember_sample(
        self, sample: Optional[FuzzySet], seed: object = None, parameters: Optional[Dict] = None
    ) -> None:
        """Запомнить выборку, сгенерированную на вкладке «Генерация и выборка»."""
        self.sample = sample
        self.sample_seed = seed if sample is not None else None
        self.sample_parameters = dict(parameters or {}) if sample is not None else {}
        self.clustering_result = None

    def get_sample(self) -> Optional[FuzzySet]:
        """Текущая выборка для кластерного анализа."""
        return self.sample

    def remember_clustering(self, result: object) -> None:
        """Запомнить результат кластерного анализа."""
        self.clustering_result = result

    def _on_tab_changed(self, event: Optional[object] = None) -> None:
        """Обновить данные вкладки, на которую переключился пользователь."""
        if self._closed:
            return
        try:
            current = self.notebook.nametowidget(self.notebook.select())
        except (tk.TclError, KeyError):  # pragma: no cover - окно уже закрывается
            return
        activated = getattr(current, "on_tab_activated", None)
        if callable(activated):
            activated()

    # ------------------------------------------------------------------
    # Действия меню
    # ------------------------------------------------------------------
    def open_log_dir(self) -> None:
        """Открыть каталог журналов в системном файловом менеджере."""
        path = self.logger.log_dir
        try:
            if sys.platform.startswith("win"):
                import os

                os.startfile(path)  # type: ignore[attr-defined]
            else:  # pragma: no cover - поведение других платформ
                import subprocess

                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(path)])
            self.status_bar.set_message(f"Открыт каталог журналов: {path}")
            self.logger.info(f"Открыт каталог журналов: {path}")
        except Exception as exc:  # pragma: no cover - зависит от окружения
            self.status_bar.set_message(f"Не удалось открыть каталог журналов: {exc}")
            self.logger.log_error("Не удалось открыть каталог журналов", str(exc))

    def show_about(self) -> None:
        """Показать краткие сведения о программе."""
        messagebox.showinfo(
            "О программе",
            f"{APP_TITLE}\n\n"
            f"Ядро библиотеки: fuzzy_core {fuzzy_core.__version__}\n"
            f"Язык реализации: Python, интерфейс — Tkinter\n\n"
            "Модель: нечеткие величины с равномерной функцией принадлежности "
            "на отрезке [a, b].",
            parent=self.root,
        )

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------
    @property
    def closed(self) -> bool:
        return self._closed

    def run(self) -> int:
        """Запустить цикл обработки событий и вернуть код завершения."""
        self.root.mainloop()
        return 0

    def close(self) -> None:
        """Завершить сессию и закрыть окно (повторный вызов безопасен)."""
        if self._closed:
            return
        self._closed = True
        try:
            self.logger.session_finished()
        except Exception:  # pragma: no cover - журнал не должен мешать выходу
            pass
        finally:
            self.logger.close()
            try:
                self.root.destroy()
            except tk.TclError:
                pass


# ----------------------------------------------------------------------
# Вкладка «Арифметика»
# ----------------------------------------------------------------------
OPERATION_LABELS: Dict[str, str] = {
    "+": "Сложение (+)",
    "-": "Вычитание (−)",
    "*": "Умножение (×)",
    "/": "Деление (÷)",
}
OPERATION_SYMBOLS: Dict[str, str] = {"+": "+", "-": "−", "*": "×", "/": "÷"}
OPERATION_FUNCTIONS: Dict[str, Callable[[object, object], object]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
}
METRIC_LABELS: Dict[str, str] = {
    "hausdorff": "расстояние Хаусдорфа",
    "euclidean": "евклидово расстояние",
}

OK_COLOR = "#1a7f37"
ERROR_COLOR = "#c1121f"


class ArithmeticTab(ttk.Frame):
    """Интерактивный калькулятор нечетких величин.

    Вводятся две величины A и B, выбирается операция (сложение, вычитание,
    умножение, деление) или сравнение. Результат показывается в панели
    «Результат», записывается в протокол, в журнал сессии и на график.
    """

    def __init__(
        self,
        master: tk.Misc,
        logger: SessionLogger,
        *,
        on_message: Optional[Callable[[str], None]] = None,
        padding: int = 12,
    ) -> None:
        super().__init__(master, padding=padding)
        self.logger = logger
        self.on_message: Callable[[str], None] = on_message or (lambda text: None)
        self.last_result: Optional[UniformFuzzyVariable] = None
        self.last_operation: Optional[str] = None
        self.last_comparison: Optional[Dict[str, float]] = None

        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._build_controls()
        self._build_plot()
        self._build_protocol()

        self._append("Введите границы величин A и B и выберите операцию.")
        self._show_default_plot()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_controls(self) -> None:
        panel = ttk.Frame(self)
        panel.grid(row=0, column=0, sticky="nsw", padx=(0, 10))

        inputs = ttk.LabelFrame(panel, text="Исходные величины", padding=10)
        inputs.pack(fill="x")

        self.a_low = LabeledEntry(inputs, "A: от", value=1, width=8)
        self.a_high = LabeledEntry(inputs, "до", value=3, width=8)
        self.b_low = LabeledEntry(inputs, "B: от", value=2, width=8)
        self.b_high = LabeledEntry(inputs, "до", value=5, width=8)
        for row, entry in enumerate((self.a_low, self.a_high, self.b_low, self.b_high)):
            entry.grid(row=row, column=0, sticky="w", pady=2)

        operations = ttk.LabelFrame(panel, text="Операция", padding=10)
        operations.pack(fill="x", pady=(8, 0))

        self.operation_buttons: Dict[str, ttk.Button] = {}
        for column, symbol in enumerate(("+", "-", "*", "/")):
            button = ttk.Button(
                operations,
                text=OPERATION_SYMBOLS[symbol],
                width=4,
                command=lambda symbol=symbol: self.compute(symbol),
            )
            button.grid(row=0, column=column, padx=2)
            self.operation_buttons[symbol] = button

        self.metric_var = tk.StringVar(value="hausdorff")
        self.metric_box = ttk.Combobox(
            operations,
            textvariable=self.metric_var,
            values=list(DISTANCE_METRICS),
            state="readonly",
            width=14,
        )
        self.metric_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.compare_button = ttk.Button(operations, text="Сравнить A и B", command=self.compare)
        self.compare_button.grid(row=1, column=2, columnspan=2, sticky="ew", pady=(8, 0))

        result = ttk.LabelFrame(panel, text="Результат", padding=10)
        result.pack(fill="x", pady=(8, 0))
        self.result_label = ttk.Label(
            result, text="—", font=TEXT_FONT, wraplength=280, justify="left"
        )
        self.result_label.pack(anchor="w")

        ttk.Button(panel, text="Очистить протокол", command=self.clear_protocol).pack(
            fill="x", pady=(8, 0)
        )

    def _build_plot(self) -> None:
        self.plot = MembershipPlot(self)
        self.plot.grid(row=0, column=1, sticky="nsew")

    def _build_protocol(self) -> None:
        self.protocol = ProtocolView(self, title="Протокол вычислений", height=8)
        self.protocol.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    # ------------------------------------------------------------------
    # Ввод величин
    # ------------------------------------------------------------------
    def variable_a(self) -> UniformFuzzyVariable:
        """Прочитать величину A из полей ввода."""
        return self._read_variable("A", self.a_low, self.a_high)

    def variable_b(self) -> UniformFuzzyVariable:
        """Прочитать величину B из полей ввода."""
        return self._read_variable("B", self.b_low, self.b_high)

    @staticmethod
    def _read_variable(
        name: str, low: LabeledEntry, high: LabeledEntry
    ) -> UniformFuzzyVariable:
        try:
            a = low.number()
            b = high.number()
            return UniformFuzzyVariable(a, b)
        except ValueError as exc:
            raise ValueError(f"величина {name}: {exc}") from exc

    def _show_default_plot(self) -> None:
        try:
            left = self.variable_a()
            right = self.variable_b()
        except ValueError:
            return
        self.plot.show_variables([left, right], ["A", "B"], title="Величины A и B")

    # ------------------------------------------------------------------
    # Операции
    # ------------------------------------------------------------------
    def compute(self, operation: str) -> Optional[UniformFuzzyVariable]:
        """Выполнить арифметическую операцию над A и B.

        Возвращает результат или ``None``, если данные некорректны (в этом
        случае причина показывается пользователю и пишется в журнал).
        """
        if operation not in OPERATION_FUNCTIONS:
            raise ValueError(f"неизвестная операция: {operation!r}")
        caption = OPERATION_LABELS[operation]

        try:
            left = self.variable_a()
            right = self.variable_b()
            result = OPERATION_FUNCTIONS[operation](left, right)
        except (ValueError, ZeroDivisionError) as exc:
            self._report_error(caption, exc)
            return None

        self.last_result = result
        self.last_operation = operation
        symbol = OPERATION_SYMBOLS[operation]
        self.result_label.configure(
            text=(
                f"A {symbol} B = {format_variable(result)}\n"
                f"центр c = {result.center:.3f}, ширина w = {result.width:.3f}"
            ),
            foreground=OK_COLOR,
        )
        self._append(
            f"Операция {caption}: {describe_variable(left)} {symbol} "
            f"{describe_variable(right)} = {describe_variable(result)}"
        )
        self.logger.log_operation(operation, left, right, result)
        self.plot.show_variables(
            [left, right, result],
            [
                f"A = {format_variable(left)}",
                f"B = {format_variable(right)}",
                f"A {symbol} B = {format_variable(result)}",
            ],
            title=f"Функции принадлежности: A {symbol} B",
        )
        self.on_message(f"Выполнено: A {symbol} B = {format_variable(result)}")
        return result

    def compare(self) -> Optional[Dict[str, float]]:
        """Сравнить A и B: метрики расстояния, индексы Заде, доминирование."""
        try:
            left = self.variable_a()
            right = self.variable_b()
            metric = self.metric_var.get()
            distance_function = get_distance_function(metric)
            info: Dict[str, float] = {
                "selected": distance_function(left, right),
                "hausdorff": left.distance(right, "hausdorff"),
                "euclidean": left.distance(right, "euclidean"),
                "possibility": left.possibility_greater_or_equal(right),
                "necessity": left.necessity_greater_or_equal(right),
                "dominance": left.dominance(right),
            }
        except (ValueError, ZeroDivisionError) as exc:
            self._report_error("Сравнение A и B", exc)
            return None

        relation = left.compare(right)
        sign = {1: ">", -1: "<", 0: "="}[relation]
        info["relation"] = relation
        self.last_comparison = info

        self.result_label.configure(
            text=(
                f"A {sign} B  (сначала по центру c, затем по ширине w)\n"
                f"d_H = {info['hausdorff']:.4f},  d_E = {info['euclidean']:.4f}\n"
                f"выбрано {METRIC_LABELS[metric]} = {info['selected']:.4f}\n"
                f"Pos(A ≥ B) = {info['possibility']:.4f}\n"
                f"Nec(A ≥ B) = {info['necessity']:.4f}\n"
                f"доминирование P(A > B) = {info['dominance']:.4f}"
            ),
            foreground=OK_COLOR,
        )
        self._append(
            f"Сравнение: {describe_variable(left)} и {describe_variable(right)}"
        )
        self._append(f"    выбрана метрика: {METRIC_LABELS[metric]} = {info['selected']:.4f}")
        self._append(
            f"    d_H = {info['hausdorff']:.4f}; d_E = {info['euclidean']:.4f}; "
            f"Pos = {info['possibility']:.4f}; Nec = {info['necessity']:.4f}; "
            f"P(A > B) = {info['dominance']:.4f}"
        )
        self._append(f"    итог ранжирования: A {sign} B")
        self.logger.log_comparison(left, sign, right, f"A {sign} B")
        self.logger.log_dominance(left, right)
        self.plot.show_variables(
            [left, right],
            [f"A = {format_variable(left)}", f"B = {format_variable(right)}"],
            title="Сравнение величин A и B",
        )
        self.on_message(f"Сравнение: A {sign} B")
        return info

    def clear_protocol(self) -> None:
        """Очистить протокол вычислений."""
        self.protocol.clear()
        self._append("Протокол очищен.")
        self.on_message("Протокол очищен")

    # ------------------------------------------------------------------
    # Вспомогательное
    # ------------------------------------------------------------------
    def _append(self, line: str) -> None:
        self.protocol.append(line)

    def _report_error(self, caption: str, exc: Exception) -> None:
        text = f"{caption}: {exc}"
        self.last_result = None
        self.last_comparison = None
        self.result_label.configure(text=f"Ошибка: {exc}", foreground=ERROR_COLOR)
        self._append(f"ОШИБКА. {text}")
        self.logger.log_error(caption, str(exc))
        self.on_message(f"Ошибка: {exc}")


# ----------------------------------------------------------------------
# Вкладка «Генерация и выборка»
# ----------------------------------------------------------------------
SAMPLE_COLUMNS: Sequence[Tuple[str, str, int]] = (
    ("index", "№", 50),
    ("a", "a", 90),
    ("b", "b", 90),
    ("center", "центр c", 90),
    ("width", "ширина w", 90),
)


class GenerationTab(ttk.Frame):
    """Генерация случайной выборки и просмотр её в таблице.

    Параметры распределения (``a`` и ``w``) и объём выборки задаются полями
    ввода; зерно генератора можно указать вручную для воспроизводимости.
    Сгенерированная выборка передаётся в главное окно — её использует вкладка
    кластерного анализа.
    """

    def __init__(
        self,
        master: tk.Misc,
        logger: SessionLogger,
        *,
        on_message: Optional[Callable[[str], None]] = None,
        on_sample: Optional[Callable[[object, object, Dict[str, object]], None]] = None,
        padding: int = 12,
    ) -> None:
        super().__init__(master, padding=padding)
        self.logger = logger
        self.on_message: Callable[[str], None] = on_message or (lambda text: None)
        self.on_sample: Callable[[object, object, Dict[str, object]], None] = (
            on_sample or (lambda sample, seed, parameters: None)
        )
        self.sample: Optional[FuzzySet] = None
        self.last_seed: Optional[object] = None
        self.last_parameters: Dict[str, object] = {}

        self.rowconfigure(1, weight=1)
        self.columnconfigure(1, weight=1)

        self._build_controls()
        self._build_table()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_controls(self) -> None:
        panel = ttk.Frame(self)
        panel.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 10))

        inputs = ttk.LabelFrame(panel, text="Параметры выборки", padding=10)
        inputs.pack(fill="x")
        inputs.columnconfigure(0, weight=1)

        row = 0
        for caption in ("Границы a (левая граница интервала)",):
            ttk.Label(inputs, text=caption, font=TEXT_FONT, foreground=HINT_COLOR).grid(
                row=row, column=0, sticky="w"
            )
            row += 1
        self.a_low = LabeledEntry(inputs, "от", value="-10", width=10)
        self.a_high = LabeledEntry(inputs, "до", value="10", width=10)
        for entry in (self.a_low, self.a_high):
            entry.grid(row=row, column=0, sticky="w", pady=1)
            row += 1

        ttk.Label(
            inputs, text="Ширина w = b − a", font=TEXT_FONT, foreground=HINT_COLOR
        ).grid(row=row, column=0, sticky="w", pady=(6, 0))
        row += 1
        self.w_low = LabeledEntry(inputs, "от", value="0", width=10)
        self.w_high = LabeledEntry(inputs, "до", value="4", width=10)
        for entry in (self.w_low, self.w_high):
            entry.grid(row=row, column=0, sticky="w", pady=1)
            row += 1

        ttk.Label(
            inputs,
            text=f"Объём выборки N (по заданию {MIN_COUNT}…{MAX_COUNT})",
            font=TEXT_FONT,
            foreground=HINT_COLOR,
        ).grid(row=row, column=0, sticky="w", pady=(6, 0))
        row += 1
        self.count_low = LabeledEntry(inputs, "от", value=str(MIN_COUNT), width=10)
        self.count_high = LabeledEntry(inputs, "до", value=str(MAX_COUNT), width=10)
        for entry in (self.count_low, self.count_high):
            entry.grid(row=row, column=0, sticky="w", pady=1)
            row += 1

        ttk.Label(
            inputs,
            text="Зерно генератора (пусто — случайное)",
            font=TEXT_FONT,
            foreground=HINT_COLOR,
        ).grid(row=row, column=0, sticky="w", pady=(6, 0))
        row += 1
        self.seed_entry = LabeledEntry(inputs, "seed", value="", width=10)
        self.seed_entry.grid(row=row, column=0, sticky="w", pady=1)
        row += 1

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(8, 0))
        self.generate_button = ttk.Button(buttons, text="Сгенерировать", command=self.generate)
        self.generate_button.pack(side="left")
        self.clear_button = ttk.Button(buttons, text="Очистить", command=self.clear)
        self.clear_button.pack(side="left", padx=(6, 0))

        result = ttk.LabelFrame(panel, text="Результат", padding=10)
        result.pack(fill="x", pady=(8, 0))
        self.result_label = ttk.Label(
            result, text="Выборка ещё не сгенерирована.", font=TEXT_FONT, wraplength=300,
            justify="left",
        )
        self.result_label.pack(anchor="w")

    def _build_table(self) -> None:
        caption = ttk.Label(self, text="Список величин", font=TEXT_FONT)
        caption.grid(row=0, column=1, sticky="nw")
        self.table = Table(self, SAMPLE_COLUMNS, height=20)
        self.table.grid(row=1, column=1, sticky="nsew")
        self.rowconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Ввод параметров
    # ------------------------------------------------------------------
    def read_parameters(self) -> Dict[str, Tuple[float, float]]:
        """Прочитать параметры распределения из полей ввода."""
        return {
            "a_range": (self.a_low.number(), self.a_high.number()),
            "width_range": (self.w_low.number(), self.w_high.number()),
            "count_range": (
                self._read_count(self.count_low, "нижняя граница объёма"),
                self._read_count(self.count_high, "верхняя граница объёма"),
            ),
        }

    @staticmethod
    def _read_count(entry: LabeledEntry, caption: str) -> float:
        value = entry.number()
        if not float(value).is_integer():
            raise ValueError(f"{caption}: объём выборки должен быть целым числом, получено {value}")
        return value

    def read_seed(self) -> object:
        """Прочитать зерно генератора; пустое поле → случайное зерно."""
        text = self.seed_entry.text.strip()
        if not text:
            return random.randrange(1, 10**9)
        try:
            return int(text)
        except ValueError:
            return text

    # ------------------------------------------------------------------
    # Генерация
    # ------------------------------------------------------------------
    def generate(self) -> Optional[FuzzySet]:
        """Сгенерировать выборку по заданным параметрам.

        Возвращает :class:`fuzzy_core.FuzzySet` или ``None`` при ошибке ввода
        (причина показывается пользователю и записывается в журнал).
        """
        try:
            parameters = self.read_parameters()
            seed = self.read_seed()
            sample = generate_sample(
                seed=seed,
                a_range=parameters["a_range"],
                width_range=parameters["width_range"],
                count_range=parameters["count_range"],
            )
        except (ValueError, TypeError) as exc:
            self._report_error("Генерация выборки", exc)
            return None

        self.sample = sample
        self.last_seed = seed
        self.last_parameters = parameters
        self.fill_table()
        self.result_label.configure(text=self._summary_text(), foreground=OK_COLOR)
        self.logger.log_sample(
            sample,
            source="генератор (GUI)",
            seed=seed,
            a_range=parameters["a_range"],
            width_range=parameters["width_range"],
            count_range=parameters["count_range"],
        )
        self.on_sample(sample, seed, parameters)
        self.on_message(f"Сгенерировано величин: {len(sample)} (seed={seed!r})")
        return sample

    def fill_table(self) -> None:
        """Переписать таблицу по текущей выборке."""
        if self.sample is None:
            self.table.clear()
            return
        rows = [
            (
                index,
                f"{variable.a:.3f}",
                f"{variable.b:.3f}",
                f"{variable.center:.3f}",
                f"{variable.width:.3f}",
            )
            for index, variable in enumerate(self.sample, start=1)
        ]
        self.table.set_rows(rows)

    def clear(self) -> None:
        """Сбросить выборку, таблицу и итоговую информацию."""
        self.sample = None
        self.last_seed = None
        self.last_parameters = {}
        self.table.clear()
        self.result_label.configure(
            text="Выборка ещё не сгенерирована.", foreground=HINT_COLOR
        )
        self.on_sample(None, None, {})
        self.on_message("Выборка очищена")

    # ------------------------------------------------------------------
    # Вспомогательное
    # ------------------------------------------------------------------
    def _summary_text(self) -> str:
        sample = self.sample
        assert sample is not None
        a_low, a_high = self.last_parameters.get("a_range", (0, 0))
        w_low, w_high = self.last_parameters.get("width_range", (0, 0))
        env_low, env_high = sample.envelope()
        return (
            f"Сгенерировано величин: {len(sample)}\n"
            f"seed = {self.last_seed!r}\n"
            f"a ∈ [{a_low:g}, {a_high:g}], w ∈ [{w_low:g}, {w_high:g}]\n"
            f"средний центр = {sample.mean_center():.3f}, "
            f"средняя ширина = {sample.mean_width():.3f}\n"
            f"охватывающий интервал = [{env_low:.3f}, {env_high:.3f}]"
        )

    def _report_error(self, caption: str, exc: Exception) -> None:
        self.sample = None
        self.table.clear()
        self.result_label.configure(text=f"Ошибка: {exc}", foreground=ERROR_COLOR)
        self.logger.log_error(caption, str(exc))
        self.on_message(f"Ошибка: {exc}")


# ----------------------------------------------------------------------
# Вкладка «Кластерный анализ»
# ----------------------------------------------------------------------
METHOD_KMEANS = "kmeans"
METHOD_THRESHOLD = "threshold"
METHOD_ALPHA = "alpha"
METHOD_DENSITY = "density"

METHOD_LABELS: Dict[str, str] = {
    METHOD_KMEANS: "K-Means: на K кластеров",
    METHOD_THRESHOLD: "По порогу (полная связь)",
    METHOD_ALPHA: "По α-уровню (уровень отбора)",
    METHOD_DENSITY: "По плотности (DBSCAN-подобный)",
}

#: Как читать α-уровень: подписи в интерфейсе и ключи для библиотеки.
LINKAGE_LABELS: Dict[str, str] = {
    "complete": "полная",
    "single": "одиночная",
}

CLUSTER_COLUMNS: Sequence[Tuple[str, str, int]] = (
    ("cluster", "кластер", 70),
    ("size", "размер", 70),
    ("center_c", "центр c", 90),
    ("center_w", "центр w", 90),
    ("diameter", "диаметр", 90),
    ("variance", "дисперсия", 90),
)

POINT_COLUMNS: Sequence[Tuple[str, str, int]] = (
    ("index", "№", 50),
    ("a", "a", 80),
    ("b", "b", 80),
    ("center", "центр c", 80),
    ("width", "ширина w", 80),
    ("cluster", "кластер", 70),
)

#: Сколько размеров кластеров показывать в итоговой сводке.
MAX_SIZES_IN_SUMMARY = 12

#: Границы ползунка α-уровня, задержка пересчёта и шаг «проигрывания».
ALPHA_MIN = 0.05
ALPHA_MAX = 1.0
ALPHA_DEBOUNCE_MS = 90
ALPHA_PLAY_INTERVAL_MS = 600

#: Пауза между шагами «проигрывания» агломерации и границы скорости (шагов/с).
STEP_PLAY_INTERVAL_MS = 400
STEP_SPEED_MIN = 1.0
STEP_SPEED_MAX = 20.0
STEP_SPEED_DEFAULT = 1000.0 / STEP_PLAY_INTERVAL_MS


class ClusteringTab(ttk.Frame):
    """Кластерный анализ сгенерированной выборки.

    Доступны четыре метода: K-Means на заданное число кластеров, агломеративный
    по порогу внутрикластерного расстояния (полная связь), по α-уровню
    (уровень отбора по шкале сходства) и плотностной (DBSCAN-подобный).
    Результаты показываются таблицами по кластерам и по точкам, а также
    диаграммой рассеяния в координатах (центр c, ширина w).
    """

    def __init__(
        self,
        master: tk.Misc,
        logger: SessionLogger,
        sample_provider: Callable[[], Optional[FuzzySet]],
        *,
        on_message: Optional[Callable[[str], None]] = None,
        on_result: Optional[Callable[[object], None]] = None,
        padding: int = 12,
    ) -> None:
        super().__init__(master, padding=padding)
        self.logger = logger
        self.sample_provider = sample_provider
        self.on_message: Callable[[str], None] = on_message or (lambda text: None)
        self.on_result: Callable[[object], None] = on_result or (lambda result: None)
        self.result: Optional[ClusterResult] = None
        self.profile: List[Dict[str, object]] = []

        # Интерактивный α-уровень: движок кэшируется по (выборка, метрика, связь).
        self.engine: Optional[AlphaClusterer] = None
        self._engine_key: Optional[Tuple[int, str, str]] = None
        self._alpha_job: Optional[str] = None
        self._syncing_alpha = False
        self._playing = False
        self._play_job: Optional[str] = None
        self._play_levels: List[float] = []
        self._play_index = 0
        self._stale_views: set = set()

        # Пошаговая агломерация: трасса полной связи и позиция в ней.
        self.trace: Optional[Agglomeration] = None
        self._trace_key: Optional[Tuple[int, str]] = None
        self.step_index = 0
        self._step_playing = False
        self._step_job: Optional[str] = None
        self._syncing_speed = False
        # Во время проигрывания таблицы и легенда не пересобираются на каждом
        # шаге (это самая дорогая часть отрисовки); флаг говорит, что их нужно
        # обновить один раз при остановке.
        self._step_ui_stale = False

        self.rowconfigure(1, weight=1)
        self.columnconfigure(1, weight=1)

        self._build_controls()
        self._build_plot()
        self._build_tables()
        self.refresh_sample_info()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_controls(self) -> None:
        # Прокручиваемый левый столбец: контейнер с канвасом (содержимое слева)
        # и полосой прокрутки справа — не накладываются.
        # Разделитель с возможностью изменения ширины левой панели (как между
        # графиком и таблицами). Левый столбец — прокручиваемый, правый — график.
        self.main_pane = tk.PanedWindow(self, sashwidth=6, sashrelief=tk.RAISED, sashpad=2)
        self.main_pane.pack(fill="both", expand=True, padx=4, pady=4)

        # Левая панель (прокручиваемая)
        scroll_container = ttk.Frame(self.main_pane, width=260)
        scroll_container.pack_propagate(False)
        self.main_pane.add(scroll_container, minsize=220, sticky="nsew")

        scroll_container.columnconfigure(0, weight=1)
        scroll_container.rowconfigure(0, weight=1)

        panel_outer = tk.Canvas(scroll_container, highlightthickness=0, width=240)
        panel_outer.grid(row=0, column=0, sticky="nsew")
        scrollbar_outer = ttk.Scrollbar(scroll_container, orient="vertical", command=panel_outer.yview)
        scrollbar_outer.grid(row=0, column=1, sticky="ns")
        panel_outer.configure(yscrollcommand=scrollbar_outer.set)
        panel = ttk.Frame(panel_outer)
        panel_outer.create_window((0, 0), window=panel, anchor="nw")
        def _update_scrollregion(event=None):
            bbox = panel_outer.bbox("all")
            panel_outer.configure(scrollregion=(0, 0, bbox[2] if bbox else 0, bbox[3] if bbox else 0))
        panel.bind("<Configure>", _update_scrollregion)
        self.bind("<Configure>", lambda e: self.after_idle(_update_scrollregion))

        data = ttk.LabelFrame(panel, text="Данные", padding=10)
        data.pack(fill="x")
        self.sample_label = ttk.Label(
            data, text="", font=TEXT_FONT, wraplength=280, justify="left"
        )
        self.sample_label.pack(anchor="w")
        ttk.Button(data, text="Обновить", command=self.refresh_sample_info).pack(
            fill="x", pady=(6, 0)
        )

        method = ttk.LabelFrame(panel, text="Метод", padding=10)
        method.pack(fill="x", pady=(8, 0))
        self.method_var = tk.StringVar(value=METHOD_KMEANS)
        self.method_buttons: Dict[str, ttk.Radiobutton] = {}
        for row, key in enumerate(
            (METHOD_KMEANS, METHOD_THRESHOLD, METHOD_ALPHA, METHOD_DENSITY)
        ):
            button = ttk.Radiobutton(
                method,
                text=METHOD_LABELS[key],
                value=key,
                variable=self.method_var,
                command=self._update_parameter_state,
            )
            button.grid(row=row, column=0, sticky="w")
            self.method_buttons[key] = button

        metric = ttk.LabelFrame(panel, text="Метрика и зерно", padding=10)
        metric.pack(fill="x", pady=(8, 0))
        self.metric_var = tk.StringVar(value="hausdorff")
        ttk.Label(metric, text="Метрика расстояния", font=TEXT_FONT).grid(
            row=0, column=0, sticky="w"
        )
        self.metric_box = ttk.Combobox(
            metric,
            textvariable=self.metric_var,
            values=list(DISTANCE_METRICS),
            state="readonly",
            width=12,
        )
        self.metric_box.grid(row=1, column=0, sticky="ew")
        self.seed_entry = LabeledEntry(metric, "seed", value="", width=12)
        self.seed_entry.grid(row=2, column=0, sticky="w", pady=(6, 0))

        parameters = ttk.LabelFrame(panel, text="Параметры метода", padding=10)
        parameters.pack(fill="x", pady=(8, 0))
        self.k_entry = LabeledEntry(parameters, "K", value="3", width=8)
        self.threshold_entry = LabeledEntry(parameters, "порог", value="1.0", width=8)
        self.eps_entry = LabeledEntry(parameters, "eps", value="0.5", width=8)
        self.min_points_entry = LabeledEntry(parameters, "minPts", value="2", width=8)
        for row, entry in enumerate(
            (self.k_entry, self.threshold_entry, self.eps_entry, self.min_points_entry)
        ):
            entry.grid(row=row, column=0, sticky="w", pady=1)

        # α-уровень и способ его чтения — в одной строке, чтобы столбец не рос.
        alpha_row = ttk.Frame(parameters)
        alpha_row.grid(row=2, column=0, sticky="w", pady=1)
        self.alpha_entry = LabeledEntry(alpha_row, "α", value="0.7", width=6)
        self.alpha_entry.pack(side="left")
        self.linkage_label = ttk.Label(alpha_row, text="связь", font=TEXT_FONT)
        self.linkage_label.pack(side="left", padx=(8, 4))
        self.linkage_var = tk.StringVar(value=LINKAGE_LABELS["complete"])
        self.linkage_box = ttk.Combobox(
            alpha_row,
            textvariable=self.linkage_var,
            values=list(LINKAGE_LABELS.values()),
            state="readonly",
            width=11,
        )
        self.linkage_box.pack(side="left")
        # α-строка должна стоять между «порогом» и «eps»: переставляем eps/minPts.
        self.eps_entry.grid_configure(row=3)
        self.min_points_entry.grid_configure(row=4)

        # Интерактивный α: ползунок, текущее значение и кнопка «проигрывания».
        # Всё в одной строке, чтобы левый столбец не вылезал за окно.
        slider_row = ttk.Frame(parameters)
        slider_row.grid(row=5, column=0, sticky="ew", pady=(4, 1))
        self.alpha_value_label = ttk.Label(
            slider_row, text=self._alpha_text(0.7), font=TEXT_FONT
        )
        self.alpha_value_label.pack(side="left")
        self.alpha_scale = ttk.Scale(
            slider_row,
            from_=ALPHA_MAX,
            to=ALPHA_MIN,
            orient="horizontal",
            length=104,
            command=self._on_alpha_scale,
        )
        self.alpha_scale.set(0.7)
        self.alpha_scale.pack(side="left", padx=(6, 0))
        self.play_button = ttk.Button(
            slider_row, text="▶", width=3, command=self.toggle_alpha_play
        )
        self.play_button.pack(side="left", padx=(4, 0))

        # Смена способа построения графика: диаграмма / профиль k(α) / матрица.
        self.parameter_entries = {
            METHOD_KMEANS: (self.k_entry,),
            METHOD_THRESHOLD: (self.threshold_entry,),
            METHOD_ALPHA: (self.alpha_entry,),
            METHOD_DENSITY: (self.eps_entry, self.min_points_entry),
        }

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(8, 0))
        self.run_button = ttk.Button(buttons, text="Кластеризовать", command=self.run)
        self.run_button.pack(fill="x")

        # Пошаговая агломерация (полная связь) для метода «по порогу».
        steps = ttk.LabelFrame(panel, text="Пошаговая агломерация", padding=10)
        steps.pack(fill="x", pady=(8, 0))
        step_row = ttk.Frame(steps)
        step_row.pack(fill="x")
        self.step_label = ttk.Label(step_row, text=self._step_text(0, 0), font=TEXT_FONT)
        self.step_label.pack(side="left")
        self.step_button = ttk.Button(
            step_row, text="Шаг", width=5, command=self.step_agglomeration
        )
        self.step_button.pack(side="left", padx=(6, 0))
        self.step_play_button = ttk.Button(
            step_row, text="▶", width=3, command=self.toggle_step_play
        )
        self.step_play_button.pack(side="left", padx=(4, 0))
        self.step_reset_button = ttk.Button(
            step_row, text="↺", width=3, command=self.reset_agglomeration
        )
        self.step_reset_button.pack(side="left", padx=(4, 0))

        # Останов на пороге кластеризации: по умолчанию анимация доходит ровно
        # до разбиения кнопки «Кластеризовать» (разрез дендрограммы по порогу).
        self.step_stop_var = tk.BooleanVar(value=True)
        self.step_stop_check = ttk.Checkbutton(
            steps,
            text="останавливаться на пороге",
            variable=self.step_stop_var,
            command=self._on_step_stop_changed,
        )
        self.step_stop_check.pack(anchor="w", pady=(6, 0))

        # Скорость проигрывания: 1..20 шагов в секунду (больше — быстрее).
        speed_row = ttk.Frame(steps)
        speed_row.pack(fill="x", pady=(6, 0))
        ttk.Label(speed_row, text="скорость", font=TEXT_FONT).pack(side="left")
        # Начальное значение задаём ДО подписки на command: ttk.Scale.set
        # вызывает обработчик, а подписи ещё нет.
        self.step_speed_scale = ttk.Scale(
            speed_row,
            from_=STEP_SPEED_MIN,
            to=STEP_SPEED_MAX,
            orient="horizontal",
            length=96,
        )
        self.step_speed_scale.set(STEP_SPEED_DEFAULT)
        self.step_speed_scale.pack(side="left", padx=(6, 0))
        self.step_speed_label = ttk.Label(
            speed_row, text=self._speed_text(STEP_SPEED_DEFAULT), font=TEXT_FONT
        )
        self.step_speed_label.pack(side="left", padx=(6, 0))
        self.step_speed_scale.configure(command=self._on_step_speed)

        summary = ttk.LabelFrame(panel, text="Результат", padding=10)
        summary.pack(fill="x", pady=(8, 0))
        self.result_label = ttk.Label(
            summary, text="Анализ не выполнялся.", font=TEXT_FONT, wraplength=300,
            justify="left",
        )
        self.result_label.pack(anchor="w")

        self._update_parameter_state()
        self.scroll_container = scroll_container
        self.panel_outer = panel_outer
        self.panel_canvas = panel_outer
        self.panel_scrollbar = scrollbar_outer
        self.panel_frame = panel
        self._bind_panel_mousewheel(scroll_container)

    def _on_panel_mousewheel(self, event: object) -> str:
        """Обработка прокрутки колесом мыши левой панели."""
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", 0)
        if delta:
            step = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        elif num == 4:
            step = -1
        elif num == 5:
            step = 1
        else:
            return "break"
        self.panel_outer.yview_scroll(step * 3, "units")
        return "break"

    def _bind_panel_mousewheel(self, widget: tk.Misc) -> None:
        """Рекурсивно привязать прокрутку колесом мыши ко всем дочерним виджетам панели."""
        widget.bind("<MouseWheel>", self._on_panel_mousewheel)
        widget.bind("<Button-4>", self._on_panel_mousewheel)
        widget.bind("<Button-5>", self._on_panel_mousewheel)
        for child in widget.winfo_children():
            self._bind_panel_mousewheel(child)


    def _build_plot(self) -> None:
        # Правый контейнер для графика и таблиц — добавляется в PanedWindow
        # вместе с левой прокручиваемой панелью, давая пользователю разделитель.
        self.right_pane = ttk.Frame(self)
        self.main_pane.add(self.right_pane, sticky="nsew")
        self.main_pane.paneconfigure(self.right_pane, minsize=300)

        # Кнопка полной легенды — над графиком (внутри правой панели).
        self.right_pane.rowconfigure(0, weight=0)
        self.right_pane.rowconfigure(1, weight=1)
        self.right_pane.columnconfigure(0, weight=1)
        self.plot_toolbar = ttk.Frame(self.right_pane)
        self.plot_toolbar.grid(row=0, column=0, sticky="ew")
        self.legend_button = ttk.Button(
            self.plot_toolbar,
            text="Легенда",
            command=self.toggle_legend,
            state="disabled",
        )
        self.legend_button.pack(side="right")

        # График и таблицы — в раздвижной панели: пользователь сам решает,
        # чему отдать больше места, и ничего не уезжает за край окна.
        self.paned = ttk.PanedWindow(self.right_pane, orient="vertical")
        self.paned.grid(row=1, column=0, sticky="nsew")

        # Внутри верхней части — ещё одна раздвижная панель: график + легенда.
        self.plot_area = ttk.PanedWindow(self.paned, orient="horizontal")
        self.paned.add(self.plot_area, weight=3)

        # Три представления результата в одной вкладке-блокноте: привычная
        # диаграмма, профиль k(α) и тепловая карта матрицы сходства.
        self.view_notebook = ttk.Notebook(self.plot_area)
        self.plot_area.add(self.view_notebook, weight=4)

        self.plot = MembershipPlot(self.view_notebook, height=3.4, toolbar=False)
        self.profile_plot = MembershipPlot(self.view_notebook, height=3.4, toolbar=False)
        self.matrix_plot = MembershipPlot(self.view_notebook, height=3.4, toolbar=False)
        self.view_notebook.add(self.plot, text="Диаграмма")
        self.view_notebook.add(self.profile_plot, text="Профиль k(α)")
        self.view_notebook.add(self.matrix_plot, text="Матрица сходства")
        # Пустые профиль и матрица задают корректные подписи осей сразу.
        self.profile_plot.show_alpha_profile([])
        self.matrix_plot.show_similarity_matrix([])
        self.view_notebook.bind("<<NotebookTabChanged>>", self._on_view_changed)
        self._sync_view_tabs()

        self.legend_panel = LegendPanel(self.plot_area)
        self.legend_visible = False
        # Скрытая панель не пересобирается: сотни Tk-виджетов — дорогая часть
        # перерисовки. При открытии содержимое соберётся из свежих данных.
        self._legend_stale = False

    def _sync_view_tabs(self) -> None:
        """Разрешить закладки профиля и матрицы только для метода α-уровня.

        Для остальных методов это представления «не применимы», поэтому они
        отключаются: закладку нельзя выбрать. Если открыта отключаемая
        закладка — переключаемся на «Диаграмму».
        """
        enabled = self.method_var.get() == METHOD_ALPHA
        state = "normal" if enabled else "disabled"
        for index in (1, 2):  # «Профиль k(α)», «Матрица сходства»
            self.view_notebook.tab(index, state=state)
        if not enabled and self.view_notebook.index("current") in (1, 2):
            self.view_notebook.select(0)

    def _build_tables(self) -> None:
        self.table_notebook = ttk.Notebook(self.paned)
        self.paned.add(self.table_notebook, weight=2)

        clusters_frame = ttk.Frame(self.table_notebook)
        self.cluster_table = Table(clusters_frame, CLUSTER_COLUMNS, height=6)
        self.cluster_table.pack(fill="both", expand=True)
        self.table_notebook.add(clusters_frame, text="Кластеры")

        points_frame = ttk.Frame(self.table_notebook)
        self.point_table = Table(points_frame, POINT_COLUMNS, height=6)
        self.point_table.pack(fill="both", expand=True)
        self.table_notebook.add(points_frame, text="Точки")

    # ------------------------------------------------------------------
    # Легенда
    # ------------------------------------------------------------------
    def toggle_legend(self) -> bool:
        """Показать или скрыть панель с полной легендой кластеров."""
        if self.legend_visible:
            self.plot_area.forget(self.legend_panel)
            self.legend_visible = False
        else:
            if self._legend_stale:
                self.legend_panel.set_items(self._legend_items())
                self._legend_stale = False
            self.plot_area.add(self.legend_panel, weight=1)
            self.legend_visible = True
        self._update_legend_button()
        return self.legend_visible

    def refresh_legend(self) -> None:
        """Пересобрать содержимое панели легенды по текущему результату.

        Пока панель скрыта, строки не создаются (это самая дорогая часть
        перерисовки при десятках кластеров); при открытии панель соберётся из
        свежих данных — см. :meth:`toggle_legend`.
        """
        if self.legend_visible:
            self.legend_panel.set_items(self._legend_items())
            self._legend_stale = False
        else:
            self._legend_stale = True
        self._update_legend_button()

    def _update_legend_button(self) -> None:
        result = self.result
        if result is None:
            self.legend_button.configure(text="Легенда", state="disabled")
            return
        count = len(result.clusters) + (1 if result.noise else 0)
        if self.legend_visible:
            self.legend_button.configure(text="Скрыть легенду", state="normal")
        else:
            self.legend_button.configure(text=f"Показать легенду ({count})", state="normal")

    def _legend_items(self) -> List[Tuple[str, str, str]]:
        """Строки легенды: цветной образец, подпись и пояснение."""
        result = self.result
        if result is None:
            return []
        colors = self.plot.group_colors
        sizes = self.plot.group_sizes
        items: List[Tuple[str, str, str]] = []
        if result.noise:
            items.append(
                (colors.get(NOISE_LABEL, "#7f7f7f"), "шум", f"точек: {sizes.get(-1, 0)}")
            )
        for label, cluster in enumerate(result.clusters):
            items.append(
                (
                    colors.get(label, "#000000"),
                    f"кластер {label}",
                    f"точек: {cluster.size}, "
                    f"c={cluster.centroid.center:.2f}, w={cluster.centroid.width:.2f}",
                )
            )
        items.append(("#000000", "центры кластеров", "чёрные ромбы"))
        return items

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------
    def current_sample(self) -> Optional[FuzzySet]:
        """Выборка, которую нужно кластеризовать."""
        return self.sample_provider()

    def on_tab_activated(self) -> None:
        """Вызывается при переключении пользователя на эту вкладку."""
        self.refresh_sample_info()

    def refresh_sample_info(self) -> None:
        """Показать, какая выборка доступна для анализа."""
        sample = self.current_sample()
        if sample is None or len(sample) == 0:
            self.sample_label.configure(
                text=(
                    "Выборка не сгенерирована.\n"
                    "Сначала выполните генерацию на вкладке «Генерация и выборка»."
                ),
                foreground=HINT_COLOR,
            )
            return
        self.sample_label.configure(
            text=f"Доступна выборка: {len(sample)} величин.",
            foreground=OK_COLOR,
        )

    def _update_parameter_state(self, event: object = None) -> None:
        """Включить поля, относящиеся к выбранному методу."""
        method = self.method_var.get()
        active = set(self.parameter_entries[method])
        for entries in self.parameter_entries.values():
            for entry in entries:
                state = "normal" if entry in active else "disabled"
                entry.entry.configure(state=state)
        self.seed_entry.entry.configure(
            state="normal" if method == METHOD_KMEANS else "disabled"
        )
        is_alpha = method == METHOD_ALPHA
        self.linkage_box.configure(state="readonly" if is_alpha else "disabled")
        self.alpha_scale.configure(state="normal" if is_alpha else "disabled")
        self.play_button.configure(state="normal" if is_alpha else "disabled")
        if not is_alpha:
            self.stop_alpha_play()
        # Пошаговая агломерация относится к методу «по порогу» (полная связь).
        is_threshold = method == METHOD_THRESHOLD
        step_state = "normal" if is_threshold else "disabled"
        for widget in (
            self.step_button,
            self.step_play_button,
            self.step_reset_button,
            self.step_speed_scale,
            self.step_stop_check,
        ):
            widget.configure(state=step_state)
        if not is_threshold:
            self.stop_step_play()
        # Профиль и матрица относятся только к α-уровню; до создания блокнота
        # (в _build_controls) синхронизация ещё невозможна.
        if hasattr(self, "view_notebook"):
            self._sync_view_tabs()

    # ------------------------------------------------------------------
    # Запуск анализа
    # ------------------------------------------------------------------
    def read_parameters(self, method: Optional[str] = None) -> Dict[str, object]:
        """Прочитать параметры выбранного метода."""
        key = method or self.method_var.get()
        if key == METHOD_KMEANS:
            k = self.k_entry.number()
            if not float(k).is_integer():
                raise ValueError(f"K: число кластеров должно быть целым, получено {k}")
            return {"k": int(k), "seed": self.read_seed()}
        if key == METHOD_THRESHOLD:
            return {"threshold": self.threshold_entry.number()}
        if key == METHOD_ALPHA:
            return {"alpha": self.alpha_entry.number(), "linkage": self.read_linkage()}
        if key == METHOD_DENSITY:
            min_points = self.min_points_entry.number()
            if not float(min_points).is_integer():
                raise ValueError(
                    f"minPts: минимальное число точек должно быть целым, получено {min_points}"
                )
            return {"eps": self.eps_entry.number(), "min_points": int(min_points)}
        raise ValueError(f"неизвестный метод кластеризации: {key!r}")

    def read_linkage(self) -> str:
        """Тип связи для α-уровня: ``complete`` или ``single``."""
        label = self.linkage_var.get()
        for key, text in LINKAGE_LABELS.items():
            if text == label:
                return key
        return "complete"

    def read_seed(self) -> object:
        """Зерно генератора: пустое поле → случайное зерно."""
        text = self.seed_entry.text.strip()
        if not text:
            return random.randrange(1, 10**9)
        try:
            return int(text)
        except ValueError:
            return text

    def run(self) -> Optional[ClusterResult]:
        """Выполнить кластеризацию и показать результаты."""
        sample = self.current_sample()
        if sample is None or len(sample) == 0:
            self._report_error(
                "Кластерный анализ",
                "выборка пуста — сначала сгенерируйте её на вкладке «Генерация и выборка»",
            )
            return None

        try:
            method = self.method_var.get()
            metric = self.metric_var.get()
            get_distance_function(metric)  # проверка имени метрики
            parameters = self.read_parameters(method)
            engine: Optional[AlphaClusterer] = None
            if method == METHOD_ALPHA:
                engine = self.get_engine(sample, metric, parameters["linkage"])
                result = engine.clustering(parameters["alpha"])
            else:
                result = cluster(sample, method, metric=metric, **parameters)
        except (ValueError, TypeError) as exc:
            self._report_error("Кластерный анализ", exc)
            return None

        self._present_result(result, engine, log=True)
        seed = parameters.get("seed")
        self.on_message(
            f"Кластеризация ({METHOD_LABELS[method]}): кластеров {len(result.clusters)}"
            + (f", seed={seed!r}" if seed is not None else "")
        )
        self.on_result(result)
        return result

    #: Имена представлений результата в порядке закладок блокнота.
    VIEW_NAMES: Tuple[str, ...] = ("scatter", "profile", "matrix")

    def _present_result(
        self,
        result: ClusterResult,
        engine: Optional[AlphaClusterer],
        *,
        log: bool,
    ) -> None:
        """Показать результат: таблицы, диаграммы, сводка, легенда.

        При явном расчёте (``log=True``) обновляются все три представления.
        При живой перестройке по ползунку α рисуется только видимая закладка,
        остальные помечаются устаревшими и обновляются при переключении —
        иначе каждый сдвиг ползунка перерисовывал бы три фигуры сразу.
        """
        self.result = result
        self.fill_tables()
        self.profile = []
        if result.method == METHOD_ALPHA and engine is not None:
            self.profile = engine.profile(DEFAULT_ALPHA_GRID)
            views = {
                "scatter": self.show_plot,
                "profile": self.show_profile_plot,
                "matrix": lambda: self.show_matrix_plot(engine, result),
            }
        else:
            views = {
                "scatter": self.show_plot,
                "profile": lambda: self.profile_plot.show_alpha_profile([]),
                "matrix": lambda: self.matrix_plot.show_similarity_matrix([]),
            }

        active = self.view_notebook.index("current")
        self._stale_views: set = set()
        for index, name in enumerate(self.VIEW_NAMES):
            if log or index == active:
                views[name]()
            else:
                self._stale_views.add(name)

        self.result_label.configure(
            text=self._summary_text(include_silhouette=log), foreground=OK_COLOR
        )
        self.refresh_legend()
        if log:
            self.logger.log_clustering(result)

    def _on_view_changed(self, event: object = None) -> None:
        """Обновить представление, отложенное во время живой перестройки."""
        if not self._stale_views:
            return
        active = self.view_notebook.index("current")
        name = self.VIEW_NAMES[active]
        if name not in self._stale_views:
            return
        self._stale_views.discard(name)
        if name == "scatter":
            self.show_plot()
        elif name == "profile":
            self.show_profile_plot()
        elif name == "matrix" and self.engine is not None and self.result is not None:
            self.show_matrix_plot(self.engine, self.result)

    # ------------------------------------------------------------------
    # Интерактивный α-уровень
    # ------------------------------------------------------------------
    @staticmethod
    def _alpha_text(value: float) -> str:
        """Подпись текущего α под ползунком."""
        return f"α = {float(value):.2f}"

    def get_engine(
        self, sample: FuzzySet, metric: str, linkage: str
    ) -> AlphaClusterer:
        """Кэшированный движок α-кластеризации для текущей выборки и настроек.

        Тяжёлые матрицы (расстояний, сходства, замыкание, трасса агломерации)
        считаются один раз на комбинацию «выборка + метрика + связь», поэтому
        ползунок α пересчитывает кластеры за доли миллисекунды.
        """
        key = (id(sample), metric, linkage)
        if self.engine is None or self._engine_key != key:
            self.engine = AlphaClusterer(sample, metric=metric, linkage=linkage)
            self._engine_key = key
        return self.engine

    def _on_alpha_scale(self, value: object) -> None:
        """Ползунок α сдвинулся: обновить подписи и запланировать пересчёт."""
        if self._syncing_alpha:
            return
        level = float(value)
        self.alpha_entry.set(f"{level:.2f}")
        self.alpha_value_label.configure(text=self._alpha_text(level))
        self._schedule_alpha_recompute()

    def _schedule_alpha_recompute(self) -> None:
        """Пересчитать кластеры после паузы (движения ползунка объединяются)."""
        if self._alpha_job is not None:
            self.after_cancel(self._alpha_job)
        self._alpha_job = self.after(ALPHA_DEBOUNCE_MS, self.apply_alpha_change)

    def set_alpha_value(self, value: float, *, recompute: bool = True) -> float:
        """Задать α в ползунке и поле ввода (без обратного вызова ползунка)."""
        level = min(ALPHA_MAX, max(ALPHA_MIN, float(value)))
        self._syncing_alpha = True
        try:
            self.alpha_scale.set(level)
        finally:
            self._syncing_alpha = False
        self.alpha_entry.set(f"{level:.2f}")
        self.alpha_value_label.configure(text=self._alpha_text(level))
        if recompute:
            self.apply_alpha_change()
        return level

    def apply_alpha_change(self) -> Optional[ClusterResult]:
        """Пересчитать кластеры по текущему α (без записи в журнал).

        Возвращает результат или ``None``, если метод не α-уровень или выборки
        нет. Публичный метод: его вызывают и отложенный пересчёт, и тесты.
        """
        self._alpha_job = None
        if self.method_var.get() != METHOD_ALPHA:
            return None
        sample = self.current_sample()
        if sample is None or len(sample) == 0:
            return None
        try:
            alpha = float(self.alpha_entry.number())
            metric = self.metric_var.get()
            linkage = self.read_linkage()
            engine = self.get_engine(sample, metric, linkage)
            result = engine.clustering(alpha)
        except (ValueError, TypeError) as exc:
            self._report_error("Кластерный анализ", exc)
            return None
        self._present_result(result, engine, log=False)
        return result

    def show_profile_plot(self) -> None:
        """Обновить кривую k(α) по текущему профилю."""
        if not self.profile:
            self.profile_plot.show_alpha_profile([])
            return
        current = None
        if self.result is not None:
            current = self.result.parameters.get("alpha")
        self.profile_plot.show_alpha_profile(self.profile, current=current)

    def show_matrix_plot(
        self, engine: AlphaClusterer, result: ClusterResult
    ) -> None:
        """Обновить тепловую карту матрицы сходства (блоки — кластеры)."""
        order = [
            index
            for label in sorted(set(result.labels))
            for index, value in enumerate(result.labels)
            if value == label
        ]
        self.matrix_plot.show_similarity_matrix(
            engine.similarity,
            alpha=result.parameters.get("alpha"),
            order=order,
            labels=result.labels,
        )

    def toggle_alpha_play(self) -> bool:
        """Запустить или остановить «проигрывание» уровней α."""
        if self._playing:
            self.stop_alpha_play()
            return False
        self.start_alpha_play()
        return self._playing

    def start_alpha_play(self) -> None:
        """Начать пошаговый перебор уровней α (от строгого к мягкому)."""
        if self.method_var.get() != METHOD_ALPHA:
            return
        self._play_levels = sorted(DEFAULT_ALPHA_GRID, reverse=True)
        self._play_index = 0
        self._playing = True
        self.play_button.configure(text="■")
        self._tick_alpha_play()

    def stop_alpha_play(self) -> None:
        """Остановить перебор уровней α и вернуть кнопку в исходный вид."""
        self._playing = False
        if self._play_job is not None:
            self.after_cancel(self._play_job)
            self._play_job = None
        # Позиция «в конце» — повторный вызов шага ничего не изменит.
        self._play_index = len(self._play_levels)
        self.play_button.configure(text="▶")

    def advance_alpha_play(self) -> Optional[float]:
        """Один шаг перебора: установить следующий α и пересчитать.

        Возвращает установленный уровень или ``None``, когда уровни кончились.
        Публичный метод — тесты вызывают его без таймеров.
        """
        if self._play_index >= len(self._play_levels):
            return None
        level = self._play_levels[self._play_index]
        self._play_index += 1
        self.set_alpha_value(level, recompute=True)
        return level

    def _tick_alpha_play(self) -> None:
        self._play_job = None
        if not self._playing:
            return
        if self.advance_alpha_play() is None:
            self.stop_alpha_play()
            return
        self._play_job = self.after(ALPHA_PLAY_INTERVAL_MS, self._tick_alpha_play)

    # ------------------------------------------------------------------
    # Пошаговая агломерация (полная связь)
    # ------------------------------------------------------------------
    @staticmethod
    def _step_text(done: int, total: int) -> str:
        """Подпись текущего шага агломерации."""
        return f"шаг {done}/{total}"

    @staticmethod
    def _speed_text(speed: float) -> str:
        """Подпись скорости проигрывания (шагов в секунду)."""
        return f"{float(speed):.1f}/с"

    @staticmethod
    def _interval_for(speed: float) -> int:
        """Интервал в миллисекундах для скорости в шагах в секунду."""
        value = max(STEP_SPEED_MIN, float(speed))
        return max(30, int(round(1000.0 / value)))

    def step_interval_ms(self) -> int:
        """Пауза между шагами проигрывания по текущей скорости ползунка."""
        return self._interval_for(float(self.step_speed_scale.get()))

    def set_step_speed(self, speed: float, *, reschedule: bool = True) -> float:
        """Задать скорость проигрывания (шагов в секунду) и обновить подпись."""
        value = min(STEP_SPEED_MAX, max(STEP_SPEED_MIN, float(speed)))
        self._syncing_speed = True
        try:
            self.step_speed_scale.set(value)
        finally:
            self._syncing_speed = False
        self.step_speed_label.configure(text=self._speed_text(value))
        if reschedule and self._step_playing and self._step_job is not None:
            # Перепланируем ближайший шаг, чтобы новая скорость действовала сразу.
            self.after_cancel(self._step_job)
            self._step_job = self.after(self._interval_for(value), self._tick_step_play)
        return value

    def _on_step_speed(self, value: object) -> None:
        """Ползунок скорости сдвинулся."""
        if self._syncing_speed:
            return
        self.set_step_speed(float(value))

    def get_trace(self, sample: FuzzySet, metric: str) -> Agglomeration:
        """Кэшированная трасса агломерации полной связи для выборки.

        Трасса считается один раз на комбинацию «выборка + метрика»: дальше
        каждый шаг — это просто срез уже готовой последовательности слияний, а
        не повторный пересчёт матрицы расстояний.
        """
        key = (id(sample), metric)
        if self.trace is None or self._trace_key != key:
            self.trace = agglomerate(sample, metric=metric)
            self._trace_key = key
            self.step_index = 0
            self._update_step_label()
        return self.trace

    def _step_max(self) -> int:
        """Максимальный шаг, до которого идёт анимация.

        Если включена галочка «останавливаться на пороге» — предел равен
        шагу разреза дендрограммы по текущему порогу метода. Иначе — весь
        процесс до одного кластера.
        """
        if not self.step_stop_var.get():
            return len(self.trace.merges) if self.trace is not None else 0
        # Для метода «по порогу» читаем порог из параметров и считаем шаг разреза.
        try:
            threshold = self.threshold_entry.number()
        except (ValueError, TypeError):
            threshold = 1.0
        if self.trace is not None:
            return self.trace.cut_step(threshold)
        return 0

    def _on_step_stop_changed(self) -> None:
        """Галочка «останавливаться на пороге» переключилась."""
        if self._step_playing and self.step_index >= self._step_max():
            self.stop_step_play()
        else:
            self._update_step_label()

    def _update_step_label(self) -> None:
        total = len(self.trace.merges) if self.trace is not None else 0
        limit = self._step_max() if self.step_stop_var.get() else total
        self.step_label.configure(text=self._step_text(self.step_index, limit))

    def reset_agglomeration(self) -> Optional[Agglomeration]:
        """Вернуть агломерацию к началу: все величины — отдельные кластеры."""
        if self.method_var.get() != METHOD_THRESHOLD:
            return None
        sample = self.current_sample()
        if sample is None or len(sample) == 0:
            self._report_error(
                "Пошаговая агломерация",
                "выборка пуста — сначала сгенерируйте её на вкладке «Генерация и выборка»",
            )
            return None
        try:
            trace = self.get_trace(sample, self.metric_var.get())
        except (ValueError, TypeError) as exc:
            self._report_error("Пошаговая агломерация", exc)
            return None
        self.step_index = 0
        self._update_step_label()
        self._step_ui_stale = False
        self._present_step(trace)
        self.on_message(f"Агломерация: исходное состояние, {trace.size} кластеров")
        return trace

    def step_agglomeration(self, *, update_tables: bool = True) -> Optional[int]:
        """Выполнить один шаг агломерации (слить следующую пару кластеров).

        Публичный метод без таймеров: его вызывают и кнопка «Шаг», и тесты.
        Возвращает номер выполненного шага или ``None``, если шагов больше нет
        либо выбран другой метод.

        ``update_tables=False`` используется при автоматическом проигрывании:
        диаграмма и сводка обновляются, а тяжёлые таблицы и легенда — нет.
        Их пересобирает :meth:`stop_step_play`, когда проигрывание закончится.
        """
        if self.method_var.get() != METHOD_THRESHOLD:
            return None
        sample = self.current_sample()
        if sample is None or len(sample) == 0:
            self._report_error(
                "Пошаговая агломерация",
                "выборка пуста — сначала сгенерируйте её на вкладке «Генерация и выборка»",
            )
            return None
        try:
            trace = self.get_trace(sample, self.metric_var.get())
        except (ValueError, TypeError) as exc:
            self._report_error("Пошаговая агломерация", exc)
            return None
        max_step = self._step_max()
        if self.step_index >= max_step:
            self.stop_step_play()
            # Если остановились на пороге, показываем подсказку в сводке.
            if self.step_stop_var.get() and max_step > 0:
                try:
                    threshold = self.threshold_entry.number()
                    clusters = len(self.result.clusters) if self.result else 0
                    note = (
                        f" (достигнут порог {threshold:g} — {clusters} кластеров; "
                        f"увеличьте порог, чтобы продолжить)"
                    )
                except Exception:
                    note = " (достигнут порог кластеризации)"
                current_text = self.result_label.cget("text")
                if note not in current_text:
                    self.result_label.configure(text=current_text + note)
            return None
        self.step_index += 1
        self._update_step_label()
        merge = trace.steps()[self.step_index - 1]
        self.logger.info(
            f"Агломерация, {merge.describe()}; кластеров осталось {merge.cluster_count}"
        )
        self._present_step(trace, update_tables=update_tables)
        return self.step_index

    def toggle_step_play(self) -> bool:
        """Запустить или остановить проигрывание агломерации по шагам."""
        if self._step_playing:
            self.stop_step_play()
            return False
        self.start_step_play()
        return self._step_playing

    def start_step_play(self) -> None:
        """Начать автоматический перебор шагов агломерации."""
        if self.method_var.get() != METHOD_THRESHOLD:
            return
        sample = self.current_sample()
        if sample is None or len(sample) == 0:
            self._report_error(
                "Пошаговая агломерация",
                "выборка пуста — сначала сгенерируйте её на вкладке «Генерация и выборка»",
            )
            return
        trace = self.get_trace(sample, self.metric_var.get())
        # Если включена галочка «останавливаться на пороге» и порог меньше
        # последнего слияния, сбрасываем на начало, чтобы начать с шага 0.
        if self.step_stop_var.get() and self.step_index >= self._step_max():
            pass  # оставляем текущее состояние, не сбрасываем
        if self.step_index >= len(trace.merges) and not self.step_stop_var.get():
            self.reset_agglomeration()  # дошли до конца — начинаем заново
        max_step = self._step_max()
        if max_step == 0:
            self.reset_agglomeration()
        self._step_playing = True
        self.step_play_button.configure(text="■")
        self._tick_step_play()

    def stop_step_play(self) -> None:
        """Остановить проигрывание и вернуть кнопку в исходный вид."""
        was_playing = self._step_playing
        self._step_playing = False
        if self._step_job is not None:
            self.after_cancel(self._step_job)
            self._step_job = None
        if hasattr(self, "step_play_button"):
            self.step_play_button.configure(text="▶")
        if was_playing and self._step_ui_stale and self.result is not None:
            # Во время проигрывания таблицы и легенда не пересобирались —
            # догоняем их один раз по остановке.
            self._step_ui_stale = False
            self.fill_tables()
            self.refresh_legend()

    def _tick_step_play(self) -> None:
        self._step_job = None
        if not self._step_playing:
            return
        if self.step_agglomeration(update_tables=False) is None:
            self.stop_step_play()
            return
        self._step_job = self.after(self.step_interval_ms(), self._tick_step_play)

    def _present_step(
        self, trace: Agglomeration, *, update_tables: bool = True
    ) -> None:
        """Показать разбиение после текущего числа слияний."""
        sample = self.current_sample()
        if sample is None:
            return
        total = len(trace.merges)
        if self.step_index == 0:
            # Исходное состояние: кластеров ещё нет, точки рисуются серыми.
            labels = [NOISE_LABEL] * trace.size
            title = "Исходная выборка: шагов не выполнено"
        else:
            labels = trace.labels_after(self.step_index)
            title = f"Агломерация: шаг {self.step_index}/{total}"
        self.result = grouped_result(
            sample,
            labels,
            method=METHOD_THRESHOLD,
            metric=self.metric_var.get(),
            parameters={"step": self.step_index, "steps_total": total},
        )
        self.profile = []
        if update_tables:
            self._step_ui_stale = False
            self.fill_tables()
        else:
            # Таблицы догонят по остановке проигрывания (см. stop_step_play).
            self._step_ui_stale = True
        self.show_plot(title=title)
        self.result_label.configure(
            text=self._step_summary(trace), foreground=OK_COLOR
        )
        if update_tables:
            self.refresh_legend()

    def _step_summary(self, trace: Agglomeration) -> str:
        total = len(trace.merges)
        if self.step_index == 0:
            first = (
                f"Исходное состояние: все {trace.size} величин — отдельные кластеры."
            )
        else:
            merge = trace.steps()[self.step_index - 1]
            first = f"{merge.describe()} (всего шагов: {total})"
        clusters = len(self.result.clusters) if self.result is not None else 0
        return f"{first}\nКластеров: {clusters}."

    # ------------------------------------------------------------------
    # Вывод результатов
    # ------------------------------------------------------------------
    def fill_tables(self) -> None:
        """Заполнить таблицы по кластерам и по точкам."""
        result = self.result
        if result is None:
            self.cluster_table.clear()
            self.point_table.clear()
            return

        self.cluster_table.set_rows(
            (
                index,
                cluster.size,
                f"{cluster.centroid.center:.3f}",
                f"{cluster.centroid.width:.3f}",
                f"{cluster.diameter:.3f}",
                f"{cluster.center_variance:.3f}",
            )
            for index, cluster in enumerate(result.clusters, start=1)
        )
        self.point_table.set_rows(
            (
                index,
                f"{variable.a:.3f}",
                f"{variable.b:.3f}",
                f"{variable.center:.3f}",
                f"{variable.width:.3f}",
                "шум" if label == NOISE_LABEL else label,
            )
            for index, (variable, label) in enumerate(
                zip(result.items, result.labels), start=1
            )
        )

    def show_plot(self, title: Optional[str] = None) -> None:
        """Построить диаграмму рассеяния по кластерам.

        ``title`` задаётся для пошагового просмотра; по умолчанию заголовок
        собирается из метода и метрики текущего результата.
        """
        result = self.result
        if result is None:
            return
        if title is None:
            title = (
                f"Кластеры ({METHOD_LABELS.get(result.method, result.method)}, "
                f"метрика {result.metric})"
            )
        self.plot.show_scatter(
            [(variable.center, variable.width) for variable in result.items],
            result.labels,
            centroids=[
                (cluster.centroid.center, cluster.centroid.width)
                for cluster in result.clusters
            ],
            title=title,
        )

    def _summary_text(self, *, include_silhouette: bool = True) -> str:
        result = self.result
        assert result is not None
        sizes = list(result.sizes)
        shown = ", ".join(str(size) for size in sizes[:MAX_SIZES_IN_SUMMARY])
        if len(sizes) > MAX_SIZES_IN_SUMMARY:
            shown += f", … (всего {len(sizes)})"
        parts = [
            f"Кластеров: {len(result.clusters)}, шумовых точек: {len(result.noise)}",
            f"размеры: {shown}",
            f"средняя внутрикластерная дисперсия = {result.average_center_variance:.4f}",
            f"максимальный диаметр = {result.max_diameter:.4f}",
        ]
        if include_silhouette:
            silhouette = result.silhouette()
            parts.append(
                "silhouette = —"
                if silhouette is None
                else f"silhouette = {silhouette:.4f}"
            )
        else:
            # Живая перестройка: силуэт (O(n²)) не считаем — он появится после
            # нажатия «Кластеризовать».
            parts.append("silhouette — (нажмите «Кластеризовать»)")
        if self.profile:
            key_levels = {1.0, 0.9, 0.8, 0.7, 0.5, 0.3}
            shown = [
                point
                for point in self.profile
                if round(float(point["alpha"]), 2) in key_levels
            ]
            parts.append(
                "k(α): "
                + ", ".join(
                    f"{float(point['alpha']):.1f}→{point['cluster_count']}"
                    for point in shown
                )
            )
        return "\n".join(parts)

    def _report_error(self, caption: str, exc: Exception) -> None:
        message = exc if isinstance(exc, str) else str(exc)
        self.result = None
        self.profile = []
        self.cluster_table.clear()
        self.point_table.clear()
        self.result_label.configure(text=f"Ошибка: {message}", foreground=ERROR_COLOR)
        self.logger.log_error(caption, message)
        self.on_message(f"Ошибка: {message}")


# ----------------------------------------------------------------------
# Вкладка «Журнал»
# ----------------------------------------------------------------------
class LogTab(ttk.Frame):
    """Просмотр журнала текущей сессии и сохранение его в отдельный файл."""

    def __init__(
        self,
        master: tk.Misc,
        logger: SessionLogger,
        *,
        on_message: Optional[Callable[[str], None]] = None,
        autoupdate_ms: int = 2000,
        padding: int = 12,
    ) -> None:
        super().__init__(master, padding=padding)
        self.logger = logger
        self.on_message: Callable[[str], None] = on_message or (lambda text: None)
        self.autoupdate_ms = autoupdate_ms
        self.full_text = ""
        self.total_lines = 0
        self.visible_lines = 0
        self.saved_path: Optional[object] = None
        self.last_update: Optional[datetime] = None
        self._after_id: Optional[str] = None

        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_toolbar()
        self._build_info()
        self._build_view()
        self.reload()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew")

        self.reload_button = ttk.Button(toolbar, text="Обновить", command=self.reload)
        self.reload_button.pack(side="left")
        self.save_button = ttk.Button(
            toolbar, text="Сохранить как…", command=self.save_as
        )
        self.save_button.pack(side="left", padx=(6, 0))

        self.autoupdate_var = tk.BooleanVar(value=False)
        self.autoupdate_box = ttk.Checkbutton(
            toolbar,
            text=f"Автообновление ({self.autoupdate_ms // 1000} с)",
            variable=self.autoupdate_var,
            command=self._toggle_autoupdate,
        )
        self.autoupdate_box.pack(side="left", padx=(12, 0))

        ttk.Label(toolbar, text="Фильтр:", font=TEXT_FONT).pack(side="left", padx=(16, 4))
        self.filter_var = tk.StringVar(value="")
        self.filter_entry = ttk.Entry(toolbar, textvariable=self.filter_var, width=24)
        self.filter_entry.pack(side="left")
        self.filter_entry.bind("<Return>", lambda event: self.reload())
        ttk.Button(toolbar, text="Найти", command=self.reload).pack(side="left", padx=(4, 0))

    def _build_info(self) -> None:
        self.info_label = ttk.Label(
            self, text="", font=TEXT_FONT, foreground=HINT_COLOR, wraplength=1000,
            justify="left",
        )
        self.info_label.grid(row=1, column=0, sticky="w", pady=(6, 4))

    def _build_view(self) -> None:
        self.view = ProtocolView(self, height=22, wrap="none")
        self.view.grid(row=2, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    # Чтение журнала
    # ------------------------------------------------------------------
    def reload(self) -> str:
        """Перечитать журнал с диска и показать его с учётом фильтра."""
        try:
            text = self.logger.read()
        except OSError as exc:
            self._report_error("Чтение журнала", exc)
            return ""
        self.full_text = text
        shown = self._apply_filter(text)
        self.view.set_text(shown)
        self.last_update = datetime.now()
        self.info_label.configure(text=self._info_text(), foreground=HINT_COLOR)
        return text

    def on_tab_activated(self) -> None:
        """Обновить журнал при переключении пользователя на эту вкладку."""
        self.reload()

    def _apply_filter(self, text: str) -> str:
        """Отобрать строки журнала, содержащие введённый текст."""
        lines = text.splitlines()
        self.total_lines = len(lines)
        needle = self.filter_var.get().strip().lower()
        if needle:
            lines = [line for line in lines if needle in line.lower()]
        self.visible_lines = len(lines)
        return "\n".join(lines)

    def _info_text(self) -> str:
        stamp = self.last_update.strftime("%H:%M:%S") if self.last_update else "—"
        parts = [
            f"Файл: {self.logger.log_path}",
            f"строк: {self.total_lines} (показано {self.visible_lines})",
            f"обновлено {stamp}",
        ]
        if getattr(self, "saved_path", None) is not None:
            parts.append(f"последнее сохранение: {self.saved_path}")
        return "  |  ".join(parts)

    # ------------------------------------------------------------------
    # Автообновление
    # ------------------------------------------------------------------
    def _toggle_autoupdate(self) -> None:
        if self.autoupdate_var.get():
            self._schedule_reload()
        else:
            self._cancel_reload()

    def _schedule_reload(self) -> None:
        self._cancel_reload()
        self._after_id = self.after(self.autoupdate_ms, self._auto_reload)

    def _auto_reload(self) -> None:
        self._after_id = None
        self.reload()
        self._schedule_reload()

    def _cancel_reload(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:  # pragma: no cover - окно уже закрывается
                pass
            self._after_id = None

    @property
    def autoupdate_active(self) -> bool:
        """Запланировано ли следующее автообновление."""
        return self._after_id is not None

    def destroy(self) -> None:  # pragma: no cover - вызывается при закрытии окна
        self._cancel_reload()
        super().destroy()

    # ------------------------------------------------------------------
    # Сохранение
    # ------------------------------------------------------------------
    def save_as(self) -> Optional[object]:
        """Спросить имя файла и сохранить туда журнал."""
        target = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить журнал как",
            defaultextension=".log",
            initialfile=self.logger.log_path.name,
            initialdir=str(self.logger.log_dir),
            filetypes=[
                ("Журнал сессии", "*.log"),
                ("Текстовые файлы", "*.txt"),
                ("Все файлы", "*.*"),
            ],
        )
        if not target:
            self.on_message("Сохранение журнала отменено")
            return None
        return self.save_to(target)

    def save_to(self, path: object) -> Optional[object]:
        """Скопировать журнал в указанный файл."""
        target = Path(path)
        try:
            if target.parent and not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.full_text, encoding="utf-8")
        except OSError as exc:
            self._report_error("Сохранение журнала", exc)
            return None

        self.saved_path = target
        self.logger.info(f"Журнал сохранён в файл: {target}")
        self.reload()
        self.on_message(f"Журнал сохранён: {target}")
        return target

    def _report_error(self, caption: str, exc: Exception) -> None:
        message = exc if isinstance(exc, str) else str(exc)
        self.info_label.configure(text=f"Ошибка: {caption}: {message}", foreground=ERROR_COLOR)
        self.logger.log_error(caption, message)
        self.on_message(f"Ошибка: {message}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Точка входа приложения (используется в ``main.py``)."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Нечеткие величины равномерного типа и кластерный анализ (вариант 1)",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="каталог журналов (по умолчанию logs/ в корне проекта)",
    )
    args = parser.parse_args(argv)

    try:
        app = FuzzyApp(log_dir=args.log_dir)
    except tk.TclError as exc:
        print(f"Не удалось открыть графическое окно: {exc}", file=sys.stderr)
        return 2

    return app.run()
