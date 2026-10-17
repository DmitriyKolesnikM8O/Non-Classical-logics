"""Кластерный анализ множества нечетких величин.

Реализованы три метода:

* ``kmeans`` — кластер-анализ на заданное число кластеров K (K-Means,
  адаптированный под интервальные величины: центроид — среднее границ);
* ``threshold`` — кластеризация по порогу внутрикластерного расстояния
  (агломеративная, критерий полной связи / complete-linkage);
* ``density`` — кластеризация по плотности (DBSCAN-подобная: ``eps`` и ``min_points``).

Расстояние между величинами задаётся метрикой из :mod:`fuzzy_core.fuzzy_variable`
(``hausdorff`` по умолчанию, есть ``euclidean``).

Модуль входит в независимую библиотеку ``fuzzy_core`` и не зависит от GUI.
"""

from __future__ import annotations

import heapq
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .fuzzy_variable import UniformFuzzyVariable, get_distance_function

__all__ = [
    "Cluster",
    "ClusterResult",
    "kmeans",
    "threshold_clustering",
    "density_clustering",
    "cluster",
    "CLUSTERING_METHODS",
]

NOISE_LABEL = -1


# ----------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------
def _as_items(variables: Iterable[object]) -> List[UniformFuzzyVariable]:
    """Привести вход к списку величин (числа -> вырожденные величины)."""
    return [UniformFuzzyVariable._coerce(v) for v in variables]


def _mean_variable(members: Sequence[UniformFuzzyVariable]) -> UniformFuzzyVariable:
    """Центроид кластера — среднее границ его элементов."""
    if not members:
        raise ValueError("Нельзя вычислить центроид пустого кластера")
    return UniformFuzzyVariable(
        sum(v.a for v in members) / len(members),
        sum(v.b for v in members) / len(members),
    )


def _distance_matrix(
    items: Sequence[UniformFuzzyVariable], distance: Callable[[Any, Any], float]
) -> List[List[float]]:
    size = len(items)
    matrix = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            value = distance(items[i], items[j])
            matrix[i][j] = value
            matrix[j][i] = value
    return matrix


# ----------------------------------------------------------------------
# Описание кластера и результата
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Cluster:
    """Кластер: набор величин, центроид и статистики качества."""

    members: Tuple[UniformFuzzyVariable, ...]
    centroid: UniformFuzzyVariable
    metric: str = "hausdorff"

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def diameter(self) -> float:
        """Диаметр — максимальное расстояние между элементами кластера."""
        distance = get_distance_function(self.metric)
        members = self.members
        best = 0.0
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                value = distance(members[i], members[j])
                if value > best:
                    best = value
        return best

    @property
    def inertia(self) -> float:
        """Сумма квадратов расстояний элементов до центроида кластера."""
        distance = get_distance_function(self.metric)
        return sum(distance(v, self.centroid) ** 2 for v in self.members)

    @property
    def center_variance(self) -> float:
        """Внутрикластерная дисперсия модальных центров элементов."""
        centers = [v.center for v in self.members]
        return statistics.pvariance(centers) if centers else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "centroid": [self.centroid.a, self.centroid.b],
            "center": self.centroid.center,
            "diameter": self.diameter,
            "inertia": self.inertia,
            "center_variance": self.center_variance,
            "members": [[v.a, v.b] for v in self.members],
        }


