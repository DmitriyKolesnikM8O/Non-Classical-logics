"""Тесты множества нечетких величин FuzzySet (Шаг 3)."""

import pytest

from fuzzy_core import FuzzySet, FuzzySetError, UniformFuzzyVariable as V


def sample() -> FuzzySet:
    """Фиксированный набор из четырёх величин для тестов."""
    return FuzzySet([V(0, 2), V(4, 6), V(8, 10), V(1, 3)])


# ----------------------------------------------------------------------
# Создание и доступ
# ----------------------------------------------------------------------
def test_empty_set_has_zero_length():
    items = FuzzySet()
    assert len(items) == 0
    assert list(items) == []


def test_construction_from_list_and_generator():
    assert len(FuzzySet([V(1, 2), V(3, 4)])) == 2
    assert len(FuzzySet(V(i, i + 1) for i in range(5))) == 5


def test_numbers_become_crisp_variables():
    items = FuzzySet([1, 2.5])
    assert items[0] == V(1, 1)
    assert items[1] == V(2.5, 2.5)
    assert items[0].is_crisp


def test_invalid_element_is_rejected():
    with pytest.raises(TypeError):
        FuzzySet([V(1, 2), "строка"])


def test_indexing_and_iteration():
    items = sample()
    assert items[0] == V(0, 2)
    assert items[-1] == V(1, 3)
    assert [v.a for v in items] == [0.0, 4.0, 8.0, 1.0]


def test_slice_returns_fuzzy_set():
    part = sample()[1:3]
    assert isinstance(part, FuzzySet)
    assert part == FuzzySet([V(4, 6), V(8, 10)])


def test_index_out_of_range_raises():
    with pytest.raises(IndexError):
        sample()[99]


def test_contains_variable_and_number():
    items = sample()
    assert V(0, 2) in items
    assert V(5, 5) not in items
    # число трактуется как вырожденная величина [x, x]
    assert 4 not in items
    assert 8 not in items
    assert 1 in FuzzySet([1, 2])


def test_contains_foreign_type_is_false():
    assert "строка" not in sample()


# ----------------------------------------------------------------------
# Изменение состава
# ----------------------------------------------------------------------
def test_append_insert_extend():
    items = FuzzySet()
    items.append(V(1, 2))
    items.append(3)
    items.insert(1, V(5, 6))
    items.extend([V(7, 8), V(9, 10)])
    assert len(items) == 5
    assert items[1] == V(5, 6)
    assert items[2] == V(3, 3)


def test_remove_pop_clear():
    items = sample()
    items.remove(V(4, 6))
    assert len(items) == 3
    assert items.pop() == V(1, 3)
    items.clear()
    assert len(items) == 0


def test_setitem_validates_value():
    items = sample()
    items[0] = V(100, 200)
    assert items[0] == V(100, 200)
    with pytest.raises(TypeError):
        items[0] = object()


def test_delitem():
    items = sample()
    del items[0]
    assert items[0] == V(4, 6)


def test_unique_removes_duplicates_keeping_order():
    items = FuzzySet([V(1, 2), V(3, 4), V(1, 2)])
    assert items.unique() == FuzzySet([V(1, 2), V(3, 4)])
    assert len(items) == 3  # исходное множество не меняется


def test_union_operator():
    a, b = FuzzySet([V(1, 2)]), FuzzySet([V(3, 4)])
    assert a + b == FuzzySet([V(1, 2), V(3, 4)])
    assert a + V(5, 6) == FuzzySet([V(1, 2), V(5, 6)])
    assert a + [V(7, 8)] == FuzzySet([V(1, 2), V(7, 8)])
    assert len(a) == 1  # исходное множество не изменилось


def test_inplace_union_operator():
    a = FuzzySet([V(1, 2)])
    a += [V(3, 4)]
    assert a == FuzzySet([V(1, 2), V(3, 4)])


def test_union_with_unsupported_type_raises():
    with pytest.raises(TypeError):
        FuzzySet([V(1, 2)]) + object()


def test_equality_is_order_sensitive_and_foreign_returns_false():
    assert FuzzySet([V(1, 2), V(3, 4)]) == FuzzySet([V(1, 2), V(3, 4)])
    assert FuzzySet([V(1, 2), V(3, 4)]) != FuzzySet([V(3, 4), V(1, 2)])
    assert FuzzySet([V(1, 2)]) != [V(1, 2)]


# ----------------------------------------------------------------------
# Поиск и фильтрация
# ----------------------------------------------------------------------
def test_find_returns_first_match_or_none():
    items = sample()
    assert items.find(lambda v: v.width == 2.0) == V(0, 2)
    assert items.find(lambda v: v.width > 100) is None


