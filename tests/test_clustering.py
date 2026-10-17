"""Тесты кластерного анализа (Шаг 5)."""

import json

import pytest

from fuzzy_core import FuzzySet, UniformFuzzyVariable as V, generate_sample
from fuzzy_core.clustering import (
    CLUSTERING_METHODS,
    NOISE_LABEL,
    cluster,
    density_clustering,
    kmeans,
    threshold_clustering,
)


def three_groups():
    """Три далеко разнесённые группы величин."""
    left = [V(-21 + 0.1 * i, -20 + 0.1 * i) for i in range(5)]
    middle = [V(-1 + 0.1 * i, 0 + 0.1 * i) for i in range(5)]
    right = [V(19 + 0.1 * i, 20 + 0.1 * i) for i in range(5)]
    return left, middle, right


def chain():
    """Цепочка точек с шагом 1: расстояния 1, 1 и 2 по краям."""
    return FuzzySet([V(0, 0), V(1, 1), V(2, 2)])


# ======================================================================
# K-Means
# ======================================================================
def test_kmeans_separates_three_obvious_groups():
    left, middle, right = three_groups()
    items = left + middle + right
    result = kmeans(items, 3, seed=42)

    assert len(result) == 3
    assert result.labels[:5] == [0] * 5
    assert result.labels[5:10] == [1] * 5
    assert result.labels[10:] == [2] * 5
    assert result.sizes == [5, 5, 5]


def test_kmeans_labels_cover_all_elements_and_clusters():
    items = list(generate_sample(120, seed=1, count_range=(120, 120)))
    result = kmeans(items, 5, seed=7)

    assert len(result.labels) == 120
    assert set(result.labels) == {0, 1, 2, 3, 4}   # нет пустых кластеров
    assert sum(result.sizes) == 120
    assert all(c.size > 0 for c in result.clusters)


def test_kmeans_with_one_cluster_returns_everything():
    items = list(generate_sample(50, seed=2, count_range=(50, 50)))
    result = kmeans(items, 1, seed=3)
    assert result.sizes == [50]
    assert result.labels == [0] * 50


def test_kmeans_with_k_equal_to_n_gives_singletons():
    items = [V(0, 1), V(5, 6), V(10, 11)]
    result = kmeans(items, 3, seed=1)
    assert result.sizes == [1, 1, 1]
    assert result.max_diameter == 0.0
    assert result.total_inertia == 0.0


@pytest.mark.parametrize("k", [0, -1, 4])
def test_kmeans_invalid_k_is_rejected(k):
    with pytest.raises(ValueError):
        kmeans([V(0, 1), V(5, 6), V(10, 11)], k)


def test_kmeans_non_integer_k_is_rejected():
    with pytest.raises(TypeError):
        kmeans([V(0, 1), V(5, 6)], 1.5)


def test_kmeans_of_empty_input():
    result = kmeans([], 1)
    assert len(result) == 0 and result.labels == []
    with pytest.raises(ValueError):
        kmeans([], 0)


def test_kmeans_is_reproducible_with_seed():
    items = list(generate_sample(80, seed=5, count_range=(80, 80)))
    assert kmeans(items, 4, seed=99).labels == kmeans(items, 4, seed=99).labels


def test_kmeans_centroid_is_mean_of_bounds():
    items = [V(0, 2), V(4, 6)]
    result = kmeans(items, 1, seed=1)
    centroid = result.centroids[0]
    assert centroid.a == pytest.approx(2.0)
    assert centroid.b == pytest.approx(4.0)


def test_kmeans_respects_metric_and_rejects_unknown():
    # Для точечных величин метрики пропорциональны, поэтому разбиение совпадает.
    items = [V(0, 0), V(10, 10), V(11, 11), V(21, 21)]
    haus = kmeans(items, 2, seed=1, metric="hausdorff")
    eucl = kmeans(items, 2, seed=1, metric="euclidean")
    assert haus.sizes == eucl.sizes
    assert sum(haus.sizes) == 4
    with pytest.raises(ValueError):
        kmeans(items, 2, seed=1, metric="манхэттен")


def test_kmeans_invalid_max_iter_and_tol():
    with pytest.raises(ValueError):
        kmeans([V(0, 1), V(5, 6)], 2, max_iter=0)
    with pytest.raises(ValueError):
        kmeans([V(0, 1), V(5, 6)], 2, tol=-1)


def test_kmeans_accepts_fuzzy_set_and_numbers():
    result = kmeans(FuzzySet([1, 2, 3, 50, 51]), 2, seed=1)
    assert sorted(result.sizes) == [2, 3]


# ======================================================================
# Кластеризация по порогу
# ======================================================================
def test_threshold_separates_groups_when_threshold_is_small():
    left, middle, right = three_groups()
    result = threshold_clustering(left + middle + right, threshold=5.0)
    assert result.sizes == [5, 5, 5]


def test_threshold_merges_everything_when_threshold_is_large():
    left, middle, right = three_groups()
    result = threshold_clustering(left + middle + right, threshold=100.0)
    assert result.sizes == [15]