@dataclass
class ClusterResult:
    """Результат кластерного анализа."""

    items: List[UniformFuzzyVariable]
    clusters: List[Cluster]
    labels: List[int]
    method: str
    metric: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    noise: List[int] = field(default_factory=list)

    # --- краткие характеристики ---
    def __len__(self) -> int:
        return len(self.clusters)

    def __iter__(self):
        return iter(self.clusters)

    @property
    def sizes(self) -> List[int]:
        return [c.size for c in self.clusters]

    @property
    def centroids(self) -> List[UniformFuzzyVariable]:
        return [c.centroid for c in self.clusters]

    @property
    def total_inertia(self) -> float:
        return sum(c.inertia for c in self.clusters)

    @property
    def average_center_variance(self) -> float:
        """Средняя внутрикластерная дисперсия центров."""
        if not self.clusters:
            return 0.0
        return sum(c.center_variance for c in self.clusters) / len(self.clusters)

    @property
    def max_diameter(self) -> float:
        """Наибольший диаметр среди кластеров."""
        return max((c.diameter for c in self.clusters), default=0.0)

    def silhouette(self) -> Optional[float]:
        """Средний коэффициент силуэта (``None``, если кластеров меньше двух).

        Точки-шум не учитываются.
        """
        return _silhouette(self.labels, self.items, self.metric)

    def points_by_cluster(self) -> List[List[UniformFuzzyVariable]]:
        """Списки величин по кластерам — удобно для визуализации."""
        return [list(c.members) for c in self.clusters]

    def to_dict(self) -> Dict[str, Any]:
        """Представление результата для журнала (только простые типы)."""
        return {
            "method": self.method,
            "metric": self.metric,
            "parameters": dict(self.parameters),
            "elements": len(self.items),
            "cluster_count": len(self.clusters),
            "noise_count": len(self.noise),
            "sizes": self.sizes,
            "centroids": [[c.centroid.a, c.centroid.b] for c in self.clusters],
            "diameters": [c.diameter for c in self.clusters],
            "inertias": [c.inertia for c in self.clusters],
            "center_variances": [c.center_variance for c in self.clusters],
            "total_inertia": self.total_inertia,
            "average_center_variance": self.average_center_variance,
            "max_diameter": self.max_diameter,
            "silhouette": self.silhouette(),
        }


def _silhouette(
    labels: Sequence[int], items: Sequence[UniformFuzzyVariable], metric: str
) -> Optional[float]:
    """Средний силуэт по точкам (точки-шум с меткой -1 игнорируются)."""
    distance = get_distance_function(metric)
    indices = [i for i, label in enumerate(labels) if label != NOISE_LABEL]
    if not indices:
        return None
    groups: Dict[int, List[int]] = {}
    for i in indices:
        groups.setdefault(labels[i], []).append(i)
    if len(groups) < 2:
        return None

    scores: List[float] = []
    for i in indices:
        own = groups[labels[i]]
        if len(own) < 2:
            scores.append(0.0)  # одиночная точка: силуэт не определён, берём 0
            continue
        a = sum(distance(items[i], items[j]) for j in own if j != i) / (len(own) - 1)
        b = min(
            sum(distance(items[i], items[j]) for j in members) / len(members)
            for label, members in groups.items()
            if label != labels[i]
        )
        denom = max(a, b)
        scores.append(0.0 if denom == 0.0 else (b - a) / denom)
    return sum(scores) / len(scores)


def _build_result(
    items: List[UniformFuzzyVariable],
    groups: List[List[int]],
    method: str,
    metric: str,
    parameters: Dict[str, Any],
    noise: Optional[List[int]] = None,
) -> ClusterResult:
    """Собрать результат: упорядочить кластеры по центроиду и построить метки."""
    noise = list(noise or [])
    prepared: List[Tuple[UniformFuzzyVariable, List[int]]] = []
    for members in groups:
        if not members:
            continue
        centroid = _mean_variable([items[i] for i in members])
        prepared.append((centroid, sorted(members)))
    # Детерминированный порядок кластеров: по центру, затем по ширине центроида.
    prepared.sort(key=lambda pair: pair[0].rank_key())

    labels = [NOISE_LABEL] * len(items)
    clusters: List[Cluster] = []
    for new_label, (centroid, members) in enumerate(prepared):
        for index in members:
            labels[index] = new_label
        clusters.append(
            Cluster(
                members=tuple(items[i] for i in members),
                centroid=centroid,
                metric=metric,
            )
        )
    return ClusterResult(
        items=list(items),
        clusters=clusters,
        labels=labels,
        method=method,
        metric=metric,
        parameters=dict(parameters),
        noise=noise,
    )


# ----------------------------------------------------------------------
# K-Means на заданное число кластеров
# ----------------------------------------------------------------------
def _kmeans_plus_plus(
    items: Sequence[UniformFuzzyVariable],
    k: int,
    distance: Callable[[Any, Any], float],
    rng: random.Random,
) -> List[UniformFuzzyVariable]:
    """Инициализация центроидов по схеме k-means++."""
    size = len(items)
    centroids = [items[rng.randrange(size)]]
    closest = [distance(items[i], centroids[0]) for i in range(size)]

    for _ in range(k - 1):
        weights = [d * d for d in closest]
        total = sum(weights)
        if total > 0.0:
            target = rng.random() * total
            accumulated = 0.0
            index = size - 1
            for i, weight in enumerate(weights):
                accumulated += weight
                if accumulated >= target:
                    index = i
                    break
        else:
            # Все точки совпали с уже выбранными центрами — берём произвольную.
            index = rng.randrange(size)
        centroids.append(items[index])
        closest = [
            min(old, distance(items[i], centroids[-1])) for i, old in enumerate(closest)
        ]
    return centroids


