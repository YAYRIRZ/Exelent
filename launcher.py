from __future__ import annotations

import ctypes
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QRectF
from PyQt6.QtGui import (QPainter, QColor, QLinearGradient, QBrush, QPen, QPixmap,
                         QFont, QPainterPath, QIcon, QCursor, QFontDatabase,
                         QConicalGradient)
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QMessageBox, QDialog, QListWidget,
                             QListWidgetItem, QTabWidget, QSpinBox, QCheckBox,
                             QFileDialog, QComboBox, QFrame, QGridLayout, QColorDialog,
                             QInputDialog, QScrollArea, QSizePolicy, QStackedWidget,
                             QFormLayout)

import minecraft as mc
import themes as themes_mod
from icons import svg_icon, svg_pixmap
from widgets import SnakeProgress, BorderOverlay, ProgressBar, PROGRESS_STYLES
import profiles as profiles_mod


# ═══════════════════════════════════════════════════════════════
#  Пути / константы
# ═══════════════════════════════════════════════════════════════

def _app_dir() -> Path:
    """Папка, где лежит .exe (или этот скрипт)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


APP_DIR     = _app_dir()
CONFIG_FILE = APP_DIR / "config.json"
FONTS_DIR   = APP_DIR / "fonts"
BLOCKS_DIR  = APP_DIR / "assets" / "blocks"

APP_VERSION       = "1.2"
CONFIG_VERSION    = 2     # Версия структуры config.json (для миграций)
VERSION_CHECK_URL = ("https://raw.githubusercontent.com/"
                    "YAYRIRZ/SkyPluginsVersion/refs/heads/main/ExelentLauncher")
TELEGRAM_CONTACT  = "t.me/YAYRIRZ"

# Геометрия главного окна
WINDOW_BORDER = 6      # толщина обводки (border)
WINDOW_RADIUS = 18     # радиус скругления

DEFAULT_CONFIG = {
    "username":         "Player",
    "mc_dir":           str(APP_DIR / ".ExelLauncher"),
    "last_version":     "1.21.11",
    "ram_mb":           2048,
    "show_snapshots":   False,
    "theme":            "emerald",
    "item":             "emerald",
    "custom_item_url":  "",
    "custom_colors":    {},
    "java_path":        "",
    "show_news":        True,
    "panel_position":   "bottom",
    "window_width":     1000,
    "window_height":    640,
    "background_path":  "",
    "background_blur":  False,
    "first_run_done":   False,
    "sodium_offered_versions": [],
    "ask_sodium":       True,
    "last_profile":     "",
    "progress_style":   "bar",
    "ui_style":         "classic",   # "classic" | "lunar"
    "sidebar_width":    68,          # ширина sidebar в Lunar (px)
    "border_width":     6,           # ширина обводки окна (px)
    # Java overrides: {mc_version: java_path} — если есть, запускаем без вопросов
    "java_overrides":   {},
    "config_version":   CONFIG_VERSION,
    "launcher_version": APP_VERSION,
}

CUSTOM_FONT_FAMILY = "Segoe UI"

# Текстуры блоков для заголовков секций (с mcasset.cloud)
_MCASSET_VER = "1.21.4"
BLOCK_URLS = {
    "furnace":  f"https://assets.mcasset.cloud/{_MCASSET_VER}/assets/minecraft/textures/block/furnace_front_on.png",
    "crafting": f"https://assets.mcasset.cloud/{_MCASSET_VER}/assets/minecraft/textures/block/crafting_table_front.png",
    "diamond":  f"https://assets.mcasset.cloud/{_MCASSET_VER}/assets/minecraft/textures/block/diamond_block.png",
    "redstone": f"https://assets.mcasset.cloud/{_MCASSET_VER}/assets/minecraft/textures/block/redstone_ore.png",
}


# ═══════════════════════════════════════════════════════════════
#  Шрифт
# ═══════════════════════════════════════════════════════════════

def load_custom_font() -> str:
    global CUSTOM_FONT_FAMILY
    try:
        FONTS_DIR.mkdir(exist_ok=True)
    except Exception:
        pass
    for d in (FONTS_DIR, APP_DIR):
        for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
            try:
                for font_file in sorted(d.glob(ext)):
                    fid = QFontDatabase.addApplicationFont(str(font_file))
                    if fid >= 0:
                        fams = QFontDatabase.applicationFontFamilies(fid)
                        if fams:
                            CUSTOM_FONT_FAMILY = fams[0]
                            return CUSTOM_FONT_FAMILY
            except Exception:
                continue
    return CUSTOM_FONT_FAMILY


def F() -> str:
    return CUSTOM_FONT_FAMILY


def get_font(size: int = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(CUSTOM_FONT_FAMILY, size)
    f.setWeight(weight)
    return f


# ═══════════════════════════════════════════════════════════════
#  Конфиг
# ═══════════════════════════════════════════════════════════════

def load_config() -> dict:
    """
    Загружает config.json. Применяет миграции по полю "config_version".
    Если поле отсутствует → версия 1 (старая). Обновляем до CONFIG_VERSION.
    """
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception:
            pass

    # Чистка старых полей
    cfg.pop("servers", None)
    cfg.pop("dev_mode", None)
    if not isinstance(cfg.get("sodium_offered_versions"), list):
        cfg["sodium_offered_versions"] = []
    if not isinstance(cfg.get("java_overrides"), dict):
        cfg["java_overrides"] = {}

    # ── Миграции по версии конфига ──
    user_ver = int(cfg.get("config_version", 1))
    migrated = False

    # v1 → v2: добавлены ui_style, progress_style, java_overrides;
    #          last_version обновляется с 1.21.4 на 1.21.11
    if user_ver < 2:
        if cfg.get("last_version") in (None, "", "1.21.4"):
            cfg["last_version"] = DEFAULT_CONFIG["last_version"]
        cfg.setdefault("ui_style",       DEFAULT_CONFIG["ui_style"])
        cfg.setdefault("progress_style", DEFAULT_CONFIG["progress_style"])
        migrated = True

    # Будущие миграции: if user_ver < 3: ...

    cfg["config_version"] = CONFIG_VERSION
    cfg["launcher_version"] = APP_VERSION   # для информации

    if migrated:
        try:
            save_config(cfg)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def open_folder(path: Path) -> None:
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def set_windows_app_id() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Exelent.Launcher.v3")
        except Exception:
            pass


def has_internet(timeout: float = 3.0) -> bool:
    hosts = [("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in hosts:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            continue
    return False


# ═══════════════════════════════════════════════════════════════
#  Утилиты для работы с MC-текстурами
# ═══════════════════════════════════════════════════════════════

def _square_crop_top(pix: QPixmap) -> QPixmap:
    """
    Если PNG-текстура не квадратная (анимация furnace_front_on.png = 16x32),
    берём верхний квадрат (первый кадр).
    """
    if pix.isNull():
        return pix
    w, h = pix.width(), pix.height()
    if w == h or w <= 0 or h <= 0:
        return pix
    side = min(w, h)
    return pix.copy(0, 0, side, side)


def _scaled_pixel(pix: QPixmap, size: int) -> QPixmap:
    """Пиксельный апскейл (NearestNeighbor)."""
    return pix.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation)


# ═══════════════════════════════════════════════════════════════
#  Кэш картинок блоков (для заголовков секций)
# ═══════════════════════════════════════════════════════════════

class BlockDownloadThread(QThread):
    done = pyqtSignal()

    _ASSET_REL = {
        "furnace":  "textures/block/furnace_front_on.png",
        "crafting": "textures/block/crafting_table_front.png",
        "diamond":  "textures/block/diamond_block.png",
        "redstone": "textures/block/redstone_ore.png",
    }

    def run(self):
        try:
            BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        local_root = APP_DIR / "assets" / "mc"
        for key, rel in self._ASSET_REL.items():
            target = BLOCKS_DIR / f"{key}.png"
            if target.exists() and target.stat().st_size > 200:
                continue
            src = local_root / rel
            if src.exists():
                try:
                    target.write_bytes(src.read_bytes())
                    continue
                except Exception:
                    pass
            url = BLOCK_URLS.get(key, "")
            if not url:
                continue
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "ExelentLauncher/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = r.read()
                target.write_bytes(data)
            except Exception:
                continue
        self.done.emit()


def block_pixmap(key: str, size: int) -> QPixmap:
    """
    Пиксмап блока для заголовков секций.
    Берём из локального кэша assets/blocks/<key>.png, ИЛИ напрямую из
    скачанных MC-ассетов assets/mc/textures/block/...
    """
    path = BLOCKS_DIR / f"{key}.png"
    if path.exists():
        pix = QPixmap(str(path))
        if not pix.isNull():
            pix = _square_crop_top(pix)
            return pix.scaled(size, size,
                              Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.FastTransformation)
    # Пробуем взять из MC-ассетов напрямую
    mc_map = {
        "furnace":  "textures/block/furnace_front_on.png",
        "crafting": "textures/block/crafting_table_front.png",
        "diamond":  "textures/block/diamond_block.png",
        "redstone": "textures/block/redstone_ore.png",
    }
    rel = mc_map.get(key, "")
    if rel:
        pix = themes_mod.load_mc_pixmap(rel, size, pixel_art=True)
        if pix is not None and not pix.isNull():
            return pix
    # Финальный fallback — цветной квадратик через svg_pixmap
    fallback = {
        "furnace":  ("settings",  "#cc7733"),
        "crafting": ("category",  "#aa6633"),
        "diamond":  ("sparkles",  "#5cd6e0"),
        "redstone": ("palette",   "#ff3344"),
    }.get(key, ("info", "#888"))
    return svg_pixmap(fallback[0], size, fallback[1])


# ═══════════════════════════════════════════════════════════════
#  Проверка версии лаунчера
# ═══════════════════════════════════════════════════════════════

class VersionCheckThread(QThread):
    outdated   = pyqtSignal(str)
    up_to_date = pyqtSignal()

    def run(self):
        try:
            req = urllib.request.Request(
                VERSION_CHECK_URL,
                headers={"User-Agent": f"ExelentLauncher/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=8) as r:
                remote = r.read().decode().strip()
            if remote and remote != APP_VERSION:
                self.outdated.emit(remote)
            else:
                self.up_to_date.emit()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  CSS-хелперы
# ═══════════════════════════════════════════════════════════════

def _sb_ss(t: dict) -> str:
    return f"""
        QScrollBar:vertical {{
            background: {t['bg_panel2']}; width: 7px;
            border-radius: 3px; margin: 1px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['primary_dark']};
            border-radius: 3px; min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {t['accent']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {t['bg_panel2']}; height: 7px;
            border-radius: 3px; margin: 1px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t['primary_dark']};
            border-radius: 3px; min-width: 24px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {t['accent']}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    """


def _input_ss(t: dict) -> str:
    return f"""
        QLineEdit, QComboBox, QSpinBox {{
            background: {t['bg_panel2']};
            color: {t['text']};
            border: 1.5px solid {t['primary_dark']};
            border-radius: 10px;
            padding: 4px 10px;
            min-height: 28px;
            max-height: 36px;
            font: 10pt '{F()}';
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 2px solid {t['accent']};
        }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{
            background: {t['bg_panel2']};
            color: {t['text']};
            border: 1px solid {t['primary_dark']};
            border-radius: 8px;
            selection-background-color: {t['primary_dark']};
            selection-color: {t['accent_light']};
        }}
        QCheckBox {{
            color: {t['text']};
            background: transparent;
            spacing: 8px;
            font: 10pt '{F()}';
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
        QSpinBox::up-button, QSpinBox::down-button {{
            background: {t['primary_dark']};
            border-radius: 3px;
            width: 18px;
        }}
    """


def _list_ss(t: dict) -> str:
    r, g, b = t["glow_rgb"]
    return f"""
        QListWidget {{
            background: {t['bg_panel2']};
            color: {t['text']};
            border: 1.5px solid {t['primary_dark']};
            border-radius: 12px;
            outline: none;
            font: 10pt '{F()}';
        }}
        QListWidget::item {{
            padding: 7px 12px;
            border-radius: 7px;
            margin: 1px 4px;
        }}
        QListWidget::item:hover {{
            background: rgba({r},{g},{b},0.10);
        }}
        QListWidget::item:selected {{
            background: {t['primary_dark']};
            color: {t['accent_light']};
        }}
        {_sb_ss(t)}
    """


def _tab_ss(t: dict) -> str:
    return f"""
        QTabWidget::pane {{
            border: 1.5px solid {t['primary_dark']};
            border-radius: 10px;
            background: transparent;
            margin-top: -1px;
        }}
        QTabBar::tab {{
            padding: 7px 16px;
            color: {t['text_dim']};
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            font: 600 9pt '{F()}';
            margin-right: 2px;
        }}
        QTabBar::tab:hover  {{ color: {t['accent']}; }}
        QTabBar::tab:selected {{
            color: {t['accent']};
            border-bottom: 2px solid {t['accent']};
            background: rgba(0,0,0,0.15);
            border-radius: 6px 6px 0 0;
        }}
    """


def _rb_colors(gradient):
    cols = [QColor(255,0,0), QColor(255,165,0), QColor(255,255,0),
            QColor(0,255,0), QColor(0,150,255), QColor(100,0,255),
            QColor(255,0,200), QColor(255,0,0)]
    for i, c in enumerate(cols):
        gradient.setColorAt(i / (len(cols) - 1), c)


# ═══════════════════════════════════════════════════════════════
#  ThemedDialog
# ═══════════════════════════════════════════════════════════════

class ThemedDialog(QDialog):
    BORDER = 7
    RADIUS = 22
    PEN_W  = 3.5

    def __init__(self, theme: dict, title: str = "", parent=None,
                 width: int = 500, height: int = 400):
        super().__init__(parent)
        self.theme = theme
        self._title_text = title
        self._drag_pos = None
        self._rb_phase = 0.0

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(width, height)

        if theme.get("rainbow"):
            self._rb_timer = QTimer(self)
            self._rb_timer.timeout.connect(self._rb_tick)
            self._rb_timer.start(28)

        root = QVBoxLayout(self)
        root.setContentsMargins(self.BORDER, self.BORDER, self.BORDER, self.BORDER)
        root.setSpacing(0)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(20, 8, 20, 14)
        il.setSpacing(0)

        il.addWidget(self._make_titlebar())

        sep = QFrame()
        sep.setFixedHeight(1)
        r, g, b = theme["glow_rgb"]
        sep.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 transparent,stop:0.3 rgba({r},{g},{b},120),"
            f"stop:0.7 rgba({r},{g},{b},120),stop:1 transparent);"
            f"margin:4px 0 10px 0;")
        il.addWidget(sep)

        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self.content_layout = QVBoxLayout(self._content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        il.addWidget(self._content, 1)

        root.addWidget(inner)

    def _rb_tick(self):
        self._rb_phase = (self._rb_phase + 2.0) % 360.0
        self.update()

    def _make_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(38)
        bar.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        dot = QLabel()
        dot.setPixmap(svg_pixmap("sparkles", 16, self.theme["accent"]))
        dot.setFixedSize(20, 20)
        dot.setStyleSheet("background:transparent;")
        lay.addWidget(dot)

        lbl = QLabel(self._title_text)
        lbl.setStyleSheet(
            f"font:700 12pt '{F()}'; color:{self.theme['accent']};"
            f"letter-spacing:1px; background:transparent; border:none;")
        lay.addWidget(lbl)

        lay.addStretch()

        close = QPushButton()
        close.setIcon(svg_icon("close", 14, self.theme["text_dim"]))
        close.setIconSize(QSize(14, 14))
        close.setFixedSize(28, 28)
        close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close.clicked.connect(self.reject)
        close.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; border-radius:6px;}}"
            f"QPushButton:hover{{background:rgba(180,30,30,200);}}"
            f"QPushButton:pressed{{background:rgba(220,50,50,230);}}")
        lay.addWidget(close)
        return bar

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        B = self.BORDER
        rect = QRectF(self.rect().adjusted(B, B, -B, -B))
        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS, self.RADIUS)

        grad = QLinearGradient(0, 0, self.width() * 0.4, self.height())
        grad.setColorAt(0, QColor(self.theme["bg_panel"]))
        grad.setColorAt(0.6, QColor(self.theme["bg_dark"]))
        grad.setColorAt(1, QColor(self.theme["bg_dark"]).darker(115))
        p.fillPath(path, QBrush(grad))

        r, g, b = self.theme["glow_rgb"]
        gw = QLinearGradient(0, 0, self.width(), self.height())
        gw.setColorAt(0, QColor(r, g, b, 22))
        gw.setColorAt(0.5, QColor(r, g, b, 8))
        gw.setColorAt(1, QColor(r, g, b, 22))
        p.fillPath(path, QBrush(gw))

        p.setPen(QPen(QColor(0, 0, 0, 60), 1.0))
        ip = QPainterPath()
        ip.addRoundedRect(rect.adjusted(1, 1, -1, -1),
                          self.RADIUS - 1, self.RADIUS - 1)
        p.drawPath(ip)

        pen = self._make_border_pen()
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

    def _make_border_pen(self) -> QPen:
        if self.theme.get("rainbow"):
            cg = QConicalGradient(
                QRectF(self.rect().adjusted(self.BORDER, self.BORDER,
                                            -self.BORDER, -self.BORDER)).center(),
                self._rb_phase)
            _rb_colors(cg)
            return QPen(QBrush(cg), self.PEN_W)
        bg = QLinearGradient(0, 0, self.width(), self.height())
        bg.setColorAt(0.0, QColor(self.theme["primary"]))
        bg.setColorAt(0.3, QColor(self.theme["accent"]))
        bg.setColorAt(0.6, QColor(self.theme["accent_light"]))
        bg.setColorAt(1.0, QColor(self.theme["primary"]))
        return QPen(QBrush(bg), self.PEN_W)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def add_button_row(self, *buttons) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()
        for btn in buttons:
            row.addWidget(btn)
        self.content_layout.addLayout(row)
        return row

    def make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font:600 9pt '{F()}'; color:{self.theme['accent_light']};"
            f"background:transparent; border:none;")
        return lbl

    def section_hdr(self, text: str, block_key: str | None = None) -> QWidget:
        t = self.theme
        r, g, b = t["glow_rgb"]
        w = QFrame()
        # Жёстко фиксируем высоту чтобы иконка точно не обрезалась.
        # 40px = 24 иконка + 8 верх + 8 низ + запас.
        w.setFixedHeight(42)
        # ВАЖНО: padding убираем из CSS, иначе layout считает размеры неправильно.
        # Только background + border-left.
        w.setStyleSheet(
            f"QFrame{{background:rgba({r},{g},{b},0.10);"
            f"border-left:3px solid {t['accent']};"
            f"border-radius:5px;}}")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)
        if block_key:
            ico = QLabel()
            ico.setPixmap(block_pixmap(block_key, 24))
            ico.setFixedSize(28, 28)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setScaledContents(False)
            ico.setStyleSheet("background:transparent; border:none;")
            lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font:700 10pt '{F()}'; color:{t['accent']};"
            f"background:transparent; border:none;")
        lay.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch()
        return w


# ═══════════════════════════════════════════════════════════════
#  Кнопки
# ═══════════════════════════════════════════════════════════════

class MD3Button(QPushButton):
    def __init__(self, text: str, theme: dict, primary: bool = True,
                 icon_name: str | None = None, icon_size: int = 16, parent=None):
        super().__init__(text, parent)
        self._primary   = primary
        self._icon_name = icon_name
        self._icon_size = icon_size
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setFont(get_font(9, QFont.Weight.DemiBold))
        self.apply_theme(theme)

    def apply_theme(self, theme: dict):
        self.theme = theme
        if self._icon_name:
            ic = "#061006" if self._primary else theme["accent"]
            self.setIcon(svg_icon(self._icon_name, self._icon_size, ic))
            self.setIconSize(QSize(self._icon_size, self._icon_size))
        if self._primary:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {theme['primary']},
                        stop:.45 {theme['accent']},
                        stop:1 {theme['accent_light']});
                    color: #061006; border: none;
                    border-radius: 19px;
                    padding: 0 18px;
                    font: 700 9pt '{F()}';
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {theme['accent']}, stop:1 {theme['accent_light']});
                }}
                QPushButton:pressed {{
                    background: {theme['primary_dark']};
                    color: {theme['accent']};
                }}
                QPushButton:disabled {{ background:#2a2a2a; color:#666; }}
            """)
        else:
            r, g, b = theme["glow_rgb"]
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {theme['bg_panel2']};
                    color: {theme['accent']};
                    border: 1.5px solid {theme['primary_dark']};
                    border-radius: 19px;
                    padding: 0 16px;
                    font: 600 9pt '{F()}';
                }}
                QPushButton:hover {{
                    background: rgba({r},{g},{b},0.14);
                    border-color: {theme['accent']};
                    color: {theme['accent_light']};
                }}
                QPushButton:pressed {{
                    background: rgba({r},{g},{b},0.26);
                }}
            """)


class IconButton(QPushButton):
    def __init__(self, icon_name: str, size: int, color: str,
                 tooltip: str = "", hover_bg: str = "", parent=None):
        super().__init__(parent)
        self.setIcon(svg_icon(icon_name, size, color))
        self.setIconSize(QSize(size, size))
        self.setFixedSize(size + 14, size + 14)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if tooltip:
            self.setToolTip(tooltip)
        hbg = hover_bg or "rgba(255,255,255,0.08)"
        self.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; border-radius:{(size+14)//2}px;}}"
            f"QPushButton:hover{{background:{hbg};}}"
            f"QPushButton:pressed{{background:rgba(255,255,255,0.15);}}")


# ═══════════════════════════════════════════════════════════════
#  Фоновые потоки
# ═══════════════════════════════════════════════════════════════

class VersionsThread(QThread):
    loaded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, snapshots: bool):
        super().__init__()
        self.snapshots = snapshots

    def run(self):
        try:
            self.loaded.emit(mc.fetch_version_list(self.snapshots))
        except Exception as ex:
            self.failed.emit(str(ex))


class InstallThread(QThread):
    progress = pyqtSignal(int, str)
    ok       = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, version: str, mc_dir: Path, loader: str = "vanilla"):
        super().__init__()
        self.version = version
        self.mc_dir  = Path(mc_dir)
        self.loader  = loader

    def run(self):
        try:
            if self.loader == "fabric":
                vid = mc.install_fabric(
                    self.version, self.mc_dir,
                    lambda pct, s: self.progress.emit(pct, s))
                self.ok.emit(vid)
            else:
                mc.install_version(
                    self.version, self.mc_dir,
                    lambda pct, s: self.progress.emit(pct, s))
                self.ok.emit(self.version)
        except Exception as ex:
            self.failed.emit(str(ex))


class LaunchThread(QThread):
    ok     = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, version, username, mc_dir, ram, java):
        super().__init__()
        self.args = (version, username, Path(mc_dir), ram, java, False)

    def run(self):
        try:
            mc.launch_minecraft(*self.args)
            self.ok.emit()
        except Exception as ex:
            self.failed.emit(str(ex))


class ModrinthSearchThread(QThread):
    results = pyqtSignal(list)
    error   = pyqtSignal(str)

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs

    def run(self):
        try:
            res = mc.search_modrinth(**self.kwargs)
            self.results.emit(res or [])
        except Exception as ex:
            self.error.emit(str(ex))


class ModrinthDownloadThread(QThread):
    progress = pyqtSignal(int, str)
    ok       = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, project_id: str, mc_version: str,
                 target_dir: Path, loader: str = ""):
        super().__init__()
        self.project_id = project_id
        self.mc_version = mc_version
        self.target_dir = Path(target_dir)
        self.loader = loader

    def run(self):
        try:
            versions = mc.get_modrinth_project_versions(
                self.project_id, mc_version=self.mc_version, loader=self.loader)

            if not versions and self.loader:
                try:
                    versions = mc.get_modrinth_project_versions(
                        self.project_id, loader=self.loader)
                except TypeError:
                    all_v = mc.get_modrinth_project_versions(self.project_id) or []
                    versions = [v for v in all_v
                                if self.loader in (v.get("loaders") or [])]

            if versions and self.loader:
                strict = [v for v in versions
                          if self.loader in (v.get("loaders") or [])]
                if strict:
                    versions = strict

            if not versions:
                self.failed.emit(
                    f"Нет версий {self.project_id} для "
                    f"{self.loader or 'указанного лоадера'} "
                    f"{self.mc_version or ''}".strip())
                return

            ver_id = versions[0].get("id", "")
            if not ver_id:
                self.failed.emit("Не удалось получить ID версии")
                return
            result = mc.download_modrinth_file(
                self.project_id, ver_id, self.target_dir,
                on_progress=lambda pct, msg: self.progress.emit(pct, msg))
            if result:
                self.ok.emit(str(result))
            else:
                self.failed.emit("Не удалось скачать файл")
        except Exception as ex:
            self.failed.emit(str(ex))


# Глобальный пул "осиротевших" IconLoader-потоков.
# Когда карточка ProjectCard удаляется раньше чем поток успел завершить
# urlopen() — мы НЕ можем разрушить QThread (Qt ругается фаталкой).
# Поэтому "паркуем" поток здесь: держим reference, отсоединяем от родителя,
# и удаляем из пула когда finished. Тогда Qt спокойно его утилизирует.
_PENDING_LOADERS: list = []


def _park_loader(th):
    """Положить поток в пул и автоматически удалить когда завершится."""
    if th is None:
        return
    try:
        th.setParent(None)  # отвязываем от мёртвой карточки
    except Exception:
        pass
    if th in _PENDING_LOADERS:
        return
    _PENDING_LOADERS.append(th)

    def _cleanup():
        try:
            _PENDING_LOADERS.remove(th)
        except ValueError:
            pass

    try:
        th.finished.connect(_cleanup)
    except Exception:
        pass


class IconLoaderThread(QThread):
    """
    Загружает иконку проекта Modrinth в фоне.
    Если карточка умирает раньше — поток отправляется в _PENDING_LOADERS
    и тихо завершается сам, без эмита сигнала и без краша Qt.
    """
    done = pyqtSignal(object, object)

    def __init__(self, card_id, url: str, parent=None):
        super().__init__(parent)
        self.card_id = card_id
        self.url = url
        self._alive = True
        self.setObjectName("IconLoader")

    def cancel(self):
        """Помечает поток как ненужный — сигнал больше не эмитится."""
        self._alive = False

    def _safe_emit(self, pix):
        if not self._alive:
            return
        try:
            self.done.emit(self.card_id, pix)
        except Exception:
            pass

    def run(self):
        try:
            req = urllib.request.Request(
                self.url, headers={"User-Agent": "ExelentLauncher/3.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = r.read()
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                pix = pix.scaled(52, 52,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                self._safe_emit(pix)
                return
        except Exception:
            pass
        self._safe_emit(None)


# ═══════════════════════════════════════════════════════════════
#  VersionPickerDialog
# ═══════════════════════════════════════════════════════════════

class VersionPickerDialog(ThemedDialog):
    """
    Список версий + профилей.
    Каждый элемент имеет:
      UserRole       = id версии (для запуска)
      UserRole + 1   = тип ('profile' / 'version')
      UserRole + 2   = имя профиля (если это профиль)
    """

    ROLE_KIND = Qt.ItemDataRole.UserRole + 1
    ROLE_PROFILE_NAME = Qt.ItemDataRole.UserRole + 2

    def __init__(self, versions, installed, current, theme,
                 profiles_list: list = None, parent=None):
        super().__init__(theme, "Выбор версии", parent, width=480, height=600)
        self.selected = current
        self.selected_profile = None  # имя профиля если выбран профиль

        srch = QLineEdit()
        srch.setPlaceholderText("Поиск: 1.20, fabric, MyPack...")
        srch.setStyleSheet(_input_ss(theme))
        self.content_layout.addWidget(srch)

        self.lst = QListWidget()
        self.lst.setStyleSheet(_list_ss(theme))
        self.content_layout.addWidget(self.lst, 1)

        t = theme

        # ── 1. ПРОФИЛИ (сверху) ──
        profiles_list = profiles_list or []
        if profiles_list:
            hdr = QListWidgetItem("─── ПРОФИЛИ ───")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)  # некликабельный
            hdr.setForeground(QColor(t["accent"]))
            self.lst.addItem(hdr)

            for prof in profiles_list:
                name   = prof.get("name", "?")
                base   = prof.get("base", "?")
                loader = prof.get("loader", "vanilla")
                ver_id = prof.get("version_id") or base
                label  = f"  {name}   ({loader} · MC {base})"
                it = QListWidgetItem(label)
                it.setData(Qt.ItemDataRole.UserRole, ver_id)
                it.setData(self.ROLE_KIND, "profile")
                it.setData(self.ROLE_PROFILE_NAME, name)
                it.setForeground(QColor(t["accent_light"]))
                self.lst.addItem(it)

            sep = QListWidgetItem("─── ВЕРСИИ ───")
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            sep.setForeground(QColor(t["accent"]))
            self.lst.addItem(sep)

        # ── 2. ОБЫЧНЫЕ ВЕРСИИ ──
        for v in versions:
            vid = v.get("id", "")
            suffix = "  [установлена]" if vid in installed else ""
            typ = v.get("type", "release")
            it = QListWidgetItem(
                vid + (f" [{typ}]" if typ != "release" else "") + suffix)
            it.setData(Qt.ItemDataRole.UserRole, vid)
            it.setData(self.ROLE_KIND, "version")
            self.lst.addItem(it)
            if vid == current:
                self.lst.setCurrentItem(it)

        srch.textChanged.connect(self._filter)
        self.lst.itemDoubleClicked.connect(self._accept)

        cancel = MD3Button("Отмена", theme, False, "close")
        ok     = MD3Button("Выбрать", theme, True, "check")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        self.add_button_row(cancel, ok)

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            if not (it.flags() & Qt.ItemFlag.ItemIsSelectable):
                continue  # заголовки секций не фильтруем
            data = it.data(Qt.ItemDataRole.UserRole) or ""
            name = it.data(self.ROLE_PROFILE_NAME) or ""
            it.setHidden(text not in data.lower() and text not in name.lower())

    def _accept(self):
        it = self.lst.currentItem()
        if not it or not (it.flags() & Qt.ItemFlag.ItemIsSelectable):
            return
        self.selected = it.data(Qt.ItemDataRole.UserRole)
        if it.data(self.ROLE_KIND) == "profile":
            self.selected_profile = it.data(self.ROLE_PROFILE_NAME)
        self.accept()


# ═══════════════════════════════════════════════════════════════
#  LoaderPickDialog + CreateProfileDialog
# ═══════════════════════════════════════════════════════════════

def _fabric_supports(mc_ver: str) -> bool:
    try:
        parts = mc_ver.split(".")
        major = int(parts[0]); minor = int(parts[1]) if len(parts) > 1 else 0
        return major > 1 or (major == 1 and minor >= 14)
    except Exception:
        return True


class LoaderPickDialog(ThemedDialog):
    def __init__(self, theme: dict, version: str, parent=None):
        super().__init__(theme, f"Установка {version}", parent, width=460, height=320)
        self.choice = None
        t = theme
        fabric_ok = _fabric_supports(version)

        msg = QLabel(
            f"Выбери, какую версию установить для <b>{version}</b>:")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color:{t['text']}; font:11pt '{F()}'; background:transparent;")
        self.content_layout.addWidget(msg)
        self.content_layout.addSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(10)

        vbtn = MD3Button("Vanilla", t, not fabric_ok, "rocket", 18)
        vbtn.setMinimumHeight(50)
        vbtn.clicked.connect(lambda: self._pick("vanilla"))

        fbtn = MD3Button("Fabric + Sodium", t, fabric_ok, "sparkles", 18)
        fbtn.setMinimumHeight(50)
        fbtn.setEnabled(fabric_ok)
        if not fabric_ok:
            fbtn.setToolTip("Fabric поддерживает только MC 1.14 и новее")
        fbtn.clicked.connect(lambda: self._pick("fabric"))

        row.addWidget(vbtn, 1)
        row.addWidget(fbtn, 1)
        self.content_layout.addLayout(row)

        if fabric_ok:
            note_txt = ("Fabric — модлоадер. Sodium даст +FPS.\n"
                        "Vanilla — чистая версия без модов.")
        else:
            note_txt = (f"Fabric не поддерживает MC {version} (только 1.14+).\n"
                        f"Для старых версий нужна Java 8 — лаунчер её найдёт.")

        note = QLabel(note_txt)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{t['text_dim']}; font:9pt '{F()}'; background:transparent;")
        self.content_layout.addWidget(note)

        self.content_layout.addStretch()

        cancel = MD3Button("Отмена", t, False, "close", 14)
        cancel.clicked.connect(self.reject)
        self.add_button_row(cancel)

    def _pick(self, val: str):
        self.choice = val
        self.accept()


class CreateProfileDialog(ThemedDialog):
    def __init__(self, theme: dict, versions: list,
                 default_version: str = "", parent=None):
        super().__init__(theme, "Новый профиль", parent, width=520, height=440)
        self.result_data: dict | None = None
        self._versions = versions
        self._default_version = default_version
        self._build()

    def _build(self):
        t = self.theme
        iss = _input_ss(t)

        self.content_layout.addWidget(self.make_label("Имя профиля:"))
        self.in_name = QLineEdit("MyPack")
        self.in_name.setStyleSheet(iss)
        self.in_name.setMaxLength(48)
        self.content_layout.addWidget(self.in_name)

        self.content_layout.addSpacing(6)
        self.content_layout.addWidget(self.make_label("Ядро (loader):"))
        self.loader_cb = QComboBox()
        self.loader_cb.addItem("Fabric (для модов)", "fabric")
        self.loader_cb.addItem("Vanilla (без модов)", "vanilla")
        self.loader_cb.setStyleSheet(iss)
        self.content_layout.addWidget(self.loader_cb)

        self.content_layout.addSpacing(6)
        self.content_layout.addWidget(self.make_label("Версия Minecraft:"))
        self.ver_cb = QComboBox()
        self.ver_cb.setStyleSheet(iss)
        for v in self._versions:
            self.ver_cb.addItem(v, v)
        if self._default_version:
            idx = self.ver_cb.findData(self._default_version)
            if idx >= 0:
                self.ver_cb.setCurrentIndex(idx)
        self.content_layout.addWidget(self.ver_cb)

        self.content_layout.addSpacing(10)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            f"color:{t['text_dim']}; font:9pt '{F()}';"
            f"background:{t['bg_panel2']};"
            f"border:1px solid {t['primary_dark']};"
            f"border-radius:8px; padding:8px 12px;")
        self.content_layout.addWidget(self.hint)
        self.content_layout.addStretch()

        self.loader_cb.currentIndexChanged.connect(self._update_hint)
        self.ver_cb.currentIndexChanged.connect(self._update_hint)
        self._update_hint()

        cancel = MD3Button("Отмена", t, False, "close", 14)
        cancel.clicked.connect(self.reject)
        create = MD3Button("Создать и установить", t, True, "download", 14)
        create.clicked.connect(self._on_create)
        self.add_button_row(cancel, create)

    def _update_hint(self):
        loader = self.loader_cb.currentData()
        ver    = self.ver_cb.currentData() or ""
        if loader == "fabric":
            if not _fabric_supports(ver):
                self.hint.setText(
                    f"Fabric не поддерживает MC {ver} (только 1.14+).\n"
                    f"Переключись на Vanilla или выбери более новую версию.")
            else:
                self.hint.setText(
                    f"Будет установлен Fabric для MC {ver}.\n"
                    f"После установки сможешь добавлять моды через Кастомизацию.")
        else:
            self.hint.setText(
                f"Будет установлена Vanilla MC {ver}.\n"
                f"Моды в vanilla не работают — только текстуры и шейдеры.")

    def _on_create(self):
        name = profiles_mod.sanitize_name(self.in_name.text())
        if not name:
            QMessageBox.warning(self, "Имя", "Введи корректное имя профиля.")
            return
        loader = self.loader_cb.currentData()
        ver = self.ver_cb.currentData() or ""
        if not ver:
            QMessageBox.warning(self, "Версия", "Выбери версию Minecraft.")
            return
        if loader == "fabric" and not _fabric_supports(ver):
            QMessageBox.warning(
                self, "Fabric",
                f"Fabric не поддерживает MC {ver}.")
            return
        self.result_data = {"name": name, "loader": loader, "version": ver}
        self.accept()


# ═══════════════════════════════════════════════════════════════
#  ProjectCard
# ═══════════════════════════════════════════════════════════════

class ProjectCard(QFrame):
    download_requested = pyqtSignal(dict)

    def __init__(self, data: dict, theme: dict, mc_version: str = "", parent=None):
        super().__init__(parent)
        self.data = data
        self._icon_thread = None
        t = theme
        r, g, b = t["glow_rgb"]

        self.setFixedHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            ProjectCard {{
                background:{t['bg_panel2']};
                border:1px solid {t['primary_dark']};
                border-radius:13px;
            }}
            ProjectCard:hover {{
                border-color:{t['accent']};
                background:rgba({r},{g},{b},0.06);
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        self._ico = QLabel()
        self._ico.setFixedSize(52, 52)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setPixmap(svg_pixmap("mods", 28, t["accent"]))
        self._ico.setStyleSheet(
            f"background:{t['bg_panel']};"
            f"border:1px solid {t['primary_dark']}; border-radius:10px;")
        lay.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(3)
        info.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        tlbl = QLabel(data.get("title", "—"))
        tlbl.setStyleSheet(
            f"color:{t['accent']}; font:700 10pt '{F()}';"
            f"background:transparent; border:none;")
        title_row.addWidget(tlbl, 1)
        vlist = data.get("versions", [])
        if mc_version and vlist:
            ok_ico = "check" if mc_version in vlist else "info"
            ok_clr = t["accent"] if mc_version in vlist else "#ffaa00"
            compat = QLabel()
            compat.setPixmap(svg_pixmap(ok_ico, 14, ok_clr))
            compat.setFixedSize(18, 18)
            compat.setStyleSheet("background:transparent; border:none;")
            compat.setToolTip("Совместимо" if mc_version in vlist
                              else "Версия может не поддерживаться")
            title_row.addWidget(compat)
        info.addLayout(title_row)

        author = data.get("author", "N/A")
        dl = data.get("downloads", 0)
        fl = data.get("follows", 0)
        dl_s = (f"{dl/1_000_000:.1f}M" if dl >= 1_000_000
                else f"{dl/1000:.1f}K" if dl >= 1000 else str(dl))
        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        for ico_n, ico_c, txt in [
            ("user",     t["text_dim"],  author),
            ("download", t["text_dim"],  dl_s),
            ("heart",    t["text_dim"],  str(fl)),
        ]:
            lbl = QLabel()
            lbl.setPixmap(svg_pixmap(ico_n, 12, ico_c))
            lbl.setFixedSize(16, 16)
            lbl.setStyleSheet("background:transparent; border:none;")
            meta_row.addWidget(lbl)
            vlbl = QLabel(txt)
            vlbl.setStyleSheet(
                f"color:{t['text_dim']}; font:8pt '{F()}';"
                f"background:transparent; border:none;")
            meta_row.addWidget(vlbl)
        meta_row.addStretch()
        info.addLayout(meta_row)

        desc = (data.get("description") or "")[:95]
        if desc:
            dl2 = QLabel(desc)
            dl2.setWordWrap(True)
            dl2.setStyleSheet(
                f"color:{t['text']}; font:9pt '{F()}';"
                f"background:transparent; border:none;")
            info.addWidget(dl2)

        cats    = (data.get("display_categories") or data.get("categories") or [])[:3]
        loaders = (data.get("loaders") or [])[:2]
        tags    = cats + loaders
        if tags:
            tr = QHBoxLayout()
            tr.setSpacing(4)
            tr.setContentsMargins(0, 2, 0, 0)
            for tag in tags[:5]:
                tl = QLabel(tag)
                tl.setStyleSheet(f"""
                    color:{t['accent']};
                    background:rgba({r},{g},{b},0.10);
                    border:1px solid rgba({r},{g},{b},0.24);
                    border-radius:5px;
                    padding:0px 6px;
                    font:7pt '{F()}';
                """)
                tr.addWidget(tl)
            tr.addStretch()
            info.addLayout(tr)

        info.addStretch()
        lay.addLayout(info, 1)

        dl_btn = MD3Button("Скачать", t, True, "download", 15)
        dl_btn.setFixedWidth(88)
        dl_btn.clicked.connect(lambda: self.download_requested.emit(self.data))
        lay.addWidget(dl_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        icon_url = data.get("icon_url", "")
        if icon_url:
            self._icon_thread = IconLoaderThread(id(self), icon_url, parent=self)
            self._icon_thread.done.connect(self._on_icon)
            self._icon_thread.start()

    def _on_icon(self, _cid, pix):
        # Виджет мог уже умереть — проверяем
        try:
            if pix and not pix.isNull():
                self._ico.setPixmap(pix)
        except RuntimeError:
            # C++ object deleted
            return
        except Exception:
            pass
        self._icon_thread = None

    def stop_thread(self):
        """
        Безопасная остановка фоновой загрузки иконки.
        Если поток ещё в urlopen — паркуем его в глобальный пул, чтобы Qt
        не словил фаталку 'QThread destroyed while still running'.
        """
        t = self._icon_thread
        self._icon_thread = None
        if t is None:
            return
        try:
            t.cancel()
        except Exception:
            pass
        if t.isRunning():
            # Не разрушаем Python-объект потока — паркуем его
            _park_loader(t)
        # Если уже не running — обычный сборщик мусора уберёт

    def closeEvent(self, e):
        self.stop_thread()
        super().closeEvent(e)


# ═══════════════════════════════════════════════════════════════
#  ResultsPage
# ═══════════════════════════════════════════════════════════════

class ResultsPage(QWidget):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        t = theme

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background:transparent;
                border:1px solid {t['primary_dark']};
                border-radius:12px;
            }}
            {_sb_ss(t)}
        """)
        self._container = QWidget()
        self._container.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._container)
        lay.addWidget(self._scroll, 1)

        self._empty_lbl = QLabel("Нет результатов")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{t['text_dim']}; font:11pt '{F()}'; background:transparent;")
        self._empty_lbl.hide()
        lay.addWidget(self._empty_lbl)

    @property
    def grid(self) -> QGridLayout:
        return self._grid

    def clear(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                # Если это карточка — глушим её фоновый поток
                if isinstance(w, ProjectCard):
                    try:
                        w.stop_thread()
                    except Exception:
                        pass
                w.setParent(None)
                w.deleteLater()
        self._empty_lbl.hide()

    def show_empty(self, text: str = "Ничего не найдено"):
        self.clear()
        self._empty_lbl.setText(text)
        self._empty_lbl.show()

    def fill(self, results: list, mc_version: str, on_download, cols: int = 2):
        self.clear()
        if not results:
            self.show_empty()
            return
        for idx, data in enumerate(results):
            card = ProjectCard(data, self.theme, mc_version)
            card.download_requested.connect(on_download)
            self._grid.addWidget(card, idx // cols, idx % cols)
        rows = (len(results) + cols - 1) // cols
        self._grid.setRowStretch(rows, 1)


def _safe_categories(ptype: str) -> list:
    try:
        if ptype == "mod":
            return list(getattr(mc, "MOD_CATEGORIES", []))
        if ptype == "resourcepack":
            return list(getattr(mc, "RESOURCEPACK_CATEGORIES", []))
        if ptype == "shader":
            return list(getattr(mc, "SHADER_CATEGORIES", []))
    except Exception:
        pass
    return []


# ═══════════════════════════════════════════════════════════════
#  ModrinthBrowser
# ═══════════════════════════════════════════════════════════════

class ModrinthBrowser(QWidget):
    def __init__(self, mc_dir: Path, theme: dict, mod_type: str,
                 mc_version: str, online: bool,
                 target_dir: Path | None = None,
                 loader: str = "fabric", parent=None):
        super().__init__(parent)
        self.theme       = theme
        self._mc_dir     = Path(mc_dir)
        self._mod_type   = mod_type
        self._mc_version = mc_version or ""
        self._online     = online
        self._loader     = loader or "fabric"

        if mod_type == "resourcepacks":
            self._ptype = "resourcepack"
            self._target_dir = Path(target_dir) if target_dir else self._mc_dir / "resourcepacks"
        elif mod_type == "shaderpacks":
            self._ptype = "shader"
            self._target_dir = Path(target_dir) if target_dir else self._mc_dir / "shaderpacks"
        else:
            self._ptype = "mod"
            self._target_dir = Path(target_dir) if target_dir else self._mc_dir / "mods"

        try:
            self._target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self._search_thread = None
        self._dl_thread     = None
        self._cur_tab       = "popular"
        self._page          = 0
        self._page_sz       = 18

        self._build()
        if self._online:
            QTimer.singleShot(80, lambda: self._load_tab("popular"))

    def set_target_dir(self, new_dir: Path) -> None:
        self._target_dir = Path(new_dir)
        try:
            self._target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def set_loader(self, loader: str) -> None:
        self._loader = loader or "fabric"

    def set_mc_version(self, mc_version: str) -> None:
        self._mc_version = mc_version or ""

    def _build(self):
        t = self.theme
        r, g, b = t["glow_rgb"]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        if not self._online:
            ob = QLabel(
                "Нет интернета. Скачивание из Modrinth недоступно.\n"
                "Можно играть только в уже установленные версии.")
            ob.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ob.setWordWrap(True)
            ob.setStyleSheet(
                f"color:#ffaa55; font:600 10pt '{F()}';"
                f"background:rgba(255,170,85,0.10);"
                f"border:1px solid #ffaa55; border-radius:10px; padding:10px;")
            outer.addWidget(ob)
            return

        top = QFrame()
        top.setStyleSheet(
            f"QFrame{{background:rgba({r},{g},{b},0.05);"
            f"border:1px solid {t['primary_dark']}; border-radius:12px;}}")
        tl = QVBoxLayout(top)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(6)

        sr = QHBoxLayout()
        sr.setSpacing(8)

        self._search_in = QLineEdit()
        ph = {"mod": "Поиск модов...", "resourcepack": "Поиск текстурпаков...",
              "shader": "Поиск шейдеров..."}.get(self._ptype, "Поиск...")
        self._search_in.setPlaceholderText(ph)
        self._search_in.setStyleSheet(_input_ss(t))
        self._search_in.returnPressed.connect(self._do_search)
        sr.addWidget(self._search_in, 1)

        self._sort_cb = QComboBox()
        for lbl, val in [("По загрузкам", "downloads"), ("По лайкам", "follows"),
                         ("Новинки", "newest"), ("Обновлённые", "updated"),
                         ("Релевантность", "relevance")]:
            self._sort_cb.addItem(lbl, val)
        self._sort_cb.setStyleSheet(_input_ss(t))
        self._sort_cb.setFixedWidth(155)
        sr.addWidget(self._sort_cb)

        if self._mc_version:
            vlbl = QLabel(f"MC {self._mc_version}")
            vlbl.setStyleSheet(
                f"color:{t['text_dim']}; font:9pt '{F()}'; background:transparent;")
            sr.addWidget(vlbl)

        btn_find = MD3Button("Найти", t, True, "search", 15)
        btn_find.setFixedWidth(90)
        btn_find.clicked.connect(self._do_search)
        sr.addWidget(btn_find)
        tl.addLayout(sr)

        tr = QHBoxLayout()
        tr.setSpacing(4)
        self._tab_btns = {}
        tabs = [
            ("popular",    "trending",  "Популярные"),
            ("new",        "star",      "Новые"),
            ("updated",    "refresh",   "Обновлённые"),
            ("search",     "search",    "Поиск"),
            ("categories", "category",  "Категории"),
        ]
        for tid, ico, tlbl in tabs:
            btn = QPushButton()
            btn.setIcon(svg_icon(ico, 14, t["text_dim"]))
            btn.setIconSize(QSize(14, 14))
            btn.setText(f" {tlbl}")
            btn.setCheckable(True)
            btn.setChecked(tid == "popular")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _=False, i=tid: self._switch_tab(i))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{t['text_dim']};
                    border:none; border-radius:7px;
                    padding:2px 12px; font:600 9pt '{F()}';
                    text-align:left;
                }}
                QPushButton:checked {{
                    background:rgba({r},{g},{b},0.16);
                    color:{t['accent']};
                    border:1px solid {t['accent']};
                }}
                QPushButton:hover:!checked {{
                    background:rgba({r},{g},{b},0.08);
                    color:{t['text']};
                }}
            """)
            tr.addWidget(btn)
            self._tab_btns[tid] = btn
        tr.addStretch()
        tl.addLayout(tr)

        outer.addWidget(top)

        self._pages_stack = QStackedWidget()
        outer.addWidget(self._pages_stack, 1)

        self._pages = {}
        for tid in ("popular", "new", "updated", "search"):
            page = ResultsPage(t)
            self._pages[tid] = page
            self._pages_stack.addWidget(page)

        cat_page = self._make_cat_page()
        self._pages["categories"] = cat_page
        self._pages_stack.addWidget(cat_page)

        self._pages_stack.setCurrentWidget(self._pages["popular"])

        pg_row = QHBoxLayout()
        self._btn_prev = MD3Button("Назад", t, False, "back", 14)
        self._btn_prev.setFixedWidth(84)
        self._btn_prev.setEnabled(False)
        self._btn_prev.clicked.connect(self._prev_page)

        self._page_lbl = QLabel("1")
        self._page_lbl.setFixedWidth(32)
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_lbl.setStyleSheet(
            f"color:{t['accent']}; font:700 9pt '{F()}'; background:transparent;")

        self._btn_next = MD3Button("Вперёд", t, False, "arrow_right", 14)
        self._btn_next.setFixedWidth(90)
        self._btn_next.clicked.connect(self._next_page)

        self._status = QLabel("Загрузка...")
        self._status.setStyleSheet(
            f"color:{t['text_dim']}; font:9pt '{F()}'; background:transparent;")
        self._prog = SnakeProgress(t)
        self._prog.setFixedWidth(110)
        self._prog.hide()

        pg_row.addWidget(self._btn_prev)
        pg_row.addWidget(self._page_lbl)
        pg_row.addWidget(self._btn_next)
        pg_row.addSpacing(12)
        pg_row.addWidget(self._status)
        pg_row.addStretch()
        pg_row.addWidget(self._prog)
        outer.addLayout(pg_row)

    def _make_cat_page(self) -> QWidget:
        t = self.theme
        r, g, b = t["glow_rgb"]
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        cats = _safe_categories(self._ptype)

        if not cats:
            empty = QLabel("Категории недоступны для этого типа контента.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{t['text_dim']}; font:10pt '{F()}'; background:transparent;")
            lay.addWidget(empty)
            self._cat_hdr = QLabel("")
            self._cat_results = ResultsPage(t)
            lay.addWidget(self._cat_hdr)
            lay.addWidget(self._cat_results, 1)
            return page

        cw = QWidget()
        cw.setStyleSheet("background:transparent;")
        cg = QGridLayout(cw)
        cg.setSpacing(6)
        cg.setContentsMargins(0, 0, 0, 0)
        cols = 4

        for idx, item in enumerate(cats):
            try:
                cat_id, cat_name = item
            except Exception:
                cat_id = str(item); cat_name = str(item)
            btn = QPushButton(cat_name)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{t['bg_panel2']}; color:{t['text']};
                    border:1px solid {t['primary_dark']}; border-radius:9px;
                    padding:4px 10px; font:600 9pt '{F()}';
                }}
                QPushButton:hover {{
                    background:rgba({r},{g},{b},0.13);
                    border-color:{t['accent']}; color:{t['accent_light']};
                }}
            """)
            btn.clicked.connect(
                lambda _=False, c=cat_id, n=cat_name: self._search_cat(c, n))
            cg.addWidget(btn, idx // cols, idx % cols)
        lay.addWidget(cw)

        self._cat_hdr = QLabel("")
        self._cat_hdr.setStyleSheet(
            f"font:700 10pt '{F()}'; color:{t['accent']};"
            f"background:transparent; padding:2px 0;")
        lay.addWidget(self._cat_hdr)

        self._cat_results = ResultsPage(t)
        lay.addWidget(self._cat_results, 1)
        return page

    def _switch_tab(self, tid: str):
        self._cur_tab = tid
        self._page = 0
        for k, btn in self._tab_btns.items():
            btn.setChecked(k == tid)
            btn.setIcon(svg_icon(
                {"popular": "trending", "new": "star", "updated": "refresh",
                 "search":  "search",   "categories": "category"}[k],
                14,
                self.theme["accent"] if k == tid else self.theme["text_dim"]))
        self._pages_stack.setCurrentWidget(self._pages[tid])
        if tid in ("popular", "new", "updated"):
            rp = self._pages[tid]
            if rp.grid.count() == 0:
                self._load_tab(tid)

    def _load_tab(self, tid: str):
        idx_map = {"popular": "downloads", "new": "newest", "updated": "updated"}
        self._run_search(query="", index=idx_map[tid],
                         results_page=self._pages[tid])

    def _do_search(self):
        q = self._search_in.text().strip()
        self._switch_tab("search")
        self._run_search(query=q, index=self._sort_cb.currentData(),
                         results_page=self._pages["search"])

    def _search_cat(self, cat_id: str, cat_name: str):
        self._cat_hdr.setText(cat_name)
        self._run_search(query="", categories=[cat_id],
                         index="downloads", results_page=self._cat_results)

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._reload()

    def _next_page(self):
        self._page += 1
        self._reload()

    def _reload(self):
        tid = self._cur_tab
        if tid in ("popular", "new", "updated"):
            self._load_tab(tid)
        elif tid == "search":
            self._do_search()

    def _run_search(self, query: str = "", categories=None,
                    index: str = "downloads",
                    results_page=None):
        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.quit()
            self._search_thread.wait(300)

        self._status.setText("Поиск...")
        self._prog.setIndeterminate(True)
        self._prog.show()
        self._page_lbl.setText(str(self._page + 1))
        self._btn_prev.setEnabled(self._page > 0)

        game_ver = self._mc_version if self._ptype == "mod" else ""

        thread = ModrinthSearchThread(
            query=query,
            project_type=self._ptype,
            categories=categories,
            game_version=game_ver,
            index=index,
            limit=self._page_sz,
            offset=self._page * self._page_sz,
        )
        rp = results_page

        def on_results(res):
            self._prog.hide()
            self._btn_next.setEnabled(len(res) == self._page_sz)
            if not res:
                self._status.setText("Ничего не найдено")
                if rp:
                    rp.show_empty()
            else:
                self._status.setText(f"{len(res)} проектов")
                if rp:
                    rp.fill(res, self._mc_version, self._download)

        def on_err(err):
            self._prog.hide()
            self._status.setText(f"Ошибка: {err[:60]}")
            if rp:
                rp.show_empty(f"Ошибка: {err[:60]}")

        thread.results.connect(on_results)
        thread.error.connect(on_err)
        thread.start()
        self._search_thread = thread

    def _download(self, data: dict):
        pid   = data.get("project_id") or data.get("slug", "")
        title = data.get("title", "проект")
        if not pid:
            QMessageBox.warning(self, "Ошибка", "Нет ID проекта")
            return
        if self._dl_thread and self._dl_thread.isRunning():
            QMessageBox.information(self, "Загрузка", "Уже идёт загрузка...")
            return

        loaders = data.get("loaders") or []
        if self._ptype == "mod":
            loader = self._loader
        else:
            loader = ("fabric" if "fabric" in loaders
                      else "forge" if "forge" in loaders else "")

        self._status.setText(f"Скачивание: {title}...")
        self._prog.setValue(0)
        self._prog.show()

        self._dl_thread = ModrinthDownloadThread(
            pid, self._mc_version, self._target_dir, loader)
        self._dl_thread.progress.connect(
            lambda p, s: (self._prog.setValue(p), self._status.setText(s)))
        self._dl_thread.ok.connect(self._dl_ok)
        self._dl_thread.failed.connect(self._dl_fail)
        self._dl_thread.start()

    def _dl_ok(self, path: str):
        name = Path(path).name
        self._status.setText(f"Сохранено: {name}")
        self._prog.setValue(100)
        QTimer.singleShot(500, self._prog.hide)
        QMessageBox.information(self, "Готово", f"Сохранено:\n{name}")

    def _dl_fail(self, err: str):
        self._status.setText(f"Ошибка: {err[:60]}")
        self._prog.hide()
        QMessageBox.critical(self, "Ошибка", err)

    def shutdown(self):
        # 1. Гасим поиск/скачивание
        for th in (self._search_thread, self._dl_thread):
            if th and th.isRunning():
                th.quit()
                th.wait(400)
        # 2. Гасим все карточки во всех страницах (там сидят IconLoaderThread)
        try:
            for page in getattr(self, "_pages", {}).values():
                if hasattr(page, "clear"):
                    page.clear()
            if hasattr(self, "_cat_results"):
                self._cat_results.clear()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  LocalModsPage + NoModsPlaceholder
# ═══════════════════════════════════════════════════════════════

class LocalModsPage(QWidget):
    def __init__(self, mods_dir: Path, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.mods_dir = Path(mods_dir)
        try:
            self.mods_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.lst = QListWidget()
        self.lst.setStyleSheet(_list_ss(theme))
        lay.addWidget(self.lst, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        for lbl, ico, prim, cb in [
            ("Добавить .jar", "folder",      False, self._add_local),
            ("Открыть папку", "folder_open", False, lambda: open_folder(self.mods_dir)),
            ("Обновить",      "refresh",     False, self._refresh),
            ("Удалить",       "trash",       False, self._delete),
        ]:
            b = MD3Button(lbl, theme, prim, ico, 14)
            b.clicked.connect(cb)
            row.addWidget(b)
        lay.addLayout(row)

        self._refresh()

    def set_mods_dir(self, new_dir: Path) -> None:
        self.mods_dir = Path(new_dir)
        try:
            self.mods_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._refresh()

    def _refresh(self):
        self.lst.clear()
        if not self.mods_dir.exists():
            return
        for p in sorted(self.mods_dir.glob("*.jar")):
            try:
                kb = p.stat().st_size // 1024
            except Exception:
                kb = 0
            it = QListWidgetItem(f"{p.name}  ({kb} KB)")
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            self.lst.addItem(it)

    def _add_local(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите моды", "", "Minecraft mods (*.jar)")
        for f in files:
            try:
                shutil.copy2(f, self.mods_dir / Path(f).name)
            except Exception:
                pass
        self._refresh()

    def _delete(self):
        it = self.lst.currentItem()
        if not it:
            return
        path = Path(it.data(Qt.ItemDataRole.UserRole))
        if QMessageBox.question(
                self, "Удаление", f"Удалить {path.name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
            except Exception as ex:
                QMessageBox.warning(self, "Ошибка", str(ex))
            self._refresh()

    def shutdown(self):
        pass


class NoModsPlaceholder(QWidget):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()
        ico = QLabel()
        ico.setPixmap(svg_pixmap("lock", 48, theme["text_dim"]))
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        lay.addWidget(ico)
        t = QLabel("Моды доступны только для лоадеров (Fabric/Forge)")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setWordWrap(True)
        t.setStyleSheet(
            f"color:{theme['accent']}; font:700 12pt '{F()}'; "
            f"background:transparent;")
        lay.addWidget(t)
        h = QLabel("Создай профиль с лоадером Fabric и выбери его сверху.")
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.setWordWrap(True)
        h.setStyleSheet(
            f"color:{theme['text_dim']}; font:10pt '{F()}'; "
            f"background:transparent;")
        lay.addWidget(h)
        lay.addStretch()
        self.setStyleSheet("background:transparent;")

    def shutdown(self):
        pass


# ═══════════════════════════════════════════════════════════════
#  CustomizationDialog
# ═══════════════════════════════════════════════════════════════

class CustomizationDialog(ThemedDialog):
    def __init__(self, mc_dir: Path, theme: dict, default_profile: str,
                 online: bool, parent=None):
        super().__init__(theme, "Кастомизация", parent, width=1020, height=740)
        self._mc_dir = Path(mc_dir)
        self._online = online
        self._default_profile_name = default_profile
        self._profile = None
        self._pages = []
        self._build()

    def _build(self):
        t = self.theme

        sel_row = QFrame()
        r, g, b = t["glow_rgb"]
        sel_row.setStyleSheet(
            f"QFrame{{background:rgba({r},{g},{b},0.06);"
            f"border:1px solid {t['primary_dark']}; border-radius:12px;}}")
        sl = QHBoxLayout(sel_row)
        sl.setContentsMargins(12, 8, 12, 8)
        sl.setSpacing(10)

        ico = QLabel()
        ico.setPixmap(svg_pixmap("package", 18, t["accent"]))
        ico.setFixedSize(22, 22)
        ico.setStyleSheet("background:transparent;")
        sl.addWidget(ico)

        lbl = QLabel("Профиль:")
        lbl.setStyleSheet(
            f"color:{t['accent_light']}; font:700 10pt '{F()}'; "
            f"background:transparent;")
        sl.addWidget(lbl)

        self.prof_cb = QComboBox()
        self.prof_cb.setStyleSheet(_input_ss(t))
        self.prof_cb.setMinimumWidth(280)
        sl.addWidget(self.prof_cb, 1)

        self.prof_info = QLabel("")
        self.prof_info.setStyleSheet(
            f"color:{t['text_dim']}; font:9pt '{F()}'; "
            f"background:transparent;")
        sl.addWidget(self.prof_info)

        btn_new = MD3Button("Новый профиль", t, True, "plus", 14)
        btn_new.clicked.connect(self._new_profile)
        sl.addWidget(btn_new)

        self.content_layout.addWidget(sel_row)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(_tab_ss(t))
        self.content_layout.addWidget(self.tabs, 1)

        self.mods_page = None
        self.mods_tab_index = -1

        self.rp_page = ModrinthBrowser(
            self._mc_dir, t, "resourcepacks", "", self._online,
            target_dir=self._mc_dir / "resourcepacks", parent=self)
        self.tabs.addTab(self.rp_page, "Текстурпаки")
        self._pages.append(self.rp_page)

        self.sh_page = ModrinthBrowser(
            self._mc_dir, t, "shaderpacks", "", self._online,
            target_dir=self._mc_dir / "shaderpacks", parent=self)
        self.tabs.addTab(self.sh_page, "Шейдеры")
        self._pages.append(self.sh_page)

        self.local_page = LocalModsPage(
            self._mc_dir / "mods", t, self)
        self.tabs.addTab(self.local_page, "Установленные моды")

        self._refresh_mods_tab()

        close = MD3Button("Закрыть", t, False, "close", 14)
        close.clicked.connect(self.reject)
        self.add_button_row(close)

        self._reload_profiles()
        self.prof_cb.currentIndexChanged.connect(self._on_profile_changed)

    def _reload_profiles(self):
        self.prof_cb.blockSignals(True)
        self.prof_cb.clear()
        profs = profiles_mod.list_profiles(self._mc_dir)
        if not profs:
            self.prof_cb.addItem("— нет профилей — создай новый —", None)
        else:
            select_idx = 0
            for i, p in enumerate(profs):
                loader = p.get("loader", "vanilla")
                base   = p.get("base", "?")
                label = f"{p['name']}   [{loader} · {base}]"
                self.prof_cb.addItem(label, p)
                if p["name"] == self._default_profile_name:
                    select_idx = i
            self.prof_cb.setCurrentIndex(select_idx)
        self.prof_cb.blockSignals(False)
        self._on_profile_changed()

    def _on_profile_changed(self):
        prof = self.prof_cb.currentData()
        self._profile = prof
        if not prof:
            self.prof_info.setText("нет данных")
            self._refresh_mods_tab()
            self.rp_page.set_target_dir(self._mc_dir / "resourcepacks")
            self.rp_page.set_mc_version("")
            self.sh_page.set_target_dir(self._mc_dir / "shaderpacks")
            self.sh_page.set_mc_version("")
            self.local_page.set_mods_dir(self._mc_dir / "mods")
            return

        loader = prof.get("loader", "vanilla")
        base   = prof.get("base", "?")
        self.prof_info.setText(f"{loader} · MC {base}")

        name = prof["name"]
        mods_d = profiles_mod.mods_dir(self._mc_dir, name)
        rp_d   = profiles_mod.resourcepacks_dir(self._mc_dir, name)
        sh_d   = profiles_mod.shaderpacks_dir(self._mc_dir, name)

        self.rp_page.set_target_dir(rp_d)
        self.rp_page.set_mc_version(base)

        self.sh_page.set_target_dir(sh_d)
        self.sh_page.set_mc_version(base)

        self.local_page.set_mods_dir(mods_d)
        self._refresh_mods_tab()

    def _refresh_mods_tab(self):
        if self.mods_tab_index >= 0:
            try:
                w = self.tabs.widget(0)
                self.tabs.removeTab(0)
                if w in self._pages:
                    self._pages.remove(w)
                # ВАЖНО: сначала останавливаем все потоки внутри браузера
                if hasattr(w, "shutdown"):
                    try:
                        w.shutdown()
                    except Exception:
                        pass
                w.setParent(None)
                w.deleteLater()
            except Exception:
                pass
            self.mods_tab_index = -1
            self.mods_page = None

        prof = self._profile
        t = self.theme
        if prof and profiles_mod.supports_mods(prof):
            mods_d = profiles_mod.mods_dir(self._mc_dir, prof["name"])
            page = ModrinthBrowser(
                self._mc_dir, t, "mods", prof.get("base", ""),
                self._online, target_dir=mods_d,
                loader=prof.get("loader", "fabric"), parent=self)
            self._pages.insert(0, page)
            self.mods_page = page
            self.tabs.insertTab(0, page, "Моды")
        else:
            page = NoModsPlaceholder(t, self)
            self.mods_page = page
            self.tabs.insertTab(0, page, "Моды")
        self.mods_tab_index = 0
        self.tabs.setCurrentIndex(0)

    def _new_profile(self):
        win = self.parent()
        while win and not isinstance(win, LauncherWindow):
            win = win.parent()
        if win is None:
            QMessageBox.information(self, "Профили", "Не могу найти главное окно.")
            return
        created = win.create_profile_flow()
        if created:
            self._default_profile_name = created.get("name", "")
            self._reload_profiles()

    def closeEvent(self, e):
        # Останавливаем все ModrinthBrowser'ы и LocalModsPage
        for p in list(self._pages):
            try:
                if hasattr(p, "shutdown"):
                    p.shutdown()
            except Exception:
                pass
        # Дополнительно сами явно ссылающиеся
        for attr in ("rp_page", "sh_page", "local_page", "mods_page"):
            obj = getattr(self, attr, None)
            if obj is not None and hasattr(obj, "shutdown"):
                try:
                    obj.shutdown()
                except Exception:
                    pass
        super().closeEvent(e)


# ═══════════════════════════════════════════════════════════════
#  SodiumOfferDialog
# ═══════════════════════════════════════════════════════════════

class SodiumOfferDialog(ThemedDialog):
    def __init__(self, theme: dict, mc_version: str, mods_dir: Path,
                 is_fabric: bool, parent=None):
        super().__init__(theme, "Оптимизация", parent, width=480, height=340)
        self._mc_version = mc_version
        self._mods_dir   = Path(mods_dir)
        self._is_fabric  = is_fabric
        self._thread = None
        self._build()

    def _build(self):
        t = self.theme
        ico = QLabel()
        ico.setPixmap(svg_pixmap("sparkles", 48, t["accent"]))
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        self.content_layout.addWidget(ico)

        title = QLabel("Установить Sodium?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font:700 14pt '{F()}'; color:{t['accent']}; background:transparent;")
        self.content_layout.addWidget(title)

        if self._is_fabric:
            desc_text = (
                f"Sodium значительно увеличивает FPS.\n"
                f"Требуется Fabric · MC {self._mc_version}")
        else:
            desc_text = (
                f"Sodium работает только на Fabric.\n"
                f"Создай профиль с Fabric и установи Sodium через Кастомизацию.")
        desc = QLabel(desc_text)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color:{t['text_dim']}; font:10pt '{F()}'; background:transparent;")
        self.content_layout.addWidget(desc)

        self._prog = SnakeProgress(t)
        self._prog.hide()
        self.content_layout.addWidget(self._prog)

        self._st = QLabel("")
        self._st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._st.setStyleSheet(
            f"color:{t['text_dim']}; font:8pt '{F()}'; background:transparent;")
        self.content_layout.addWidget(self._st)

        skip = MD3Button("Пропустить", t, False, "close", 14)
        skip.clicked.connect(self.reject)

        if self._is_fabric:
            inst = MD3Button("Установить", t, True, "download", 15)
            inst.clicked.connect(self._install)
            self.add_button_row(skip, inst)
        else:
            self.add_button_row(skip)

    def _install(self):
        self._mods_dir.mkdir(parents=True, exist_ok=True)
        self._prog.show()
        self._prog.setIndeterminate(True)
        self._st.setText("Поиск на Modrinth...")
        self._thread = ModrinthDownloadThread(
            "sodium", self._mc_version, self._mods_dir, "fabric")
        self._thread.progress.connect(
            lambda p, s: (self._prog.setValue(p), self._st.setText(s)))
        self._thread.ok.connect(self._ok)
        self._thread.failed.connect(self._fail)
        self._thread.start()

    def _ok(self, path: str):
        self._prog.setValue(100)
        self._st.setText(f"Установлено: {Path(path).name}")
        QTimer.singleShot(1200, self.accept)

    def _fail(self, err: str):
        self._prog.hide()
        self._st.setText(f"Ошибка: {err[:50]}")


# ═══════════════════════════════════════════════════════════════
#  OutdatedDialog
# ═══════════════════════════════════════════════════════════════

class OutdatedDialog(ThemedDialog):
    def __init__(self, theme: dict, remote: str, parent=None):
        super().__init__(theme, "Обновление", parent, width=400, height=240)
        t = theme
        ico = QLabel()
        ico.setPixmap(svg_pixmap("info", 44, "#ffaa00"))
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        self.content_layout.addWidget(ico)

        msg = QLabel(
            f"Доступна версия <b>{remote}</b>.<br>"
            f"Ваша версия: {APP_VERSION}<br><br>"
            f"Для обновления свяжитесь:")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color:{t['text']}; font:10pt '{F()}'; background:transparent;")
        self.content_layout.addWidget(msg)

        tg = QLabel(
            f"<a href='https://{TELEGRAM_CONTACT}' "
            f"style='color:{t['accent']};'>{TELEGRAM_CONTACT}</a>")
        tg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tg.setOpenExternalLinks(True)
        tg.setStyleSheet(f"font:700 11pt '{F()}'; background:transparent;")
        self.content_layout.addWidget(tg)

        ok = MD3Button("Понятно", t, True, "check", 15)
        ok.clicked.connect(self.accept)
        self.add_button_row(ok)


# ═══════════════════════════════════════════════════════════════
#  SettingsDialog
# ═══════════════════════════════════════════════════════════════

class SettingsDialog(ThemedDialog):
    def __init__(self, cfg: dict, theme: dict, online: bool, parent=None):
        self.cfg        = cfg
        self.theme      = theme
        self._online    = online
        self.result_cfg = dict(cfg)
        super().__init__(theme, "Настройки", parent, width=760, height=720)
        self._build()
        # Даём Qt построить layout до показа
        for _ in range(3):
            QApplication.processEvents()

    def _build(self):
        tabs = QTabWidget()
        tabs.setStyleSheet(_tab_ss(self.theme))
        tabs.addTab(self._tab_launcher(), "Лаунчер")
        tabs.addTab(self._tab_style(),    "Стиль")
        tabs.addTab(self._tab_java(),     "Java")
        self.content_layout.addWidget(tabs, 1)

        cancel = MD3Button("Отмена", self.theme, False, "close", 14)
        cancel.clicked.connect(self.reject)
        save = MD3Button("Сохранить", self.theme, True, "check", 14)
        save.clicked.connect(self._save)
        self.add_button_row(cancel, save)

    def _sh(self, text: str, key=None) -> QWidget:
        return self.section_hdr(text, key)

    def _lbl(self, text: str) -> QLabel:
        return self.make_label(text)

    def _tab_launcher(self) -> QWidget:
        """Вкладка Лаунчер. Через QFormLayout + scroll area, чтобы поля
        не наезжали даже если контента много."""
        # Внешний контейнер — scroll, внутри сам контент
        outer = QWidget(); outer.setStyleSheet("background:transparent;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent; border:none;}}"
            f"{_sb_ss(self.theme)}")
        outer_lay.addWidget(scroll)

        w = QWidget(); w.setStyleSheet("background:transparent;")
        scroll.setWidget(w)

        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(8, 8, 8, 8)
        iss = _input_ss(self.theme)

        def _form() -> QFormLayout:
            f = QFormLayout()
            f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            f.setFormAlignment(Qt.AlignmentFlag.AlignTop)
            f.setHorizontalSpacing(14)
            f.setVerticalSpacing(10)
            f.setContentsMargins(6, 6, 6, 6)
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            return f

        # ── Производительность ──
        lay.addWidget(self._sh("Производительность", "furnace"))
        f1 = _form()
        self.ram = QSpinBox()
        self.ram.setRange(512, 32768); self.ram.setSingleStep(512)
        self.ram.setValue(int(self.cfg.get("ram_mb", 2048)))
        self.ram.setSuffix(" MB"); self.ram.setStyleSheet(iss)
        f1.addRow(self._lbl("RAM:"), self.ram)
        lay.addLayout(f1)

        # ── Интерфейс ──
        lay.addWidget(self._sh("Интерфейс", "crafting"))
        f2 = _form()
        self.width_sp = QSpinBox()
        self.width_sp.setRange(760, 2400)
        self.width_sp.setValue(int(self.cfg.get("window_width", 1000)))
        self.width_sp.setSuffix(" px"); self.width_sp.setStyleSheet(iss)
        self.height_sp = QSpinBox()
        self.height_sp.setRange(520, 1600)
        self.height_sp.setValue(int(self.cfg.get("window_height", 640)))
        self.height_sp.setSuffix(" px"); self.height_sp.setStyleSheet(iss)
        self.panel = QComboBox()
        for txt, dat in [("Снизу","bottom"),("Сверху","top"),
                         ("Слева","left"),("Справа","right")]:
            self.panel.addItem(txt, dat)
        self.panel.setCurrentIndex(
            max(0, self.panel.findData(self.cfg.get("panel_position", "bottom"))))
        self.panel.setStyleSheet(iss)
        f2.addRow(self._lbl("Ширина:"), self.width_sp)
        f2.addRow(self._lbl("Высота:"), self.height_sp)
        f2.addRow(self._lbl("Панель:"), self.panel)
        lay.addLayout(f2)

        # ── Опции ──
        lay.addWidget(self._sh("Опции", "diamond"))
        self.snap = QCheckBox("Показывать снапшоты")
        self.snap.setChecked(bool(self.cfg.get("show_snapshots")))
        self.snap.setStyleSheet(iss)
        self.news_cb = QCheckBox("Показывать новости")
        self.news_cb.setChecked(bool(self.cfg.get("show_news", True)))
        self.news_cb.setStyleSheet(iss)
        self.ask_sodium_cb = QCheckBox("Предлагать установку Sodium для Fabric")
        self.ask_sodium_cb.setChecked(bool(self.cfg.get("ask_sodium", True)))
        self.ask_sodium_cb.setStyleSheet(iss)
        lay.addWidget(self.snap)
        lay.addWidget(self.news_cb)
        lay.addWidget(self.ask_sodium_cb)
        lay.addSpacing(8)

        # ── Стиль интерфейса (classic / lunar) ──
        lay.addWidget(self._sh("Стиль интерфейса", "crafting"))
        f3 = QFormLayout()
        f3.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f3.setHorizontalSpacing(14)
        f3.setVerticalSpacing(10)
        f3.setContentsMargins(6, 6, 6, 6)
        f3.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.ui_style_cb = QComboBox()
        self.ui_style_cb.addItem("Классическая (центр)", "classic")
        self.ui_style_cb.addItem("Lunar (sidebar слева)", "lunar")
        cur_ui = self.cfg.get("ui_style", "classic")
        idx_ui = self.ui_style_cb.findData(cur_ui)
        if idx_ui >= 0:
            self.ui_style_cb.setCurrentIndex(idx_ui)
        self.ui_style_cb.setStyleSheet(iss)
        f3.addRow(self._lbl("Компоновка:"), self.ui_style_cb)
        lay.addLayout(f3)

        # Стиль прогресс-бара
        lay.addWidget(self._sh("Стиль загрузки", "redstone"))
        f4 = QFormLayout()
        f4.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f4.setHorizontalSpacing(14)
        f4.setVerticalSpacing(10)
        f4.setContentsMargins(6, 6, 6, 6)
        f4.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.progress_style_cb = QComboBox()
        for sid, sname in PROGRESS_STYLES:
            self.progress_style_cb.addItem(sname, sid)
        cur = self.cfg.get("progress_style", "bar")
        idx = self.progress_style_cb.findData(cur)
        if idx >= 0:
            self.progress_style_cb.setCurrentIndex(idx)
        self.progress_style_cb.setStyleSheet(iss)
        f4.addRow(self._lbl("Анимация:"), self.progress_style_cb)
        lay.addLayout(f4)
        # Превью прогресса (живая анимация)
        self.progress_preview = ProgressBar(
            self.theme, style_name=cur)
        self.progress_preview.setIndeterminate(True)
        lay.addWidget(self.progress_preview)
        self.progress_style_cb.currentIndexChanged.connect(
            lambda _i: self.progress_preview.setStyleName(
                self.progress_style_cb.currentData()))
        lay.addSpacing(8)

        lay.addWidget(self._sh("Фон", "redstone"))
        bgr = QHBoxLayout()
        self.bg_edit = QLineEdit(self.cfg.get("background_path", ""))
        self.bg_edit.setPlaceholderText("Путь к изображению...")
        self.bg_edit.setStyleSheet(iss)
        pbg = MD3Button("Выбрать...", self.theme, False, "image", 14)
        pbg.clicked.connect(self._pick_bg)
        self.bg_blur = QCheckBox("Размытие фона")
        self.bg_blur.setChecked(bool(self.cfg.get("background_blur")))
        self.bg_blur.setStyleSheet(iss)
        bgr.addWidget(self.bg_edit, 1); bgr.addWidget(pbg)
        lay.addLayout(bgr)
        lay.addWidget(self.bg_blur)

        lay.addStretch()
        return outer

    def _tab_style(self) -> QWidget:
        # Scroll-обёртка для предотвращения наезжания контента
        outer = QWidget(); outer.setStyleSheet("background:transparent;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent; border:none;}}"
            f"{_sb_ss(self.theme)}")
        outer_lay.addWidget(scroll)

        w = QWidget(); w.setStyleSheet("background:transparent;")
        scroll.setWidget(w)
        lay = QVBoxLayout(w); lay.setSpacing(10); lay.setContentsMargins(8, 8, 8, 8)
        iss = _input_ss(self.theme)

        # ── Размеры окна и сайдбара (новая секция) ──
        lay.addWidget(self._sh("Размеры элементов", "redstone"))
        f_sz = QFormLayout()
        f_sz.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f_sz.setHorizontalSpacing(14)
        f_sz.setVerticalSpacing(10)
        f_sz.setContentsMargins(6, 6, 6, 6)
        f_sz.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.border_sp = QSpinBox()
        self.border_sp.setRange(2, 16)
        self.border_sp.setValue(int(self.cfg.get("border_width", 6)))
        self.border_sp.setSuffix(" px")
        self.border_sp.setStyleSheet(iss)
        f_sz.addRow(self._lbl("Обводка окна:"), self.border_sp)

        self.sidebar_sp = QSpinBox()
        self.sidebar_sp.setRange(48, 120)
        self.sidebar_sp.setValue(int(self.cfg.get("sidebar_width", 68)))
        self.sidebar_sp.setSuffix(" px")
        self.sidebar_sp.setStyleSheet(iss)
        f_sz.addRow(self._lbl("Sidebar (Lunar):"), self.sidebar_sp)
        lay.addLayout(f_sz)
        lay.addSpacing(8)

        lay.addWidget(self._sh("Тема", "crafting"))
        g1 = QGridLayout(); g1.setSpacing(6)
        self.theme_combo = QComboBox()
        for tid, t_ in themes_mod.THEMES.items():
            self.theme_combo.addItem(t_["name"], tid)
        self.theme_combo.addItem("Своя (custom)", "custom")
        self.theme_combo.setCurrentIndex(
            max(0, self.theme_combo.findData(self.cfg.get("theme", "emerald"))))
        self.theme_combo.setStyleSheet(iss)

        self.item_combo = QComboBox()
        for iid, info in themes_mod.ITEMS.items():
            self.item_combo.addItem(info["name"], iid)
        self.item_combo.setCurrentIndex(
            max(0, self.item_combo.findData(self.cfg.get("item", "emerald"))))
        self.item_combo.setStyleSheet(iss)

        self.icon_url = QLineEdit(self.cfg.get("custom_item_url", ""))
        self.icon_url.setPlaceholderText("https://.../icon.png")
        self.icon_url.setStyleSheet(iss)
        if not self._online:
            self.icon_url.setEnabled(False)
            self.icon_url.setPlaceholderText("Нет интернета — URL недоступен")

        g1.addWidget(self._lbl("Тема"),       0, 0); g1.addWidget(self.theme_combo, 0, 1)
        g1.addWidget(self._lbl("Иконка"),     1, 0); g1.addWidget(self.item_combo, 1, 1)
        g1.addWidget(self._lbl("URL иконки"), 2, 0); g1.addWidget(self.icon_url, 2, 1)
        lay.addLayout(g1)

        lay.addWidget(self._sh("Кастомная палитра", "diamond"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent; border:1px solid {self.theme['primary_dark']};"
            f"border-radius:8px;}}"
            f"{_sb_ss(self.theme)}")
        cw = QWidget(); cw.setStyleSheet("background:transparent;")
        cg = QGridLayout(cw); cg.setSpacing(5)
        self.color_edits = {}
        color_keys = [
            ("accent", "Акцент"), ("accent_light", "Акцент светлый"),
            ("primary", "Primary"), ("primary_dark", "Primary dark"),
            ("bg_dark", "Фон тёмный"), ("bg_panel", "Панель"),
            ("bg_panel2", "Карточки"), ("text", "Текст"),
        ]
        for ri, (key, title) in enumerate(color_keys):
            edit = QLineEdit(self.cfg.get("custom_colors", {}).get(key, ""))
            edit.setPlaceholderText("#rrggbb")
            edit.setFixedWidth(100); edit.setStyleSheet(iss)
            btn = IconButton("palette", 16, self.theme["accent"],
                             "Выбрать цвет", self.theme["primary_dark"])
            btn.clicked.connect(lambda _=False, e=edit: self._pick_color(e))
            cg.addWidget(self._lbl(title), ri, 0)
            cg.addWidget(edit, ri, 1)
            cg.addWidget(btn, ri, 2)
            self.color_edits[key] = edit
        scroll.setWidget(cw)
        lay.addWidget(scroll, 1)
        return outer

    def _tab_java(self) -> QWidget:
        outer = QWidget(); outer.setStyleSheet("background:transparent;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent; border:none;}}"
            f"{_sb_ss(self.theme)}")
        outer_lay.addWidget(scroll)
        w = QWidget(); w.setStyleSheet("background:transparent;")
        scroll.setWidget(w)
        lay = QVBoxLayout(w); lay.setSpacing(10); lay.setContentsMargins(8, 8, 8, 8)
        iss = _input_ss(self.theme)

        lay.addWidget(self._sh("Путь к Java", "furnace"))
        self.java_edit = QLineEdit(self.cfg.get("java_path", ""))
        self.java_edit.setPlaceholderText("Пусто = автопоиск")
        self.java_edit.setStyleSheet(iss)
        pj = MD3Button("Выбрать...", self.theme, False, "folder", 14)
        pj.clicked.connect(self._pick_java)

        try:
            auto = mc.find_java()
        except Exception:
            auto = None
        ok_c = self.theme["accent"] if auto else self.theme.get("error", "#ff4444")
        ok_i = "check" if auto else "close"
        info_row = QHBoxLayout()
        info_ico = QLabel()
        info_ico.setPixmap(svg_pixmap(ok_i, 16, ok_c))
        info_ico.setFixedSize(20, 20)
        info_ico.setStyleSheet("background:transparent;")
        info_txt = QLabel(f"Найдена: {auto}" if auto else "Java не найдена")
        info_txt.setWordWrap(True)
        info_txt.setStyleSheet(
            f"color:{ok_c}; font:9pt Consolas;"
            f"background:{self.theme['bg_panel2']};"
            f"border:1px solid {self.theme['primary_dark']};"
            f"border-radius:8px; padding:6px 10px;")
        info_row.addWidget(info_ico)
        info_row.addWidget(info_txt, 1)

        note = QLabel("MC 1.17+ требует Java 17\nMC 1.21+ требует Java 21\nMC <= 1.16 требует Java 8")
        note.setStyleSheet(
            f"color:{self.theme['text_dim']}; font:9pt '{F()}';"
            f"background:transparent;")

        lay.addWidget(self.java_edit)
        lay.addWidget(pj)
        lay.addLayout(info_row)
        lay.addWidget(note)

        lay.addWidget(self._sh("О программе", "redstone"))
        about = QLabel(
            f"Exelent Launcher v{APP_VERSION}\n"
            f"Font: {F()}\n"
            f"Python {sys.version.split()[0]}")
        about.setWordWrap(True)
        about.setStyleSheet(
            f"color:{self.theme['text_dim']}; font:9pt '{F()}';"
            f"background:{self.theme['bg_panel2']};"
            f"border:1px solid {self.theme['primary_dark']};"
            f"border-radius:8px; padding:8px 12px;")
        lay.addWidget(about)

        lay.addStretch()
        return outer

    def _pick_bg(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Фон", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if f:
            self.bg_edit.setText(f)

    def _pick_java(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Java", "", "Java (*.exe);;All (*)")
        if f:
            self.java_edit.setText(f)

    def _pick_color(self, edit: QLineEdit):
        c = QColorDialog.getColor(
            QColor(edit.text() or self.theme["accent"]), self, "Цвет")
        if c.isValid():
            edit.setText(c.name())

    def _save(self):
        self.result_cfg.update({
            "ram_mb":          int(self.ram.value()),
            "show_snapshots":  self.snap.isChecked(),
            "show_news":       self.news_cb.isChecked(),
            "ask_sodium":      self.ask_sodium_cb.isChecked(),
            "panel_position":  self.panel.currentData(),
            "window_width":    int(self.width_sp.value()),
            "window_height":   int(self.height_sp.value()),
            "background_path": self.bg_edit.text().strip(),
            "background_blur": self.bg_blur.isChecked(),
            "theme":           self.theme_combo.currentData(),
            "item":            self.item_combo.currentData(),
            "custom_item_url": self.icon_url.text().strip(),
            "java_path":       self.java_edit.text().strip(),
            "progress_style":  self.progress_style_cb.currentData() or "bar",
            "ui_style":        self.ui_style_cb.currentData() or "classic",
            "border_width":    int(self.border_sp.value()),
            "sidebar_width":   int(self.sidebar_sp.value()),
            "custom_colors":   {
                k: e.text().strip()
                for k, e in self.color_edits.items()
                if e.text().strip()},
        })

        if (self.result_cfg["item"] == "custom"
                and self.result_cfg["custom_item_url"]
                and self.result_cfg["custom_item_url"] != self.cfg.get("custom_item_url")):
            if not self._online:
                QMessageBox.warning(
                    self, "Иконка", "Нет интернета — не могу скачать иконку.")
                return
            ok = _download_custom_icon(self.result_cfg["custom_item_url"])
            if not ok:
                QMessageBox.warning(
                    self, "Иконка", "Не удалось скачать иконку по URL.")
                return

        self.accept()


def _download_custom_icon(url: str) -> bool:
    fn = getattr(themes_mod, "download_custom_icon", None)
    if callable(fn):
        try:
            if fn(url):
                return True
        except Exception:
            pass
    try:
        items_dir = APP_DIR / "assets" / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            url, headers={"User-Agent": "ExelentLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if not data or len(data) < 16:
            return False
        (items_dir / "custom.png").write_bytes(data)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
#  LauncherWindow
# ═══════════════════════════════════════════════════════════════

class LauncherWindow(QWidget):
    BORDER = WINDOW_BORDER
    RADIUS = WINDOW_RADIUS

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.theme = themes_mod.get_theme(
            self.cfg.get("theme", "emerald"),
            self.cfg.get("custom_colors", {}))
        self.mc_dir = Path(self.cfg.get("mc_dir", APP_DIR / ".ExelLauncher"))
        try:
            mc.ensure_mc_dirs(self.mc_dir)
        except Exception:
            try:
                self.mc_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        self.versions        = []
        self.current_version = self.cfg.get("last_version", "1.21.4")
        self._drag_pos       = None
        self._rb_phase       = 0.0
        self.online          = has_internet()
        self._pending_loader  = None
        self._pending_profile = None

        self._install_thread  = None
        self._launch_thread   = None
        self._versions_thread = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Exelent Launcher")
        self.resize(int(self.cfg.get("window_width", 1000)),
                    int(self.cfg.get("window_height", 640)))
        self.setMinimumSize(760, 520)

        self._rb_timer = QTimer(self)
        self._rb_timer.timeout.connect(self._rb_tick)
        if self.theme.get("rainbow"):
            self._rb_timer.start(28)

        # Скачиваем блоки + после успеха перегенерируем items из MC-текстур
        self._blocks_th = BlockDownloadThread()
        self._blocks_th.done.connect(self._on_blocks_downloaded)
        self._blocks_th.start()

        self._apply_icon()
        self._build_ui()

        # Толстая обводка ПОВЕРХ всего. Ширину берём из cfg.
        border_w = int(self.cfg.get("border_width", self.BORDER))
        self._overlay = BorderOverlay(self.theme, border_w, self.RADIUS, self)
        self._overlay.setGeometry(self.rect())
        # КЛЮЧЕВОЕ: raise_() поднимает overlay над всеми дочерними виджетами,
        # включая sidebar в Lunar — рамка всегда поверх содержимого
        self._overlay.raise_()

        self._center()

        if self.online:
            self._load_versions()
            self._ver_check = VersionCheckThread()
            self._ver_check.outdated.connect(self._on_outdated)
            self._ver_check.start()
        else:
            self._load_installed_only()

    def _on_blocks_downloaded(self):
        """Когда фон-поток скачал текстуры — пересобираем PNG-иконки items
        из реальных MC-текстур (если ассеты были скачаны установщиком)."""
        try:
            cnt = themes_mod.refresh_items_from_mc_assets()
            if cnt > 0:
                # Обновим иконку окна и big-item на главной
                self._apply_icon()
                if hasattr(self, "big_item"):
                    self.big_item.setPixmap(self._item_pix(210))
                self.update()
        except Exception:
            pass

    def _rb_tick(self):
        self._rb_phase = (self._rb_phase + 1.6) % 360.0
        self.update()

    def _on_outdated(self, remote: str):
        OutdatedDialog(self.theme, remote, self).exec()

    def _apply_icon(self):
        try:
            p = themes_mod.get_item_path(self.cfg.get("item", "emerald"))
            if p.exists():
                icon = QIcon(str(p))
                self.setWindowIcon(icon)
                inst = QApplication.instance()
                if inst is not None:
                    inst.setWindowIcon(icon)
        except Exception:
            pass

    def _center(self):
        try:
            geo = QApplication.primaryScreen().geometry()
            self.move((geo.width() - self.width()) // 2,
                      (geo.height() - self.height()) // 2)
        except Exception:
            pass

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        BW = self.BORDER
        rect = QRectF(self.rect().adjusted(BW, BW, -BW, -BW))
        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS, self.RADIUS)

        bg_path = self.cfg.get("background_path", "")
        if bg_path and Path(bg_path).exists():
            pix = QPixmap(bg_path).scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            if self.cfg.get("background_blur") and not pix.isNull():
                tiny = pix.scaled(
                    max(1, self.width() // 18), max(1, self.height() // 18),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                pix = tiny.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
            p.save()
            p.setClipPath(path)
            p.drawPixmap(BW, BW, pix)
            p.fillPath(path, QColor(0, 0, 0, 115 if self.cfg.get("background_blur") else 70))
            p.restore()
        else:
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0, QColor(self.theme["bg_panel"]))
            grad.setColorAt(1, QColor(self.theme["bg_dark"]))
            p.fillPath(path, QBrush(grad))

        r, g, b = self.theme["glow_rgb"]
        p.fillPath(path, QColor(r, g, b, 16))
        p.end()
        # Рамка — отдельный BorderOverlay поверх всего

    def mousePressEvent(self, e):
        # Перетаскивание окна — только за верхнюю полосу заголовка
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < (self.BORDER + 48):
            self._drag_pos = (e.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_overlay"):
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
        self.cfg["window_width"]  = self.width()
        self.cfg["window_height"] = self.height()
        save_config(self.cfg)

    # ── UI ──
    def _item_pix(self, size: int) -> QPixmap:
        """Большая иконка выбранного item — квадрат size×size, пиксельный апскейл."""
        try:
            pix = themes_mod.get_item_pixmap(
                self.cfg.get("item", "diamond"), size)
            if not pix.isNull():
                return pix
        except Exception:
            pass
        # Самый крайний случай
        return svg_pixmap("rocket", size, self.theme["accent"])

    def _clear_layout(self):
        old = self.layout()
        if old:
            QWidget().setLayout(old)

    def _build_ui(self):
        self._clear_layout()
        root = QVBoxLayout(self)
        b = self.BORDER
        root.setContentsMargins(b, b, b, b)
        root.setSpacing(0)
        root.addWidget(self._title_bar())

        if not self.online:
            ob = QLabel(
                "Нет интернета — Modrinth и установка новых версий недоступны. "
                "Можно играть только в уже установленные.")
            ob.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ob.setStyleSheet(
                f"color:#ffaa55; font:600 9pt '{F()}';"
                f"background:rgba(255,170,85,0.10);"
                f"border-bottom:1px solid #ffaa55; padding:6px;")
            root.addWidget(ob)

        ui_style = self.cfg.get("ui_style", "classic")
        if ui_style == "lunar":
            root.addWidget(self._build_lunar_body(), 1)
            # КЛЮЧЕВОЕ: после построения lunar body поднимаем overlay
            # ещё раз — он должен быть НА САМОМ ВЕРХУ всех виджетов
            if hasattr(self, "_overlay"):
                self._overlay.raise_()
            return

        # Classic layout
        pos = self.cfg.get("panel_position", "bottom")
        if pos in ("left", "right"):
            body = QHBoxLayout()
            body.setContentsMargins(22, 8, 22, 18)
            body.setSpacing(16)
            panel   = self._control_panel(vertical=True)
            content = self._content_area()
            if pos == "left":
                body.addWidget(panel); body.addWidget(content, 1)
            else:
                body.addWidget(content, 1); body.addWidget(panel)
            wrap = QWidget(); wrap.setLayout(body)
            root.addWidget(wrap, 1)
        else:
            if pos == "top":
                root.addWidget(self._control_panel(False))
                root.addWidget(self._content_area(), 1)
            else:
                root.addWidget(self._content_area(), 1)
                root.addWidget(self._control_panel(False))
        # После построения главного layout поднимаем overlay
        if hasattr(self, "_overlay"):
            self._overlay.raise_()

    # ───────────────────────────────────────────────────────────
    #  LUNAR LAYOUT — sidebar слева + большая центральная зона
    # ───────────────────────────────────────────────────────────

    def _build_lunar_body(self) -> QWidget:
        t = self.theme
        wrap = QWidget()
        body = QHBoxLayout(wrap)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # ── SIDEBAR слева (узкий, с иконками) ──
        side = QFrame()
        sw = int(self.cfg.get("sidebar_width", 68))
        side.setFixedWidth(sw)
        # ВАЖНО: оставляем место СЛЕВА равное толщине обводки
        # чтобы обводка не перекрывалась sidebar'ом
        side.setStyleSheet(
            f"QFrame{{background:rgba(8,12,8,230);"
            f"border-right:1px solid {t['primary_dark']};"
            f"border-top-left-radius:0px;"
            f"border-bottom-left-radius:0px;}}")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 12, 0, 12)
        sl.setSpacing(6)
        sl.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Логотип сверху
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(self._item_pix(40))
        logo.setStyleSheet("background:transparent;")
        sl.addWidget(logo)
        sl.addSpacing(16)

        # Вертикальные кнопки-иконки
        sidebar_btns = [
            ("rocket",   "Главная",      lambda: None),
            ("puzzle",   "Кастомизация", self._show_customization),
            ("package",  "Профили",      self._new_profile_btn),
            ("folder",   "Папка",        lambda: open_folder(self.mc_dir)),
        ]
        for ico, tip, cb in sidebar_btns:
            btn = self._lunar_side_btn(ico, tip)
            btn.clicked.connect(cb)
            sl.addWidget(btn)

        sl.addStretch()

        # Настройки внизу sidebar
        settings_btn = self._lunar_side_btn("settings", "Настройки")
        settings_btn.clicked.connect(self._show_settings)
        sl.addWidget(settings_btn)

        body.addWidget(side)

        # ── ОСНОВНАЯ ОБЛАСТЬ (большая, с играть-карточкой как у lunar) ──
        main = QWidget()
        main.setStyleSheet("background:transparent;")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(24, 20, 24, 20)
        ml.setSpacing(16)

        # ── ОГРОМНАЯ КАРТОЧКА LAUNCH ──
        launch_card = QFrame()
        r, g, bb = t["glow_rgb"]
        launch_card.setStyleSheet(
            f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {t['bg_panel']},"
            f"stop:0.5 {t['bg_panel2']},"
            f"stop:1 {t['bg_dark']});"
            f"border:1px solid {t['primary_dark']};"
            f"border-radius:18px;}}")
        launch_card.setMinimumHeight(280)
        lcl = QVBoxLayout(launch_card)
        lcl.setContentsMargins(40, 36, 40, 36)
        lcl.setSpacing(12)
        lcl.addStretch()

        # Большой item-арт по центру
        big = QLabel()
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big.setPixmap(self._item_pix(140))
        big.setStyleSheet("background:transparent;")
        lcl.addWidget(big)

        # ОГРОМНАЯ кнопка ИГРАТЬ
        play_row = QHBoxLayout()
        play_row.addStretch()
        self.btn_play = QPushButton(f"ИГРАТЬ  {self.current_version}")
        self.btn_play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_play.setMinimumHeight(64)
        self.btn_play.setMinimumWidth(420)
        self.btn_play.setIcon(svg_icon("play", 22, "#061006"))
        self.btn_play.setIconSize(QSize(22, 22))
        self.btn_play.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {t['primary']},
                    stop:0.5 {t['accent']},
                    stop:1 {t['accent_light']});
                color: #061006;
                border: none;
                border-radius: 14px;
                font: 800 18pt '{F()}';
                letter-spacing: 2px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_light']});
            }}
            QPushButton:pressed {{
                background: {t['primary_dark']};
                color: {t['accent']};
            }}
            QPushButton:disabled {{ background:#2a2a2a; color:#666; }}
        """)
        self.btn_play.clicked.connect(self._play)
        play_row.addWidget(self.btn_play)
        play_row.addStretch()
        lcl.addLayout(play_row)

        # Под кнопкой — статус
        self.dl_label = QLabel("Готов к запуску")
        self.dl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dl_label.setStyleSheet(
            f"color:{t['text_dim']}; font:500 9pt '{F()}';"
            f"background:transparent; border:none;")
        lcl.addWidget(self.dl_label)

        self.dl_pct = QLabel("")
        self.dl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dl_pct.setStyleSheet(
            f"color:{t['accent']}; font:700 9pt '{F()}';"
            f"background:transparent;")
        lcl.addWidget(self.dl_pct)

        # Прогресс-бар (узкий)
        prog_wrap = QHBoxLayout()
        prog_wrap.addStretch()
        self.progress = ProgressBar(
            self.theme, style_name=self.cfg.get("progress_style", "bar"))
        self.progress.setFixedWidth(420)
        prog_wrap.addWidget(self.progress)
        prog_wrap.addStretch()
        lcl.addLayout(prog_wrap)

        lcl.addStretch()
        ml.addWidget(launch_card, 1)

        # ── Нижняя строка: ник + кнопка версии ──
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        nick_lbl = QLabel("Никнейм:")
        nick_lbl.setStyleSheet(
            f"color:{t['text_dim']}; font:600 9pt '{F()}'; background:transparent;")
        bottom.addWidget(nick_lbl)

        self.nick = QLineEdit(self.cfg.get("username", "Player"))
        self.nick.setMaxLength(16)
        self.nick.setPlaceholderText("Никнейм")
        self.nick.editingFinished.connect(self._save_nick)
        self.nick.setStyleSheet(self._inline_input())
        self.nick.setFixedWidth(220)
        bottom.addWidget(self.nick)

        bottom.addStretch()

        ver_lbl = QLabel("Версия:")
        ver_lbl.setStyleSheet(
            f"color:{t['text_dim']}; font:600 9pt '{F()}'; background:transparent;")
        bottom.addWidget(ver_lbl)

        self.btn_ver = MD3Button(self.current_version, self.theme, False, "arrow_right", 14)
        self.btn_ver.clicked.connect(self._pick_version)
        bottom.addWidget(self.btn_ver)

        ml.addLayout(bottom)

        body.addWidget(main, 1)
        # Обновим btn_ver текстом профиля если надо
        QTimer.singleShot(0, self._upd_ver_btn)
        return wrap

    def _lunar_side_btn(self, icon: str, tooltip: str) -> QPushButton:
        t = self.theme
        r, g, b = t["glow_rgb"]
        btn = QPushButton()
        btn.setIcon(svg_icon(icon, 22, t["accent"]))
        btn.setIconSize(QSize(22, 22))
        btn.setFixedSize(52, 52)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 10px;
                margin: 4px 8px;
            }}
            QPushButton:hover {{
                background: rgba({r},{g},{b},0.16);
            }}
            QPushButton:pressed {{
                background: rgba({r},{g},{b},0.28);
            }}
        """)
        return btn

    def _title_bar(self) -> QWidget:
        bar = QWidget(); bar.setFixedHeight(48)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 10, 0)
        lay.setSpacing(8)

        ico = QLabel(); ico.setPixmap(self._item_pix(26))
        ico.setStyleSheet("background:transparent;")
        lay.addWidget(ico)

        t1 = QLabel("Exelent")
        t1.setStyleSheet(
            f"color:{self.theme['accent']}; font:800 14pt '{F()}';"
            f"letter-spacing:2px; background:transparent;")
        lay.addWidget(t1)

        t2 = QLabel("Launcher")
        t2.setStyleSheet(
            f"color:{self.theme['text_dim']}; font:600 11pt '{F()}';"
            f"background:transparent;")
        lay.addWidget(t2)

        vl = QLabel(f"v{APP_VERSION}")
        vl.setStyleSheet(
            f"color:{self.theme['primary']}; font:7pt '{F()}';"
            f"background:transparent;")
        lay.addWidget(vl)

        if not self.online:
            off = QLabel("OFFLINE")
            off.setStyleSheet(
                f"color:#ffaa55; font:700 8pt '{F()}';"
                f"background:rgba(255,170,85,0.15);"
                f"border:1px solid #ffaa55; border-radius:4px;"
                f"padding:1px 6px;")
            lay.addWidget(off)

        lay.addStretch()

        for ico_n, tip, cb in [
            ("settings", "Настройки", self._show_settings),
            ("minimize", "Свернуть",   self.showMinimized),
            ("close",    "Закрыть",    self.close),
        ]:
            hover = "rgba(180,30,30,200)" if ico_n == "close" else self.theme["bg_panel2"]
            b = IconButton(ico_n, 16, self.theme["text"], tip, hover)
            b.clicked.connect(cb)
            lay.addWidget(b)
        return bar

    def _content_area(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(28, 8, 28, 8)
        lay.setSpacing(20)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addStretch()

        self.big_item = QLabel()
        self.big_item.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_item.setPixmap(self._item_pix(210))
        self.big_item.setStyleSheet("background:transparent;")
        ll.addWidget(self.big_item)

        tag = QLabel("MINECRAFT")
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setStyleSheet(
            f"color:{self.theme['text']}; font:800 25pt '{F()}';"
            f"letter-spacing:6px; background:transparent;")
        ll.addWidget(tag)

        st = QLabel("premium offline  -  fabric  -  mod manager")
        st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        st.setStyleSheet(
            f"color:{self.theme['accent']}; font:500 9pt '{F()}';"
            f"letter-spacing:3px; background:transparent;")
        ll.addWidget(st)

        ll.addStretch()
        lay.addWidget(left, 1)

        if self.cfg.get("show_news", True):
            lay.addWidget(self._news_card())

        return w

    def _card(self, width: int = 280) -> QFrame:
        f = QFrame(); f.setFixedWidth(width)
        f.setStyleSheet(
            f"QFrame{{background:rgba(15,22,15,215);"
            f"border:1px solid {self.theme['primary_dark']};"
            f"border-radius:16px;}}")
        return f

    def _news_card(self) -> QFrame:
        card = self._card(270)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        hrow = QHBoxLayout()
        hico = QLabel(); hico.setPixmap(svg_pixmap("news", 18, self.theme["accent"]))
        hico.setFixedSize(22, 22); hico.setStyleSheet("background:transparent;")
        hl = QLabel("Новости")
        hl.setStyleSheet(
            f"color:{self.theme['accent']}; font:700 13pt '{F()}';"
            f"background:transparent; border:none;")
        hrow.addWidget(hico); hrow.addWidget(hl); hrow.addStretch()
        lay.addLayout(hrow)
        news = [
            ("Профили",      "Каждый профиль — своя папка модов и тп."),
            ("Кастомизация", "Моды, текстуры и шейдеры — в одном окне."),
            ("Sodium",       "Предлагается при установке Fabric."),
            ("Офлайн",       "Можно играть без интернета."),
        ]
        for a, b_ in news:
            l = QLabel(f"<b>{a}</b>: {b_}")
            l.setWordWrap(True)
            l.setStyleSheet(
                f"color:{self.theme['text_dim']}; font:9pt '{F()}';"
                f"background:transparent; border:none;")
            lay.addWidget(l)
        lay.addStretch()
        return card

    def _control_panel(self, vertical=False) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame{{background:rgba(6,10,6,235);"
            f"border:1px solid {self.theme['primary_dark']};"
            f"border-radius:16px;}}")
        if vertical:
            panel.setFixedWidth(232)
        else:
            panel.setFixedHeight(124)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 10, 16, 12)
        outer.setSpacing(6)

        top = QHBoxLayout()
        self.dl_label = QLabel("Готов к запуску")
        self.dl_label.setStyleSheet(
            f"color:{self.theme['text_dim']}; font:9pt '{F()}';"
            f"background:transparent; border:none;")
        top.addWidget(self.dl_label)
        top.addStretch()
        self.dl_pct = QLabel("")
        self.dl_pct.setStyleSheet(
            f"color:{self.theme['accent']}; font:700 9pt '{F()}';"
            f"background:transparent; border:none;")
        top.addWidget(self.dl_pct)
        outer.addLayout(top)

        self.progress = ProgressBar(
            self.theme,
            style_name=self.cfg.get("progress_style", "bar"))
        outer.addWidget(self.progress)

        row = QVBoxLayout() if vertical else QHBoxLayout()
        row.setSpacing(6)

        self.nick = QLineEdit(self.cfg.get("username", "Player"))
        self.nick.setMaxLength(16)
        self.nick.setPlaceholderText("Никнейм")
        self.nick.editingFinished.connect(self._save_nick)
        self.nick.setStyleSheet(self._inline_input())
        row.addWidget(self.nick)

        self.btn_ver = MD3Button(self.current_version, self.theme, False, "arrow_right", 14)
        self.btn_ver.clicked.connect(self._pick_version)
        row.addWidget(self.btn_ver)

        btns = [
            ("Профиль",       "plus",     self._new_profile_btn),
            ("Кастомизация",  "sparkles", self._show_customization),
            ("Папка",         "folder",   lambda: open_folder(self.mc_dir)),
        ]
        for lbl, ico, cb in btns:
            b = MD3Button(lbl, self.theme, False, ico, 14)
            b.clicked.connect(cb)
            row.addWidget(b)

        self.btn_play = MD3Button("ИГРАТЬ", self.theme, True, "play", 16)
        self.btn_play.clicked.connect(self._play)
        row.addWidget(self.btn_play)

        outer.addLayout(row)
        return panel

    def _inline_input(self) -> str:
        t = self.theme
        return (f"QLineEdit,QComboBox{{"
                f"background:{t['bg_panel2']}; color:{t['text']};"
                f"border:1.5px solid {t['primary_dark']}; border-radius:16px;"
                f"padding:6px 10px; min-height:22px; font:9pt '{F()}';  }}"
                f"QComboBox::drop-down{{border:none; width:20px;}}")

    # ── Versions ──
    def _load_versions(self):
        self.dl_label.setText("Загрузка версий...")
        self.progress.setIndeterminate(True)
        self._versions_thread = VersionsThread(bool(self.cfg.get("show_snapshots")))
        self._versions_thread.loaded.connect(self._on_versions)
        self._versions_thread.failed.connect(self._on_versions_failed)
        self._versions_thread.start()

    def _on_versions_failed(self, err):
        self.progress.setValue(0)
        self.dl_label.setText(f"Ошибка: {err[:40]}")
        self._load_installed_only()

    def _load_installed_only(self):
        try:
            installed = sorted(mc.get_installed_versions(self.mc_dir))
        except Exception:
            installed = []
        installed = [v for v in installed if self._is_modern_version(v)]
        self.versions = [{"id": v, "type": "release"} for v in installed]
        if self.versions and self.current_version not in installed:
            self.current_version = installed[0]
        self._upd_ver_btn()
        self.progress.setValue(0)
        if installed:
            self.dl_label.setText(f"Офлайн  -  {len(installed)} установлено")
        else:
            self.dl_label.setText("Офлайн  -  нет установленных версий")

    @staticmethod
    def _is_modern_version(vid: str) -> bool:
        if not vid:
            return False
        s = vid.split("-")[0]
        try:
            parts = s.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
        except Exception:
            return True
        if major < 1:
            return False
        if major == 1 and minor < 7:
            return False
        if major == 1 and minor == 7 and patch < 10:
            return False
        return True

    def _on_versions(self, versions):
        versions = [v for v in versions
                    if self._is_modern_version(v.get("id", ""))]
        self.versions = versions
        ids = [v.get("id") for v in versions]
        if self.current_version not in ids and ids:
            self.current_version = ids[0]
        self._upd_ver_btn()
        self.progress.setValue(0)
        self.dl_label.setText(f"Готово  -  {len(versions)} версий")

    def _upd_ver_btn(self):
        try:
            installed = mc.is_version_installed(self.mc_dir, self.current_version)
        except Exception:
            installed = False

        # Текст для btn_ver
        prof_name = self.cfg.get("last_profile", "")
        display = self.current_version
        if prof_name:
            try:
                prof = profiles_mod.get_profile(self.mc_dir, prof_name)
            except Exception:
                prof = None
            if prof:
                ver_id = prof.get("version_id") or prof.get("base", "")
                if ver_id == self.current_version:
                    base = prof.get("base", "")
                    display = f"{prof_name} · {base}"

        if hasattr(self, "btn_ver") and self.btn_ver is not None:
            mark = "  [уст]" if installed and display == self.current_version else ""
            self.btn_ver.setText(display + mark)

        # В Lunar-стиле кнопка играть содержит версию — обновляем
        if hasattr(self, "btn_play") and self.btn_play is not None:
            cur_text = self.btn_play.text()
            if cur_text.startswith("ИГРАТЬ"):
                self.btn_play.setText(f"ИГРАТЬ  {display}")

    def _pick_version(self):
        if not self.versions:
            QMessageBox.information(self, "Версии", "Список загружается...")
            return
        try:
            installed = mc.get_installed_versions(self.mc_dir)
        except Exception:
            installed = []
        try:
            profs = profiles_mod.list_profiles(self.mc_dir)
        except Exception:
            profs = []
        dlg = VersionPickerDialog(
            self.versions, installed,
            self.current_version, self.theme,
            profiles_list=profs, parent=self)
        if dlg.exec():
            self.current_version = dlg.selected
            self.cfg["last_version"] = dlg.selected
            # Запоминаем выбранный профиль (если выбран)
            if dlg.selected_profile:
                self.cfg["last_profile"] = dlg.selected_profile
            else:
                # Выбрали vanilla — сбрасываем last_profile
                self.cfg["last_profile"] = ""
            save_config(self.cfg)
            self._upd_ver_btn()

    # ── Профили ──
    def create_profile_flow(self):
        if not self.online and not self.versions:
            QMessageBox.warning(self, "Профили",
                                "Нет интернета и нет загруженных версий.")
            return None

        all_ids = [v.get("id", "") for v in self.versions
                   if v.get("type", "release") == "release"]
        all_ids = [v for v in all_ids if v and self._is_modern_version(v)]
        if not all_ids:
            QMessageBox.warning(self, "Профили",
                                "Нет доступных версий Minecraft.")
            return None

        dlg = CreateProfileDialog(
            self.theme, all_ids, self.current_version, self)
        if not dlg.exec() or not dlg.result_data:
            return None

        data = dlg.result_data
        name   = data["name"]
        loader = data["loader"]
        base   = data["version"]

        if profiles_mod.get_profile(self.mc_dir, name):
            QMessageBox.warning(self, "Профили",
                                f"Профиль «{name}» уже существует.")
            return None

        try:
            already = mc.is_version_installed(self.mc_dir, base)
        except Exception:
            already = False

        if loader == "fabric":
            if not self.online:
                QMessageBox.warning(
                    self, "Офлайн",
                    "Для установки Fabric нужен интернет.")
                return None
            self._pending_profile = {"name": name, "loader": loader, "base": base}
            self._install(base, "fabric")
            return None

        if not already:
            if not self.online:
                QMessageBox.warning(
                    self, "Офлайн",
                    f"Версия {base} не установлена, а интернета нет.")
                return None
            self._pending_profile = {"name": name, "loader": loader, "base": base}
            self._install(base, "vanilla")
            return None

        try:
            meta = profiles_mod.create_profile(
                self.mc_dir, name, base, loader, base)
            self.cfg["last_profile"] = name
            save_config(self.cfg)
            QMessageBox.information(
                self, "Профиль",
                f"Профиль «{name}» создан (MC {base}, {loader}).")
            return meta
        except Exception as ex:
            QMessageBox.critical(self, "Ошибка", str(ex))
            return None

    def _new_profile_btn(self):
        self.create_profile_flow()

    # ── Play / Install / Launch ──
    def _save_nick(self):
        nick = "".join(c for c in self.nick.text().strip()
                       if c.isalnum() or c == "_")[:16] or "Player"
        self.nick.setText(nick)
        self.cfg["username"] = nick
        save_config(self.cfg)

    def _play(self):
        if not getattr(mc, "HAS_MLL", True):
            QMessageBox.critical(self, "Библиотека",
                                 "pip install minecraft-launcher-lib")
            return
        self._save_nick()
        target = self.current_version

        try:
            already = mc.is_version_installed(self.mc_dir, target)
        except Exception:
            already = False

        if already:
            self._launch(target)
            return

        if not self.online:
            QMessageBox.warning(
                self, "Офлайн",
                f"Версия {target} не установлена, а интернета нет.\n"
                f"Выбери уже установленную версию.")
            return

        dlg = LoaderPickDialog(self.theme, target, self)
        if not dlg.exec() or not dlg.choice:
            return
        loader = dlg.choice
        self._install(target, loader)

    def _install(self, version: str, loader: str):
        self._pending_loader = loader
        self.btn_play.setEnabled(False)
        self.btn_play.setText("Загрузка...")
        self.dl_label.setText(f"Установка {loader}: {version}...")

        # Фейковый плавный прогресс (особенно для fabric, который висит на 5%)
        # Делаем сильно длиннее, чтобы пользователь видел плавный рост
        fake_duration = 90.0 if loader == "fabric" else 50.0
        self._fake_prog = FakeProgressTimer(
            self.progress, max_pct=92, target_seconds=fake_duration, parent=self)
        self._fake_prog.start_fake()

        self._install_thread = InstallThread(version, self.mc_dir, loader)
        self._install_thread.progress.connect(self._on_install_progress)
        self._install_thread.ok.connect(self._install_ok)
        self._install_thread.failed.connect(self._fail)
        self._install_thread.start()

    def _on_install_progress(self, pct: int, s: str):
        # Реальный прогресс ТОЛЬКО если он больше текущего fake (не идёт назад)
        # и больше 30% (Fabric отдаёт только 5% или 100% — оба не годятся для UI)
        if hasattr(self, "_fake_prog") and self._fake_prog is not None:
            current_fake = self._fake_prog.current_value()
            if pct >= max(30, current_fake):
                self._fake_prog.set_real(pct)
            # Показываем процент FAKE а не реального — fake плавно растёт
            shown_pct = self._fake_prog.current_value()
        else:
            shown_pct = pct
        self.dl_pct.setText(f"{shown_pct}%")
        self.dl_label.setText(s[:80])

    def _on_progress(self, pct: int, s: str):
        self.progress.setValue(pct)
        self.dl_pct.setText(f"{pct}%")
        self.dl_label.setText(s[:80])

    def _install_ok(self, version: str):
        # Останавливаем фейковый прогресс
        if hasattr(self, "_fake_prog") and self._fake_prog is not None:
            try:
                self._fake_prog.finish()
            except Exception:
                pass
            self._fake_prog = None

        pp = self._pending_profile
        self._pending_profile = None

        # Если это была установка ДЛЯ ПРОФИЛЯ — НЕ меняем last_version,
        # vanilla остаётся доступной как раньше
        if pp:
            try:
                profiles_mod.create_profile(
                    self.mc_dir,
                    pp["name"], pp["base"], pp["loader"], version)
                self.cfg["last_profile"] = pp["name"]
                save_config(self.cfg)
                QMessageBox.information(
                    self, "Профиль",
                    f"Профиль «{pp['name']}» создан.\n"
                    f"Vanilla {pp['base']} осталась доступна без модов.\n"
                    f"Открой Кастомизацию, чтобы добавить моды.")
            except Exception as ex:
                QMessageBox.warning(self, "Профиль",
                                    f"Не удалось создать профиль: {ex}")
            self.btn_play.setEnabled(True)
            self.btn_play.setText("ИГРАТЬ")
            self._upd_ver_btn()
        else:
            self.current_version     = version
            self.cfg["last_version"] = version
            save_config(self.cfg)
            self.btn_play.setEnabled(True)
            self.btn_play.setText("ИГРАТЬ")
            self._upd_ver_btn()

        loader = self._pending_loader or "vanilla"
        self._pending_loader = None

        offered = self.cfg.get("sodium_offered_versions", [])
        base_ver = self._base_mc_version(version)

        if (loader == "fabric"
                and self.cfg.get("ask_sodium", True)
                and base_ver not in offered
                and self.online):
            offered.append(base_ver)
            self.cfg["sodium_offered_versions"] = offered
            save_config(self.cfg)
            # Если установка под профиль — кладём sodium в его mods/
            target_mods = None
            if pp:
                try:
                    target_mods = profiles_mod.mods_dir(
                        self.mc_dir, pp["name"])
                except Exception:
                    target_mods = None
            QTimer.singleShot(
                400, lambda: self._offer_sodium(base_ver, target_mods))
        else:
            QTimer.singleShot(350, lambda: self._launch(version))

    def _offer_sodium(self, base_ver: str, mods_dir: Path = None):
        # Если есть профиль — кладём sodium в его mods/, иначе в global mods/
        if mods_dir is None:
            last_p = self.cfg.get("last_profile", "")
            if last_p:
                try:
                    mods_dir = profiles_mod.mods_dir(self.mc_dir, last_p)
                except Exception:
                    mods_dir = self.mc_dir / "mods"
            else:
                mods_dir = self.mc_dir / "mods"
        dlg = SodiumOfferDialog(
            self.theme, base_ver, mods_dir, is_fabric=True, parent=self)
        dlg.exec()
        QTimer.singleShot(200, lambda: self._launch(self.current_version))

    @staticmethod
    def _base_mc_version(vid: str) -> str:
        if "-" not in vid:
            return vid
        parts = vid.split("-")
        for p in reversed(parts):
            if p and p[0].isdigit() and "." in p:
                return p
        return vid

    @staticmethod
    def _required_java(vid: str) -> int:
        base = LauncherWindow._base_mc_version(vid)
        try:
            parts = base.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
        except Exception:
            return 17
        if major < 1 or (major == 1 and minor <= 16):
            return 8
        if major == 1 and minor == 17:
            return 16
        if major == 1 and (minor < 20 or (minor == 20 and patch <= 4)):
            return 17
        return 21

    @staticmethod
    def _java_major(java_path: str):
        if not java_path:
            return None
        try:
            kw = {}
            if sys.platform == "win32":
                kw["creationflags"] = 0x08000000
            r = subprocess.run([java_path, "-version"],
                               capture_output=True, text=True, timeout=4, **kw)
            out = (r.stderr or "") + (r.stdout or "")
            import re as _re
            m = _re.search(r'version\s+"([^"]+)"', out)
            if not m:
                return None
            v = m.group(1)
            if v.startswith("1."):
                return int(v.split(".")[1])
            return int(v.split(".")[0])
        except Exception:
            return None

    def _find_compatible_java(self, want_major: int):
        user_path = self.cfg.get("java_path", "").strip()
        if user_path and Path(user_path).exists():
            if self._java_major(user_path) == want_major:
                return user_path

        try:
            auto = mc.find_java(user_path) if user_path else mc.find_java()
        except Exception:
            auto = None
        if auto and self._java_major(auto) == want_major:
            return auto

        candidates = []
        if sys.platform == "win32":
            roots = [
                Path("C:/Program Files/Java"),
                Path("C:/Program Files (x86)/Java"),
                Path("C:/Program Files/Eclipse Adoptium"),
                Path("C:/Program Files/Microsoft"),
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Eclipse Adoptium",
            ]
            for root in roots:
                try:
                    if root.exists() and root.is_dir():
                        for j in root.rglob("javaw.exe"):
                            candidates.append(j)
                        for j in root.rglob("java.exe"):
                            candidates.append(j)
                except Exception:
                    continue
        else:
            for base in ("/usr/lib/jvm", "/Library/Java/JavaVirtualMachines"):
                p = Path(base)
                if p.exists():
                    try:
                        for j in p.rglob("java"):
                            if j.is_file() and os.access(j, os.X_OK):
                                candidates.append(j)
                    except Exception:
                        continue

        for c in candidates:
            if self._java_major(str(c)) == want_major:
                return str(c)
        return None

    def _launch(self, version: str):
        need_java = self._required_java(version)
        base_ver = self._base_mc_version(version)

        # 1. ПРИОРИТЕТ: ранее одобренный override для этой версии
        overrides = self.cfg.get("java_overrides", {}) or {}
        saved_java = overrides.get(base_ver) or overrides.get(version)
        if saved_java and Path(saved_java).exists():
            java = saved_java
            current_major = self._java_major(java)
            self._do_launch(version, java)
            return

        # 2. Указанный в настройках Java
        user_path = self.cfg.get("java_path", "").strip()
        try:
            java = mc.find_java(user_path) if user_path else mc.find_java()
        except Exception:
            java = None
        current_major = self._java_major(java) if java else None

        # 3. Если несовпадение — пробуем найти подходящую
        if current_major is None or current_major < need_java:
            better = self._find_compatible_java(need_java)
            if better:
                java = better
                current_major = need_java

        # 4. Если до сих пор Java нет — ошибка
        if not java:
            QMessageBox.warning(
                self, "Java",
                f"Java не найдена.\n"
                f"Для MC {base_ver} нужна Java {need_java}.\n"
                f"Укажите путь в настройках.")
            self.btn_play.setEnabled(True)
            self.btn_play.setText("ИГРАТЬ")
            return

        # 5. ПРАВИЛО: если Java БОЛЬШЕ или РАВНА требуемой — не спрашиваем
        if current_major is not None and current_major >= need_java:
            self._do_launch(version, java)
            return

        # 6. Java меньше требуемой — спрашиваем (один раз, потом запоминаем)
        res = QMessageBox.question(
            self, "Java несовместима",
            f"Для Minecraft {base_ver} нужна Java {need_java}, "
            f"а найдена Java {current_major}.\n\n"
            f"Установи Java {need_java}:\n"
            f"  Java 8:  adoptium.net/temurin/releases?version=8\n"
            f"  Java 17: adoptium.net/temurin/releases?version=17\n"
            f"  Java 21: adoptium.net/temurin/releases?version=21\n\n"
            f"Если нажмёшь «Да» — больше не спросим для этой версии.\n"
            f"Запустить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if res != QMessageBox.StandardButton.Yes:
            self.btn_play.setEnabled(True)
            self.btn_play.setText("ИГРАТЬ")
            return

        # Запоминаем согласие: для этой версии запускаем с этой Java без вопросов
        overrides[base_ver] = java
        self.cfg["java_overrides"] = overrides
        save_config(self.cfg)

        self._do_launch(version, java)

    def _do_launch(self, version: str, java: str):
        """Финальный запуск (без диалогов)."""

        self.dl_label.setText(f"Запуск {version}...")
        self.progress.setValue(100)
        self.btn_play.setEnabled(False)
        self._launch_thread = LaunchThread(
            version, self.nick.text(), self.mc_dir,
            int(self.cfg.get("ram_mb", 2048)), java)
        self._launch_thread.ok.connect(self._launch_ok)
        self._launch_thread.failed.connect(self._fail)
        self._launch_thread.start()

    def _launch_ok(self):
        self.dl_label.setText("Minecraft запущен")
        self.btn_play.setEnabled(True)
        self.btn_play.setText("ИГРАТЬ")
        QTimer.singleShot(2500, lambda: (
            self.progress.setValue(0),
            self.dl_pct.setText(""),
            self.dl_label.setText("Готов к запуску"),
        ))

    def _fail(self, err: str):
        if hasattr(self, "_fake_prog") and self._fake_prog is not None:
            try:
                self._fake_prog.stop()
            except Exception:
                pass
            self._fake_prog = None
        self.btn_play.setEnabled(True)
        self.btn_play.setText("ИГРАТЬ")
        self.progress.setValue(0)
        QMessageBox.critical(self, "Ошибка", err)

    # ── Dialogs ──
    def _show_settings(self):
        old_snap = self.cfg.get("show_snapshots")
        dlg = SettingsDialog(self.cfg, self.theme, self.online, self)
        # Прогоняем event loop чтобы все иконки секций успели прорисоваться
        for _ in range(3):
            QApplication.processEvents()
        if dlg.exec():
            self.cfg.update(dlg.result_cfg)
            save_config(self.cfg)
            self.theme = themes_mod.get_theme(
                self.cfg.get("theme"), self.cfg.get("custom_colors", {}))
            self.resize(int(self.cfg["window_width"]),
                        int(self.cfg["window_height"]))
            self._apply_icon()
            # Обновить стиль главного прогресс-бара
            if hasattr(self, "progress") and hasattr(self.progress, "setStyleName"):
                self.progress.setStyleName(
                    self.cfg.get("progress_style", "bar"))
            if hasattr(self, "_overlay"):
                self._overlay.apply_theme(self.theme)
                # Применяем новую ширину обводки
                new_b = int(self.cfg.get("border_width", self.BORDER))
                self._overlay.set_border(new_b)
            if self.theme.get("rainbow"):
                if not self._rb_timer.isActive():
                    self._rb_timer.start(28)
            else:
                self._rb_timer.stop()
            self._build_ui()
            self.update()
            if self.online and old_snap != self.cfg.get("show_snapshots"):
                self._load_versions()
            else:
                self._upd_ver_btn()

    def _show_customization(self):
        default_name = self.cfg.get("last_profile", "")
        if not default_name:
            profs = profiles_mod.list_profiles(self.mc_dir)
            default_name = profs[0]["name"] if profs else ""
        CustomizationDialog(
            self.mc_dir, self.theme, default_name,
            self.online, self).exec()


# ═══════════════════════════════════════════════════════════════
#  SplashScreen — заставка при запуске лаунчера
# ═══════════════════════════════════════════════════════════════

class SplashScreen(QWidget):
    """Безрамочная заставка с крутящимся item (easy-out)."""

    def __init__(self, theme: dict, item_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.item_pix = item_pixmap
        self._angle = 0.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 360)

        try:
            scr = QApplication.primaryScreen().geometry()
            self.move((scr.width() - self.width()) // 2,
                      (scr.height() - self.height()) // 2)
        except Exception:
            pass

        import time as _t
        self._t_mod = _t
        self._start_ms = _t.time() * 1000
        self._tm = QTimer(self)
        self._tm.timeout.connect(self._tick)
        self._tm.start(16)

    def _tick(self):
        elapsed = (self._t_mod.time() * 1000 - self._start_ms) / 1000.0
        if elapsed < 1.4:
            t = elapsed / 1.4
            ease = 1 - (1 - t) ** 3
            self._angle = ease * 540
        else:
            self._angle = 540 + (elapsed - 1.4) * 60
        self.update()

    def paintEvent(self, _e):
        from PyQt6.QtGui import QTransform, QRadialGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() // 2
        cy = self.height() // 2
        radius = 130

        glow = QRadialGradient(cx, cy, radius + 40)
        r, g, b = self.theme["glow_rgb"]
        glow.setColorAt(0.0, QColor(r, g, b, 110))
        glow.setColorAt(0.6, QColor(r, g, b, 30))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - radius - 40, cy - radius - 40,
                              (radius + 40) * 2, (radius + 40) * 2))

        if not self.item_pix.isNull():
            tr = QTransform()
            tr.translate(cx, cy)
            tr.rotate(self._angle)
            tr.translate(-self.item_pix.width() / 2,
                         -self.item_pix.height() / 2)
            p.setTransform(tr)
            p.drawPixmap(0, 0, self.item_pix)
            p.resetTransform()

        p.setPen(QColor(self.theme["accent"]))
        f = QFont(F(), 14, QFont.Weight.Bold)
        p.setFont(f)
        text_rect = QRectF(0, cy + radius + 10, self.width(), 30)
        p.drawText(text_rect, int(Qt.AlignmentFlag.AlignCenter), "Exelent Launcher")

        f2 = QFont(F(), 9)
        p.setFont(f2)
        p.setPen(QColor(self.theme["text_dim"]))
        text_rect2 = QRectF(0, cy + radius + 38, self.width(), 20)
        p.drawText(text_rect2, int(Qt.AlignmentFlag.AlignCenter), "загрузка...")

        p.end()


# ═══════════════════════════════════════════════════════════════
#  FakeProgressTimer — медленная имитация загрузки 0 -> max_pct
# ═══════════════════════════════════════════════════════════════

class FakeProgressTimer(QTimer):
    """
    Имитирует плавную загрузку. Полезно для Fabric, который реальный
    прогресс почти не отдаёт (висит на 5% и резко 100%).
    """

    def __init__(self, progress_widget, max_pct: int = 88,
                 target_seconds: float = 60.0, parent=None):
        super().__init__(parent)
        self.pw = progress_widget
        self.max_pct = max_pct
        self.duration = target_seconds
        self._t0 = None
        self._real_pct = None
        self._cur_val = 0
        self.timeout.connect(self._tick)

    def current_value(self) -> int:
        return self._cur_val

    def start_fake(self):
        import time as _t
        self._t0 = _t.time()
        self._real_pct = None
        self._cur_val = 0
        try:
            self.pw.setValue(0)
        except Exception:
            pass
        self.start(60)  # 60ms тик — более плавно

    def set_real(self, pct: int):
        new = max(0, min(100, int(pct)))
        # Никогда не идём назад
        if new < self._cur_val:
            return
        self._real_pct = new
        self._cur_val = new
        try:
            self.pw.setValue(new)
        except Exception:
            pass

    def finish(self):
        self._cur_val = 100
        try:
            self.pw.setValue(100)
        except Exception:
            pass
        self.stop()

    def _tick(self):
        # Если был set_real — продолжаем плавно от него к max_pct
        import time as _t
        if self._t0 is None:
            return
        elapsed = _t.time() - self._t0
        t = min(1.0, elapsed / self.duration)
        # Easy-out квадратичный — медленнее в конце
        ease = 1 - (1 - t) ** 2
        fake_val = int(ease * self.max_pct)
        # Берём максимум из fake и реального — не идём назад
        target = max(fake_val, self._cur_val)
        if self._real_pct is not None:
            target = max(target, self._real_pct)
        if target != self._cur_val:
            self._cur_val = target
            try:
                self.pw.setValue(target)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════

def main():
    set_windows_app_id()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    load_custom_font()
    app.setFont(get_font(10))

    try:
        themes_mod.ensure_builtin_assets()
    except Exception:
        pass

    # ── Splash с крутящимся item ──
    cfg = load_config()
    theme = themes_mod.get_theme(
        cfg.get("theme", "emerald"), cfg.get("custom_colors", {}))
    try:
        item_pix = themes_mod.get_item_pixmap(
            cfg.get("item", "emerald"), 160)
    except Exception:
        item_pix = QPixmap()

    splash = SplashScreen(theme, item_pix)
    splash.show()
    app.processEvents()

    w = LauncherWindow()

    # Минимум 1.2 сек показываем splash чтобы анимация была видна
    def _show_main():
        w.show()
        splash.close()

    QTimer.singleShot(1200, _show_main)

    if os.environ.get("EXELENT_SCREENSHOT") == "1":
        QTimer.singleShot(2600, lambda: (
            w.grab().save(str(APP_DIR / "screenshot.png")),
            print("Saved screenshot.png"),
        ))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
