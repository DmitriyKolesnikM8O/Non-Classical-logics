"""Общие фикстуры тестов.

GUI-тесты используют один общий корень Tk на всю сессию: пересоздавать
``tk.Tk()`` после ``destroy()`` в одном процессе нельзя (Tcl-интерпретатор
частично разрушается), поэтому каждому тесту выдаётся своё окно ``Toplevel``.
"""

import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """Единственный на всю сессию (скрытый) корень Tk."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - зависит от окружения
        pytest.skip(f"Tk недоступен: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.fixture
def tk_window(tk_root):
    """Отдельное окно для одного теста; закрывается автоматически."""
    window = tk.Toplevel(tk_root)
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:  # pragma: no cover
        pass
