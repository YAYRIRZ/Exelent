"""Темы и items (иконки лаунчера) для Exelent Launcher.

Items — это ПРЕДМЕТЫ (apple, iron_sword, diamond, emerald и т.д.),
которые лаунчер показывает как свою иконку.

Текстуры берутся из РЕАЛЬНЫХ assets/mc/ (упакованных через build_windows.py).
Поддерживаются ЛЮБЫЕ структуры папки:
  • assets/mc/textures/item/<file>.png   (полный путь)
  • assets/mc/item/<file>.png            (короткий)
  • assets/mc/<file>.png                 (плоский)
  • рекурсивный поиск по basename        (last resort)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QPainter, QPixmap, QGuiApplication
from PyQt6.QtSvg import QSvgRenderer

from icons import SVG as _SVG_DICT


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


APP_DIR    = _app_dir()
ASSETS_DIR = APP_DIR / "assets"
ITEMS_DIR  = ASSETS_DIR / "items"
MC_ASSETS  = ASSETS_DIR / "mc"


# ═══════════════════════════════════════════════════════════════
#  ТЕМЫ
# ═══════════════════════════════════════════════════════════════

def _T(name, accent, accent_light, primary, primary_dark,
       bg_dark, bg_panel, bg_panel2, text="#e8eef0", text_dim="#8a9098",
       glow=None, error="#ff5566", rainbow=False) -> dict:
    if glow is None:
        c = accent.lstrip("#")
        glow = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    return {
        "name": name,
        "accent": accent,
        "accent_light": accent_light,
        "primary": primary,
        "primary_dark": primary_dark,
        "bg_dark": bg_dark,
        "bg_panel": bg_panel,
        "bg_panel2": bg_panel2,
        "text": text,
        "text_dim": text_dim,
        "glow_rgb": glow,
        "error": error,
        "rainbow": rainbow,
    }


THEMES: dict[str, dict] = {
    "emerald":   _T("Emerald",   "#3ddc84", "#7af0a8", "#1f7a4d", "#155634",
                    "#070d09", "#0d1813", "#13231b"),
    "diamond":   _T("Diamond",   "#5cd6e0", "#9bedf2", "#2a8a99", "#155760",
                    "#070d10", "#0d1820", "#12222b"),
    "ruby":      _T("Ruby",      "#ff4060", "#ff7d95", "#a01030", "#660820",
                    "#0d0608", "#180a0e", "#220d14"),
    "amethyst":  _T("Amethyst",  "#b574ff", "#d4a8ff", "#6a30b5", "#3f1d6e",
                    "#0a0712", "#15101f", "#1f1830"),
    "gold":      _T("Gold",      "#ffc740", "#ffe089", "#a87a10", "#6b4a08",
                    "#100c05", "#1c1608", "#2a210d"),
    "iron":      _T("Iron",      "#c0c8d0", "#e6ebef", "#7a8088", "#4a4f56",
                    "#0a0b0d", "#161819", "#22262a"),
    "copper":    _T("Copper",    "#e07a4a", "#f0a878", "#a04020", "#661f0e",
                    "#0d0805", "#1a100a", "#241810"),
    "lapis":     _T("Lapis",     "#3a78ff", "#7ba5ff", "#1d40a8", "#0e2470",
                    "#05070d", "#0c1020", "#10162e"),
    "redstone":  _T("Redstone",  "#ff3030", "#ff7a7a", "#a01010", "#660808",
                    "#0c0606", "#1a0c0c", "#241010"),
    "netherite": _T("Netherite", "#7a6b73", "#a89aa1", "#42363c", "#251c21",
                    "#080607", "#13101a", "#1a1620",
                    text="#d8ccd2", text_dim="#827078"),
    "ocean":     _T("Ocean",     "#00bcd4", "#80deea", "#00838f", "#005662",
                    "#03161a", "#0a2329", "#10333a"),
    "forest":    _T("Forest",    "#66bb6a", "#a5d6a7", "#388e3c", "#1b5e20",
                    "#080d09", "#101810", "#162018"),
    "sunset":    _T("Sunset",    "#ff8a3c", "#ffb87a", "#d05a00", "#7d2f00",
                    "#0d0805", "#180e08", "#22150e"),
    "midnight":  _T("Midnight",  "#7986cb", "#aab6f0", "#3949ab", "#1a237e",
                    "#040510", "#0a0d1c", "#101428"),
    "rose":      _T("Rose",      "#ff5d8f", "#ff9bbf", "#c91e5e", "#7d0e3a",
                    "#0d0608", "#180a10", "#221018"),
    "neon":      _T("Neon",      "#39ff14", "#aaff80", "#1aa006", "#0e5a04",
                    "#000400", "#001000", "#001a05"),
    "mono":      _T("Mono",      "#ffffff", "#e0e0e0", "#888888", "#555555",
                    "#0a0a0a", "#141414", "#1f1f1f",
                    text="#f0f0f0", text_dim="#7a7a7a"),
    "obsidian":  _T("Obsidian",  "#9c64ff", "#c094ff", "#5a2db8", "#321861",
                    "#040208", "#0e0716", "#160c22"),
    "void":      _T("Void",      "#e040fb", "#ea80fc", "#9c27b0", "#6a1b9a",
                    "#06030a", "#100619", "#180a23"),
    "honey":     _T("Honey",     "#ffd54f", "#fff176", "#fbc02d", "#f57f17",
                    "#100b03", "#1d1505", "#2a1f08"),
    "ice":       _T("Ice",       "#b3e5fc", "#e1f5fe", "#4fc3f7", "#0288d1",
                    "#06101a", "#0c1a28", "#13263a"),
    "ender":     _T("Ender",     "#1de9b6", "#84ffff", "#00897b", "#004d40",
                    "#020a08", "#0a1612", "#10211c"),
    "rainbow":   _T("Rainbow",   "#ff66cc", "#ffaaff", "#aa55ff", "#552288",
                    "#070710", "#10101e", "#1a1a2c", rainbow=True),
}


def get_theme(theme_id: str, custom_colors: dict | None = None) -> dict:
    if theme_id == "custom":
        base = dict(THEMES["emerald"])
        if custom_colors:
            for k, v in custom_colors.items():
                if v and isinstance(v, str):
                    base[k] = v
            if "accent" in custom_colors and custom_colors["accent"]:
                try:
                    c = custom_colors["accent"].lstrip("#")
                    base["glow_rgb"] = (
                        int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
                except Exception:
                    pass
        base["name"] = "Custom"
        return base
    return dict(THEMES.get(theme_id, THEMES["emerald"]))


# ═══════════════════════════════════════════════════════════════
#  ITEMS — все на ПРЕДМЕТАХ (textures/item/*.png)
# ═══════════════════════════════════════════════════════════════
# Где у предмета нет item-варианта (TNT, Obsidian, Glowstone) —
# используем блок.
# ═══════════════════════════════════════════════════════════════

ITEMS: dict[str, dict] = {
    # Драгоценности / руды
    "emerald":         {"name": "Изумруд",         "mc_texture": "textures/item/emerald.png"},
    "diamond":         {"name": "Алмаз",           "mc_texture": "textures/item/diamond.png"},
    "gold":            {"name": "Золотой слиток",  "mc_texture": "textures/item/gold_ingot.png"},
    "iron":            {"name": "Железный слиток", "mc_texture": "textures/item/iron_ingot.png"},
    "netherite":       {"name": "Незеритовый слиток", "mc_texture": "textures/item/netherite_ingot.png"},
    "redstone":        {"name": "Красная пыль",    "mc_texture": "textures/item/redstone.png"},
    "lapis":           {"name": "Лазурит",         "mc_texture": "textures/item/lapis_lazuli.png"},
    "amethyst":        {"name": "Аметист",         "mc_texture": "textures/item/amethyst_shard.png"},
    "copper":          {"name": "Медный слиток",   "mc_texture": "textures/item/copper_ingot.png"},
    "quartz":          {"name": "Кварц",           "mc_texture": "textures/item/quartz.png"},

    # Оружие / инструменты
    "iron_sword":      {"name": "Железный меч",    "mc_texture": "textures/item/iron_sword.png"},
    "diamond_sword":   {"name": "Алмазный меч",    "mc_texture": "textures/item/diamond_sword.png"},
    "netherite_sword": {"name": "Незеритовый меч", "mc_texture": "textures/item/netherite_sword.png"},
    "golden_sword":    {"name": "Золотой меч",     "mc_texture": "textures/item/golden_sword.png"},
    "iron_pickaxe":    {"name": "Железная кирка",  "mc_texture": "textures/item/iron_pickaxe.png"},
    "diamond_pickaxe": {"name": "Алмазная кирка",  "mc_texture": "textures/item/diamond_pickaxe.png"},
    "iron_axe":        {"name": "Железный топор",  "mc_texture": "textures/item/iron_axe.png"},
    "bow":             {"name": "Лук",             "mc_texture": "textures/item/bow.png"},

    # Броня
    "iron_helmet":      {"name": "Железный шлем",     "mc_texture": "textures/item/iron_helmet.png"},
    "diamond_helmet":   {"name": "Алмазный шлем",     "mc_texture": "textures/item/diamond_helmet.png"},
    "netherite_helmet": {"name": "Незеритовый шлем",  "mc_texture": "textures/item/netherite_helmet.png"},
    "shield":           {"name": "Щит",               "mc_texture": "textures/item/shield.png"},

    # Еда
    "apple":             {"name": "Яблоко",                "mc_texture": "textures/item/apple.png"},
    "golden_apple":      {"name": "Золотое яблоко",        "mc_texture": "textures/item/golden_apple.png"},
    "enchanted_apple":   {"name": "Заколдованное яблоко",  "mc_texture": "textures/item/enchanted_golden_apple.png"},
    "bread":             {"name": "Хлеб",                  "mc_texture": "textures/item/bread.png"},
    "cake":              {"name": "Торт",                  "mc_texture": "textures/item/cake.png"},
    "cooked_beef":       {"name": "Жареная говядина",      "mc_texture": "textures/item/cooked_beef.png"},

    # Магия и эндер
    "ender_pearl":     {"name": "Эндер-жемчуг",    "mc_texture": "textures/item/ender_pearl.png"},
    "ender_eye":       {"name": "Глаз эндера",     "mc_texture": "textures/item/ender_eye.png"},
    "nether_star":     {"name": "Незеритовая звезда", "mc_texture": "textures/item/nether_star.png"},
    "totem":           {"name": "Тотем бессмертия", "mc_texture": "textures/item/totem_of_undying.png"},
    "dragon_breath":   {"name": "Дыхание дракона", "mc_texture": "textures/item/dragon_breath.png"},

    # Утилиты
    "compass":         {"name": "Компас",          "mc_texture": "textures/item/compass_00.png"},
    "clock":           {"name": "Часы",            "mc_texture": "textures/item/clock_00.png"},
    "book":            {"name": "Книга",           "mc_texture": "textures/item/book.png"},
    "enchanted_book":  {"name": "Зачарованная книга", "mc_texture": "textures/item/enchanted_book.png"},
    "map":             {"name": "Карта",           "mc_texture": "textures/item/map.png"},
    "spyglass":        {"name": "Подзорная труба", "mc_texture": "textures/item/spyglass.png"},

    # Блоки (только те у которых нет item-формы)
    "obsidian":  {"name": "Обсидиан",  "mc_texture": "textures/block/obsidian.png"},
    "glowstone": {"name": "Светокамень", "mc_texture": "textures/block/glowstone.png"},
    "tnt":       {"name": "ТНТ",       "mc_texture": "textures/block/tnt_side.png"},
    "grass":     {"name": "Трава",     "mc_texture": "textures/block/grass_block_top.png"},

    # Кастом
    "custom":    {"name": "Своя (URL)", "mc_texture": ""},
}


# ═══════════════════════════════════════════════════════════════
#  Файловая система
# ═══════════════════════════════════════════════════════════════

def _qt_ready() -> bool:
    try:
        return QGuiApplication.instance() is not None
    except Exception:
        return False


def find_mc_texture(rel: str) -> Path | None:
    """
    Ищет файл текстуры MC в нескольких возможных местах.
    rel — относительный путь как в minecraft.jar:
          'textures/item/diamond.png' или 'textures/block/diamond_block.png'
    """
    if not rel:
        return None
    rel = rel.replace("\\", "/").lstrip("/")
    basename = Path(rel).name

    candidates = []
    candidates.append(MC_ASSETS / rel)
    if rel.startswith("textures/"):
        candidates.append(MC_ASSETS / rel[len("textures/"):])
    candidates.append(MC_ASSETS / basename)

    for c in candidates:
        try:
            if c.is_file() and c.stat().st_size > 32:
                return c
        except Exception:
            continue

    # Рекурсивный поиск (медленно, но даст результат)
    if MC_ASSETS.exists():
        try:
            for f in MC_ASSETS.rglob(basename):
                if f.is_file() and f.stat().st_size > 32:
                    return f
        except Exception:
            pass
    return None


def square_crop_top(pix: QPixmap) -> QPixmap:
    """Берёт верхний квадрат для анимированных PNG (16x32 → 16x16)."""
    if pix.isNull():
        return pix
    w, h = pix.width(), pix.height()
    if w == h or w <= 0 or h <= 0:
        return pix
    side = min(w, h)
    return pix.copy(0, 0, side, side)


def load_mc_pixmap(rel: str, size: int = 256,
                   pixel_art: bool = True) -> QPixmap | None:
    """
    Главная функция: грузит PNG-текстуру Minecraft и возвращает QPixmap
    нужного размера, обработанный как пиксель-арт (NearestNeighbor + crop_top).
    Возвращает None если не нашли.
    """
    if not _qt_ready():
        return None
    src = find_mc_texture(rel)
    if src is None:
        return None
    try:
        pix = QPixmap(str(src))
        if pix.isNull():
            return None
        pix = square_crop_top(pix)
        mode = (Qt.TransformationMode.FastTransformation if pixel_art
                else Qt.TransformationMode.SmoothTransformation)
        # IgnoreAspectRatio чтобы ТОЧНО квадрат на выходе
        return pix.scaled(size, size,
                          Qt.AspectRatioMode.IgnoreAspectRatio,
                          mode)
    except Exception:
        return None


def _save_pixmap_png(pix: QPixmap, target: Path) -> bool:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        return pix.save(str(target), "PNG")
    except Exception:
        return False


def ensure_builtin_assets() -> None:
    """
    Генерирует PNG-иконки items из реальных MC-текстур.
    Никаких SVG-заглушек — если текстуры нет, файл не создаётся.
    Вызывать ТОЛЬКО после QApplication.
    """
    if not _qt_ready():
        return
    try:
        ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    for iid, info in ITEMS.items():
        if iid == "custom":
            continue
        target = ITEMS_DIR / f"{iid}.png"
        if target.exists() and target.stat().st_size > 200:
            continue

        rel = info.get("mc_texture", "")
        if not rel:
            continue
        pix = load_mc_pixmap(rel, 256, pixel_art=True)
        if pix is not None:
            _save_pixmap_png(pix, target)


def get_item_path(item_id: str) -> Path:
    """
    Путь к PNG предмета. Всегда возвращает Path; если файла нет — пытается
    создать на лету. Не использует SVG.
    """
    target = ITEMS_DIR / f"{item_id}.png"
    if target.exists():
        return target
    info = ITEMS.get(item_id)
    if not info or not _qt_ready():
        return target
    rel = info.get("mc_texture", "")
    if rel:
        pix = load_mc_pixmap(rel, 256, pixel_art=True)
        if pix is not None:
            _save_pixmap_png(pix, target)
    return target


def get_item_pixmap(item_id: str, size: int = 256) -> QPixmap:
    """
    Возвращает QPixmap для item напрямую (без записи в файл).
    Гарантирует ровный квадрат size×size с пиксельным апскейлом.
    Если ничего нет — возвращает пустой QPixmap.
    """
    info = ITEMS.get(item_id) or ITEMS["emerald"]
    rel = info.get("mc_texture", "")
    if rel:
        pix = load_mc_pixmap(rel, size, pixel_art=True)
        if pix is not None:
            return pix
    # Последний шанс — взять уже созданный файл из items/
    f = ITEMS_DIR / f"{item_id}.png"
    if f.exists():
        try:
            p = QPixmap(str(f))
            if not p.isNull():
                return p.scaled(size, size,
                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.FastTransformation)
        except Exception:
            pass
    return QPixmap()


def download_custom_icon(url: str) -> bool:
    """Скачивает иконку и сохраняет как assets/items/custom.png."""
    import urllib.request
    try:
        ITEMS_DIR.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            url, headers={"User-Agent": "ExelentLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if len(data) < 32:
            return False
        (ITEMS_DIR / "custom.png").write_bytes(data)
        return True
    except Exception:
        return False


def refresh_items_from_mc_assets() -> int:
    """Принудительно перегенерировать все items. Возвращает кол-во обновлённых."""
    if not _qt_ready():
        return 0
    count = 0
    try:
        ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return 0
    for iid, info in ITEMS.items():
        if iid == "custom":
            continue
        rel = info.get("mc_texture", "")
        if not rel:
            continue
        pix = load_mc_pixmap(rel, 256, pixel_art=True)
        if pix is None:
            continue
        target = ITEMS_DIR / f"{iid}.png"
        if _save_pixmap_png(pix, target):
            count += 1
    return count
