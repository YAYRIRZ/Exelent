"""
Exelent Launcher Installer.

Шаги:
  1. Пользователь выбирает папку установки.
  2. Копируется содержимое папки рядом с .exe (включая _internal/).
  3. Скачиваются дефолтные ассеты Minecraft:
       (а) сначала пробуем готовый ZIP с GitHub (1 запрос, быстро)
       (б) если не получилось — фоллбек на поштучную скачку с
           assets.mcasset.cloud
  4. Создаётся config.json — это переключит main.py в режим лаунчера.
  5. Создаётся ярлык на рабочем столе.
  6. Запускается установленный .exe и установщик закрывается.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from PyQt6.QtCore import (Qt, QTimer, QRectF, QThread, pyqtSignal, QSize)
from PyQt6.QtGui import (QPainter, QColor, QLinearGradient, QBrush, QPen,
                         QPainterPath, QIcon, QCursor, QFont)
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QMessageBox, QPushButton,
                             QFrame, QSizePolicy, QCheckBox)

from icons import svg_icon, svg_pixmap
import themes as themes_mod
from widgets import SnakeProgress, BorderOverlay


# ═══════════════════════════════════════════════════════════════
#  Константы / определение источника установки
# ═══════════════════════════════════════════════════════════════

EXE_NAME    = "Exelent Launcher.exe"
CUSTOM_FONT = "Segoe UI"

MCASSET_VERSION = "1.21.4"
MCASSET_BASE    = f"https://assets.mcasset.cloud/{MCASSET_VERSION}/assets/minecraft"

# Готовый ZIP с ассетами (быстрая установка)
ASSETS_ZIP_URL = (
    "https://github.com/YAYRIRZ/SkyPluginsVersion/raw/refs/heads/main/"
    "mc-assets-1.21.4.zip"
)

# Если в ZIP корневая папка называется так — её содержимое распакуется в assets/mc/
# (как сгенерировал download_assets.py). Делаем гибко: ищем любой подкаталог
# с textures/ внутри.
ASSETS_ZIP_ROOT_HINT = f"mc-assets-{MCASSET_VERSION}"

# Фоллбек: поштучное скачивание (если ZIP недоступен).
# Список оставлен короткий — только самое нужное для UI лаунчера.
ASSET_FILES_FALLBACK: list[str] = [
    "textures/item/iron_sword.png",
    "textures/item/diamond_sword.png",
    "textures/item/netherite_sword.png",
    "textures/item/iron_pickaxe.png",
    "textures/item/diamond_pickaxe.png",
    "textures/item/iron_ingot.png",
    "textures/item/gold_ingot.png",
    "textures/item/diamond.png",
    "textures/item/emerald.png",
    "textures/item/netherite_ingot.png",
    "textures/item/redstone.png",
    "textures/item/lapis_lazuli.png",
    "textures/item/amethyst_shard.png",
    "textures/item/copper_ingot.png",
    "textures/item/quartz.png",
    "textures/block/furnace_front_on.png",
    "textures/block/crafting_table_front.png",
    "textures/block/diamond_block.png",
    "textures/block/iron_block.png",
    "textures/block/gold_block.png",
    "textures/block/emerald_block.png",
    "textures/block/redstone_block.png",
    "textures/block/redstone_ore.png",
    "textures/block/lapis_block.png",
    "textures/block/netherite_block.png",
    "textures/block/copper_block.png",
    "textures/block/amethyst_block.png",
    "textures/block/quartz_block_top.png",
    "textures/block/obsidian.png",
    "textures/block/glowstone.png",
    "textures/block/end_stone.png",
    "textures/block/grass_block_top.png",
]


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _source_dir() -> Path:
    if _is_frozen():
        return Path(sys.executable).parent.resolve()
    here = Path(__file__).parent.resolve()
    cand = here / "dist" / "Exelent Launcher"
    if (cand / EXE_NAME).exists():
        return cand
    return here


HERE     = _source_dir()
DIST_DIR = HERE
SRC_DIR  = HERE


# ═══════════════════════════════════════════════════════════════
#  Хелперы
# ═══════════════════════════════════════════════════════════════

def get_font(size: int = 10, bold: bool = False) -> QFont:
    f = QFont(CUSTOM_FONT, size)
    if bold:
        f.setWeight(QFont.Weight.Bold)
    return f


def desktop_path() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)
            return Path(buf.value)
        except Exception:
            return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    return Path.home() / "Desktop"


def save_installed_info(install_dir: Path) -> None:
    """Записывает путь install_dir в %USERPROFILE%/exelent/installed_info.txt.
    На Linux/Mac: ~/.exelent/installed_info.txt.

    main.py при следующем запуске прочитает этот файл и сразу запустит
    лаунчер из install_dir, не показывая инсталлер повторно.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get(
            "USERPROFILE", os.path.expanduser("~"))) / "exelent"
    else:
        base = Path(os.path.expanduser("~")) / ".exelent"
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / "installed_info.txt").write_text(
            str(Path(install_dir).resolve()), encoding="utf-8")
    except Exception:
        pass


