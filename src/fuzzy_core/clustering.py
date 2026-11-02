"""Кластерный анализ множества нечетких величин.

Реализованы четыре метода:

* ``kmeans`` — кластер-анализ на заданное число кластеров K (K-Means,
  адаптированный под интервальные величины: центроид — среднее границ);
* ``threshold`` — кластеризация по порогу внутрикластерного расстояния
  (агломеративная, критерий полной связи / complete-linkage);
* ``alpha`` — кластеризация по α-уровню: α-срез отношения сходства между
  величинами (уровень — безразмерная величина из ``(0, 1]``, она же
  «уровень отбора», от которого зависит число кластеров);
* ``density`` — кластеризация по плотности (DBSCAN-подобная: ``eps`` и ``min_points``).

Расстояние между величинами задаётся метрикой из :mod:`fuzzy_core.fuzzy_variable`
(``hausdorff`` по умолчанию, есть ``euclidean``).

Модуль входит в независимую библиотеку ``fuzzy_core`` и не зависит от GUI.
"""

from __future__ import annotations

import bisect
import heapq
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .fuzzy_variable import UniformFuzzyVariable, get_distance_function

try:  # numpy ускоряет транзитивное замыкание; без него работает чистый Python
    import numpy as _np
except ImportError:  # pragma: no cover - окружение без numpy
    _np = None

__all__ = [
    "Cluster",
    "ClusterResult",
    "Agglomeration",
    "AlphaClusterer",
    "kmeans",
    "threshold_clustering",
    "alpha_cut_clustering",
    "alpha_cut_profile",
    "similarity_matrix",
    "max_min_closure",
    "density_clustering",
    "cluster",
    "CLUSTERING_METHODS",
]

NOISE_LABEL = -1

#: Допуск при сравнении высот слияний с порогом (защита от ошибок округления).
_HEIGHT_EPS = 1e-12


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
@dataclass(frozen=True)
class Agglomeration:
    """Трасса агломеративной кластеризации (критерий полной связи).

    Хранит полную последовательность слияний: пары узлов и высоту (расстояние)
    каждого слияния. Листья — исходные величины с индексами ``0 ... size-1``.
    По трассе можно быстро получить разбиение при любом пороге (см.
    :meth:`labels`), не пересчитывая матрицу расстояний заново — это и нужно
    интерфейсу для интерактивного перебора уровня.
    """

    size: int
    merges: Tuple[Tuple[int, int, float], ...] = ()

    @property
    def heights(self) -> Tuple[float, ...]:
        """Высоты слияний по порядку их выполнения."""
        return tuple(height for _, _, height in self.merges)

    def labels(self, threshold: float) -> List[int]:
        """Метки кластеров при разрезе дендрограммы на высоте ``threshold``.

        Слияния выше порога не выполняются. Метки неотрицательны и нумеруются
        в порядке появления; у элементов одного кластера метка совпадает.
        """
        parent = list(range(self.size))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        for first, second, height in self.merges:
            if height > threshold + _HEIGHT_EPS:
                continue
            root_first, root_second = find(first), find(second)
            if root_first != root_second:
                parent[root_second] = root_first

        mapping: Dict[int, int] = {}
        result: List[int] = []
        for index in range(self.size):
            root = find(index)
            if root not in mapping:
                mapping[root] = len(mapping)
            result.append(mapping[root])
        return result

    def cluster_count(self, threshold: float) -> int:
        """Число кластеров при разрезе дендрограммы на высоте ``threshold``."""
        return len(set(self.labels(threshold)))


def _group_by_labels(labels: Sequence[int]) -> List[List[int]]:
    """Индексы элементов, сгруппированные по меткам кластеров."""
    groups: Dict[int, List[int]] = {}
    for index, label in enumerate(labels):
        groups.setdefault(int(label), []).append(index)
    return list(groups.values())


