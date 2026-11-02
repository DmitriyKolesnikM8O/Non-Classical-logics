"""Независимая библиотека для работы с нечеткими величинами равномерного типа.

Пакет не зависит от GUI и подсистемы журналирования, поэтому может
использоваться сторонними программами как обычная библиотека.
"""

from .clustering import (
    CLUSTERING_METHODS,
    DEFAULT_ALPHA_GRID,
    NOISE_LABEL,
    Agglomeration,
    AlphaClusterer,
    Cluster,
    ClusterResult,
    Merge,
    agglomerate,
    alpha_cut_clustering,
    alpha_cut_profile,
    cluster,
    density_clustering,
    grouped_result,
    kmeans,
    max_min_closure,
    similarity_matrix,
    threshold_clustering,
)
from .fuzzy_set import FuzzySet, FuzzySetError
from .fuzzy_variable import (
    DISTANCE_METRICS,
    FuzzyVariableError,
    UniformFuzzyVariable,
    alpha_cut_trapezoid,
    alpha_cut_triangular,
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
    "alpha_cut_trapezoid",
    "alpha_cut_triangular",
    "euclidean_distance",
    "hausdorff_distance",
    "DISTANCE_METRICS",
    "get_distance_function",
    "generate_sample",
    "generate_variables",
    "kmeans",
    "threshold_clustering",
    "alpha_cut_clustering",
    "alpha_cut_profile",
    "AlphaClusterer",
    "Agglomeration",
    "Merge",
    "agglomerate",
    "grouped_result",
    "similarity_matrix",
    "max_min_closure",
    "DEFAULT_ALPHA_GRID",
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