def create_shortcut_windows(exe_path: Path, install_dir: Path,
                            icon_path: Path | None = None) -> str:
    desk = desktop_path()
    desk.mkdir(parents=True, exist_ok=True)
    link = desk / "Exelent Launcher.lnk"

    def esc(s) -> str:
        return str(s).replace("'", "''")

    ps_lines = [
        "$ws = New-Object -ComObject WScript.Shell",
        f"$s = $ws.CreateShortcut('{esc(link)}')",
        f"$s.TargetPath = '{esc(exe_path)}'",
        f"$s.WorkingDirectory = '{esc(install_dir)}'",
        "$s.Description = 'Exelent Launcher'",
        "$s.WindowStyle = 1",
    ]
    if icon_path and icon_path.exists():
        ps_lines.append(f"$s.IconLocation = '{esc(icon_path)}'")
    ps_lines.append("$s.Save()")

    ps_cmd = "; ".join(ps_lines)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True, text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    if result.returncode == 0 and link.exists():
        return f"Ярлык создан:\n{link}"
    return f"Ярлык не создан: {(result.stderr or '').strip()[:160]}"


def create_shortcut_linux(exe_path: Path, icon_path: Path | None = None) -> str:
    desk = desktop_path()
    desk.mkdir(parents=True, exist_ok=True)
    entry = desk / "Exelent Launcher.desktop"
    icon_line = f"Icon={icon_path}" if icon_path and icon_path.exists() else ""
    entry.write_text(
        f"[Desktop Entry]\nType=Application\nName=Exelent Launcher\n"
        f"Exec={exe_path}\n{icon_line}\nTerminal=false\nCategories=Game;\n",
        encoding="utf-8")
    try:
        entry.chmod(0o755)
    except Exception:
        pass
    return f"Ярлык создан:\n{entry}"


# ═══════════════════════════════════════════════════════════════
#  Поток установки
# ═══════════════════════════════════════════════════════════════

