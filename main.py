"""Exelent Launcher — умная точка входа.

Логика выбора:
  1. Сначала смотрим глобальный файл-маркер:
        Windows: %USERPROFILE%\\exelent\\installed_info.txt
        Linux:   ~/.exelent/installed_info.txt
     В нём — путь к папке, куда лаунчер был установлен ранее.
     Если файл есть, путь существует и в нём лежит исполняемый
     "Exelent Launcher.exe" — просто запускаем его и выходим.
     Это значит «лаунчер уже установлен, инсталлер больше не нужен».

  2. Если рядом с этим скриптом/exe уже есть config.json —
     значит мы и есть установленный лаунчер. Запускаем launcher.main().

  3. Иначе — это первый запуск (или файл-маркер пропал, или его удалили):
     запускаем installer, который скопирует всё в выбранную пользователем
     папку, создаст config.json и обновит installed_info.txt.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


# ── Пути ──
def _app_dir() -> Path:
    """Папка, где реально лежит запущенный .exe (или этот скрипт)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


APP_DIR     = _app_dir()
CONFIG_FILE = APP_DIR / "config.json"

INSTALLED_INFO_FILENAME = "installed_info.txt"
LAUNCHER_EXE_NAME       = "Exelent Launcher.exe"


def _installed_info_file() -> Path:
    """Путь к файлу-маркеру с местом установки.

    Windows: %USERPROFILE%/exelent/installed_info.txt
    Linux/Mac: ~/.exelent/installed_info.txt
    """
    if sys.platform == "win32":
        base = Path(os.environ.get(
            "USERPROFILE", os.path.expanduser("~"))) / "exelent"
    else:
        base = Path(os.path.expanduser("~")) / ".exelent"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base / INSTALLED_INFO_FILENAME


def _read_installed_dir() -> Path | None:
    """Прочитать путь установки или None, если файла нет / путь невалиден."""
    f = _installed_info_file()
    if not f.exists():
        return None
    try:
        raw = f.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None
    p = Path(raw)
    if not p.exists() or not p.is_dir():
        return None
    return p


def _save_installed_dir(path: Path) -> None:
    try:
        _installed_info_file().write_text(
            str(Path(path).resolve()), encoding="utf-8")
    except Exception:
        pass


def _launch_external(install_dir: Path) -> bool:
    """Пытается запустить Exelent Launcher.exe из install_dir.
    Возвращает True если процесс был стартован, иначе False.
    """
    # Windows .exe
    exe = install_dir / LAUNCHER_EXE_NAME
    if exe.exists():
        try:
            subprocess.Popen([str(exe)], cwd=str(install_dir), close_fds=True)
            return True
        except Exception:
            return False
    # Fallback — python запуск launcher.py из этой папки
    py_main = install_dir / "main.py"
    if py_main.exists() and not getattr(sys, "frozen", False):
        try:
            subprocess.Popen(
                [sys.executable, str(py_main)],
                cwd=str(install_dir), close_fds=True)
            return True
        except Exception:
            return False
    return False


def main() -> None:
    # ─── 1) Глобальный файл-маркер: уже установлен? ───
    installed_dir = _read_installed_dir()
    if installed_dir is not None and installed_dir != APP_DIR:
        # Не наша папка — запустить установленный лаунчер и выйти.
        if _launch_external(installed_dir):
            return
        # Если не получилось — продолжаем по обычной логике (на крайний случай).

    # ─── 2) Мы и есть установленный лаунчер ───
    if CONFIG_FILE.exists():
        # На всякий случай обновим маркер — пусть указывает на нас.
        _save_installed_dir(APP_DIR)
        from launcher import main as run
        run()
        return

    # ─── 3) Первый запуск — инсталлер ───
    from installer import main as run
    run()


if __name__ == "__main__":
    main()
