"""Графический интерфейс пользователя (Tkinter).

Пакет использует библиотеку :mod:`fuzzy_core` и подсистему журналирования
:mod:`logger`, но сам от них не зависит в обратную сторону.
"""

from .app import (
    APP_TITLE,
    TAB_TITLES,
    ArithmeticTab,
    ClusteringTab,
    FuzzyApp,
    GenerationTab,
    LogTab,
    main,
)
from .plotter import MembershipPlot, membership_points
from .widgets import (
    LabeledEntry,
    PlaceholderTab,
    ProtocolView,
    StatusBar,
    Table,
    center_window,
    parse_number,
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
    "MembershipPlot",
    "membership_points",
    "PlaceholderTab",
    "LabeledEntry",
    "ProtocolView",
    "StatusBar",
    "Table",
    "center_window",
    "parse_number",
]
__version__ = "0.1.0"
