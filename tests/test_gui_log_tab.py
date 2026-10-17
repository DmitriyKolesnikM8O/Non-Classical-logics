"""Тесты вкладки «Журнал» (Шаг 7e)."""

import pytest

from gui import app as app_module
from gui.app import TAB_LOG, FuzzyApp, LogTab
from logger import SessionLogger


@pytest.fixture
def messages():
    return []


@pytest.fixture
def tab(tk_window, tmp_path, messages):
    logger = SessionLogger(tmp_path / "logs")
    logger.session_started("тест")
    logger.info("первая рабочая запись")
    widget = LogTab(tk_window, logger, on_message=messages.append, autoupdate_ms=100000)
    yield widget
    widget._cancel_reload()
    if not logger.closed:
        logger.close()


def info_text(tab) -> str:
    return tab.info_label.cget("text")


# ----------------------------------------------------------------------
# Просмотр
# ----------------------------------------------------------------------
def test_log_is_shown_on_start(tab):
    content = tab.view.content
    assert "Сессия начата" in content
    assert "первая рабочая запись" in content
    assert tab.total_lines == len(tab.full_text.splitlines())
    assert tab.visible_lines == tab.total_lines


def test_info_label_shows_file_and_counts(tab):
    text = info_text(tab)
    assert tab.logger.log_path.name in text
    assert f"строк: {tab.total_lines}" in text
    assert "обновлено" in text
    assert tab.last_update is not None


def test_reload_picks_up_new_records(tab):
    tab.logger.info("новая запись после обновления")
    assert "новая запись после обновления" not in tab.view.content

    text = tab.reload()
    assert "новая запись после обновления" in text
    assert "новая запись после обновления" in tab.view.content


def test_on_tab_activated_reloads(tab):
    tab.logger.info("запись перед переключением вкладки")
    tab.on_tab_activated()
    assert "запись перед переключением вкладки" in tab.view.content


# ----------------------------------------------------------------------
# Фильтр
# ----------------------------------------------------------------------
def test_filter_keeps_only_matching_lines(tab):
    tab.logger.info("строка про кластеры")
    tab.logger.warning("строка про ошибку")
    tab.reload()

    tab.filter_var.set("кластер")
    tab.reload()

    assert "строка про кластеры" in tab.view.content
    assert "строка про ошибку" not in tab.view.content
    assert tab.visible_lines < tab.total_lines
    assert f"(показано {tab.visible_lines})" in info_text(tab)


def test_filter_is_case_insensitive(tab):
    tab.logger.info("Строка С Большими Буквами")
    tab.filter_var.set("большими")
    tab.reload()
    assert "Строка С Большими Буквами" in tab.view.content


def test_filter_can_be_cleared(tab):
    tab.filter_var.set("несуществующий текст")
    tab.reload()
    assert tab.view.content == ""

    tab.filter_var.set("")
    tab.reload()
    assert tab.visible_lines == tab.total_lines
    assert "Сессия начата" in tab.view.content


# ----------------------------------------------------------------------
# Сохранение
# ----------------------------------------------------------------------
def test_save_to_copies_log_and_notes_it(tab, tmp_path, messages):
    target = tmp_path / "копия" / "журнал.log"
    result = tab.save_to(target)

    assert result == target
    assert target.exists()
    copied = target.read_text(encoding="utf-8")
    assert "Сессия начата" in copied
    assert "первая рабочая запись" in copied
    assert tab.saved_path == target
    assert f"Журнал сохранён: {target}" == messages[-1]
    assert str(target) in info_text(tab)

    # сама запись о сохранении попадает в журнал сессии и в окно просмотра
    assert f"Журнал сохранён в файл: {target}" in tab.logger.read()
    assert f"Журнал сохранён в файл: {target}" in tab.view.content


def test_save_as_uses_file_dialog(tab, tmp_path, monkeypatch):
    target = tmp_path / "выбранный.log"
    monkeypatch.setattr(
        app_module.filedialog, "asksaveasfilename", lambda **kwargs: str(target)
    )
    assert tab.save_as() == target
    assert target.exists()


def test_save_as_cancelled(tab, messages, monkeypatch):
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **kwargs: "")
    assert tab.save_as() is None
    assert messages[-1] == "Сохранение журнала отменено"


def test_save_to_directory_reports_error(tab, tmp_path):
    assert tab.save_to(tmp_path) is None
    assert "Ошибка" in info_text(tab)
    assert "ERROR" in tab.logger.read()


# ----------------------------------------------------------------------
# Автообновление
# ----------------------------------------------------------------------
def test_autoupdate_can_be_turned_on_and_off(tab):
    assert tab.autoupdate_active is False

    tab.autoupdate_var.set(True)
    tab._toggle_autoupdate()
    assert tab.autoupdate_active is True

    tab.autoupdate_var.set(False)
    tab._toggle_autoupdate()
    assert tab.autoupdate_active is False


def test_auto_reload_reads_log_and_reschedules(tab):
    tab.autoupdate_var.set(True)
    tab._toggle_autoupdate()

    tab.logger.info("запись во время автообновления")
    tab._auto_reload()

    assert "запись во время автообновления" in tab.view.content
    assert tab.autoupdate_active is True
    tab._cancel_reload()


# ----------------------------------------------------------------------
# Встраивание в главное окно
# ----------------------------------------------------------------------
def test_app_has_log_tab_and_refreshes_it(tk_window, tmp_path):
    application = FuzzyApp(master=tk_window, logger=SessionLogger(tmp_path))
    try:
        widget = application.tabs[TAB_LOG]
        assert isinstance(widget, LogTab)
        assert widget.logger is application.logger

        application.notebook.select(application.tabs[TAB_LOG])
        application.notebook.update_idletasks()
        application.logger.info("запись через главное окно")
        application._on_tab_changed()
        assert "запись через главное окно" in widget.view.content
    finally:
        application.close()


def test_no_placeholder_tabs_left(tk_window, tmp_path):
    """Все четыре вкладки реализованы — заготовок больше нет."""
    from gui.widgets import PlaceholderTab

    application = FuzzyApp(master=tk_window, logger=SessionLogger(tmp_path))
    try:
        assert set(application.tabs) == set(app_module.TAB_TITLES)
        assert not any(
            isinstance(tab, PlaceholderTab) for tab in application.tabs.values()
        )
    finally:
        application.close()
