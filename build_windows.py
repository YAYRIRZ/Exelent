"""Сборка Exelent Launcher в .exe через PyInstaller.

Что делает:
  1. Готовит assets/mc/ — копирует туда содержимое папки
     mc-assets-1.21.4/ (если она есть рядом). После этого все текстуры
     Minecraft (item/*.png, block/*.png и т.д.) будут ВНУТРИ EXE.
  2. Генерирует assets/items/<id>.png из MC-текстур (для иконок лаунчера).
  3. Делает emerald.ico → diamond.ico (для иконки .exe).
  4. Запускает PyInstaller с --add-data assets;assets — всё попадает в сборку.
  5. После 1-го запуска у пользователя СРАЗУ есть готовые иконки items,
     даже до того как установщик что-то скачает.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT       = Path(__file__).parent.resolve()
ASSETS     = ROOT / "assets"
ITEMS_DIR  = ASSETS / "items"
MC_DIR     = ASSETS / "mc"          # сюда копируются MC-текстуры
DIST       = ROOT / "dist" / "Exelent Launcher"
ICON_NAME  = "emerald.ico"          # иконка .exe
ICON       = ITEMS_DIR / ICON_NAME
REQ        = ROOT / "requirements.txt"

# Источники MC-текстур — пробуем несколько вариантов
MC_ASSETS_CANDIDATES = [
    ROOT / "mc-assets-1.21.4",                          # рядом со скриптом (твой случай)
    ROOT / "mc-assets",
    ROOT.parent / "mc-assets-1.21.4",                   # на уровень выше
]


# ═══════════════════════════════════════════════════════════════
#  Утилиты
# ═══════════════════════════════════════════════════════════════

def run(cmd: list[str], title: str) -> None:
    print(f"\n=== {title} ===")
    print(" ".join(map(str, cmd)))
    p = subprocess.run(cmd, cwd=str(ROOT), text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(p.stdout)
    if p.returncode != 0:
        raise SystemExit(
            f"\n[ERROR] {title}\n"
            f"Код возврата: {p.returncode}\n"
            f"Смотрите вывод выше.\n"
        )


# ═══════════════════════════════════════════════════════════════
#  1. Подготовка assets/mc/ из mc-assets-1.21.4/
# ═══════════════════════════════════════════════════════════════

def prepare_mc_assets() -> bool:
    """
    Копирует все текстуры из mc-assets-1.21.4/ в assets/mc/.
    Сохраняет полную структуру (textures/item/..., textures/block/...).
    Возвращает True если что-то скопировано.
    """
    src_dir: Path | None = None
    for cand in MC_ASSETS_CANDIDATES:
        if cand.exists() and cand.is_dir():
            # Проверяем что внутри есть текстуры
            has_textures = any(cand.rglob("*.png"))
            if has_textures:
                src_dir = cand
                break

    if src_dir is None:
        print("[MC] Папка с MC-ассетами не найдена. Искал:")
        for c in MC_ASSETS_CANDIDATES:
            print(f"     {c}")
        print("[MC] Положи mc-assets-1.21.4/ рядом со скриптом и пересобери.")
        print("[MC] Сборка продолжится без MC-текстур (будут белые квадраты).")
        return False

    print(f"[MC] Источник: {src_dir}")
    print(f"[MC] Назначение: {MC_DIR}")

    # Чистим старое содержимое assets/mc/
    if MC_DIR.exists():
        shutil.rmtree(MC_DIR, ignore_errors=True)
    MC_DIR.mkdir(parents=True, exist_ok=True)

    # Определяем структуру src_dir:
    #   Если внутри сразу 'textures/' — копируем как есть
    #   Если 'mc-assets-1.21.4/textures/...' — копируем содержимое
    if (src_dir / "textures").is_dir():
        # Уже корень
        copy_root = src_dir
    else:
        # Возможно лежит ещё одна обёртка
        subs = [d for d in src_dir.iterdir()
                if d.is_dir() and (d / "textures").is_dir()]
        copy_root = subs[0] if subs else src_dir

    copied = 0
    for f in copy_root.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(copy_root)
        target = MC_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(f, target)
            copied += 1
        except Exception as ex:
            print(f"[MC] WARN: не скопировано {rel}: {ex}")

    print(f"[MC] Скопировано файлов: {copied}")
    return copied > 0


# ═══════════════════════════════════════════════════════════════
#  2. Генерация PNG-иконок items из MC-текстур
# ═══════════════════════════════════════════════════════════════

def generate_items() -> int:
    """
    Запускает themes.ensure_builtin_assets() через мини-Qt-приложение.
    Это создаст файлы assets/items/<id>.png из реальных MC-текстур.
    Возвращает кол-во созданных файлов.
    """
    print(f"\n=== Генерация иконок items в {ITEMS_DIR} ===")
    try:
        # Запускаем в отдельном процессе чтобы не тащить Qt в build-скрипт
        helper = ROOT / "_build_gen_items.py"
        helper.write_text('''
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from PyQt6.QtWidgets import QApplication
import themes as themes_mod
app = QApplication([])
themes_mod.ensure_builtin_assets()
# Считаем сколько файлов в итоге
items_dir = themes_mod.ITEMS_DIR
files = [f for f in items_dir.glob("*.png") if f.stat().st_size > 200]
print(f"[items] Готово, файлов: {len(files)}")
for f in files:
    print(f"  {f.name}  ({f.stat().st_size//1024} KB)")
''', encoding="utf-8")
        run([sys.executable, str(helper)], "Генерация items.png")
        try:
            helper.unlink()
        except Exception:
            pass
        return sum(1 for f in ITEMS_DIR.glob("*.png")
                   if f.stat().st_size > 200)
    except Exception as ex:
        print(f"[items] Ошибка генерации: {ex}")
        return 0


# ═══════════════════════════════════════════════════════════════
#  3. Создание .ico для иконки .exe
# ═══════════════════════════════════════════════════════════════

def ensure_ico() -> None:
    """Конвертируем emerald.png → emerald.ico (для иконки .exe)."""
    png = ITEMS_DIR / "emerald.png"
    if ICON.exists():
        print(f"[ICO] Уже существует: {ICON}")
        return
    if not png.exists():
        # Если emerald.png ещё нет — пробуем diamond.png
        png = ITEMS_DIR / "diamond.png"
        if not png.exists():
            print(f"[ICO] Нет ни emerald.png, ни diamond.png в {ITEMS_DIR}")
            return
    try:
        from PIL import Image
        img = Image.open(png).convert("RGBA")
        ICON.parent.mkdir(parents=True, exist_ok=True)
        img.save(ICON, format="ICO",
                 sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
        print(f"[ICO] Создан: {ICON}")
    except Exception as ex:
        print(f"[ICO] Не удалось создать (сборка продолжится без иконки): {ex}")


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    if not REQ.exists():
        raise SystemExit(f"Не найден requirements.txt: {REQ}")

    # 1. Обновляем pip
    run([sys.executable, "-m", "pip", "install", "--upgrade",
         "pip", "setuptools", "wheel"],
        "Обновление pip")

    # 2. Зависимости
    run([sys.executable, "-m", "pip", "install", "-r", str(REQ)],
        "Установка зависимостей")

    # 3. PyInstaller
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"],
        "Установка PyInstaller")

    # 4. Pillow для .ico
    run([sys.executable, "-m", "pip", "install", "--upgrade", "Pillow"],
        "Установка Pillow")

    # 5. Готовим MC-ассеты в assets/mc/
    prepare_mc_assets()

    # 6. Генерируем PNG-иконки items из MC-ассетов
    n_items = generate_items()
    print(f"\n[BUILD] Готовых items: {n_items}")

    # 7. .ico для exe
    ensure_ico()

    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "Exelent Launcher",

        "--hidden-import", "PyQt6.QtSvg",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "minecraft_launcher_lib",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        # Наши модули — на всякий случай
        "--hidden-import", "profiles",
        "--hidden-import", "widgets",
        "--hidden-import", "themes",
        "--hidden-import", "icons",

        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
    ]

    # КЛЮЧЕВОЕ: добавляем assets целиком (включая mc/items/...)
    if ASSETS.exists():
        cmd += ["--add-data", f"{ASSETS}{sep}assets"]
        print(f"[BUILD] Включаю в EXE: {ASSETS}")
    else:
        print(f"[BUILD] WARN: папка assets не найдена!")

    if ICON.exists():
        cmd += ["--icon", str(ICON)]

    # Шрифты
    fonts_dir = ROOT / "fonts"
    if fonts_dir.exists() and list(fonts_dir.glob("*.ttf")):
        cmd += ["--add-data", f"{fonts_dir}{sep}fonts"]

    # Точка входа
    cmd += [str(ROOT / "main.py")]

    run(cmd, "Сборка PyInstaller")

    exe = DIST / "Exelent Launcher.exe"
    if exe.exists():
        size_mb = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1024 / 1024
        print(f"\n[OK] Сборка завершена!")
        print(f"     EXE:  {exe}")
        print(f"     Размер папки: {size_mb:.1f} MB")
        # Проверяем что MC-ассеты тоже попали
        check = DIST / "_internal" / "assets" / "mc" / "textures" / "item" / "emerald.png"
        if check.exists():
            print(f"[OK] MC-текстуры в сборке: {check.parent.parent}")
        else:
            print(f"[WARN] MC-текстуры не нашёл в сборке: {check}")
        print(f"\nДля установки запустите EXE напрямую (он установщик при 1-м запуске).")
    else:
        print(f"\n[ERROR] EXE не найден: {exe}")
        print("Проверьте папку dist/")


if __name__ == "__main__":
    main()