def _agglomerate(
    items: Sequence[UniformFuzzyVariable],
    distance: Callable[[Any, Any], float],
    threshold: Optional[float] = None,
) -> Tuple[List[List[int]], List[float], List[Tuple[int, int, float]]]:
    """Агломеративная кластеризация с критерием полной связи.

    Возвращает ``(группы индексов, высоты слияний, слияния)``. Если
    ``threshold`` задан, слияния выше порога не выполняются; если ``None`` —
    выполняется весь процесс, а высоты и пары собираются целиком (нужны для
    профиля α-уровней и для интерактивного разреза дендрограммы).
    """
    size = len(items)
    matrix = _distance_matrix(items, distance)
    clusters: Dict[int, List[int]] = {i: [i] for i in range(size)}
    pair_distance: Dict[Tuple[int, int], float] = {}
    heap: List[Tuple[float, int, int]] = []
    heights: List[float] = []
    merges: List[Tuple[int, int, float]] = []

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
        if threshold is not None and value > threshold:
            break  # минимальное расстояние по полной связи превысило порог

        heights.append(value)
        merges.append((first, second, value))
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

    return list(clusters.values()), heights, merges


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
    if threshold < 0:
        raise ValueError(f"threshold не может быть отрицательным, получено {threshold!r}")

    parameters = {"threshold": threshold}
    if not items:
        return _build_result(items, [], "threshold", metric, parameters)

    groups, _, _ = _agglomerate(items, get_distance_function(metric), threshold)
    return _build_result(items, groups, "threshold", metric, parameters)


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
# Кластеризация по α-уровню (α-срезы отношения сходства)
# ----------------------------------------------------------------------
def _validate_alpha(alpha: float) -> float:
    """Проверить α-уровень: конечное число из интервала ``(0, 1]``."""
    value = float(alpha)
    if not math.isfinite(value):
        raise ValueError(f"α-уровень должен быть конечным числом, получено {alpha!r}")
    if not 0.0 < value <= 1.0:
        raise ValueError(f"α-уровень должен лежать в (0, 1], получено {alpha!r}")
    return value


def _validate_scale(scale: Optional[float]) -> Optional[float]:
    """Проверить масштаб расстояний ``d0`` (положительное конечное число)."""
    if scale is None:
        return None
    value = float(scale)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(
            "масштаб расстояний должен быть положительным числом, "
            f"получено {scale!r}"
        )
    return value


def _similarity_data(
    items: Sequence[UniformFuzzyVariable],
    distance: Callable[[Any, Any], float],
    scale: Optional[float],
) -> Tuple[List[List[float]], float]:
    """Матрица сходства ``r_ij = 1 - d_ij / d0`` и использованный масштаб ``d0``."""
    size = len(items)
    if size == 0:
        return [], 0.0
    distances = _distance_matrix(items, distance)
    if scale is None:
        d0 = max((max(row) for row in distances), default=0.0)
    else:
        d0 = _validate_scale(scale) or 0.0
    if d0 <= 0.0:
        # Все величины совпадают: сходство максимально на всех парах.
        return [[1.0] * size for _ in range(size)], 0.0
    matrix = [
        [1.0 - distances[i][j] / d0 for j in range(size)] for i in range(size)
    ]
    for i in range(size):
        matrix[i][i] = 1.0
    return matrix, d0


def similarity_matrix(
    variables: Iterable[object],
    *,
    metric: str = "hausdorff",
    scale: Optional[float] = None,
) -> List[List[float]]:
    """Матрица сходства величин со значениями из ``[0, 1]``.

    ``r_ij = 1 - d_ij / d0``, где ``d0`` — аргумент ``scale`` либо (по
    умолчанию) максимальное расстояние в выборке. ``r_ii = 1``, матрица
    симметрична.
    """
    items = _as_items(variables)
    matrix, _ = _similarity_data(items, get_distance_function(metric), scale)
    return matrix


def max_min_closure(similarity: Sequence[Sequence[float]]) -> List[List[float]]:
    """Max-min транзитивное замыкание отношения сходства.

    Результат — нечеткое отношение эквивалентности (рефлексивное,
    симметричное, транзитивное, ``R* >= R``). Его α-срезы задают вложенную
    иерархию разбиений (декомпозиция Заде).
    """
    size = len(similarity)
    if size == 0:
        return []
    if _np is not None:
        matrix = _np.array(similarity, dtype=float)
        for k in range(size):
            column = matrix[:, [k]]
            row = matrix[[k], :]
            matrix = _np.maximum(matrix, _np.minimum(column, row))
        return matrix.tolist()
    result = [list(map(float, row)) for row in similarity]
    for k in range(size):
        row_k = result[k]
        for i in range(size):
            row_i = result[i]
            value = row_i[k]
            if value <= 0.0:
                continue
            for j in range(size):
                candidate = value if value < row_k[j] else row_k[j]
                if candidate > row_i[j]:
                    row_i[j] = candidate
    return result


