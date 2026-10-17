"""Подсистема журналирования сессии работы с нечеткими величинами.

Журнал — обычный текстовый файл ``logs/session_<дата>_<время>.log`` с метками
времени. Все записи идут через стандартный модуль :mod:`logging`, поэтому
подсистему можно использовать и в GUI, и в консольных сценариях.

Пример
------
::

    with SessionLogger() as log:
        log.session_started()
        log.log_variable("создание", UniformFuzzyVariable(1, 2))
        log.log_operation("+", UniformFuzzyVariable(1, 2), UniformFuzzyVariable(3, 4),
                          result=UniformFuzzyVariable(4, 6))
"""

from __future__ import annotations

import itertools
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

from fuzzy_core.clustering import NOISE_LABEL, ClusterResult
from fuzzy_core.fuzzy_set import FuzzySet
from fuzzy_core.fuzzy_variable import UniformFuzzyVariable

__all__ = [
    "SessionLogger",
    "TIMESTAMP_FORMAT",
    "FILE_TIMESTAMP_FORMAT",
    "default_log_dir",
    "format_variable",
    "describe_variable",
]

#: Формат метки времени внутри строки журнала.
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

#: Формат метки времени в имени файла журнала.
FILE_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"

LINE_FORMAT = "%(asctime)s,%(msecs)03d | %(levelname)-8s | %(message)s"

_instances = itertools.count(1)


# ----------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------
def default_log_dir() -> Path:
    """Каталог журналов по умолчанию: ``<корень проекта>/logs``.

    Если по расположению модуля корень проекта не определяется (например,
    библиотека установлена как обычный пакет), используется ``./logs``.
    """
    project_root = Path(__file__).resolve().parents[2]
    if (project_root / "pyproject.toml").exists() or (project_root / "README.md").exists():
        return project_root / "logs"
    return Path.cwd() / "logs"


def format_variable(value: Any, digits: int = 3) -> str:
    """Короткая запись величины: ``[a, b]``; числа и строки — как есть."""
    if isinstance(value, UniformFuzzyVariable):
        return f"[{value.a:.{digits}f}, {value.b:.{digits}f}]"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.{digits}f}"
    if isinstance(value, str):
        return value
    return repr(value)


def describe_variable(variable: UniformFuzzyVariable, digits: int = 3) -> str:
    """Подробная запись величины: носитель, центр и ширина."""
    return (
        f"{format_variable(variable, digits)} "
        f"(c={variable.center:.{digits}f}, w={variable.width:.{digits}f})"
    )


def _number(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}g}"


def _parameters_text(parameters: dict) -> str:
    if not parameters:
        return "нет"
    return ", ".join(f"{key}={value!r}" for key, value in parameters.items())


def _as_sequence(values: Union[FuzzySet, Iterable[Any]]) -> Sequence[Any]:
    if isinstance(values, FuzzySet):
        return list(values)
    try:
        return list(values)
    except TypeError:
        return [values]


