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
from numbers import Real
from typing import Callable, Iterator, Tuple

__all__ = [
    "UniformFuzzyVariable",
    "FuzzyVariableError",
    "euclidean_distance",
    "hausdorff_distance",
    "DISTANCE_METRICS",
    "get_distance_function",
]


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
    # Арифметические операции (принцип обобщения Заде / интервальная арифметика)
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce(other: object) -> "UniformFuzzyVariable":
        """Привести операнд к нечеткой величине (число -> вырожденный интервал)."""
        if isinstance(other, UniformFuzzyVariable):
            return other
        if isinstance(other, Real):
            return UniformFuzzyVariable(float(other), float(other))
        raise TypeError(
            f"Ожидалась нечеткая величина или число, получено {type(other).__name__}"
        )

    def _try_coerce(self, other: object) -> "UniformFuzzyVariable | None":
        """Как ``_coerce``, но возвращает ``None`` вместо исключения."""
        try:
            return self._coerce(other)
        except TypeError:
            return None

    def __add__(self, other: object) -> "UniformFuzzyVariable":
        """[a1, b1] + [a2, b2] = [a1 + a2, b1 + b2]."""
        o = self._coerce(other)
        return UniformFuzzyVariable(self._a + o._a, self._b + o._b)

    # Сложение коммутативно.
    __radd__ = __add__

    def __sub__(self, other: object) -> "UniformFuzzyVariable":
        """[a1, b1] - [a2, b2] = [a1 - b2, b1 - a2]."""
        o = self._coerce(other)
        return UniformFuzzyVariable(self._a - o._b, self._b - o._a)

    def __rsub__(self, other: object) -> "UniformFuzzyVariable":
        return self._coerce(other).__sub__(self)

    def __neg__(self) -> "UniformFuzzyVariable":
        """-[a, b] = [-b, -a]."""
        return UniformFuzzyVariable(-self._b, -self._a)

    def __mul__(self, other: object) -> "UniformFuzzyVariable":
        """[a1, b1] * [a2, b2] = [min P, max P], P = {a1a2, a1b2, b1a2, b1b2}."""
        o = self._coerce(other)
        products = (
            self._a * o._a,
            self._a * o._b,
            self._b * o._a,
            self._b * o._b,
        )
        return UniformFuzzyVariable(min(products), max(products))

    # Умножение коммутативно.
    __rmul__ = __mul__

    def __truediv__(self, other: object) -> "UniformFuzzyVariable":
        """[a1, b1] / [a2, b2] = [a1, b1] * [1/b2, 1/a2], если 0 не в [a2, b2]."""
        o = self._coerce(other)
        if o._a <= 0.0 <= o._b:
            raise FuzzyVariableError(
                f"Деление невозможно: интервал делителя [{o._a:g}, {o._b:g}] содержит 0"
            )
        reciprocal = UniformFuzzyVariable(1.0 / o._b, 1.0 / o._a)
        return self.__mul__(reciprocal)

    def __rtruediv__(self, other: object) -> "UniformFuzzyVariable":
        return self._coerce(other).__truediv__(self)

    # ------------------------------------------------------------------
    # Расстояния между величинами
    # ------------------------------------------------------------------
    def hausdorff_distance(self, other: object) -> float:
        """Метрика Хаусдорфа: ``max(|a1 - a2|, |b1 - b2|)``."""
        o = self._coerce(other)
        return max(abs(self._a - o._a), abs(self._b - o._b))

    def euclidean_distance(self, other: object) -> float:
        """Евклидово расстояние между границами.

        ``sqrt(((a1 - a2)^2 + (b1 - b2)^2) / 2)``.
        """
        o = self._coerce(other)
        return math.sqrt(
            ((self._a - o._a) ** 2 + (self._b - o._b) ** 2) / 2.0
        )

    def distance(self, other: object, metric: str = "hausdorff") -> float:
        """Расстояние до другой величины по выбранной метрике."""
        return get_distance_function(metric)(self, other)

    # ------------------------------------------------------------------
    # Сравнение и ранжирование
    # ------------------------------------------------------------------
    def rank_key(self) -> Tuple[float, float]:
        """Ключ ранжирования: сначала модальный центр, затем ширина."""
        return (self.center, self.width)

    def compare(self, other: object) -> int:
        """Сравнить с другой величиной: -1, 0 или 1."""
        o = self._coerce(other)
        if self.rank_key() < o.rank_key():
            return -1
        if self.rank_key() > o.rank_key():
            return 1
        return 0

    def __lt__(self, other: object) -> bool:
        o = self._try_coerce(other)
        if o is None:
            return NotImplemented
        return self.rank_key() < o.rank_key()

    def __le__(self, other: object) -> bool:
        o = self._try_coerce(other)
        if o is None:
            return NotImplemented
        return self.rank_key() <= o.rank_key()

    def __gt__(self, other: object) -> bool:
        o = self._try_coerce(other)
        if o is None:
            return NotImplemented
        return self.rank_key() > o.rank_key()

    def __ge__(self, other: object) -> bool:
        o = self._try_coerce(other)
        if o is None:
            return NotImplemented
        return self.rank_key() >= o.rank_key()

    def possibility_greater_or_equal(self, other: object) -> float:
        """Индекс возможности ``Pos(A >= B)``: 1, если ``b1 >= a2``, иначе 0."""
        o = self._coerce(other)
        return 1.0 if self._b >= o._a else 0.0

    def necessity_greater_or_equal(self, other: object) -> float:
        """Индекс необходимости ``Nec(A >= B)``: 1, если ``a1 >= b2``, иначе 0."""
        o = self._coerce(other)
        return 1.0 if self._a >= o._b else 0.0

    def dominance(self, other: object) -> float:
        """Степень доминирования — вероятность превышения ``P(X_A > X_B)``.

        Величины трактуются как равномерно распределённые на своих носителях
        (что соответствует равномерной функции принадлежности варианта 1).
        Результат лежит в ``[0, 1]``; для одинаковых вырожденных величин — 0.5.
        """
        o = self._coerce(other)
        return _probability_greater(self._a, self._b, o._a, o._b)

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


