"""Простые компоненты интерфейса: вкладки, строка состояния, служебные функции."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "LabeledEntry",
    "LegendPanel",
    "PlaceholderTab",
    "ProtocolView",
    "StatusBar",
    "Table",
    "center_window",
    "parse_number",
]

TITLE_FONT = ("Segoe UI", 12, "bold")
TEXT_FONT = ("Segoe UI", 10)
LEGEND_FONT = ("Segoe UI", 8)
MONO_FONT = ("Consolas", 9)
HINT_COLOR = "#444444"
PATH_COLOR = "#555555"


def center_window(window: tk.Misc, width: int, height: int) -> None:
    """Разместить окно по центру экрана с заданными размерами."""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 3)
    window.geometry(f"{width}x{height}+{x}+{y}")


class PlaceholderTab(ttk.Frame):
    """Вкладка-заготовка: заголовок, описание и список планируемых возможностей.

    Используется на этапе разработки интерфейса, пока вкладка ещё не наполнена.
    """

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        description: str = "",
        hints: Optional[Iterable[str]] = None,
    ) -> None:
        super().__init__(master, padding=20)
        self.title = title

        self.title_label = ttk.Label(self, text=title, font=TITLE_FONT)
        self.title_label.pack(anchor="w")

        if description:
            self.description_label = ttk.Label(
                self, text=description, font=TEXT_FONT, wraplength=900, justify="left"
            )
            self.description_label.pack(anchor="w", pady=(8, 12))
        else:
            self.description_label = None

        self.hint_labels = []
        for hint in hints or ():
            label = ttk.Label(
                self, text=f"•  {hint}", font=TEXT_FONT, foreground=HINT_COLOR, justify="left"
            )
            label.pack(anchor="w", pady=1)
            self.hint_labels.append(label)


class StatusBar(ttk.Frame):
    """Строка состояния: текущее сообщение и путь к файлу журнала."""

    def __init__(
        self,
        master: tk.Misc,
        message: str = "Готово",
        log_path: Optional[object] = None,
    ) -> None:
        super().__init__(master, padding=(8, 4))
        self._message = tk.StringVar(value=message)
        self._log_text = tk.StringVar(value="" if log_path is None else f"Журнал: {log_path}")

        self.message_label = ttk.Label(self, textvariable=self._message, font=TEXT_FONT)
        self.message_label.pack(side="left")

        self.path_label = ttk.Label(
            self, textvariable=self._log_text, font=TEXT_FONT, foreground=PATH_COLOR
        )
        self.path_label.pack(side="right")

    # ------------------------------------------------------------------
    @property
    def message(self) -> str:
        """Текущее сообщение строки состояния."""
        return self._message.get()

    @property
    def log_text(self) -> str:
        """Подпись с путём к журналу."""
        return self._log_text.get()

    def set_message(self, text: str) -> None:
        """Заменить текущее сообщение."""
        self._message.set(text)

    def set_log_path(self, path: object) -> None:
        """Показать путь к файлу журнала."""
        self._log_text.set(f"Журнал: {path}")


def parse_number(text: object, *, name: str = "значение") -> float:
    """Преобразовать введённый текст в число.

    Принимается и точка, и запятая как десятичный разделитель (привычная
    русская запись), например ``"1,5"`` → ``1.5``.
    """
    if text is None:
        raise ValueError(f"не задано поле «{name}»")
    cleaned = str(text).strip().replace(",", ".")
    if cleaned == "":
        raise ValueError(f"не задано поле «{name}»")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"поле «{name}»: не удалось прочитать число из {text!r}") from exc


class LabeledEntry(ttk.Frame):
    """Поле ввода с подписью слева.

    Доступ к введённому тексту — :attr:`text`, к числу — :meth:`number`.
    """

    def __init__(
        self,
        master: tk.Misc,
        label: str,
        *,
        value: object = "",
        width: int = 10,
    ) -> None:
        super().__init__(master)
        self._label_text = label
        self.variable = tk.StringVar(value=str(value))
        self.label = ttk.Label(self, text=label, font=TEXT_FONT)
        self.label.pack(side="left", padx=(0, 4))
        self.entry = ttk.Entry(self, textvariable=self.variable, width=width)
        self.entry.pack(side="left")

    @property
    def text(self) -> str:
        """Текущее содержимое поля."""
        return self.variable.get()

    def set(self, value: object) -> None:
        """Записать значение в поле."""
        self.variable.set(str(value))

    def number(self) -> float:
        """Прочитать содержимое поля как число."""
        return parse_number(self.variable.get(), name=self._label_text)


class ProtocolView(ttk.Frame):
    """Прокручиваемый протокол (текст только для чтения)."""

    def __init__(
        self, master: tk.Misc, *, title: str = "", height: int = 10, wrap: str = "word"
    ) -> None:
        super().__init__(master)
        self.title_label: Optional[ttk.Label] = None
        if title:
            self.title_label = ttk.Label(self, text=title, font=TEXT_FONT)
            self.title_label.pack(anchor="w")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        self.text = tk.Text(
            body,
            height=height,
            wrap=wrap,
            state="disabled",
            font=MONO_FONT,
            background="#fbfbfb",
        )
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        # Полосу упаковываем ДО текста, иначе текст занимает всю ширину и сжимает её.
        scrollbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    @property
    def content(self) -> str:
        """Весь текст протокола без завершающих переводов строки."""
        return self.text.get("1.0", "end-1c").rstrip("\n")

    def append(self, line: str = "") -> None:
        """Добавить строку в конец протокола."""
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def append_many(self, lines: Iterable[str]) -> None:
        """Добавить несколько строк."""
        for line in lines:
            self.append(line)

    def set_text(self, text: str) -> None:
        """Полностью заменить текст протокола."""
        self.clear()
        if text:
            self.append(text.rstrip("\n"))

    def clear(self) -> None:
        """Очистить протокол."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class Table(ttk.Frame):
    """Таблица с прокруткой на основе ``ttk.Treeview``.

    Столбцы задаются последовательностью троек ``(ключ, заголовок, ширина)``.
    """

    def __init__(
        self,
        master: tk.Misc,
        columns: Sequence[Tuple[str, str, int]],
        *,
        height: int = 18,
    ) -> None:
        super().__init__(master)
        self.keys: Tuple[str, ...] = tuple(key for key, _, _ in columns)

        self.tree = ttk.Treeview(self, columns=list(self.keys), show="headings", height=height)
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            anchor = "e" if key != "index" else "center"
            self.tree.column(key, width=width, anchor=anchor, stretch=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        # Полосу упаковываем ДО таблицы, иначе таблица занимает всю ширину и сжимает её.
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

    # ------------------------------------------------------------------
    @property
    def row_count(self) -> int:
        """Число строк в таблице."""
        return len(self.tree.get_children())

    def add_row(self, values: Sequence[object]) -> None:
        """Добавить строку в конец таблицы."""
        self.tree.insert("", "end", values=tuple(values))

    def set_rows(self, rows: Iterable[Sequence[object]]) -> None:
        """Заменить всё содержимое таблицы."""
        self.clear()
        for row in rows:
            self.add_row(row)

    def row(self, index: int) -> Tuple[str, ...]:
        """Значения строки по её номеру (строки — числа, как в таблице)."""
        item = self.tree.get_children()[index]
        return tuple(str(value) for value in self.tree.item(item, "values"))

    def rows(self) -> Iterable[Tuple[str, ...]]:
        """Все строки таблицы."""
        for item in self.tree.get_children():
            yield tuple(str(value) for value in self.tree.item(item, "values"))

    def clear(self) -> None:
        """Удалить все строки."""
        for item in self.tree.get_children():
            self.tree.delete(item)


class LegendPanel(ttk.Frame):
    """Прокручиваемый список легенды: цветной образец и пояснение.

    Используется, когда подписей слишком много для легенды на самом графике:
    панель можно показать кнопкой и снова скрыть. Список прокручивается
    полосой и колесом мыши.
    """

    def __init__(self, master: tk.Misc, *, title: str = "Легенда", width: int = 230) -> None:
        super().__init__(master, padding=(6, 4))
        self.title_label = ttk.Label(self, text=title, font=TEXT_FONT)
        self.title_label.pack(anchor="w", pady=(0, 4))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, width=width, highlightthickness=0, background="#fdfdfd")
        self.scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        # Полосу упаковываем ДО холста: иначе холст займёт всю ширину и сожмёт её.
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.rows: List[tk.Widget] = []
        self.items: List[Tuple[str, str, str]] = []

    # ------------------------------------------------------------------
    def _on_inner_configure(self, event: object = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: object = None) -> None:
        self.canvas.itemconfigure(self._window, width=max(self.canvas.winfo_width(), 1))

    def _on_mousewheel(self, event: object) -> str:
        step = -1 if getattr(event, "delta", 0) > 0 else 1
        self.canvas.yview_scroll(step * 3, "units")
        return "break"

    def _bind_wheel(self, widget: tk.Misc) -> None:
        """Прокрутка колесом: событие приходит тому виджету, на который наведён курсор."""
        widget.bind("<MouseWheel>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_wheel(child)

    @property
    def item_count(self) -> int:
        """Число строк легенды."""
        return len(self.rows)

    @property
    def captions(self) -> List[str]:
        """Подписи строк (например, ``кластер 3``)."""
        return [caption for _, caption, _ in self.items]

    def set_items(self, items: Iterable[Tuple[str, str, str]]) -> None:
        """Заполнить легенду тройками ``(цвет, подпись, пояснение)``."""
        self.clear()
        self.items = list(items)
        for color, caption, description in self.items:
            row = ttk.Frame(self.inner)
            row.pack(fill="x", pady=1)

            swatch = tk.Frame(row, width=14, height=14, background=color, relief="solid",
                              borderwidth=1)
            swatch.pack(side="left", padx=(0, 6))
            swatch.pack_propagate(False)

            column = ttk.Frame(row)
            column.pack(side="left", fill="x", expand=True)
            ttk.Label(column, text=caption, font=TEXT_FONT).pack(anchor="w")
            if description:
                ttk.Label(
                    column, text=description, font=LEGEND_FONT, foreground=HINT_COLOR
                ).pack(anchor="w")
            self.rows.append(row)
        self.canvas.yview_moveto(0.0)
        self._bind_wheel(self.canvas)
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def clear(self) -> None:
        """Убрать все строки легенды."""
        for row in self.rows:
            row.destroy()
        self.rows = []
        self.items = []
        self.canvas.configure(scrollregion=(0, 0, 0, 0))

