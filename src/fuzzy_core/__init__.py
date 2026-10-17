"""Независимая библиотека для работы с нечеткими величинами равномерного типа.

Пакет не зависит от GUI и подсистемы журналирования, поэтому может
использоваться сторонними программами как обычная библиотека.
"""

from .fuzzy_set import FuzzySet, FuzzySetError
from .fuzzy_variable import (
    DISTANCE_METRICS,
    FuzzyVariableError,
    UniformFuzzyVariable,
    euclidean_distance,
    get_distance_function,
    hausdorff_distance,
)

__all__ = [
    "UniformFuzzyVariable",
    "FuzzyVariableError",
    "FuzzySet",
    "FuzzySetError",
    "euclidean_distance",
    "hausdorff_distance",
    "DISTANCE_METRICS",
    "get_distance_function",
]
__version__ = "0.1.0"
