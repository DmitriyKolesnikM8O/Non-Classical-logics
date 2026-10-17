"""Нечеткая величина с равномерной (прямоугольной) функцией принадлежности.

Теоретическая модель (вариант 1):

        ⎧ 1, если a <= x <= b
mu(x) = ⎨
        ⎩ 0, если x < a или x > b

Числовые характеристики:
    - модальный центр  c = (a + b) / 2,
    - ширина носителя  w = b - a.

Модуль намеренно не зависит от GUI и логгера: это часть независимой
библиотеки ``fuzzy_core``.
"""

from __future__ import annotations

import math
from typing import Iterator, Tuple

__all__ = ["UniformFuzzyVariable", "FuzzyVariableError"]


class FuzzyVariableError(ValueError):
    """Некорректные параметры нечеткой величины."""


class UniformFuzzyVariable:
    """Нечеткая величина равномерного типа, задаваемая носителем ``[a, b]``.

    Параметры
    ---------
    a, b:
        Границы носителя, должны удовлетворять условию ``a <= b`` и быть
        конечными числами. При ``a == b`` величина вырождается в точку.
    """

    __slots__ = ("_a", "_b")

    def __init__(self, a: float, b: float) -> None:
        a = float(a)
        b = float(b)
        if not (math.isfinite(a) and math.isfinite(b)):
            raise FuzzyVariableError(
                f"Границы должны быть конечными числами, получено a={a!r}, b={b!r}"
            )
        if a > b:
            raise FuzzyVariableError(
                f"Требуется a <= b, получено a={a!r}, b={b!r}"
            )
        self._a = a
        self._b = b

    # ------------------------------------------------------------------
    # Конструирование
    # ------------------------------------------------------------------
    @classmethod
    def from_center_width(cls, center: float, width: float) -> "UniformFuzzyVariable":
        """Создать величину по центру ``c`` и ширине ``w`` (``w >= 0``)."""
        center = float(center)
        width = float(width)
        if not math.isfinite(center) or not math.isfinite(width):
            raise FuzzyVariableError("Центр и ширина должны быть конечными числами")
        if width < 0:
            raise FuzzyVariableError(f"Ширина не может быть отрицательной, получено {width!r}")
        half = width / 2.0
        return cls(center - half, center + half)

    # ------------------------------------------------------------------
    # Параметры и числовые характеристики
    # ------------------------------------------------------------------
    @property
    def a(self) -> float:
        """Левая граница носителя."""
        return self._a

    @property
    def b(self) -> float:
        """Правая граница носителя."""
        return self._b

    @property
    def center(self) -> float:
        """Модальный центр ``c = (a + b) / 2``."""
        return (self._a + self._b) / 2.0

    @property
    def width(self) -> float:
        """Ширина носителя ``w = b - a``."""
        return self._b - self._a

    # Короткие псевдонимы по обозначениям из методички.
    c = center
    w = width

    @property
    def support(self) -> Tuple[float, float]:
        """Носитель величины ``[a, b]``."""
        return (self._a, self._b)

    @property
    def core(self) -> Tuple[float, float]:
        """Ядро (множество точек с ``mu(x) = 1``).

        Для равномерного типа ядро совпадает с носителем.
        """
        return (self._a, self._b)

    @property
    def is_crisp(self) -> bool:
        """``True``, если величина вырождена в точку (``a == b``)."""
        return self._a == self._b

    # ------------------------------------------------------------------
    # Функция принадлежности
    # ------------------------------------------------------------------
    def membership(self, x: float) -> float:
        """Значение функции принадлежности ``mu(x)``."""
        x = float(x)
        return 1.0 if self._a <= x <= self._b else 0.0

    mu = membership

    def __call__(self, x: float) -> float:
        """``v(x)`` — сокращённая запись для ``v.mu(x)``."""
        return self.membership(x)

    # ------------------------------------------------------------------
    # Служебные методы
    # ------------------------------------------------------------------
    def __iter__(self) -> Iterator[float]:
        """Позволяет распаковывать величину: ``a, b = variable``."""
        yield self._a
        yield self._b

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UniformFuzzyVariable):
            return NotImplemented
        return self._a == other._a and self._b == other._b

    def __hash__(self) -> int:
        return hash((self._a, self._b))

    def __repr__(self) -> str:
        return f"UniformFuzzyVariable(a={self._a:g}, b={self._b:g})"
