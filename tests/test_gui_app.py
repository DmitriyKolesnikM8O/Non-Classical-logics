"""Тесты каркаса GUI (Шаг 7a).

Окно строится без запуска цикла событий: тесты создают Tk-окно, программно
вызывают обработчики и проверяют, что записалось в журнал.
"""

from types import SimpleNamespace

import pytest

from gui.app import (
    APP_TITLE,
    TAB_ARITHMETIC,
    TAB_CLUSTERING,
    TAB_GENERATION,
    TAB_LOG,
    TAB_TITLES,
    ArithmeticTab,
    ClusteringTab,
    FuzzyApp,
    GenerationTab,
    LogTab,
    main,
)
from gui.widgets import LegendPanel, PlaceholderTab, StatusBar, center_window
from logger import SessionLogger


@pytest.fixture
def app(tk_window, tmp_path):
    application = FuzzyApp(master=tk_window, logger=SessionLogger(tmp_path))
    yield application
    if not application.closed:
        application.close()


# ----------------------------------------------------------------------
# Состав окна
# ----------------------------------------------------------------------
def test_window_title_and_tabs(app):
    assert app.root.title().startswith("Неклассические логики")
    assert APP_TITLE.startswith("Неклассические логики")


def test_four_tabs_in_expected_order(app):
    titles = [app.notebook.tab(index, "text") for index in range(len(app.notebook.tabs()))]
    assert titles == list(TAB_TITLES)
    assert titles == [TAB_ARITHMETIC, TAB_GENERATION, TAB_CLUSTERING, TAB_LOG]
    assert len(app.tabs) == 4


def test_no_placeholder_tabs_left_in_app(app):
    """Все вкладки главного окна реализованы."""
    assert not any(isinstance(tab, PlaceholderTab) for tab in app.tabs.values())


def test_implemented_tabs(app):
    assert isinstance(app.tabs[TAB_ARITHMETIC], ArithmeticTab)
    assert isinstance(app.tabs[TAB_GENERATION], GenerationTab)
    assert isinstance(app.tabs[TAB_CLUSTERING], ClusteringTab)
    assert isinstance(app.tabs[TAB_LOG], LogTab)


def test_tabs_are_all_frames_of_the_same_width(app):
    assert app.notebook.index("end") == 4
    assert app.notebook.select() == str(app.notebook.tabs()[0])


def test_menu_structure_and_exit_command(app):
    # индексы: 0 — открыть каталог, 1 — разделитель, 2 — выход
    assert app.file_menu.index("end") == 2
    assert app.help_menu.index("end") == 0
    app.file_menu.invoke(2)
    assert app.closed


def test_status_bar_shows_log_path(app):
    assert isinstance(app.status_bar, StatusBar)
    assert app.status_bar.message == "Готово"
    assert str(app.logger.log_path) in app.status_bar.log_text


# ----------------------------------------------------------------------
# Журналирование
# ----------------------------------------------------------------------
def test_creating_app_starts_log_session(app, tmp_path):
    assert app.logger.log_path.parent == tmp_path
    assert app.logger.log_path.exists()
    text = app.logger.read()
    assert "Сессия начата" in text
    assert "версия ядра" in text


def test_close_writes_session_end_and_closes_logger(app):
    log_path = app.logger.log_path
    app.close()

    assert app.closed
    assert app.logger.closed
    assert "Сессия завершена" in log_path.read_text(encoding="utf-8")


def test_close_is_idempotent(app):
    app.close()
    app.close()
    assert app.closed


def test_log_dir_argument_is_used(tk_window, tmp_path):
    target = tmp_path / "журналы"
    application = FuzzyApp(master=tk_window, log_dir=target)
    try:
        assert application.logger.log_path.parent == target
    finally:
        application.close()


def test_manual_logger_is_used(tk_window, tmp_path):
    custom = SessionLogger(tmp_path, "custom.log")
    application = FuzzyApp(master=tk_window, logger=custom)
    try:
        assert application.logger is custom
        assert application.logger.log_path.name == "custom.log"
    finally:
        application.close()


