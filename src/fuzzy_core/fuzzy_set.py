"""Множество нечетких величин: коллекция с операциями доступа, поиска и фильтрации.

Модуль входит в независимую библиотеку ``fuzzy_core`` и не зависит от GUI
и подсистемы журналирования.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Callable, List, Optional, Union

from .fuzzy_variable import UniformFuzzyVariable, get_distance_function

__all__ = ["FuzzySet", "FuzzySetError"]

Number = Union[int, float]
Predicate = Callable[[UniformFuzzyVariable], bool]


class FuzzySetError(ValueError):
    """Ошибка при работе с множеством нечетких величин."""


class FuzzySet:
    """Упорядоченная коллекция нечетких величин равномерного типа.

    Элементы хранятся в порядке добавления. Числа, переданные вместо величин,
    автоматически превращаются в вырожденные величины ``[x, x]``.
    """

    __slots__ = ("_items",)

    def __init__(self, variables: Iterable[object] = ()) -> None:
        self._items: List[UniformFuzzyVariable] = []
        self.extend(variables)

    # ------------------------------------------------------------------
    # Доступ к элементам
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[UniformFuzzyVariable]:
        return iter(self._items)

    def __getitem__(self, index):
        """``items[i]`` — величина; ``items[i:j]`` — новое множество."""
        if isinstance(index, slice):
            return FuzzySet(self._items[index])
        return self._items[index]

    def __setitem__(self, index: int, value: object) -> None:
        self._items[index] = UniformFuzzyVariable._coerce(value)

    def __delitem__(self, index) -> None:
        del self._items[index]

    def __contains__(self, value: object) -> bool:
        if isinstance(value, UniformFuzzyVariable):
            return value in self._items
        try:
            return UniformFuzzyVariable._coerce(value) in self._items
        except TypeError:
            return False

    # ------------------------------------------------------------------
    # Изменение состава
    # ------------------------------------------------------------------
    def append(self, variable: object) -> None:
        """Добавить величину в конец множества."""
        self._items.append(UniformFuzzyVariable._coerce(variable))

    def insert(self, index: int, variable: object) -> None:
        """Вставить величину в заданную позицию."""
        self._items.insert(index, UniformFuzzyVariable._coerce(variable))

    def extend(self, variables: Iterable[object]) -> None:
        """Добавить все величины из итерируемого объекта."""
        for variable in variables:
            self.append(variable)

    def remove(self, variable: object) -> None:
        """Удалить первое вхождение величины."""
        self._items.remove(UniformFuzzyVariable._coerce(variable))

    def pop(self, index: int = -1) -> UniformFuzzyVariable:
        """Удалить и вернуть величину по индексу (по умолчанию последнюю)."""
        return self._items.pop(index)

    def clear(self) -> None:
        """Удалить все величины."""
        self._items.clear()

    def unique(self) -> "FuzzySet":
        """Новое множество без дубликатов (порядок сохраняется)."""
        seen = set()
        result = FuzzySet()
        for variable in self._items:
            if variable not in seen:
                seen.add(variable)
                result.append(variable)
        return result

    # ------------------------------------------------------------------
    # Объединение
    # ------------------------------------------------------------------
    def __add__(self, other: object) -> "FuzzySet":
        """Объединение: ``set + set``, ``set + [величины]`` или ``set + величина``."""
        result = FuzzySet(self._items)
        if isinstance(other, (UniformFuzzyVariable, int, float)):
            result.append(other)
        else:
            try:
                result.extend(other)  # type: ignore[arg-type]
            except TypeError as exc:
                raise TypeError(
                    f"Ожидалось множество, список величин или одна величина, "
                    f"получено {type(other).__name__}"
                ) from exc
        return result

    def __iadd__(self, other: object) -> "FuzzySet":
        self.extend([other] if isinstance(other, (UniformFuzzyVariable, int, float)) else other)  # type: ignore[arg-type]
        return self

    # ------------------------------------------------------------------
    # Поиск
    # ------------------------------------------------------------------
    def find(self, predicate: Predicate) -> Optional[UniformFuzzyVariable]:
        """Первая величина, удовлетворяющая условию, или ``None``."""
        for variable in self._items:
            if predicate(variable):
                return variable
        return None

    def filter(self, predicate: Predicate) -> "FuzzySet":
        """Новое множество из величин, удовлетворяющих условию."""
        return FuzzySet(v for v in self._items if predicate(v))

    def filter_by_center(self, low: Optional[float] = None, high: Optional[float] = None) -> "FuzzySet":
        """Отбор по модальному центру ``c`` (границы включаются, ``None`` — без ограничения)."""
        return self.filter(
            lambda v: (low is None or v.center >= low) and (high is None or v.center <= high)
        )

    def filter_by_width(self, low: Optional[float] = None, high: Optional[float] = None) -> "FuzzySet":
        """Отбор по ширине ``w`` (границы включаются, ``None`` — без ограничения)."""
        return self.filter(
            lambda v: (low is None or v.width >= low) and (high is None or v.width <= high)
        )

    def sorted_by_rank(self, reverse: bool = False) -> "FuzzySet":
        """Новое множество, упорядоченное по центру, затем по ширине."""
        return FuzzySet(sorted(self._items, key=UniformFuzzyVariable.rank_key, reverse=reverse))

    # ------------------------------------------------------------------
    # Агрегаты и характеристики
    # ------------------------------------------------------------------
    def _require_not_empty(self, what: str) -> None:
        if not self._items:
            raise FuzzySetError(f"Нельзя вычислить {what}: множество пусто")

    def mean_center(self) -> float:
        """Средний модальный центр."""
        self._require_not_empty("средний центр")
        return sum(v.center for v in self._items) / len(self._items)

    def mean_width(self) -> float:
        """Средняя ширина носителя."""
        self._require_not_empty("среднюю ширину")
        return sum(v.width for v in self._items) / len(self._items)

    def envelope(self) -> tuple:
        """Охватывающий интервал ``(min a, max b)`` — полезен для графиков."""
        self._require_not_empty("охватывающий интервал")
        return (
            min(v.a for v in self._items),
            max(v.b for v in self._items),
        )

    def min_by_rank(self) -> Optional[UniformFuzzyVariable]:
        """Величина с минимальным ключом ранжирования (``None`` для пустого множества)."""
        if not self._items:
            return None
        return min(self._items, key=UniformFuzzyVariable.rank_key)

    def max_by_rank(self) -> Optional[UniformFuzzyVariable]:
        """Величина с максимальным ключом ранжирования (``None`` для пустого множества)."""
        if not self._items:
            return None
        return max(self._items, key=UniformFuzzyVariable.rank_key)

    # ------------------------------------------------------------------
    # Расстояния (используются кластерным анализом)
    # ------------------------------------------------------------------
    def distances_to(self, variable: object, metric: str = "hausdorff") -> List[float]:
        """Расстояния от заданной величины до всех элементов множества."""
        distance = get_distance_function(metric)
        target = UniformFuzzyVariable._coerce(variable)
        return [distance(target, v) for v in self._items]

    def nearest(self, variable: object, metric: str = "hausdorff") -> Optional[UniformFuzzyVariable]:
        """Ближайшая к заданной величине (``None`` для пустого множества)."""
        if not self._items:
            return None
        target = UniformFuzzyVariable._coerce(variable)
        distance = get_distance_function(metric)
        return min(self._items, key=lambda v: distance(target, v))

    def distance_matrix(self, metric: str = "hausdorff") -> List[List[float]]:
        """Матрица попарных расстояний (симметричная, с нулевой диагональю)."""
        distance = get_distance_function(metric)
        items = self._items
        size = len(items)
        matrix = [[0.0] * size for _ in range(size)]
        for i in range(size):
            for j in range(i + 1, size):
                value = distance(items[i], items[j])
                matrix[i][j] = value
                matrix[j][i] = value
        return matrix

    # ------------------------------------------------------------------
    # Служебные методы
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FuzzySet):
            return NotImplemented
        return self._items == other._items

    def __repr__(self) -> str:
        return f"FuzzySet({self._items!r})"
