"""Тесты арифметики, метрик и сравнения нечетких величин (Шаг 2)."""

import math

import pytest

from fuzzy_core import (
    DISTANCE_METRICS,
    FuzzyVariableError,
    UniformFuzzyVariable,
    euclidean_distance,
    get_distance_function,
    hausdorff_distance,
)
from fuzzy_core import UniformFuzzyVariable as V


# ----------------------------------------------------------------------
# Сложение
# ----------------------------------------------------------------------
def test_addition_of_two_variables():
    assert V(1, 2) + V(3, 5) == V(4, 7)


def test_addition_with_scalar_and_reflected():
    assert V(1, 2) + 1 == V(2, 3)
    assert 1 + V(1, 2) == V(2, 3)
    assert V(1, 2) + 0.5 == V(1.5, 2.5)


def test_addition_with_negative_operand():
    assert V(1, 2) + V(-5, -3) == V(-4, -1)


# ----------------------------------------------------------------------
# Вычитание
# ----------------------------------------------------------------------
def test_subtraction_of_two_variables():
    assert V(5, 10) - V(1, 2) == V(3, 9)


def test_subtraction_with_scalar_and_reflected():
    assert V(5, 10) - 1 == V(4, 9)
    assert 10 - V(1, 2) == V(8, 9)


def test_variable_minus_itself_contains_zero():
    diff = V(1, 2) - V(1, 2)
    assert diff == V(-1, 1)
    assert diff.mu(0.0) == 1.0


def test_negation():
    assert -V(1, 2) == V(-2, -1)
    assert -V(-3, 5) == V(-5, 3)


# ----------------------------------------------------------------------
# Умножение
# ----------------------------------------------------------------------
def test_multiplication_of_two_variables():
    assert V(1, 2) * V(3, 4) == V(3, 8)


def test_multiplication_with_negative_interval():
    assert V(-2, -1) * V(3, 4) == V(-8, -3)


def test_multiplication_spanning_zero():
    assert V(0, 2) * V(-1, 3) == V(-2, 6)


def test_multiplication_with_scalar_and_reflected():
    assert V(2, 3) * 2 == V(4, 6)
    assert 2 * V(2, 3) == V(4, 6)
    assert V(-2, 3) * -1 == V(-3, 2)


# ----------------------------------------------------------------------
# Деление
# ----------------------------------------------------------------------
def test_division_of_two_variables():
    assert V(10, 20) / V(2, 4) == V(2.5, 10)


def test_division_with_scalar_and_reflected():
    assert V(2, 4) / 2 == V(1, 2)
    assert 12 / V(2, 3) == V(4, 6)


def test_division_by_degenerate_interval():
    assert V(4, 8) / V(2, 2) == V(2, 4)


def test_division_by_negative_interval():
    assert V(2, 4) / V(-2, -1) == V(-4, -1)


@pytest.mark.parametrize("divisor", [V(-1, 1), V(0, 3), V(-3, 0), V(0, 0)])
def test_division_by_interval_containing_zero_is_rejected(divisor):
    with pytest.raises(FuzzyVariableError):
        V(1, 2) / divisor


def test_division_by_zero_scalar_is_rejected():
    with pytest.raises(FuzzyVariableError):
        V(1, 2) / 0


def test_reflected_division_by_zero_interval_is_rejected():
    with pytest.raises(FuzzyVariableError):
        1 / V(-1, 1)


# ----------------------------------------------------------------------
# Общие свойства операций
# ----------------------------------------------------------------------
def test_operations_return_new_objects_and_do_not_mutate():
    a, b = V(1, 2), V(3, 4)
    _ = a + b
    _ = a * b
    assert a == V(1, 2) and b == V(3, 4)


def test_unsupported_operand_raises_type_error():
    with pytest.raises(TypeError):
        V(1, 2) + "строка"
    with pytest.raises(TypeError):
        V(1, 2) * None


# ----------------------------------------------------------------------
# Метрики расстояния
# ----------------------------------------------------------------------
def test_hausdorff_distance_values():
    assert hausdorff_distance(V(0, 1), V(0, 1)) == 0.0
    assert hausdorff_distance(V(0, 1), V(3, 4)) == 3.0
    assert hausdorff_distance(V(0, 2), V(1, 3)) == 1.0


def test_hausdorff_distance_is_symmetric():
    a, b = V(-3, 7), V(2, 4)
    assert hausdorff_distance(a, b) == hausdorff_distance(b, a)