def test_filter_returns_new_set():
    wide = sample().filter(lambda v: v.width >= 2.0)
    assert wide == sample()
    assert len(sample().filter(lambda v: v.center > 100)) == 0


def test_filter_by_center_includes_boundaries():
    # центры величин: 1, 5, 9
    items = FuzzySet([V(0, 2), V(4, 6), V(8, 10)])
    assert items.filter_by_center(low=5, high=9) == FuzzySet([V(4, 6), V(8, 10)])
    assert items.filter_by_center(low=5) == FuzzySet([V(4, 6), V(8, 10)])
    assert items.filter_by_center(high=1) == FuzzySet([V(0, 2)])
    assert items.filter_by_center(high=0) == FuzzySet()
    assert items.filter_by_center() == items  # без ограничений — всё множество


def test_filter_by_width():
    items = FuzzySet([V(0, 1), V(0, 5), V(0, 10)])
    assert items.filter_by_width(high=5) == FuzzySet([V(0, 1), V(0, 5)])
    assert items.filter_by_width(low=5) == FuzzySet([V(0, 5), V(0, 10)])


def test_sorted_by_rank():
    items = FuzzySet([V(10, 12), V(0, 4), V(1, 3), V(0, 2)])
    # центры: 11, 2, 2, 1 -> при равных центрах первым идёт меньшая ширина
    assert items.sorted_by_rank() == FuzzySet([V(0, 2), V(1, 3), V(0, 4), V(10, 12)])
    assert items.sorted_by_rank(reverse=True)[0] == V(10, 12)
    assert items[0] == V(10, 12)  # исходный порядок не изменился


# ----------------------------------------------------------------------
# Агрегаты
# ----------------------------------------------------------------------
def test_mean_center_and_mean_width():
    items = FuzzySet([V(0, 2), V(0, 4)])
    # центры: 1 и 2 -> средний 1.5; ширины: 2 и 4 -> средняя 3
    assert items.mean_center() == pytest.approx(1.5)
    assert items.mean_width() == pytest.approx(3.0)


def test_envelope():
    assert FuzzySet([V(-3, 1), V(5, 12)]).envelope() == (-3.0, 12.0)


def test_min_and_max_by_rank():
    items = sample()
    assert items.min_by_rank() == V(0, 2)
    assert items.max_by_rank() == V(8, 10)


def test_aggregates_on_empty_set():
    empty = FuzzySet()
    with pytest.raises(FuzzySetError):
        empty.mean_center()
    with pytest.raises(FuzzySetError):
        empty.mean_width()
    with pytest.raises(FuzzySetError):
        empty.envelope()
    assert empty.min_by_rank() is None
    assert empty.max_by_rank() is None


# ----------------------------------------------------------------------
# Расстояния
# ----------------------------------------------------------------------
def test_distances_to():
    items = FuzzySet([V(0, 1), V(3, 4), V(0, 1)])
    assert items.distances_to(V(0, 1)) == [0.0, 3.0, 0.0]


def test_nearest():
    items = FuzzySet([V(0, 1), V(3, 4), V(5, 6)])
    assert items.nearest(V(3.4, 4.4)) == V(3, 4)
    assert FuzzySet().nearest(V(0, 1)) is None


def test_distance_matrix_is_symmetric_with_zero_diagonal():
    items = FuzzySet([V(0, 1), V(3, 4), V(10, 20)])
    matrix = items.distance_matrix()
    assert len(matrix) == 3 and len(matrix[0]) == 3
    assert all(matrix[i][i] == 0.0 for i in range(3))
    for i in range(3):
        for j in range(3):
            assert matrix[i][j] == matrix[j][i]
    assert matrix[0][1] == 3.0
    assert matrix[0][2] == 19.0


def test_distance_matrix_respects_metric():
    items = FuzzySet([V(0, 2), V(1, 3)])
    assert items.distance_matrix("hausdorff")[0][1] == 1.0
    assert items.distance_matrix("euclidean")[0][1] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        items.distance_matrix("манхэттен")


def test_distance_matrix_of_empty_and_single_sets():
    assert FuzzySet().distance_matrix() == []
    assert FuzzySet([V(1, 2)]).distance_matrix() == [[0.0]]


# ----------------------------------------------------------------------
# Служебное
# ----------------------------------------------------------------------
def test_repr_contains_elements():
    text = repr(FuzzySet([V(1, 2)]))
    assert text.startswith("FuzzySet(")
    assert "UniformFuzzyVariable" in text
