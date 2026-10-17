"""Независимая библиотека для работы с нечеткими величинами равномерного типа.

Пакет не зависит от GUI и подсистемы журналирования, поэтому может
использоваться сторонними программами как обычная библиотека.
"""

from .clustering import (
    CLUSTERING_METHODS,
    NOISE_LABEL,
    Cluster,
    ClusterResult,
    cluster,
    density_clustering,
    kmeans,
    threshold_clustering,
)
from .fuzzy_set import FuzzySet, FuzzySetError
from .fuzzy_variable import (
    DISTANCE_METRICS,
    FuzzyVariableError,
    UniformFuzzyVariable,
    euclidean_distance,
    get_distance_function,
    hausdorff_distance,
)
from .generator import (
    DEFAULT_A_RANGE,
    DEFAULT_COUNT_RANGE,
    DEFAULT_WIDTH_RANGE,
    MAX_COUNT,
    MIN_COUNT,
    generate_sample,
    generate_variables,
)

__all__ = [
    "UniformFuzzyVariable",
    "FuzzyVariableError",
    "FuzzySet",
    "FuzzySetError",
    "euclidean_distance",
    "hausdorff_distance",
    "DISTANCE_METRICS",
    "get_distance_function",
    "generate_sample",
    "generate_variables",
    "kmeans",
    "threshold_clustering",
    "density_clustering",
    "cluster",
    "Cluster",
    "ClusterResult",
    "CLUSTERING_METHODS",
    "NOISE_LABEL",
    "MIN_COUNT",
    "MAX_COUNT",
    "DEFAULT_COUNT_RANGE",
    "DEFAULT_A_RANGE",
    "DEFAULT_WIDTH_RANGE",
]
__version__ = "0.1.0"
