"""Exelent Launcher — точка входа (Windows only).

Логика:
  1. Если рядом с этим .exe уже есть config.json — значит мы и есть
     установленный лаунчер. Запускаем launcher.main().

  2. Иначе — это инсталлер/обновлятор. Запускаем installer.
     Инсталлер сам прочитает %USERPROFILE%\\exelent\\installed_info.txt
     и подставит сохранённый путь как путь установки по умолчанию,
     чтобы при обновлении не нужно было выбирать папку повторно.
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
        # Мы — установленный лаунчер.
        from launcher import main as run
        run()
        return

    # Это инсталлер.
    from installer import main as run
    run()


if __name__ == "__main__":
    main()