class InstallThread(QThread):
    progress = pyqtSignal(int, str)
    success  = pyqtSignal(str, str)   # (install_dir, shortcut_msg)
    error    = pyqtSignal(str)

    SKIP_TOP = {"config.json", ".ExelLauncher", "logs", "__pycache__"}

    def __init__(self, src_dir: Path, install_dir: Path, download_assets: bool):
        super().__init__()
        self.src_dir         = Path(src_dir)
        self.install_dir     = Path(install_dir)
        self.download_assets = bool(download_assets)

    # ── Скачивание ZIP с прогрессом ──
    def _download_zip_to_memory(self, url: str,
                                start_pct: int, end_pct: int) -> bytes | None:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ExelentLauncher/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                total = 0
                try:
                    total = int(r.headers.get("Content-Length") or 0)
                except Exception:
                    total = 0
                chunks: list[bytes] = []
                done = 0
                span = max(1, end_pct - start_pct)
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    done += len(chunk)
                    if total > 0:
                        pct = start_pct + int(done / total * span)
                        mb = done / 1024 / 1024
                        mb_total = total / 1024 / 1024
                        self.progress.emit(
                            pct,
                            f"Скачивание ассетов: {mb:.1f} / {mb_total:.1f} MB")
                    else:
                        # неизвестный размер — не двигаем прогресс
                        self.progress.emit(
                            start_pct,
                            f"Скачивание ассетов: {done/1024/1024:.1f} MB")
                return b"".join(chunks)
        except Exception as ex:
            self.progress.emit(start_pct,
                               f"ZIP с GitHub недоступен: {ex}")
            return None

    # ── Распаковка ZIP в assets/mc/ ──
    def _extract_zip(self, data: bytes, dst_root: Path,
                     start_pct: int, end_pct: int) -> int:
        """
        Возвращает число извлечённых файлов.
        Внутри ZIP может быть либо плоский 'textures/...' либо обёртка
        'mc-assets-1.21.4/textures/...' — обрабатываем оба варианта.
        """
        assets_dir = dst_root / "assets" / "mc"
        assets_dir.mkdir(parents=True, exist_ok=True)

        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except Exception as ex:
            self.progress.emit(start_pct, f"Битый ZIP: {ex}")
            return 0

        names = zf.namelist()
        if not names:
            return 0

        # Определяем «корень» внутри ZIP
        # Если все пути начинаются с одной папки (например mc-assets-1.21.4/) — срезаем её.
        prefix = ""
        first = names[0].split("/")[0] + "/"
        if all(n.startswith(first) for n in names if n.strip()):
            prefix = first
        # Дополнительно: если в zip всё лежит в .../textures/... то prefix будет правильным

        count = 0
        total = sum(1 for n in names if not n.endswith("/"))
        span  = max(1, end_pct - start_pct)
        i = 0

        for n in names:
            if n.endswith("/"):
                continue
            rel = n[len(prefix):] if prefix and n.startswith(prefix) else n
            if not rel:
                continue
            target = assets_dir / rel
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(n) as src, open(target, "wb") as f:
                    shutil.copyfileobj(src, f)
                count += 1
            except Exception:
                pass
            i += 1
            if total > 0:
                pct = start_pct + int(i / total * span)
                self.progress.emit(
                    pct, f"Распаковка ассетов: {i}/{total}")

        try:
            zf.close()
        except Exception:
            pass
        return count

    # ── Фоллбек: поштучная скачка ──
    def _download_files_one_by_one(self, dst_root: Path,
                                   start_pct: int, end_pct: int) -> int:
        assets_dir = dst_root / "assets" / "mc"
        assets_dir.mkdir(parents=True, exist_ok=True)
        ok_cnt = 0
        total = max(1, len(ASSET_FILES_FALLBACK))
        span  = max(1, end_pct - start_pct)
        for i, rel in enumerate(ASSET_FILES_FALLBACK):
            target = assets_dir / rel
            if target.exists() and target.stat().st_size > 100:
                ok_cnt += 1
                pct = start_pct + int((i + 1) / total * span)
                self.progress.emit(
                    pct, f"Ассеты ({ok_cnt}/{total}): кэш")
                continue
            url = f"{MCASSET_BASE}/{rel}"
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "ExelentLauncher/1.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    data = r.read()
                if len(data) < 32:
                    raise RuntimeError("empty")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                ok_cnt += 1
            except Exception:
                pass
            pct = start_pct + int((i + 1) / total * span)
            self.progress.emit(
                pct, f"Ассеты ({ok_cnt}/{total}): {Path(rel).name}")
        return ok_cnt

    def _install_assets(self, dst_root: Path,
                        start_pct: int, end_pct: int) -> None:
        """
        Основная функция установки ассетов.
          1) Качаем ZIP с GitHub (50..80 от диапазона)
          2) Распаковываем (80..100 от диапазона)
          3) Если ZIP не вышел — фоллбек на поштучную скачку
        """
        # Делим диапазон: 60% на скачивание ZIP, 40% на распаковку
        span = end_pct - start_pct
        zip_end    = start_pct + int(span * 0.6)
        unpack_end = end_pct

        ok_count   = 0
        used_zip   = False

        # 1) ZIP
        self.progress.emit(start_pct, "Скачивание ассетов (ZIP)…")
        data = self._download_zip_to_memory(ASSETS_ZIP_URL, start_pct, zip_end)
        if data and len(data) > 1024:
            extracted = self._extract_zip(data, dst_root, zip_end, unpack_end)
            if extracted > 0:
                ok_count = extracted
                used_zip = True

        # 2) Fallback если ZIP не получился
        if not used_zip:
            self.progress.emit(zip_end,
                               "Переключаюсь на поштучную скачку с mcasset.cloud…")
            ok_count = self._download_files_one_by_one(
                dst_root, zip_end, unpack_end)

        # Метаданные
        try:
            assets_dir = dst_root / "assets" / "mc"
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / "_meta.json").write_text(
                json.dumps({
                    "version":   MCASSET_VERSION,
                    "source":    "github-zip" if used_zip else "mcasset.cloud",
                    "zip_url":   ASSETS_ZIP_URL,
                    "base_url":  MCASSET_BASE,
                    "files_ok":  int(ok_count),
                }, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def run(self):
        try:
            src = self.src_dir
            dst = self.install_dir
            exe_src = src / EXE_NAME
            exe_dst = dst / EXE_NAME

            self.progress.emit(2, "Проверка файлов установки…")
            if not exe_src.exists():
                self.error.emit(
                    f"Не найден исполняемый файл рядом с установщиком:\n"
                    f"{exe_src}\n\n"
                    f"Запустите программу из папки сборки "
                    f"(где лежит {EXE_NAME} и _internal/).")
                return

            try:
                if dst.resolve() == src.resolve():
                    self.error.emit(
                        "Нельзя устанавливать в ту же папку, "
                        "из которой запущен установщик.")
                    return
            except Exception:
                pass

            preserved_config: bytes | None = None
            old_cfg = dst / "config.json"
            if old_cfg.exists():
                try:
                    preserved_config = old_cfg.read_bytes()
                except Exception:
                    preserved_config = None

            self.progress.emit(5, "Очистка старой версии…")
            if dst.exists():
                for child in dst.iterdir():
                    try:
                        if child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                        else:
                            child.unlink(missing_ok=True)
                    except Exception:
                        pass
            else:
                dst.mkdir(parents=True, exist_ok=True)

            self.progress.emit(8, "Сканирование файлов…")
            all_files: list[Path] = []
            for f in src.rglob("*"):
                if not f.is_file():
                    continue
                rel = f.relative_to(src)
                top = rel.parts[0] if rel.parts else ""
                if top in self.SKIP_TOP:
                    continue
                if f.suffix.lower() == ".pyc":
                    continue
                all_files.append(f)

            if not all_files:
                self.error.emit("Нет файлов для копирования.")
                return

            # Копируем (10..50%)
            total = len(all_files)
            for i, f in enumerate(all_files):
                rel    = f.relative_to(src)
                target = dst / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(f, target)
                except PermissionError:
                    tmp = target.with_suffix(target.suffix + ".new")
                    shutil.copy2(f, tmp)
                    try:
                        target.unlink(missing_ok=True)
                    except Exception:
                        pass
                    try:
                        tmp.rename(target)
                    except Exception:
                        pass
                pct = 10 + int((i + 1) / total * 40)
                self.progress.emit(pct, f"Копирование: {rel.as_posix()}")

            # Ассеты (50..90%)
            if self.download_assets:
                self._install_assets(dst, 50, 90)

            # Config (ключевое: его наличие → лаунчер вместо установщика)
            self.progress.emit(92, "Создание конфигурации…")
            cfg_path = dst / "config.json"
            if preserved_config:
                cfg_path.write_bytes(preserved_config)
            else:
                default_cfg = {
                    "username":         "Player",
                    "mc_dir":           str(dst / ".ExelLauncher"),
                    "last_version":     "1.21.11",
                    "ram_mb":           2048,
                    "show_snapshots":   False,
                    "theme":            "emerald",
                    "item":             "emerald",
                    "ui_style":         "classic",
                    "progress_style":   "bar",
                    "first_run_done":   True,
                    "installed_at":     str(dst),
                    "assets_root":      str(dst / "assets" / "mc"),
                    # КЛЮЧЕВОЕ: версия структуры конфига и лаунчера.
                    # При обновлении лаунчер увидит config_version < CONFIG_VERSION
                    # и применит миграции, не теряя пользовательские настройки.
                    "config_version":   2,
                    "launcher_version": "1.2",
                }
                cfg_path.write_text(
                    json.dumps(default_cfg, indent=2, ensure_ascii=False),
                    encoding="utf-8")

            try:
                (dst / ".ExelLauncher").mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            # Ярлык
            self.progress.emit(95, "Создание ярлыка…")
            icon_path: Path | None = None
            for sub in ("_internal/assets/items", "assets/items"):
                for ico in ("emerald.ico", "emerald.png", "diamond.ico", "diamond.png"):
                    c = dst / sub / ico
                    if c.exists():
                        icon_path = c
                        break
                if icon_path:
                    break

            try:
                if sys.platform == "win32":
                    shortcut_msg = create_shortcut_windows(exe_dst, dst, icon_path)
                else:
                    shortcut_msg = create_shortcut_linux(exe_dst, icon_path)
            except Exception as ex:
                shortcut_msg = f"Ярлык не создан: {ex}"

            self.progress.emit(100, "Готово!")
            self.success.emit(str(dst), shortcut_msg)

        except Exception as ex:
            self.error.emit(f"{type(ex).__name__}: {ex}")


# ═══════════════════════════════════════════════════════════════
#  Кнопки
# ═══════════════════════════════════════════════════════════════

class GradientButton(QPushButton):
    def __init__(self, text: str, theme: dict,
                 icon_name: str | None = None, parent=None):
        super().__init__(text, parent)
        t = theme
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(44)
        self.setFont(get_font(11, True))
        if icon_name:
            self.setIcon(svg_icon(icon_name, 18, "#061006"))
            self.setIconSize(QSize(18, 18))
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {t['primary']},
                    stop:.45 {t['accent']},
                    stop:1 {t['accent_light']});
                color: #061006;
                border: none;
                border-radius: 22px;
                padding: 0 28px;
                font: 700 11pt '{CUSTOM_FONT}';
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_light']});
            }}
            QPushButton:pressed {{
                background: {t['primary_dark']};
                color: {t['accent']};
            }}
            QPushButton:disabled {{
                background: #2a2a2a;
                color: #666;
            }}
        """)


class OutlineButton(QPushButton):
    def __init__(self, text: str, theme: dict,
                 icon_name: str | None = None, parent=None):
        super().__init__(text, parent)
        t = theme
        r, g, b = t["glow_rgb"]
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(38)
        self.setFont(get_font(10))
        if icon_name:
            self.setIcon(svg_icon(icon_name, 16, t["accent"]))
            self.setIconSize(QSize(16, 16))
        self.setStyleSheet(f"""
            QPushButton {{
                background: {t['bg_panel2']};
                color: {t['accent']};
                border: 1.5px solid {t['primary_dark']};
                border-radius: 19px;
                padding: 0 18px;
                font: 600 10pt '{CUSTOM_FONT}';
            }}
            QPushButton:hover {{
                background: rgba({r},{g},{b},0.14);
                border-color: {t['accent']};
                color: {t['accent_light']};
            }}
            QPushButton:pressed {{
                background: rgba({r},{g},{b},0.26);
            }}
        """)


def _themed_checkbox_ss(theme: dict) -> str:
    t = theme
    return f"""
        QCheckBox {{
            color: {t['text']};
            background: transparent;
            spacing: 8px;
            font: 10pt '{CUSTOM_FONT}';
        }}
        QCheckBox::indicator {{
            width: 18px; height: 18px;
            border: 2px solid {t['primary_dark']};
            border-radius: 4px;
            background: {t['bg_panel2']};
        }}
        QCheckBox::indicator:checked {{
            background: {t['accent']};
            border-color: {t['accent']};
        }}
    """


# ═══════════════════════════════════════════════════════════════
#  Installer Window
# ═══════════════════════════════════════════════════════════════

class Installer(QWidget):
    BORDER = 6
    RADIUS = 18

    def __init__(self):
        super().__init__()
        self.theme       = themes_mod.get_theme("emerald")
        self.install_dir = Path.home() / "ExelentLauncher"
        self._drag_pos   = None
        self._thread: InstallThread | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Exelent Launcher — Установка")
        self.setFixedSize(640, 540)

        ico = themes_mod.get_item_path("emerald")
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        self._build()

        # Overlay рамки — поверх всего
        self._overlay = BorderOverlay(self.theme, self.BORDER, self.RADIUS, self)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()

        self._center()

    def _center(self):
        try:
            geo = QApplication.primaryScreen().geometry()
            self.move((geo.width() - self.width()) // 2,
                      (geo.height() - self.height()) // 2)
        except Exception:
            pass

    def paintEvent(self, _e):
        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        B   = self.BORDER
        rect = QRectF(self.rect().adjusted(B, B, -B, -B))
        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS, self.RADIUS)

        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(self.theme["bg_panel"]))
        grad.setColorAt(1, QColor(self.theme["bg_dark"]))
        p.fillPath(path, QBrush(grad))

        r, g, b = self.theme["glow_rgb"]
        p.fillPath(path, QColor(r, g, b, 18))

        p.setPen(QPen(QColor(0, 0, 0, 55), 1.0))
        ip = QPainterPath()
        ip.addRoundedRect(rect.adjusted(1, 1, -1, -1),
                          self.RADIUS - 1, self.RADIUS - 1)
        p.drawPath(ip)
        p.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_overlay"):
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (e.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # ── UI ──
    def _build(self):
        t       = self.theme
        r, g, b = t["glow_rgb"]

        root = QVBoxLayout(self)
        # Ключевое: контент не залезает на рамку
        root.setContentsMargins(self.BORDER, self.BORDER,
                                self.BORDER, self.BORDER)
        root.setSpacing(0)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 16, 28, 24)
        lay.setSpacing(14)

        # ── Заголовок ──
        hrow = QHBoxLayout()
        hrow.setSpacing(12)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(svg_pixmap("rocket", 34, t["accent"]))
        ico_lbl.setFixedSize(40, 40)
        ico_lbl.setStyleSheet("background:transparent;")
        hrow.addWidget(ico_lbl)

        tcol = QVBoxLayout()
        tcol.setSpacing(1)
        t1 = QLabel("Exelent Launcher")
        t1.setFont(get_font(20, True))
        t1.setStyleSheet(
            f"color:{t['accent']}; background:transparent; letter-spacing:1px;")
        tcol.addWidget(t1)
        t2 = QLabel("Установщик")
        t2.setFont(get_font(10))
        t2.setStyleSheet(f"color:{t['text_dim']}; background:transparent;")
        tcol.addWidget(t2)
        hrow.addLayout(tcol)
        hrow.addStretch()

        close_btn = QPushButton()
        close_btn.setIcon(svg_icon("close", 14, t["text_dim"]))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent; border:none; border-radius:7px;}"
            "QPushButton:hover{background:rgba(180,30,30,200);}"
            "QPushButton:pressed{background:rgba(220,50,50,230);}")
        hrow.addWidget(close_btn)
        lay.addLayout(hrow)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 transparent,stop:0.3 rgba({r},{g},{b},100),"
            f"stop:0.7 rgba({r},{g},{b},100),stop:1 transparent);")
        lay.addWidget(sep)

        # ── Статус источника ──
        src_ok = (SRC_DIR / EXE_NAME).exists()
        brow = QHBoxLayout()
        brow.setSpacing(10)
        bico = QLabel()
        bico.setPixmap(svg_pixmap(
            "check" if src_ok else "close", 18,
            t["accent"] if src_ok else "#ff5555"))
        bico.setFixedSize(24, 24)
        bico.setStyleSheet("background:transparent;")
        brow.addWidget(bico)

        if src_ok:
            btxt_str = f"Готов к установке.\nИсточник: {SRC_DIR}"
        else:
            btxt_str = (
                "Файлы установки не найдены!\n"
                f"Ожидается: {SRC_DIR / EXE_NAME}\n\n"
                f"Запустите программу из папки сборки.")
        btxt = QLabel(btxt_str)
        btxt.setWordWrap(True)
        btxt.setFont(get_font(9))
        btxt.setStyleSheet(
            f"color:{t['accent'] if src_ok else '#ff7777'};"
            f"background:{t['bg_panel2']};"
            f"border:1px solid {t['primary_dark']};"
            f"border-radius:10px; padding:10px 14px;")
        brow.addWidget(btxt, 1)
        lay.addLayout(brow)

        # ── Выбор папки ──
        dir_hdr = QLabel("Папка установки:")
        dir_hdr.setFont(get_font(9, True))
        dir_hdr.setStyleSheet(
            f"color:{t['accent_light']}; background:transparent;")
        lay.addWidget(dir_hdr)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)

        self.path_lbl = QLabel(str(self.install_dir))
        self.path_lbl.setFont(get_font(9))
        self.path_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.path_lbl.setStyleSheet(
            f"color:{t['text']};"
            f"background:{t['bg_panel2']};"
            f"border:1px solid {t['primary_dark']};"
            f"border-radius:10px; padding:8px 12px;")
        dir_row.addWidget(self.path_lbl, 1)

        pick_btn = QPushButton()
        pick_btn.setIcon(svg_icon("folder", 18, t["accent"]))
        pick_btn.setIconSize(QSize(18, 18))
        pick_btn.setFixedSize(42, 38)
        pick_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        pick_btn.setToolTip("Выбрать папку")
        pick_btn.clicked.connect(self._pick_dir)
        pick_btn.setStyleSheet(
            f"QPushButton{{background:{t['bg_panel2']};"
            f"border:1px solid {t['primary_dark']}; border-radius:10px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{b},0.15);"
            f"border-color:{t['accent']};}}"
            f"QPushButton:pressed{{background:rgba({r},{g},{b},0.28);}}")
        dir_row.addWidget(pick_btn)
        lay.addLayout(dir_row)

        # Подсказка
        hint = QLabel(
            "В выбранной папке будет создана директория ExelentLauncher/\n"
            "Ярлык появится на рабочем столе и запустит лаунчер.")
        hint.setFont(get_font(8))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{t['text_dim']}; background:transparent;")
        lay.addWidget(hint)

        # ── Опция: скачать ассеты ──
        self.cb_assets = QCheckBox(
            f"Скачать ассеты Minecraft {MCASSET_VERSION} (для офлайн-UI лаунчера)")
        self.cb_assets.setChecked(True)
        self.cb_assets.setStyleSheet(_themed_checkbox_ss(t))
        lay.addWidget(self.cb_assets)

        # ── Прогресс ──
        self.progress = SnakeProgress(t)
        lay.addWidget(self.progress)

        self.status_lbl = QLabel("Готов к установке")
        self.status_lbl.setFont(get_font(9))
        self.status_lbl.setStyleSheet(
            f"color:{t['text_dim']}; background:transparent;")
        lay.addWidget(self.status_lbl)

        lay.addStretch()

        # ── Кнопки ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_install = GradientButton("  Установить", t, "download")
        self.btn_install.setEnabled(src_ok)
        self.btn_install.clicked.connect(self._start_install)

        btn_cancel = OutlineButton("Отмена", t, "close")
        btn_cancel.setFixedWidth(110)
        btn_cancel.clicked.connect(self.close)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self.btn_install, 1)
        lay.addLayout(btn_row)

        root.addWidget(inner)

    # ── Actions ──
    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Папка для установки",
            str(self.install_dir.parent))
        if d:
            base = Path(d)
            self.install_dir = (
                base / "ExelentLauncher"
                if base.name.lower() != "exelentlauncher"
                else base)
            self.path_lbl.setText(str(self.install_dir))

    def _start_install(self):
        try:
            if self.install_dir.resolve() == SRC_DIR.resolve():
                QMessageBox.warning(
                    self, "Установка",
                    "Нельзя устанавливать в ту же папку, откуда запущен "
                    "установщик.")
                return
        except Exception:
            pass

        self.btn_install.setEnabled(False)
        self.cb_assets.setEnabled(False)
        self.progress.setIndeterminate(True)

        self._thread = InstallThread(
            SRC_DIR, self.install_dir, self.cb_assets.isChecked())
        self._thread.progress.connect(self._on_progress)
        self._thread.success.connect(self._on_success)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, pct: int, msg: str):
        self.progress.setValue(pct)
        self.status_lbl.setText(msg)

    def _on_success(self, install_dir: str, shortcut_msg: str):
        self.progress.setValue(100)
        self.status_lbl.setText("Установка завершена")
        # Сохраняем путь установки — main.py больше не покажет инсталлер
        try:
            save_installed_info(Path(install_dir))
        except Exception:
            pass
        QMessageBox.information(
            self, "Готово",
            f"Exelent Launcher установлен в:\n{install_dir}\n\n"
            f"{shortcut_msg}\n\n"
            f"Сейчас запустим лаунчер. Для следующих запусков "
            f"используйте ярлык на рабочем столе.")
        QTimer.singleShot(400, lambda: self._launch_installed(Path(install_dir)))

    def _on_error(self, err: str):
        self.progress.setValue(0)
        self.btn_install.setEnabled(True)
        self.cb_assets.setEnabled(True)
        self.status_lbl.setText("Ошибка")
        QMessageBox.critical(self, "Ошибка установки", err)

    def _launch_installed(self, install_dir: Path):
        exe = install_dir / EXE_NAME
        if not exe.exists():
            QMessageBox.warning(
                self, "Запуск",
                f"EXE не найден:\n{exe}\nЗапустите вручную.")
            self.close()
            return
        try:
            kw: dict = {}
            if sys.platform == "win32":
                kw["creationflags"] = 0x00000008 | 0x00000200
            subprocess.Popen([str(exe)], cwd=str(install_dir),
                             close_fds=True, **kw)
        except Exception as ex:
            QMessageBox.warning(self, "Запуск", f"Не удалось запустить:\n{ex}")
        finally:
            QTimer.singleShot(200, QApplication.instance().quit)


# ═══════════════════════════════════════════════════════════════
#  Точка входа
# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(get_font(10))
    try:
        themes_mod.ensure_builtin_assets()
    except Exception:
        pass
    w = Installer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
