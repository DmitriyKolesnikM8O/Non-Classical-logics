"""Тесты генератора выборки (Шаг 4)."""

import random
import statistics

import pytest

from fuzzy_core import FuzzySet, UniformFuzzyVariable as V
from fuzzy_core.generator import (
    DEFAULT_A_RANGE,
    DEFAULT_COUNT_RANGE,
    DEFAULT_WIDTH_RANGE,
    MAX_COUNT,
    MIN_COUNT,
    generate_sample,
    generate_variables,
)

SMALL_RANGE = (5, 10)  # для быстрых тестов вместо 100…300


# ----------------------------------------------------------------------
# Объём выборки
# ----------------------------------------------------------------------
def test_default_count_is_within_required_range():
    for seed in range(5):
        items = generate_sample(seed=seed)
        assert MIN_COUNT <= len(items) <= MAX_COUNT


def test_default_count_range_is_100_300():
    assert DEFAULT_COUNT_RANGE == (100, 300)
    assert (MIN_COUNT, MAX_COUNT) == (100, 300)


def test_explicit_count_is_respected():
    assert len(generate_sample(150, seed=1)) == 150
    assert len(generate_sample(100, seed=1, count_range=(100, 300))) == 100
    assert len(generate_sample(300, seed=1)) == 300


@pytest.mark.parametrize("count", [99, 301, 0, -5, 1000])
def test_explicit_count_outside_range_is_rejected(count):
    with pytest.raises(ValueError):
        generate_sample(count, seed=1)


def test_non_integer_count_is_rejected():
    with pytest.raises(TypeError):
        generate_sample(150.0, seed=1)
    with pytest.raises(TypeError):
        generate_sample(True, seed=1)


def test_custom_count_range_allows_small_samples():
    items = generate_sample(seed=1, count_range=SMALL_RANGE)
    assert SMALL_RANGE[0] <= len(items) <= SMALL_RANGE[1]


def test_count_outside_custom_range_is_rejected():
    with pytest.raises(ValueError):
        generate_sample(12, seed=1, count_range=SMALL_RANGE)


# ----------------------------------------------------------------------
# Корректность величин
# ----------------------------------------------------------------------
def test_every_variable_satisfies_a_le_b():
    for variable in generate_sample(200, seed=42):
        assert variable.a <= variable.b
        assert variable.width >= 0.0


def test_values_respect_default_ranges():
    a_low, a_high = DEFAULT_A_RANGE
    w_low, w_high = DEFAULT_WIDTH_RANGE
    for variable in generate_sample(300, seed=7):
        assert a_low <= variable.a <= a_high
        assert w_low <= variable.width <= w_high


def test_custom_ranges_are_respected():
    items = generate_sample(
        120, seed=3, a_range=(100.0, 110.0), width_range=(0.0, 0.5)
    )
    for variable in items:
        assert 100.0 <= variable.a <= 110.0
        assert 0.0 <= variable.width <= 0.5


def test_degenerate_variables_are_possible_with_zero_width():
    items = generate_sample(200, seed=11, width_range=(0.0, 0.0))
    assert all(v.is_crisp for v in items)


def test_result_is_fuzzy_set():
    items = generate_sample(100, seed=1)
    assert isinstance(items, FuzzySet)
    assert len(items) == 100


# ----------------------------------------------------------------------
# Воспроизводимость
# ----------------------------------------------------------------------
def test_same_seed_gives_identical_sample():
    first = generate_sample(150, seed=12345)
    second = generate_sample(150, seed=12345)
    assert first == second


def test_different_seeds_give_different_samples():
    assert generate_sample(150, seed=1) != generate_sample(150, seed=2)


def test_seed_is_respected_with_random_count():
    assert generate_sample(seed=99) == generate_sample(seed=99)


def test_without_seed_samples_usually_differ():
    samples = {repr(generate_sample(100)) for _ in range(5)}
    assert len(samples) > 1


def test_generate_variables_with_explicit_rng_is_reproducible():
    first = generate_variables(random.Random(0), 10)
    second = generate_variables(random.Random(0), 10)
    assert first == second
    assert all(isinstance(v, V) for v in first)


def test_generate_variables_returns_requested_count():
    assert len(generate_variables(random.Random(1), 7)) == 7
    assert generate_variables(random.Random(1), 0) == []


# ----------------------------------------------------------------------
# Статистическая проверка на большой выборке
# ----------------------------------------------------------------------
def test_uniform_statistics_on_large_sample():
    """На 200 000 величин: a ~ U(-10, 10), w ~ U(0, 4), центр ~ U(-10, 14).

    Проверяет не только попадание в границы, но и то, что распределение
    действительно равномерное (средние близки к серединам диапазонов).
    Ограничение задания 100…300 здесь сознательно переопределено.
    """
    size = 200_000
    items = generate_sample(seed=1, count_range=(size, size))
    assert len(items) == size

    a_values = [v.a for v in items]
    widths = [v.width for v in items]

    assert min(a_values) >= -10.0
    assert max(a_values) <= 10.0
    assert min(widths) >= 0.0
    assert max(widths) <= 4.0

    # Равномерность: средние сходятся к серединам диапазонов.
    assert statistics.mean(a_values) == pytest.approx(0.0, abs=0.15)
    assert statistics.mean(widths) == pytest.approx(2.0, abs=0.05)

    # Хвосты почти упираются в границы — признак того, что диапазон покрыт целиком.
    assert min(a_values) < -9.9
    assert max(a_values) > 9.9
    assert min(widths) < 0.01
    assert max(widths) > 3.99

    # Величины лежат в диапазоне центров [-10, 14] и всегда a <= b.
    assert all(-10.0 <= v.center <= 14.0 for v in items)
    assert all(v.a <= v.b for v in items)
    assert len(set(items)) > size // 2  # величины практически не повторяются


# ----------------------------------------------------------------------
# Валидация параметров
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs",
    [
        {"a_range": (5, 1)},
        {"a_range": (0, float("inf"))},
        {"a_range": (0, float("nan"))},
        {"a_range": (1,)},
        {"width_range": (-1, 2)},
        {"width_range": (3, 1)},
        {"count_range": (0, 5)},
        {"count_range": (10, 5)},
    ],
)
def test_invalid_ranges_are_rejected(kwargs):
    with pytest.raises(ValueError):
        generate_sample(seed=1, **kwargs)


@pytest.mark.parametrize("bad_range", [None, 5, "abc", {"low": 0}])
def test_non_pair_range_is_rejected(bad_range):
    with pytest.raises(ValueError):
        generate_sample(seed=1, a_range=bad_range)