# ----------------------------------------------------------------------
# Основной класс
# ----------------------------------------------------------------------
class SessionLogger:
    """Журнал одной сессии работы с программой.

    Параметры
    ---------
    log_dir:
        Каталог журналов (по умолчанию ``<корень проекта>/logs``).
    filename:
        Имя файла; по умолчанию ``session_<дата>_<время>.log``.
    level:
        Минимальный уровень записей (по умолчанию ``logging.INFO``).
    echo:
        Дублировать записи в консоль (удобно для отладки).
    encoding:
        Кодировка файла журнала (по умолчанию ``utf-8``).
    """

    def __init__(
        self,
        log_dir: Optional[Union[str, Path]] = None,
        filename: Optional[str] = None,
        *,
        level: int = logging.INFO,
        echo: bool = False,
        encoding: str = "utf-8",
    ) -> None:
        self._dir = Path(log_dir) if log_dir is not None else default_log_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._filename = filename or f"session_{datetime.now().strftime(FILE_TIMESTAMP_FORMAT)}.log"
        self._path = self._dir / self._filename
        self._encoding = encoding
        self._closed = False

        logger = logging.getLogger(f"fuzzy_session.{next(_instances)}")
        logger.setLevel(level)
        logger.propagate = False  # записи не должны уходить в корневой журнал

        formatter = logging.Formatter(LINE_FORMAT, datefmt=TIMESTAMP_FORMAT)
        file_handler = logging.FileHandler(self._path, mode="a", encoding=encoding)
        file_handler.setFormatter(formatter)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        self._file_handler = file_handler

        self._console_handler: Optional[logging.Handler] = None
        if echo:
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            logger.addHandler(console)
            self._console_handler = console

        self._logger = logger

    # ------------------------------------------------------------------
    # Свойства
    # ------------------------------------------------------------------
    @property
    def log_path(self) -> Path:
        """Путь к файлу журнала."""
        return self._path

    @property
    def log_dir(self) -> Path:
        """Каталог журналов."""
        return self._dir

    @property
    def closed(self) -> bool:
        """Закрыт ли журнал."""
        return self._closed

    # ------------------------------------------------------------------
    # Базовые записи
    # ------------------------------------------------------------------
    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    def log_error(self, message: str, details: str = "") -> None:
        """Записать ошибку (при необходимости — с пояснением)."""
        text = message if not details else f"{message} ({details})"
        self._logger.error(text)

    # ------------------------------------------------------------------
    # Сессия
    # ------------------------------------------------------------------
    def session_started(self, note: Optional[str] = None) -> None:
        """Отметить начало сессии."""
        self._logger.info("=" * 70)
        self._logger.info(f"Сессия начата: {datetime.now().strftime(TIMESTAMP_FORMAT)}")
        self._logger.info(f"Файл журнала: {self._path}")
        if note:
            self._logger.info(f"Примечание: {note}")

    def session_finished(self, note: Optional[str] = None) -> None:
        """Отметить завершение сессии."""
        if note:
            self._logger.info(f"Примечание: {note}")
        self._logger.info(f"Сессия завершена: {datetime.now().strftime(TIMESTAMP_FORMAT)}")
        self._logger.info("=" * 70)

    # ------------------------------------------------------------------
    # Нечеткие величины и операции
    # ------------------------------------------------------------------
    def log_variable(self, action: str, variable: Any) -> None:
        """Записать действие с величиной (создание, изменение, удаление)."""
        if isinstance(variable, UniformFuzzyVariable):
            self._logger.info(f"Величина ({action}): {describe_variable(variable)}")
        else:
            self._logger.info(f"Величина ({action}): {format_variable(variable)}")

    def log_variables(self, action: str, variables: Union[FuzzySet, Iterable[Any]]) -> None:
        """Записать действие над несколькими величинами."""
        items = _as_sequence(variables)
        self._logger.info(f"Величины ({action}), всего {len(items)}:")
        for variable in items:
            if isinstance(variable, UniformFuzzyVariable):
                self._logger.info(f"    {describe_variable(variable)}")
            else:
                self._logger.info(f"    {format_variable(variable)}")

    def log_operation(
        self,
        operation: str,
        left: Any = None,
        right: Any = None,
        result: Any = None,
    ) -> None:
        """Записать арифметическую операцию с её операндами и результатом."""
        parts = [format_variable(operand) for operand in (left, right) if operand is not None]
        text = f"Операция {operation}: " + " и ".join(parts) if parts else f"Операция {operation}"
        if result is not None:
            text += f" = {format_variable(result)}"
            if isinstance(result, UniformFuzzyVariable):
                text += f" (c={result.center:.3f}, w={result.width:.3f})"
        self._logger.info(text)

    def log_comparison(self, left: Any, relation: str, right: Any, outcome: Any) -> None:
        """Записать результат сравнения величин."""
        self._logger.info(
            f"Сравнение: {format_variable(left)} {relation} {format_variable(right)}"
            f" -> {outcome}"
        )

    def log_dominance(self, left: UniformFuzzyVariable, right: UniformFuzzyVariable) -> None:
        """Записать индексы сравнения двух величин (возможность/необходимость/доминирование)."""
        self._logger.info(
            f"Сравнение индексов для {format_variable(left)} и {format_variable(right)}: "
            f"Pos={left.possibility_greater_or_equal(right):.3f}, "
            f"Nec={left.necessity_greater_or_equal(right):.3f}, "
            f"доминирование={left.dominance(right):.4f}"
        )

    # ------------------------------------------------------------------
    # Выборка
    # ------------------------------------------------------------------
    def log_sample(
        self,
        variables: Union[FuzzySet, Iterable[Any]],
        *,
        source: str = "генератор",
        seed: Any = None,
        a_range: Any = None,
        width_range: Any = None,
        count_range: Any = None,
    ) -> None:
        """Записать параметры и характеристики сгенерированной выборки."""
        items = _as_sequence(variables)
        self._logger.info(f"Выборка ({source}): элементов={len(items)}")
        if seed is not None:
            self._logger.info(f"    seed={seed!r}")
        if a_range is not None or width_range is not None or count_range is not None:
            self._logger.info(
                f"    параметры: a_range={a_range}, width_range={width_range}, "
                f"count_range={count_range}"
            )
        if not items:
            self._logger.info("    выборка пуста")
            return
        if isinstance(variables, FuzzySet):
            low, high = variables.envelope()
            self._logger.info(
                f"    охватывающий интервал=[{low:.3f}, {high:.3f}], "
                f"средний центр={_number(variables.mean_center())}, "
                f"средняя ширина={_number(variables.mean_width())}"
            )

    # ------------------------------------------------------------------
    # Кластеризация
    # ------------------------------------------------------------------
    def log_clustering(self, result: ClusterResult, *, include_clusters: bool = True) -> None:
        """Записать параметры и результаты кластерного анализа."""
        self._logger.info(
            f"Кластеризация: метод={result.method}, метрика={result.metric}, "
            f"параметры: {_parameters_text(result.parameters)}"
        )
        self._logger.info(
            f"    элементов={len(result.items)}, кластеров={len(result.clusters)}, "
            f"точек-шума={len(result.noise)}"
        )
        if result.noise:
            self._logger.info(f"    индексы шума={sorted(result.noise)}")
        self._logger.info(f"    размеры кластеров={result.sizes}")
        self._logger.info(
            f"    суммарная инерция={_number(result.total_inertia)}, "
            f"средняя внутрикластерная дисперсия центров={_number(result.average_center_variance)}, "
            f"максимальный диаметр={_number(result.max_diameter)}"
        )
        silhouette = result.silhouette()
        if silhouette is not None:
            self._logger.info(f"    средний силуэт={silhouette:.4f}")

        if include_clusters:
            for index, cluster in enumerate(result.clusters, start=1):
                centroid = cluster.centroid
                self._logger.info(
                    f"    Кластер {index}: размер={cluster.size}, "
                    f"центроид=[{centroid.a:.3f}, {centroid.b:.3f}] "
                    f"(c={centroid.center:.3f}, w={centroid.width:.3f}), "
                    f"инерция={_number(cluster.inertia)}, "
                    f"дисперсия центров={_number(cluster.center_variance)}, "
                    f"диаметр={_number(cluster.diameter)}"
                )

    # ------------------------------------------------------------------
    # Чтение и закрытие
    # ------------------------------------------------------------------
    def read(self) -> str:
        """Прочитать текущее содержимое журнала (для отображения в GUI)."""
        try:
            return self._path.read_text(encoding=self._encoding)
        except FileNotFoundError:
            return ""

    def tail(self, lines: int = 200) -> str:
        """Последние ``lines`` строк журнала."""
        content = self.read().splitlines()
        return "\n".join(content[-lines:])

    def close(self) -> None:
        """Закрыть журнал (повторный вызов безопасен)."""
        if self._closed:
            return
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.flush()
            handler.close()
        self._console_handler = None
        self._closed = True

    def __enter__(self) -> "SessionLogger":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"SessionLogger(path={str(self._path)!r}, closed={self._closed})"
