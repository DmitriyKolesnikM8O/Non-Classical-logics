"""Генератор случайных выборок нечетких величин равномерного типа.

По заданию объём выборки — от 100 до 300 элементов. Величина строится по схеме

    a ~ U(a_low, a_high),   w ~ U(width_low, width_high),   [a, a + w],

то есть левая граница и ширина разыгрываются независимо, а условие ``a <= b``
выполняется автоматически при ``w >= 0``.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

from .fuzzy_set import FuzzySet
from .fuzzy_variable import UniformFuzzyVariable

__all__ = [
    "generate_sample",
    "generate_variables",
    "MIN_COUNT",
    "MAX_COUNT",
    "DEFAULT_COUNT_RANGE",
    "DEFAULT_A_RANGE",
    "DEFAULT_WIDTH_RANGE",
]

#: Границы объёма выборки из задания.
MIN_COUNT = 100
MAX_COUNT = 300

DEFAULT_COUNT_RANGE: Tuple[int, int] = (MIN_COUNT, MAX_COUNT)
DEFAULT_A_RANGE: Tuple[float, float] = (-10.0, 10.0)
DEFAULT_WIDTH_RANGE: Tuple[float, float] = (0.0, 4.0)

NumberPair = Sequence[float]


def _validate_pair(bounds: NumberPair, name: str) -> Tuple[float, float]:
    """Проверить пару границ ``(low, high)`` и вернуть её как кортеж чисел."""
    try:
        low = float(bounds[0])
        high = float(bounds[1])
    except (TypeError, IndexError, KeyError, ValueError) as exc:
        raise ValueError(f"{name}: ожидалась пара (low, high), получено {bounds!r}") from exc
    if not (math.isfinite(low) and math.isfinite(high)):
        raise ValueError(f"{name}: границы должны быть конечными числами")
    if low > high:
        raise ValueError(f"{name}: требуется low <= high, получено {low!r} > {high!r}")
    return low, high


def generate_variables(
    rng: random.Random,
    count: int,
    a_range: NumberPair = DEFAULT_A_RANGE,
    width_range: NumberPair = DEFAULT_WIDTH_RANGE,
) -> List[UniformFuzzyVariable]:
    """Сгенерировать список величин, используя готовый генератор случайных чисел.

    Низкоуровневая функция: удобна для воспроизводимых экспериментов
    (задаётся ``random.Random(seed)``).
    """
    a_low, a_high = _validate_pair(a_range, "a_range")
    w_low, w_high = _validate_pair(width_range, "width_range")
    if w_low < 0.0:
        raise ValueError(f"width_range: ширина не может быть отрицательной, получено {w_low!r}")

    variables: List[UniformFuzzyVariable] = []
    for _ in range(count):
        a = rng.uniform(a_low, a_high)
        width = rng.uniform(w_low, w_high)
        variables.append(UniformFuzzyVariable(a, a + width))
    return variables


def generate_sample(
    count: Optional[int] = None,
    *,
    seed: Optional[object] = None,
    a_range: NumberPair = DEFAULT_A_RANGE,
    width_range: NumberPair = DEFAULT_WIDTH_RANGE,
    count_range: Sequence[int] = DEFAULT_COUNT_RANGE,
) -> FuzzySet:
    """Сгенерировать случайную выборку нечетких величин.

    Параметры
    ---------
    count:
        Число величин. Если ``None``, выбирается случайно из ``count_range``.
        Явно заданное значение должно попадать в ``count_range``.
    seed:
        Зерно генератора для воспроизводимости. Одинаковый ``seed`` даёт
        одинаковую выборку; ``None`` — случайную.
    a_range:
        Диапазон левой границы ``a`` (по умолчанию ``(-10, 10)``).
    width_range:
        Диапазон ширины ``w = b - a`` (по умолчанию ``(0, 4)``).
    count_range:
        Допустимый объём выборки (по умолчанию 100…300 по заданию).

    Возвращает
    ----------
    FuzzySet
        Сгенерированное множество величин (условие ``a <= b`` гарантировано).
    """
    a_low, a_high = _validate_pair(a_range, "a_range")
    w_low, w_high = _validate_pair(width_range, "width_range")
    if w_low < 0.0:
        raise ValueError(f"width_range: ширина не может быть отрицательной, получено {w_low!r}")

    count_low_raw, count_high_raw = _validate_pair(count_range, "count_range")
    count_low, count_high = int(count_low_raw), int(count_high_raw)
    if count_low < 1:
        raise ValueError(f"count_range: минимальный объём должен быть >= 1, получено {count_low}")

    rng = random.Random(seed)

    if count is None:
        count = rng.randint(count_low, count_high)
    else:
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError(f"count должен быть целым числом, получено {type(count).__name__}")
        if not count_low <= count <= count_high:
            raise ValueError(
                f"count={count} вне допустимого диапазона {count_low}..{count_high}"
            )

    variables = generate_variables(rng, count, (a_low, a_high), (w_low, w_high))
    return FuzzySet(variables)