# ----------------------------------------------------------------------
# Расстояния (модульный уровень — удобно передавать как функцию в
# кластерный анализ: metric может быть как именем, так и callable)
# ----------------------------------------------------------------------
def hausdorff_distance(first: object, second: object) -> float:
    """Метрика Хаусдорфа между двумя нечеткими величинами (или числами)."""
    return UniformFuzzyVariable._coerce(first).hausdorff_distance(second)


def euclidean_distance(first: object, second: object) -> float:
    """Евклидово расстояние между границами двух величин (или чисел)."""
    return UniformFuzzyVariable._coerce(first).euclidean_distance(second)


DISTANCE_METRICS: dict[str, Callable[[object, object], float]] = {
    "hausdorff": hausdorff_distance,
    "euclidean": euclidean_distance,
}


def get_distance_function(metric: str = "hausdorff") -> Callable[[object, object], float]:
    """Вернуть функцию расстояния по её имени (``hausdorff`` / ``euclidean``)."""
    key = str(metric).strip().lower()
    if key not in DISTANCE_METRICS:
        available = ", ".join(sorted(DISTANCE_METRICS))
        raise ValueError(f"Неизвестная метрика {metric!r}. Доступны: {available}")
    return DISTANCE_METRICS[key]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _probability_greater(a1: float, b1: float, a2: float, b2: float) -> float:
    """Вероятность ``P(X_A > X_B)`` для независимых ``X_A ~ U[a1, b1]``, ``X_B ~ U[a2, b2]``.

    Реализована по замкнутой формуле для трапецеидального распределения разности;
    вырожденные (точечные) интервалы обрабатываются отдельно.
    """
    w1 = b1 - a1
    w2 = b2 - a2

    if w1 <= 0.0 and w2 <= 0.0:  # обе величины вырождены в точки
        if a1 > a2:
            return 1.0
        if a1 < a2:
            return 0.0
        return 0.5
    if w1 <= 0.0:  # A — точка
        return _clamp((a1 - a2) / w2)
    if w2 <= 0.0:  # B — точка
        return _clamp((b1 - a2) / w1)

    def positive(x: float) -> float:
        return x if x > 0.0 else 0.0

    numerator = (
        positive(b1 - a2) ** 2
        - positive(a1 - a2) ** 2
        - positive(b1 - b2) ** 2
        + positive(a1 - b2) ** 2
    )
    return _clamp(numerator / (2.0 * w1 * w2))