def kmeans(
    variables: Iterable[object],
    k: int,
    *,
    metric: str = "hausdorff",
    seed: Optional[object] = None,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> ClusterResult:
    """Кластеризация на заданное число кластеров K.

    Центроид кластера — величина со средними границами его элементов.
    Пустой кластер заполняется точкой, наиболее удалённой от своего центроида.

    Параметры
    ---------
    variables:
        Множество величин (``FuzzySet``, список, любой итерируемый объект).
    k:
        Число кластеров, ``1 <= k <= n``.
    metric:
        Имя метрики расстояния (``hausdorff`` / ``euclidean``).
    seed:
        Зерно для воспроизводимости (влияет на инициализацию k-means++).
    max_iter, tol:
        Максимум итераций и порог стабилизации центроидов.
    """
    items = _as_items(variables)
    size = len(items)

    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k должно быть целым числом, получено {type(k).__name__}")
    if k < 1:
        raise ValueError(f"k должно быть >= 1, получено {k}")
    if size == 0:
        return _build_result(items, [], "kmeans", metric, {"k": k})
    if k > size:
        raise ValueError(f"k должно удовлетворять 1 <= k <= {size}, получено {k}")
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter < 1:
        raise ValueError(f"max_iter должен быть целым числом >= 1, получено {max_iter!r}")
    if tol < 0:
        raise ValueError(f"tol не может быть отрицательным, получено {tol!r}")

    distance = get_distance_function(metric)
    parameters = {"k": k, "max_iter": max_iter, "tol": tol, "seed": seed}

    if size == 0:
        return _build_result(items, [], "kmeans", metric, parameters)

    rng = random.Random(seed)
    centroids = _kmeans_plus_plus(items, k, distance, rng)
    labels = [0] * size

    for _ in range(max_iter):
        labels = [
            min(range(k), key=lambda c: (distance(v, centroids[c]), c)) for v in items
        ]

        # Заполнение пустых кластеров: переносим самую удалённую точку
        # из кластера, где элементов больше одного.
        counts = [labels.count(c) for c in range(k)]
        for cluster_index in range(k):
            if counts[cluster_index] > 0:
                continue
            candidates = [
                (distance(items[i], centroids[labels[i]]), i)
                for i in range(size)
                if counts[labels[i]] > 1
            ]
            if not candidates:
                break
            _, victim = max(candidates)
            counts[labels[victim]] -= 1
            labels[victim] = cluster_index
            counts[cluster_index] = 1

        new_centroids: List[UniformFuzzyVariable] = []
        for cluster_index in range(k):
            members = [items[i] for i in range(size) if labels[i] == cluster_index]
            new_centroids.append(
                _mean_variable(members) if members else centroids[cluster_index]
            )

        shift = max(
            max(abs(new.a - old.a), abs(new.b - old.b))
            for new, old in zip(new_centroids, centroids)
        )
        centroids = new_centroids
        if shift <= tol:
            break

    groups = [
        [i for i in range(size) if labels[i] == cluster_index] for cluster_index in range(k)
    ]
    return _build_result(items, groups, "kmeans", metric, parameters)


# ----------------------------------------------------------------------
# Кластеризация по порогу (полная связь)
# ----------------------------------------------------------------------
def threshold_clustering(
    variables: Iterable[object],
    *,
    threshold: float,
    metric: str = "hausdorff",
) -> ClusterResult:
    """Кластеризация по порогу внутрикластерного расстояния.

    Агломеративный алгоритм с критерием **полной связи**: два кластера
    объединяются, только если *максимальное* расстояние между их элементами
    не превышает ``threshold``. Такой критерий (в отличие от одиночной связи)
    не даёт «цепного эффекта», при котором цепочка близких элементов стягивает
    весь набор в один кластер.
    """
    items = _as_items(variables)
    size = len(items)
    if threshold < 0:
        raise ValueError(f"threshold не может быть отрицательным, получено {threshold!r}")

    distance = get_distance_function(metric)
    parameters = {"threshold": threshold}

    if size == 0:
        return _build_result(items, [], "threshold", metric, parameters)

    matrix = _distance_matrix(items, distance)
    clusters: Dict[int, List[int]] = {i: [i] for i in range(size)}
    pair_distance: Dict[Tuple[int, int], float] = {}
    heap: List[Tuple[float, int, int]] = []

    for i in range(size):
        for j in range(i + 1, size):
            pair_distance[(i, j)] = matrix[i][j]
            heap.append((matrix[i][j], i, j))
    heapq.heapify(heap)

    while heap:
        value, first, second = heapq.heappop(heap)
        if first not in clusters or second not in clusters:
            continue
        if pair_distance.get((first, second)) != value:
            continue  # устаревшая запись
        if value > threshold:
            break  # минимальное расстояние по полной связи превысило порог

        merged = clusters[first] + clusters[second]
        del clusters[second]
        clusters[first] = merged

        for other in list(clusters):
            if other == first:
                continue
            new_value = max(matrix[x][y] for x in clusters[first] for y in clusters[other])
            key = (first, other) if first < other else (other, first)
            pair_distance[key] = new_value
            heapq.heappush(heap, (new_value, key[0], key[1]))

    return _build_result(
        items, list(clusters.values()), "threshold", metric, parameters
    )


# ----------------------------------------------------------------------
# Кластеризация по плотности (DBSCAN-подобная)
# ----------------------------------------------------------------------
def density_clustering(
    variables: Iterable[object],
    *,
    eps: float,
    min_points: int = 2,
    metric: str = "hausdorff",
) -> ClusterResult:
    """Кластеризация по плотности.

    Точка считается ядровой, если в радиусе ``eps`` находится не менее
    ``min_points`` точек (включая саму точку). Кластеры строятся из ядровых
    точек; граничные точки присоединяются к достижимым кластерам, остальные
    помечаются как шум (метка ``-1``).
    """
    items = _as_items(variables)
    size = len(items)
    if eps <= 0:
        raise ValueError(f"eps должен быть больше нуля, получено {eps!r}")
    if isinstance(min_points, bool) or not isinstance(min_points, int) or min_points < 1:
        raise ValueError(f"min_points должен быть целым числом >= 1, получено {min_points!r}")

    distance = get_distance_function(metric)
    parameters = {"eps": eps, "min_points": min_points}

    if size == 0:
        return _build_result(items, [], "density", metric, parameters)

    neighbors: List[List[int]] = [
        [j for j in range(size) if distance(items[i], items[j]) <= eps] for i in range(size)
    ]
    core = [i for i in range(size) if len(neighbors[i]) >= min_points]

    labels = [NOISE_LABEL] * size
    groups: List[List[int]] = []
    for start in core:
        if labels[start] != NOISE_LABEL:
            continue
        cluster_index = len(groups)
        members: List[int] = []
        queue = [start]
        labels[start] = cluster_index
        while queue:
            current = queue.pop()
            members.append(current)
            if current not in core:
                continue  # граничная точка: расширение не продолжается
            for neighbor in neighbors[current]:
                if labels[neighbor] == NOISE_LABEL:
                    labels[neighbor] = cluster_index
                    queue.append(neighbor)
        groups.append(members)

    noise = [i for i in range(size) if labels[i] == NOISE_LABEL]
    return _build_result(items, groups, "density", metric, parameters, noise=noise)


# ----------------------------------------------------------------------
# Единая точка входа
# ----------------------------------------------------------------------
CLUSTERING_METHODS: Dict[str, Callable[..., ClusterResult]] = {
    "kmeans": kmeans,
    "threshold": threshold_clustering,
    "density": density_clustering,
}


def cluster(
    variables: Iterable[object],
    method: str = "kmeans",
    *,
    metric: str = "hausdorff",
    **parameters: Any,
) -> ClusterResult:
    """Выполнить кластеризацию выбранным методом.

    ``method`` — одно из ``kmeans``, ``threshold``, ``density``; остальные
    именованные аргументы передаются выбранному методу (например ``k=5``
    или ``threshold=0.5``).
    """
    key = str(method).strip().lower()
    if key not in CLUSTERING_METHODS:
        available = ", ".join(sorted(CLUSTERING_METHODS))
        raise ValueError(f"Неизвестный метод кластеризации {method!r}. Доступны: {available}")
    return CLUSTERING_METHODS[key](variables, metric=metric, **parameters)
