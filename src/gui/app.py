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
    DISTANCE_METRICS,
    MAX_COUNT,
    MIN_COUNT,
    NOISE_LABEL,
    ClusterResult,
    FuzzySet,
    UniformFuzzyVariable,
    cluster,
    generate_sample,
    get_distance_function,
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
        "внутрикластерного расстояния или по плотности; таблица результатов и диаграмма."
    ),
    TAB_LOG: (
        "Журнал текущей сессии с метками времени: просмотр и сохранение в отдельный файл."
    ),
}

TAB_HINTS: Dict[str, Sequence[str]] = {
    TAB_ARITHMETIC: ("Операции: сложение, вычитание, умножение, деление, сравнение",),
    TAB_GENERATION: ("Параметры: a ~ U(-10, 10), w ~ U(0, 4), объём 100…300, seed",),
    TAB_CLUSTERING: ("Методы: K-Means, пороговый (полная связь), плотностной (DBSCAN)",),
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
        self.root.configure(menu=menu_bar)

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
METHOD_DENSITY = "density"

METHOD_LABELS: Dict[str, str] = {
    METHOD_KMEANS: "K-Means: на K кластеров",
    METHOD_THRESHOLD: "По порогу (полная связь)",
    METHOD_DENSITY: "По плотности (DBSCAN-подобный)",
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


class ClusteringTab(ttk.Frame):
    """Кластерный анализ сгенерированной выборки.

    Доступны три метода: K-Means на заданное число кластеров, агломеративный
    по порогу внутрикластерного расстояния (полная связь) и плотностной
    (DBSCAN-подобный). Результаты показываются таблицами по кластерам и по
    точкам, а также диаграммой рассеяния в координатах (центр c, ширина w).
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
        panel = ttk.Frame(self)
        panel.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 10))

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
        for row, key in enumerate((METHOD_KMEANS, METHOD_THRESHOLD, METHOD_DENSITY)):
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
        self.parameter_entries = {
            METHOD_KMEANS: (self.k_entry,),
            METHOD_THRESHOLD: (self.threshold_entry,),
            METHOD_DENSITY: (self.eps_entry, self.min_points_entry),
        }

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(8, 0))
        self.run_button = ttk.Button(buttons, text="Кластеризовать", command=self.run)
        self.run_button.pack(fill="x")

        summary = ttk.LabelFrame(panel, text="Результат", padding=10)
        summary.pack(fill="x", pady=(8, 0))
        self.result_label = ttk.Label(
            summary, text="Анализ не выполнялся.", font=TEXT_FONT, wraplength=300,
            justify="left",
        )
        self.result_label.pack(anchor="w")

        self._update_parameter_state()

    def _build_plot(self) -> None:
        # Кнопка полной легенды — над графиком.
        self.plot_toolbar = ttk.Frame(self)
        self.plot_toolbar.grid(row=0, column=1, sticky="ew")
        self.legend_button = ttk.Button(
            self.plot_toolbar,
            text="Легенда",
            command=self.toggle_legend,
            state="disabled",
        )
        self.legend_button.pack(side="right")

        # График и таблицы — в раздвижной панели: пользователь сам решает,
        # чему отдать больше места, и ничего не уезжает за край окна.
        self.paned = ttk.PanedWindow(self, orient="vertical")
        self.paned.grid(row=1, column=1, sticky="nsew")

        # Внутри верхней части — ещё одна раздвижная панель: график + легенда.
        self.plot_area = ttk.PanedWindow(self.paned, orient="horizontal")
        self.paned.add(self.plot_area, weight=3)

        self.plot = MembershipPlot(self.plot_area, height=3.4, toolbar=False)
        self.plot_area.add(self.plot, weight=4)

        self.legend_panel = LegendPanel(self.plot_area)
        self.legend_visible = False

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
            self.plot_area.add(self.legend_panel, weight=1)
            self.legend_visible = True
        self._update_legend_button()
        return self.legend_visible

    def refresh_legend(self) -> None:
        """Пересобрать содержимое панели легенды по текущему результату."""
        self.legend_panel.set_items(self._legend_items())
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
        active = set(self.parameter_entries[self.method_var.get()])
        for entries in self.parameter_entries.values():
            for entry in entries:
                state = "normal" if entry in active else "disabled"
                entry.entry.configure(state=state)
        self.seed_entry.entry.configure(
            state="normal" if self.method_var.get() == METHOD_KMEANS else "disabled"
        )

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
        if key == METHOD_DENSITY:
            min_points = self.min_points_entry.number()
            if not float(min_points).is_integer():
                raise ValueError(
                    f"minPts: минимальное число точек должно быть целым, получено {min_points}"
                )
            return {"eps": self.eps_entry.number(), "min_points": int(min_points)}
        raise ValueError(f"неизвестный метод кластеризации: {key!r}")

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
            result = cluster(sample, method, metric=metric, **parameters)
        except (ValueError, TypeError) as exc:
            self._report_error("Кластерный анализ", exc)
            return None

        self.result = result
        self.fill_tables()
        self.show_plot()
        self.result_label.configure(text=self._summary_text(), foreground=OK_COLOR)
        self.refresh_legend()
        self.logger.log_clustering(result)
        seed = parameters.get("seed")
        self.on_message(
            f"Кластеризация ({METHOD_LABELS[method]}): кластеров {len(result.clusters)}"
            + (f", seed={seed!r}" if seed is not None else "")
        )
        self.on_result(result)
        return result

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

    def show_plot(self) -> None:
        """Построить диаграмму рассеяния по кластерам."""
        result = self.result
        if result is None:
            return
        self.plot.show_scatter(
            [(variable.center, variable.width) for variable in result.items],
            result.labels,
            centroids=[
                (cluster.centroid.center, cluster.centroid.width)
                for cluster in result.clusters
            ],
            title=(
                f"Кластеры ({METHOD_LABELS.get(result.method, result.method)}, "
                f"метрика {result.metric})"
            ),
        )

    def _summary_text(self) -> str:
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
        silhouette = result.silhouette()
        parts.append(
            "silhouette = —" if silhouette is None else f"silhouette = {silhouette:.4f}"
        )
        return "\n".join(parts)

    def _report_error(self, caption: str, exc: Exception) -> None:
        message = exc if isinstance(exc, str) else str(exc)
        self.result = None
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
