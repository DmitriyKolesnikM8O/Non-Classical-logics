"""Тесты подсистемы журналирования (Шаг 6)."""

import logging
import re

import pytest

from fuzzy_core import UniformFuzzyVariable as V, cluster
from logger import SessionLogger, default_log_dir, describe_variable, format_variable

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \| \w+\s+\| ")


def make_logger(tmp_path, filename=None, **kwargs):
    return SessionLogger(tmp_path, filename, **kwargs)


# ----------------------------------------------------------------------
# Создание файла журнала
# ----------------------------------------------------------------------
def test_creates_log_directory_and_file(tmp_path):
    target = tmp_path / "вложенный" / "logs"
    log = make_logger(target, "test.log")
    log.info("привет")
    log.close()

    assert target.is_dir()
    assert log.log_path == target / "test.log"
    assert log.log_path.exists()


def test_default_filename_contains_date_and_time(tmp_path):
    log = make_logger(tmp_path)
    name = log.log_path.name
    log.close()
    assert re.fullmatch(r"session_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log", name), name


def test_default_log_dir_is_project_logs():
    path = default_log_dir()
    assert path.name == "logs"
    assert (path.parent / "pyproject.toml").exists()


def test_each_line_has_timestamp_and_level(tmp_path):
    with make_logger(tmp_path) as log:
        log.info("строка один")
        log.warning("строка два")
    lines = [line for line in log.read().splitlines() if line]
    assert len(lines) == 2
    for line in lines:
        assert TIMESTAMP_RE.match(line), line
    assert "INFO" in lines[0] and "строка один" in lines[0]
    assert "WARNING" in lines[1] and "строка два" in lines[1]


def test_explicit_filename_is_used(tmp_path):
    with make_logger(tmp_path, "my_session.log") as log:
        log.info("x")
    assert log.log_path.name == "my_session.log"


# ----------------------------------------------------------------------
# Записи о сессии
# ----------------------------------------------------------------------
def test_session_started_and_finished(tmp_path):
    with make_logger(tmp_path) as log:
        log.session_started("тестовый запуск")
        log.session_finished()
    text = log.read()
    assert "Сессия начата" in text
    assert "Сессия завершена" in text
    assert "тестовый запуск" in text