def test_threshold_with_zero_merges_only_identical():
    items = [V(1, 2), V(1, 2), V(5, 6)]
    result = threshold_clustering(items, threshold=0.0)
    assert sorted(result.sizes) == [1, 2]


def test_threshold_uses_complete_linkage_and_avoids_chaining():
    # Одиночная связь слила бы все три точки в один кластер (1 + 1),
    # полная связь не может: расстояние между 0 и 2 равно 2 > 1.5.
    result = threshold_clustering(chain(), threshold=1.5)
    assert sorted(result.sizes) == [1, 2]


def test_threshold_exact_boundary_is_inclusive():
    # Порог ровно равен расстоянию между крайними точками -> всё в одном кластере.
    result = threshold_clustering(chain(), threshold=2.0)
    assert result.sizes == [3]


def test_threshold_respects_metric():
    items = [V(0, 2), V(1, 3)]
    assert threshold_clustering(items, threshold=1.5).sizes == [2]      # хаусдорф = 1
    assert threshold_clustering(items, threshold=1.5, metric="euclidean").sizes == [2]
    assert threshold_clustering(items, threshold=0.5, metric="euclidean").sizes == [1, 1]


def test_threshold_negative_is_rejected():
    with pytest.raises(ValueError):
        threshold_clustering([V(0, 1)], threshold=-0.5)


def test_threshold_of_empty_input():
    result = threshold_clustering([], threshold=1.0)
    assert len(result) == 0 and result.labels == []


def test_threshold_labels_match_clusters():
    result = threshold_clustering([V(0, 5), V(1, 6), V(50, 55)], threshold=1.0)
    assert result.labels == [0, 0, 1]
    assert len(result.labels) == len(result.items)


def _brute_force_complete_linkage(items, threshold, metric="hausdorff"):
    """Эталонная (медленная) реализация полной связи — проверка основного алгоритма."""
    from fuzzy_core import get_distance_function

    distance = get_distance_function(metric)
    clusters = [[i] for i in range(len(items))]

    def linkage(first, second):
        return max(distance(items[x], items[y]) for x in first for y in second)

    while True:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                value = linkage(clusters[i], clusters[j])
                if best is None or value < best[0]:
                    best = (value, i, j)
        if best is None or best[0] > threshold:
            break
        _, i, j = best
        clusters[i] = clusters[i] + clusters[j]
        del clusters[j]
    return sorted(sorted(cluster) for cluster in clusters)


def _groups_from_labels(result):
    groups = {}
    for index, label in enumerate(result.labels):
        groups.setdefault(label, []).append(index)
    return sorted(sorted(g) for g in groups.values())


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("threshold", [0.0, 0.25, 0.5, 1.0, 2.0, 5.0])
def test_threshold_matches_brute_force_complete_linkage(seed, threshold):
    items = list(generate_sample(40, seed=seed, count_range=(40, 40), width_range=(0.0, 1.0)))
    fast = threshold_clustering(items, threshold=threshold)
    assert _groups_from_labels(fast) == _brute_force_complete_linkage(items, threshold)


@pytest.mark.parametrize("threshold", [0.0, 0.5, 1.5])
def test_threshold_matches_brute_force_on_euclidean_metric(threshold):
    items = [V(0, 2), V(1, 3), V(5, 6), V(6, 7), V(-1, 1), V(20, 22)]
    fast = threshold_clustering(items, threshold=threshold, metric="euclidean")
    assert _groups_from_labels(fast) == _brute_force_complete_linkage(
        items, threshold, metric="euclidean"
    )


# ======================================================================
# Кластеризация по плотности
# ======================================================================
def test_density_finds_two_dense_clouds_and_one_noise_point():
    cloud_a = [V(float(i), float(i)) for i in range(5)]
    cloud_b = [V(100.0 + i, 100.0 + i) for i in range(5)]
    outlier = V(50.0, 50.0)
    items = cloud_a + cloud_b + [outlier]

    result = density_clustering(items, eps=1.5, min_points=3)
    assert len(result) == 2
    assert result.sizes == [5, 5]
    assert result.noise == [10]
    assert result.labels[10] == NOISE_LABEL
    assert result.labels[:5] == [0] * 5
    assert result.labels[5:10] == [1] * 5


def test_density_without_core_points_returns_only_noise():
    items = [V(0, 0), V(10, 10), V(20, 20)]
    result = density_clustering(items, eps=1.0, min_points=2)
    assert len(result) == 0
    assert result.noise == [0, 1, 2]
    assert result.labels == [NOISE_LABEL] * 3


def test_density_with_min_points_one_groups_neighbours():
    items = [V(0, 0), V(1, 1), V(2, 2), V(50, 50)]
    result = density_clustering(items, eps=1.1, min_points=1)
    # При min_points=1 ядровая любая точка, поэтому шума нет вообще:
    # кластеры упорядочены по центроиду — {0,1,2}, затем одиночный {50}.
    assert result.sizes == [3, 1]
    assert result.noise == []
    assert result.labels == [0, 0, 0, 1]


