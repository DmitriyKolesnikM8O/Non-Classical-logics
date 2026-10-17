"""Независимая библиотека для работы с нечеткими величинами равномерного типа.

Пакет не зависит от GUI и подсистемы журналирования, поэтому может
использоваться сторонними программами как обычная библиотека.
"""

from .fuzzy_variable import FuzzyVariableError, UniformFuzzyVariable

__all__ = ["UniformFuzzyVariable", "FuzzyVariableError"]
__version__ = "0.1.0"