def test_euclidean_distance_values():
    assert euclidean_distance(V(0, 2), V(1, 3)) == pytest.approx(1.0)
    assert euclidean_distance(V(0, 1), V(3, 4)) == pytest.approx(3.0)
    assert euclidean_distance(V(0, 1), V(0, 1)) == 0.0


def test_euclidean_matches_formula():
    a, b = V(1, 5), V(-2, 6)
    expected = math.sqrt(((1 - (-2)) ** 2 + (5 - 6) ** 2) / 2)
    assert euclidean_distance(a, b) == pytest.approx(expected)


def test_distance_method_switches_metric():
    a, b = V(0, 1), V(3, 4)
    assert a.distance(b) == a.distance(b, "hausdorff") == 3.0
    assert a.distance(b, "EUCLIDEAN") == pytest.approx(3.0)


def test_distance_to_scalar():
    assert V(0, 1).distance(5, "hausdorff") == 5.0


def test_distance_metrics_registry_and_unknown_metric():
    assert set(DISTANCE_METRICS) == {"hausdorff", "euclidean"}
    assert get_distance_function("euclidean") is euclidean_distance
    with pytest.raises(ValueError):
        get_distance_function("манхэттен")
    with pytest.raises(ValueError):
        V(0, 1).distance(V(2, 3), "манхэттен")


# ----------------------------------------------------------------------
# Сравнение (ранжирование по центру, затем по ширине)
# ----------------------------------------------------------------------
def test_comparison_by_center():
    assert V(0, 2) < V(10, 12)
    assert V(10, 12) > V(0, 2)


def test_comparison_by_width_when_centers_equal():
    narrow, wide = V(1, 3), V(0, 4)
    assert narrow.center == wide.center == 2.0
    assert narrow < wide
    assert wide > narrow


def test_equal_variables_are_not_ordered():
    a, b = V(1, 3), V(1, 3)
    assert not (a < b) and not (a > b)
    assert a <= b and a >= b


def test_comparison_with_scalar():
    assert V(0, 2) > 0
    assert V(-2, 0) < 0


def test_compare_returns_minus_one_zero_one():
    assert V(0, 2).compare(V(10, 12)) == -1
    assert V(0, 2).compare(V(0, 2)) == 0
    assert V(10, 12).compare(V(0, 2)) == 1


def test_ordering_with_foreign_type_raises():
    with pytest.raises(TypeError):
        V(0, 1) < "строка"


# ----------------------------------------------------------------------
# Индексы возможности/необходимости и степень доминирования
# ----------------------------------------------------------------------
def test_possibility_and_necessity_for_separated_intervals():
    a, b = V(0, 2), V(3, 4)
    assert b.possibility_greater_or_equal(a) == 1.0
    assert b.necessity_greater_or_equal(a) == 1.0
    assert a.possibility_greater_or_equal(b) == 0.0
    assert a.necessity_greater_or_equal(b) == 0.0


def test_possibility_and_necessity_for_overlapping_intervals():
    a, b = V(0, 2), V(1, 3)
    assert a.possibility_greater_or_equal(b) == 1.0
    assert a.necessity_greater_or_equal(b) == 0.0


def test_dominance_is_one_for_clearly_greater_interval():
    assert V(2, 3).dominance(V(0, 1)) == 1.0


def test_dominance_is_zero_for_clearly_smaller_interval():
    assert V(0, 1).dominance(V(2, 3)) == 0.0


def test_dominance_for_overlapping_intervals():
    assert V(0, 2).dominance(V(1, 3)) == pytest.approx(0.125)
    assert V(1, 3).dominance(V(0, 2)) == pytest.approx(0.875)


def test_dominance_is_complementary_for_continuous_intervals():
    a, b = V(-1, 4), V(2, 6)
    assert a.dominance(b) + b.dominance(a) == pytest.approx(1.0)


def test_dominance_of_identical_intervals_is_half():
    assert V(0, 1).dominance(V(0, 1)) == 0.5


def test_dominance_with_crisp_variables():
    assert V(5, 5).dominance(V(5, 5)) == 0.5
    assert V(5, 5).dominance(V(7, 7)) == 0.0
    assert V(5, 5).dominance(V(1, 5)) == 1.0
    assert V(1, 5).dominance(V(5, 5)) == 0.0


def test_dominance_is_consistent_with_clear_separation():
    pairs = [
        (V(0, 1), V(5, 6)),
        (V(-10, -5), V(0, 1)),
        (V(2, 4), V(8, 9)),
    ]
    for smaller, bigger in pairs:
        assert bigger.dominance(smaller) == 1.0
        assert smaller.dominance(bigger) == 0.0