@pytest.mark.parametrize("eps", [0, -1.0])
def test_density_invalid_eps_is_rejected(eps):
    with pytest.raises(ValueError):
        density_clustering([V(0, 1)], eps=eps, min_points=1)


@pytest.mark.parametrize("min_points", [0, -2, 1.5])
def test_density_invalid_min_points_is_rejected(min_points):
    with pytest.raises(ValueError):
        density_clustering([V(0, 1)], eps=1.0, min_points=min_points)


def test_density_of_empty_input():
    result = density_clustering([], eps=1.0)
    assert len(result) == 0 and result.labels == [] and result.noise == []


# ======================================================================
# Статистики качества
# ======================================================================
def test_quality_statistics_for_known_cluster():
    result = kmeans([V(0, 1), V(3, 4)], 1, seed=1)
    one = result.clusters[0]
    assert one.size == 2
    assert one.centroid == V(1.5, 2.5)
    assert one.diameter == 3.0                          # max(|0-3|, |1-4|) = 3
    # расстояние Хаусдорфа от каждого элемента до центроида равно 1.5
    assert one.inertia == pytest.approx(2 * 1.5**2)
    # центры элементов 0.5 и 3.5 -> дисперсия ((0.5-2)^2 + (3.5-2)^2)/2
    assert one.center_variance == pytest.approx(2.25)


def test_singleton_cluster_statistics_are_zero():
    result = kmeans([V(0, 1), V(10, 11)], 2, seed=1)
    assert all(c.diameter == 0.0 for c in result.clusters)
    assert all(c.inertia == 0.0 for c in result.clusters)
    assert all(c.center_variance == 0.0 for c in result.clusters)


def test_total_inertia_and_average_variance_aggregate_clusters():
    left, middle, right = three_groups()
    result = kmeans(left + middle + right, 3, seed=1)
    assert result.total_inertia == pytest.approx(sum(c.inertia for c in result.clusters))
    assert result.average_center_variance == pytest.approx(
        sum(c.center_variance for c in result.clusters) / 3
    )
    assert result.max_diameter == pytest.approx(max(c.diameter for c in result.clusters))


def test_silhouette_is_high_for_separated_groups_and_none_for_single_cluster():
    left, middle, right = three_groups()
    separated = kmeans(left + middle + right, 3, seed=1)
    assert separated.silhouette() is not None
    assert separated.silhouette() > 0.9
    assert kmeans(left + middle + right, 1, seed=1).silhouette() is None


def test_silhouette_range_and_noise_exclusion():
    items = [V(0, 0), V(1, 1), V(2, 2), V(50, 50)]
    result = density_clustering(items, eps=1.1, min_points=1)
    score = result.silhouette()
    assert score is None or -1.0 <= score <= 1.0


def test_to_dict_is_json_serializable_and_complete():
    left, middle, right = three_groups()
    result = kmeans(left + middle + right, 3, seed=1)
    data = result.to_dict()
    json.dumps(data)  # не должно падать
    assert data["method"] == "kmeans" and data["metric"] == "hausdorff"
    assert data["elements"] == 15 and data["cluster_count"] == 3
    assert data["sizes"] == [5, 5, 5]
    assert len(data["centroids"]) == 3
    assert data["parameters"]["k"] == 3
    assert data["noise_count"] == 0
    assert set(data) >= {"diameters", "inertias", "total_inertia", "silhouette"}


# ======================================================================
# Единая точка входа
# ======================================================================
def test_cluster_dispatcher_calls_selected_method():
    items = list(generate_sample(60, seed=4, count_range=(60, 60)))
    assert cluster(items, "kmeans", k=3, seed=1).method == "kmeans"
    assert cluster(items, "threshold", threshold=1.0).method == "threshold"
    assert cluster(items, "density", eps=1.0, min_points=2).method == "density"
    assert cluster(items, "KMeans", k=2, seed=1).method == "kmeans"


def test_cluster_dispatcher_rejects_unknown_method():
    with pytest.raises(ValueError):
        cluster([V(0, 1)], "иерархический")


def test_methods_registry_keys():
    assert set(CLUSTERING_METHODS) == {"kmeans", "threshold", "density"}


# ======================================================================
# Работа на сгенерированной выборке
# ======================================================================
def test_on_generated_sample_all_methods_keep_all_elements():
    items = generate_sample(200, seed=2024)

    by_k = cluster(items, "kmeans", k=8, seed=1)
    assert len(by_k) == 8 and sum(by_k.sizes) == 200

    by_threshold = cluster(items, "threshold", threshold=0.5)
    assert sum(by_threshold.sizes) + len(by_threshold.noise) == 200
    assert len(by_threshold) > 1

    by_density = cluster(items, "density", eps=0.4, min_points=3)
    assert sum(by_density.sizes) + len(by_density.noise) == 200
    assert len(by_density) > 1
    assert all(by_density.labels[i] == NOISE_LABEL for i in by_density.noise)


def test_points_by_cluster_matches_sizes():
    left, middle, right = three_groups()
    result = kmeans(left + middle + right, 3, seed=1)
    groups = result.points_by_cluster()
    assert [len(g) for g in groups] == result.sizes
