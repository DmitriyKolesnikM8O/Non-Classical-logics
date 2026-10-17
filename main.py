"""Точка входа: запуск графического интерфейса.

Запуск из корня проекта::

    python main.py

Скрипт сам добавляет каталог ``src`` в путь поиска модулей, поэтому программу
можно запускать и без установки пакета (``pip install -e .``).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.is_dir() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.app import main  # noqa: E402  (импорт после настройки пути)

if __name__ == "__main__":
    raise SystemExit(main())
