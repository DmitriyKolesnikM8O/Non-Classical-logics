"""Тесты базового класса UniformFuzzyVariable (Шаг 1)."""

import math

import pytest

from fuzzy_core import FuzzyVariableError, UniformFuzzyVariable


# ----------------------------------------------------------------------
# Создание и валидация
# ----------------------------------------------------------------------
def test_bounds_are_stored_as_floats():
    v = UniformFuzzyVariable(1, 5)
    assert v.a == 1.0
    assert v.b == 5.0
    assert isinstance(v.a, float)


def test_a_equal_b_is_allowed_and_crisp():
    v = UniformFuzzyVariable(3, 3)
    assert v.is_crisp
    assert v.width == 0.0
    assert v.center == 3.0


def test_a_greater_than_b_is_rejected():
    with pytest.raises(FuzzyVariableError):
        UniformFuzzyVariable(7, 2)


@pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan])
def test_non_finite_bounds_are_rejected(bad):
    with pytest.raises(FuzzyVariableError):
        UniformFuzzyVariable(bad, 1)
    with pytest.raises(FuzzyVariableError):
        UniformFuzzyVariable(0, bad)


# ----------------------------------------------------------------------
# Числовые характеристики
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "a, b, center, width",
    [
        (2, 6, 4.0, 4.0),
        (-5, -1, -3.0, 4.0),
        (-2, 2, 0.0, 4.0),
        (0, 0, 0.0, 0.0),
        (1.5, 2.5, 2.0, 1.0),
    ],
)
def test_center_and_width(a, b, center, width):
    v = UniformFuzzyVariable(a, b)
    assert v.center == pytest.approx(center)
    assert v.width == pytest.approx(width)
    # псевдонимы c/w дают то же самое
    assert v.c == v.center
    assert v.w == v.width


def test_support_and_core_coincide_for_uniform_type():
    v = UniformFuzzyVariable(-4, 10)
    assert v.support == (-4.0, 10.0)
    assert v.core == v.support


def test_from_center_width_roundtrip():
    v = UniformFuzzyVariable.from_center_width(10, 4)
    assert v.a == pytest.approx(8.0)
    assert v.b == pytest.approx(12.0)
    assert v.center == pytest.approx(10.0)
    assert v.width == pytest.approx(4.0)


def test_from_center_width_rejects_negative_width():
    with pytest.raises(FuzzyVariableError):
        UniformFuzzyVariable.from_center_width(0, -1)


# ----------------------------------------------------------------------
# Функция принадлежности
# ----------------------------------------------------------------------
def test_membership_inside_bounds_is_one():
    v = UniformFuzzyVariable(1, 5)
    for x in (1, 2.5, 4.999, 5):
        assert v.mu(x) == 1.0


def test_membership_outside_bounds_is_zero():
    v = UniformFuzzyVariable(1, 5)
    for x in (-10, 0.999, 5.001, 100):
        assert v.mu(x) == 0.0


def test_membership_boundaries_are_inclusive():
    v = UniformFuzzyVariable(0, 2)
    assert v.mu(0) == 1.0
    assert v.mu(2) == 1.0


def test_membership_of_crisp_variable():
    v = UniformFuzzyVariable(4, 4)
    assert v.mu(4) == 1.0
    assert v.mu(3.999) == 0.0
    assert v.mu(4.001) == 0.0


def test_call_alias_and_membership_are_equal():
    v = UniformFuzzyVariable(-1, 1)
    assert v(0) == v.membership(0) == 1.0


def test_membership_of_negative_interval():
    v = UniformFuzzyVariable(-6, -2)
    assert v.mu(-4) == 1.0
    assert v.mu(0) == 0.0


# ----------------------------------------------------------------------
# Служебное
# ----------------------------------------------------------------------
def test_equality_and_hash():
    assert UniformFuzzyVariable(1, 2) == UniformFuzzyVariable(1, 2)
    assert UniformFuzzyVariable(1, 2) != UniformFuzzyVariable(1, 3)
    assert len({UniformFuzzyVariable(1, 2), UniformFuzzyVariable(1, 2)}) == 1


def test_equality_with_foreign_type_returns_not_implemented():
    assert UniformFuzzyVariable(1, 2) != (1, 2)


def test_unpacking_and_repr():
    a, b = UniformFuzzyVariable(1.5, 2.5)
    assert (a, b) == (1.5, 2.5)
    assert "UniformFuzzyVariable" in repr(UniformFuzzyVariable(1, 2))
