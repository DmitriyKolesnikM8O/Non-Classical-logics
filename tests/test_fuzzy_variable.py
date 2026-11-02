"""Тесты базового класса UniformFuzzyVariable (Шаг 1)."""

import math

import pytest

from fuzzy_core import (
    FuzzyVariableError,
    UniformFuzzyVariable,
    alpha_cut_trapezoid,
    alpha_cut_triangular,
)


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


# ----------------------------------------------------------------------
# α-уровни (α-срезы)
# ----------------------------------------------------------------------
@pytest.mark.parametrize("alpha", [0.1, 0.5, 0.999, 1.0])
def test_alpha_cut_of_uniform_variable_is_its_support(alpha):
    variable = UniformFuzzyVariable(1.0, 3.0)
    assert variable.alpha_cut(alpha) == (1.0, 3.0)


def test_alpha_cut_is_empty_above_one():
    assert UniformFuzzyVariable(1, 3).alpha_cut(1.5) == ()


@pytest.mark.parametrize("alpha", [0.0, -0.5, math.inf, math.nan])
def test_alpha_cut_rejects_invalid_level(alpha):
    with pytest.raises(FuzzyVariableError):
        UniformFuzzyVariable(1, 3).alpha_cut(alpha)


def test_alpha_cut_matches_membership_test():
    variable = UniformFuzzyVariable(-2, 4)
    cut = variable.alpha_cut(0.7)
    assert cut == variable.core
    assert variable.membership(cut[0]) == 1.0
    assert variable.membership(cut[1]) == 1.0


# ----------------------------------------------------------------------
# α-срезы треугольной и трапециевидной функций принадлежности
# ----------------------------------------------------------------------
def triangular_membership(a, m, b, x):
    """Функция принадлежности треугольного числа T(a, m, b)."""
    if x < a or x > b:
        return 0.0
    if x <= m:
        return (x - a) / (m - a) if m > a else 1.0
    return (b - x) / (b - m) if b > m else 1.0


def trapezoid_membership(a, c, d, b, x):
    """Функция принадлежности трапеции T(a, c, d, b)."""
    if x < a or x > b:
        return 0.0
    if x < c:
        return (x - a) / (c - a)
    if x <= d:
        return 1.0
    return (b - x) / (b - d)


def test_alpha_cut_triangular_known_values():
    assert alpha_cut_triangular(0, 5, 10, 0.5) == (2.5, 7.5)
    assert alpha_cut_triangular(0, 5, 10, 1.0) == (5.0, 5.0)
    assert alpha_cut_triangular(0, 5, 10, 0.1) == (0.5, 9.5)


def test_alpha_cut_trapezoid_known_values():
    assert alpha_cut_trapezoid(0, 2, 8, 10, 0.5) == (1.0, 9.0)
    assert alpha_cut_trapezoid(0, 2, 8, 10, 1.0) == (2.0, 8.0)
    assert alpha_cut_trapezoid(0, 2, 8, 10, 0.25) == (0.5, 9.5)


@pytest.mark.parametrize(
    "params, membership",
    [
        ((0.0, 5.0, 10.0), triangular_membership),
        ((0.0, 2.0, 8.0, 10.0), trapezoid_membership),
    ],
)
@pytest.mark.parametrize("alpha", [0.05, 0.25, 0.5, 0.75, 0.95])
def test_alpha_cut_borders_have_membership_equal_to_level(params, membership, alpha):
    cut = (
        alpha_cut_triangular(*params, alpha)
        if len(params) == 3
        else alpha_cut_trapezoid(*params, alpha)
    )
    assert membership(*params, cut[0]) == pytest.approx(alpha)
    assert membership(*params, cut[1]) == pytest.approx(alpha)


@pytest.mark.parametrize("alpha", [0.1, 0.3, 0.6, 0.9, 1.0])
def test_alpha_cut_borders_are_monotone(alpha):
    lower = alpha_cut_triangular(0, 5, 10, alpha)
    higher = alpha_cut_triangular(0, 5, 10, min(1.0, alpha + 0.05))
    assert higher[0] >= lower[0] - 1e-12
    assert higher[1] <= lower[1] + 1e-12
    assert higher[0] <= higher[1]


def test_alpha_cut_trapezoid_at_zero_level_is_support():
    cut = alpha_cut_trapezoid(0, 2, 8, 10, 1e-9)
    assert abs(cut[0] - 0.0) < 1e-6
    assert abs(cut[1] - 10.0) < 1e-6


@pytest.mark.parametrize("alpha", [0.1, 0.5, 0.9, 1.0])
def test_degenerate_trapezoid_matches_uniform_alpha_cut(alpha):
    # Равномерная μ — это трапеция с c = a и d = b.
    variable = UniformFuzzyVariable(1.0, 3.0)
    assert alpha_cut_trapezoid(1.0, 1.0, 3.0, 3.0, alpha) == variable.alpha_cut(alpha)


def test_alpha_cut_of_triangle_and_trapezoid_is_empty_above_one():
    assert alpha_cut_triangular(0, 5, 10, 1.5) == ()
    assert alpha_cut_trapezoid(0, 2, 8, 10, 1.5) == ()


@pytest.mark.parametrize("alpha", [0.0, -0.5, math.inf, math.nan])
def test_alpha_cut_of_triangle_and_trapezoid_rejects_invalid_level(alpha):
    with pytest.raises(FuzzyVariableError):
        alpha_cut_triangular(0, 5, 10, alpha)
    with pytest.raises(FuzzyVariableError):
        alpha_cut_trapezoid(0, 2, 8, 10, alpha)


@pytest.mark.parametrize(
    "args",
    [
        (5.0, 2.0, 8.0, 10.0),  # a > c
        (0.0, 2.0, 9.0, 8.0),  # d > b
        (0.0, 5.0, 4.0, 10.0),  # c > d
    ],
)
def test_alpha_cut_trapezoid_rejects_bad_ordering(args):
    with pytest.raises(FuzzyVariableError):
        alpha_cut_trapezoid(*args, 0.5)


@pytest.mark.parametrize("args", [(5.0, 3.0, 10.0), (0.0, 11.0, 10.0)])
def test_alpha_cut_triangular_rejects_bad_ordering(args):
    with pytest.raises(FuzzyVariableError):
        alpha_cut_triangular(*args, 0.5)


@pytest.mark.parametrize("bad", [math.inf, math.nan])
def test_alpha_cut_rejects_non_finite_parameters(bad):
    with pytest.raises(FuzzyVariableError):
        alpha_cut_trapezoid(0, 2, 8, bad, 0.5)
    with pytest.raises(FuzzyVariableError):
        alpha_cut_triangular(0, bad, 10, 0.5)


def test_crisp_triangle_and_degenerate_trapezoid():
    """Вырожденные случаи: треугольник в точку и «прямоугольник»."""
    assert alpha_cut_triangular(5, 5, 5, 0.5) == (5.0, 5.0)
    assert alpha_cut_trapezoid(1, 2, 2, 3, 0.5) == (1.5, 2.5)