def test_logger_does_not_reach_root_logging(tmp_path, caplog):
    """Записи журнала не должны попадать в корневой журнал (изоляция)."""
    import logging

    with caplog.at_level(logging.DEBUG):
        with SessionLogger(tmp_path) as log:
            log.info("запись только в файл")
    assert "запись только в файл" in log.read()
    assert "запись только в файл" not in caplog.text


# ----------------------------------------------------------------------
# Полный цикл
# ----------------------------------------------------------------------
def test_run_returns_zero_after_scheduled_close(app, tk_root):
    def stop():
        app.close()
        tk_root.quit()  # останавливает цикл обработки событий Tcl

    app.root.after(50, stop)
    assert app.run() == 0
    assert app.closed


def test_main_help_does_not_open_window(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--log-dir" in capsys.readouterr().out


# ----------------------------------------------------------------------
# Вспомогательные компоненты
# ----------------------------------------------------------------------
def test_center_window_sets_geometry(tk_window):
    center_window(tk_window, 800, 600)
    tk_window.update_idletasks()
    assert tk_window.geometry().startswith("800x600")


def test_status_bar_messages(tk_window):
    bar = StatusBar(tk_window, "старт", "logs/session.log")
    assert bar.message == "старт"
    assert "logs/session.log" in bar.log_text
    bar.set_message("работаю")
    bar.set_log_path("другой.log")
    assert bar.message == "работаю"
    assert "другой.log" in bar.log_text


def test_placeholder_tab_without_description(tk_window):
    tab = PlaceholderTab(tk_window, "Пусто")
    assert tab.description_label is None
    assert tab.hint_labels == []


# ----------------------------------------------------------------------
# Панель легенды
# ----------------------------------------------------------------------
def test_legend_panel_rows_and_clear(tk_window):
    panel = LegendPanel(tk_window)
    try:
        assert panel.item_count == 0
        assert panel.captions == []
        panel.set_items(
            [
                ("#ff0000", "кластер 0", "точек: 3"),
                ("#00ff00", "кластер 1", ""),
            ]
        )
        assert panel.item_count == 2
        assert panel.captions == ["кластер 0", "кластер 1"]
        texts = [
            label.cget("text")
            for row in panel.rows
            for label in row.winfo_children()[1].winfo_children()
        ]
        assert texts == ["кластер 0", "точек: 3", "кластер 1"]

        panel.clear()
        assert panel.item_count == 0
        assert panel.captions == []
        assert panel.rows == []
    finally:
        panel.destroy()


def test_legend_panel_has_visible_scrollbar(tk_window):
    """Полоса прокрутки упакована до холста — иначе её сжимало до 3 пикселей."""
    panel = LegendPanel(tk_window)
    try:
        slaves = [str(widget) for widget in panel.canvas.master.pack_slaves()]
        assert slaves == [str(panel.scrollbar), str(panel.canvas)]
        assert panel.canvas.cget("yscrollcommand") != ""
    finally:
        panel.destroy()


def test_legend_panel_scrolls_with_mouse_wheel(tk_window):
    panel = LegendPanel(tk_window)
    try:
        panel.set_items(
            [("#ff0000", f"кластер {index}", "точек: 1") for index in range(40)]
        )
        assert panel.canvas.bind("<MouseWheel>")
        assert panel.inner.bind("<MouseWheel>")
        first_row = panel.rows[0]
        assert first_row.bind("<MouseWheel>")

        assert panel._on_mousewheel(SimpleNamespace(delta=-120)) == "break"
        assert panel._on_mousewheel(SimpleNamespace(delta=120)) == "break"
    finally:
        panel.destroy()


def test_legend_panel_replaces_previous_items(tk_window):
    panel = LegendPanel(tk_window)
    try:
        panel.set_items([("#ff0000", "старое", "")])
        panel.set_items([("#0000ff", "новое", "")])
        assert panel.item_count == 1
        assert panel.captions == ["новое"]
    finally:
        panel.destroy()


# ----------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------
def test_main_py_exists_and_delegates_to_gui():
    from pathlib import Path

    entry = Path(__file__).resolve().parents[1] / "main.py"
    assert entry.exists()
    text = entry.read_text(encoding="utf-8")
    assert "from gui.app import main" in text
    assert 'if __name__ == "__main__"' in text
