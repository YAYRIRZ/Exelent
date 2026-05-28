"""Exelent Launcher — умная точка входа.

Логика:
  • Если рядом с .exe (или со скриптом) есть config.json → запускается лаунчер.
  • Если нет → запускается installer, который скопирует всё в выбранную
    пользователем папку, создаст там config.json и ярлык на рабочем столе,
    а затем перезапустит .exe из новой папки. На следующем запуске
    config.json уже есть → пойдёт лаунчер.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _app_dir() -> Path:
    """Папка, где реально лежит запущенный .exe (или этот скрипт)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


APP_DIR     = _app_dir()
CONFIG_FILE = APP_DIR / "config.json"


def main() -> None:
    if CONFIG_FILE.exists():
        from launcher import main as run
    else:
        from installer import main as run
    run()


if __name__ == "__main__":
    main()