def _alpha_components(
    matrix: Sequence[Sequence[float]], alpha: float
) -> List[List[int]]:
    """Компоненты связности графа ``r_ij >= alpha`` — кластеры α-среза."""
    size = len(matrix)
    parent = list(range(size))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i in range(size):
        row = matrix[i]
        for j in range(i + 1, size):
            if row[j] >= alpha:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_j] = root_i

    groups: Dict[int, List[int]] = {}
    for index in range(size):
        groups.setdefault(find(index), []).append(index)
    return list(groups.values())


def alpha_cut_clustering(
    variables: Iterable[object],
    *,
    alpha: float = 0.5,
    metric: str = "hausdorff",
    linkage: str = "single",
    closure: bool = True,
    scale: Optional[float] = None,
) -> ClusterResult:
    """Кластеризация по α-уровню отношения сходства.

    ``alpha`` — уровень отбора из ``(0, 1]`` по шкале сходства
    ``r_ij = 1 - d_ij / d0``. Чем уровень выше, тем строже критерий и тем
    больше кластеров; при ``alpha = 1`` в кластер попадают только полностью
    совпадающие величины, при малом ``alpha`` всё сливается в один кластер.

    ``linkage`` задаёт, как читать уровень:

    * ``"single"`` (по умолчанию) — канонический α-срез отношения сходства:
      кластеры — компоненты связности графа ``r_ij >= alpha``. При
      ``closure=True`` сходство предварительно замыкается до нечеткого
      отношения эквивалентности (декомпозиция Заде);
    * ``"complete"`` — разрез дендрограммы полной связи по уровню ``alpha``:
      в один кластер попадают величины, у которых *все* пары имеют сходство
      не ниже уровня. Уровень строже, поэтому число кластеров убывает
      плавнее и результат нагляднее на плотных выборках.
    """
    level = _validate_alpha(alpha)
    key = str(linkage).strip().lower()
    if key not in {"single", "complete"}:
        raise ValueError(
            f"Неизвестный тип связи {linkage!r}. Доступны: single, complete"
        )
    items = _as_items(variables)
    if not items:
        parameters = {
            "alpha": level,
            "linkage": key,
            "closure": bool(closure) and key == "single",
        }
        return _build_result(items, [], "alpha", metric, parameters)

    engine = AlphaClusterer(
        items, metric=metric, linkage=key, closure=closure, scale=scale
    )
    return engine.clustering(level)


DEFAULT_ALPHA_GRID: Tuple[float, ...] = (
    1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1,
)