# ----------------------------------------------------------------------
# Записи о величинах и операциях
# ----------------------------------------------------------------------
def test_log_variable_stores_bounds_center_and_width(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_variable("создание", V(1, 5))
    text = log.read()
    assert "создание" in text
    assert "[1.000, 5.000]" in text
    assert "c=3.000" in text and "w=4.000" in text


def test_log_variables_for_collection(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_variables("добавление", [V(0, 1), V(2, 3)])
    text = log.read()
    assert "всего 2" in text
    assert "[0.000, 1.000]" in text and "[2.000, 3.000]" in text


def test_log_operation_with_result(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_operation("+", V(1, 2), V(3, 4), result=V(4, 6))
        log.log_operation("/", V(1, 2), V(0, 3))
    text = log.read()
    assert "Операция +: [1.000, 2.000] и [3.000, 4.000] = [4.000, 6.000]" in text
    assert "Операция /: [1.000, 2.000] и [0.000, 3.000]" in text


def test_log_operation_accepts_numbers_and_strings(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_operation("*", V(1, 2), 3, result=V(3, 6))
    text = log.read()
    assert "и 3.000" in text


def test_log_comparison_and_dominance(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_comparison(V(0, 2), ">", V(5, 7), outcome=True)
        log.log_dominance(V(2, 3), V(0, 1))
    text = log.read()
    assert "Сравнение: [0.000, 2.000] > [5.000, 7.000] -> True" in text
    assert "Pos=1.000" in text and "Nec=1.000" in text and "доминирование=1.0000" in text


# ----------------------------------------------------------------------
# Записи о выборке
# ----------------------------------------------------------------------
def test_log_sample_writes_parameters_and_statistics(tmp_path):
    from fuzzy_core import generate_sample

    items = generate_sample(120, seed=5)
    with make_logger(tmp_path) as log:
        log.log_sample(
            items,
            seed=5,
            a_range=(-10.0, 10.0),
            width_range=(0.0, 4.0),
            count_range=(100, 300),
        )
    text = log.read()
    assert "элементов=120" in text
    assert "seed=5" in text
    assert "a_range=(-10.0, 10.0)" in text
    assert "охватывающий интервал=" in text
    assert "средний центр=" in text and "средняя ширина=" in text


def test_log_sample_of_empty_collection(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_sample([])
    assert "выборка пуста" in log.read()


def test_log_sample_accepts_plain_list(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_sample([V(0, 1), V(2, 3)], source="файл")
    text = log.read()
    assert "(файл): элементов=2" in text
    assert "охватывающий интервал" not in text  # статистика только для FuzzySet


# ----------------------------------------------------------------------
# Записи о кластеризации
# ----------------------------------------------------------------------
def separated_items():
    left = [V(-20 + 0.1 * i, -19 + 0.1 * i) for i in range(4)]
    right = [V(20 + 0.1 * i, 21 + 0.1 * i) for i in range(4)]
    return left + right, V(100, 101)


def test_log_clustering_writes_parameters_summary_and_clusters(tmp_path):
    items, outlier = separated_items()
    result = cluster(items + [outlier], "kmeans", k=3, seed=1)

    with make_logger(tmp_path) as log:
        log.log_clustering(result)

    text = log.read()
    assert "метод=kmeans" in text
    assert "метрика=hausdorff" in text
    assert "k=3" in text
    assert "элементов=9, кластеров=3" in text
    assert "размеры кластеров=[4, 4, 1]" in text
    assert "суммарная инерция=" in text
    assert "средний силуэт=" in text
    assert "Кластер 1: размер=4" in text
    assert "Кластер 3: размер=1" in text


def test_log_clustering_marks_noise(tmp_path):
    points = [V(float(i), float(i)) for i in range(4)] + [V(100.0, 100.0)]
    result = cluster(points, "density", eps=1.0, min_points=2)
    with make_logger(tmp_path) as log:
        log.log_clustering(result)
    text = log.read()
    assert "точек-шума=1" in text
    assert "индексы шума=[4]" in text


def test_log_clustering_can_skip_per_cluster_details(tmp_path):
    items, outlier = separated_items()
    result = cluster(items + [outlier], "kmeans", k=3, seed=1)
    with make_logger(tmp_path) as log:
        log.log_clustering(result, include_clusters=False)
    text = log.read()
    assert "размеры кластеров=" in text
    assert "Кластер 1:" not in text


# ----------------------------------------------------------------------
# Ошибки, чтение, закрытие
# ----------------------------------------------------------------------
def test_log_error_uses_error_level(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_error("Деление невозможно", "интервал содержит 0")
    line = [l for l in log.read().splitlines() if l][0]
    assert "ERROR" in line
    assert "Деление невозможно (интервал содержит 0)" in line


def test_read_and_tail(tmp_path):
    with make_logger(tmp_path) as log:
        for i in range(10):
            log.info(f"строка {i}")
    content = log.read()
    assert "строка 0" in content and "строка 9" in content
    tail = log.tail(3)
    assert tail.splitlines() == [l for l in content.splitlines() if l][-3:]


def test_close_is_idempotent_and_flushes(tmp_path):
    log = make_logger(tmp_path)
    log.info("до закрытия")
    log.close()
    assert log.closed
    log.close()  # повторный вызов не должен падать
    assert "до закрытия" in log.read()


def test_context_manager_closes_logger(tmp_path):
    with make_logger(tmp_path) as log:
        log.info("внутри")
    assert log.closed


def test_closed_logger_does_not_write_new_lines(tmp_path):
    log = make_logger(tmp_path)
    log.info("первая")
    log.close()
    log.info("вторая")
    assert "первая" in log.read()
    assert "вторая" not in log.read()


def test_write_after_close_is_silent(tmp_path):
    """После закрытия журнал не должен выбрасывать исключения (важно для GUI)."""
    log = make_logger(tmp_path)
    log.close()
    log.session_finished()
    log.log_error("после закрытия")
    log.log_variable("создание", V(0, 1))
    assert log.closed


def test_cyrillic_content_roundtrip(tmp_path):
    with make_logger(tmp_path) as log:
        log.log_variable("создание величины", V(-3, 7))
    text = log.read()
    assert "создание величины" in text
    assert "Величина" in text


# ----------------------------------------------------------------------
# Изоляция журналов
# ----------------------------------------------------------------------
def test_logger_does_not_propagate_to_root(tmp_path):
    root_handlers = list(logging.getLogger().handlers)
    with make_logger(tmp_path) as log:
        log.info("изолированная запись")
        assert log._logger.propagate is False
    assert list(logging.getLogger().handlers) == root_handlers


def test_two_loggers_write_to_separate_files(tmp_path):
    first, second = make_logger(tmp_path, "a.log"), make_logger(tmp_path, "b.log")
    first.info("в первый")
    second.info("во второй")
    first.close()
    second.close()
    assert "в первый" in first.read() and "во второй" not in first.read()
    assert "во второй" in second.read() and "в первый" not in second.read()


def test_echo_duplicates_to_console(tmp_path, capsys):
    with make_logger(tmp_path, echo=True) as log:
        log.info("и в файл, и на экран")
    assert "и в файл, и на экран" in capsys.readouterr().err
    assert "и в файл, и на экран" in log.read()


# ----------------------------------------------------------------------
# Форматирование
# ----------------------------------------------------------------------
def test_format_variable_for_various_types():
    assert format_variable(V(1.5, 2.25)) == "[1.500, 2.250]"
    assert format_variable(3) == "3.000"
    assert format_variable("текст") == "текст"
    assert format_variable(None) == "None"
    assert format_variable(V(1, 2), digits=1) == "[1.0, 2.0]"


def test_describe_variable_includes_center_and_width():
    text = describe_variable(V(0, 4))
    assert "[0.000, 4.000]" in text and "c=2.000" in text and "w=4.000" in text