def alpha_cut_profile(
    variables: Iterable[object],
    alphas: Optional[Iterable[float]] = None,
    *,
    metric: str = "hausdorff",
    linkage: str = "single",
    closure: bool = True,
    scale: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Зависимость числа кластеров от α-уровня.

    Возвращает список словарей ``{"alpha": уровень, "cluster_count": k}``.
    По умолчанию перебираются уровни :data:`DEFAULT_ALPHA_GRID`; ``linkage``
    понимается так же, как в :func:`alpha_cut_clustering`.
    """
    key = str(linkage).strip().lower()
    if key not in {"single", "complete"}:
        raise ValueError(
            f"Неизвестный тип связи {linkage!r}. Доступны: single, complete"
        )
    items = _as_items(variables)
    levels = [
        _validate_alpha(level)
        for level in (alphas if alphas is not None else DEFAULT_ALPHA_GRID)
    ]
    if not items:
        return [{"alpha": level, "cluster_count": 0} for level in levels]

    engine = AlphaClusterer(
        items, metric=metric, linkage=key, closure=closure, scale=scale
    )
    return engine.profile(levels)


class AlphaClusterer:
    """Движок α-кластеризации: тяжёлые матрицы считаются один раз.

    Нужен там, где уровень α перебирается многократно (ползунок, анимация в
    интерфейсе): матрица сходства считается при создании объекта, max-min
    замыкание и трасса агломерации — лениво и однократно, а каждый следующий
    вызов :meth:`clustering` при новом уровне стоит доли миллисекунды.

    Параметры — те же, что у :func:`alpha_cut_clustering`.

    Пример
    ------
    ::

        engine = AlphaClusterer(sample, linkage="complete")
        [len(engine.clustering(alpha).clusters) for alpha in (1.0, 0.8, 0.5)]
        # [300, 9, 3]
    """

    def __init__(
        self,
        variables: Iterable[object],
        *,
        metric: str = "hausdorff",
        linkage: str = "single",
        closure: bool = True,
        scale: Optional[float] = None,
    ) -> None:
        key = str(linkage).strip().lower()
        if key not in {"single", "complete"}:
            raise ValueError(
                f"Неизвестный тип связи {linkage!r}. Доступны: single, complete"
            )
        self.metric = metric
        self.linkage = key
        self.closure = bool(closure)
        self._items = _as_items(variables)
        self._distance = get_distance_function(metric)
        self._similarity, self.scale = _similarity_data(
            self._items, self._distance, _validate_scale(scale)
        )
        self._closed: Optional[List[List[float]]] = None
        self._trace: Optional[Agglomeration] = None

    # ------------------------------------------------------------------
    # Данные, посчитанные один раз
    # ------------------------------------------------------------------
    @property
    def size(self) -> int:
        """Число величин в выборке."""
        return len(self._items)

    @property
    def similarity(self) -> List[List[float]]:
        """Копия матрицы сходства ``r_ij = 1 - d_ij / d0``."""
        return [list(row) for row in self._similarity]

    @property
    def closed(self) -> List[List[float]]:
        """Max-min замыкание матрицы сходства (считается при первом обращении)."""
        if self._closed is None:
            self._closed = max_min_closure(self._similarity)
        return self._closed

    @property
    def trace(self) -> Agglomeration:
        """Трасса агломерации полной связи (считается при первом обращении)."""
        if self._trace is None:
            merges = (
                _agglomerate(self._items, self._distance, None)[2]
                if self._items
                else []
            )
            self._trace = Agglomeration(len(self._items), tuple(merges))
        return self._trace

    # ------------------------------------------------------------------
    # Результаты
    # ------------------------------------------------------------------
    def clustering(
        self, alpha: float = 0.5, *, closure: Optional[bool] = None
    ) -> ClusterResult:
        """Кластеры при уровне ``alpha`` (как :func:`alpha_cut_clustering`)."""
        level = _validate_alpha(alpha)
        use_closure = self.closure if closure is None else bool(closure)
        parameters: Dict[str, Any] = {
            "alpha": level,
            "linkage": self.linkage,
            "closure": use_closure and self.linkage == "single",
            "distance_scale": self.scale,
        }
        if not self._items:
            return _build_result([], [], "alpha", self.metric, parameters)

        if self.linkage == "complete":
            # Сходство >= alpha  <=>  расстояние <= (1 - alpha) * d0.
            groups = _group_by_labels(
                self.trace.labels((1.0 - level) * self.scale)
            )
        else:
            matrix = self.closed if use_closure else self._similarity
            groups = _alpha_components(matrix, level)
        return _build_result(self._items, groups, "alpha", self.metric, parameters)

    def profile(
        self,
        alphas: Optional[Iterable[float]] = None,
        *,
        closure: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Зависимость числа кластеров от уровня (как :func:`alpha_cut_profile`)."""
        levels = [
            _validate_alpha(level)
            for level in (alphas if alphas is not None else DEFAULT_ALPHA_GRID)
        ]
        if not self._items:
            return [{"alpha": level, "cluster_count": 0} for level in levels]

        if self.linkage == "complete":
            # Дендрограмма построена один раз, уровень — просто разрез по высоте.
            ordered = sorted(self.trace.heights)
            return [
                {
                    "alpha": level,
                    "cluster_count": self.size
                    - bisect.bisect_right(ordered, (1.0 - level) * self.scale),
                }
                for level in levels
            ]

        use_closure = self.closure if closure is None else bool(closure)
        matrix = self.closed if use_closure else self._similarity
        return [
            {"alpha": level, "cluster_count": len(_alpha_components(matrix, level))}
            for level in levels
        ]


# ----------------------------------------------------------------------
# Единая точка входа
# ----------------------------------------------------------------------
CLUSTERING_METHODS: Dict[str, Callable[..., ClusterResult]] = {
    "kmeans": kmeans,
    "threshold": threshold_clustering,
    "alpha": alpha_cut_clustering,
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

    ``method`` — одно из ``kmeans``, ``threshold``, ``alpha``, ``density``;
    остальные именованные аргументы передаются выбранному методу (например
    ``k=5``, ``threshold=0.5`` или ``alpha=0.6``).
    """
    key = str(method).strip().lower()
    if key not in CLUSTERING_METHODS:
        available = ", ".join(sorted(CLUSTERING_METHODS))
        raise ValueError(f"Неизвестный метод кластеризации {method!r}. Доступны: {available}")
    return CLUSTERING_METHODS[key](variables, metric=metric, **parameters)
