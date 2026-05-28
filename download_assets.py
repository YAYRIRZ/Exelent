"""
download_assets.py — отдельный скрипт для скачивания ассетов Minecraft.

Запуск:
    python download_assets.py

Что делает:
    1. Скачивает текстуры с https://assets.mcasset.cloud/<MC_VERSION>/...
    2. Сохраняет в папку  ./mc-assets-<MC_VERSION>/
    3. Упаковывает в      ./mc-assets-<MC_VERSION>.zip
    4. После проверки можно загрузить на GitHub:
       https://github.com/<твой_логин>/<репо>/releases  (или просто положить
       в репозиторий)

Файлы скачиваются те же, что и установщик кладёт в установленный лаунчер.
Можно менять MC_VERSION ниже.
"""
from __future__ import annotations

import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


MC_VERSION = "1.21.4"
BASE_URL   = f"https://assets.mcasset.cloud/{MC_VERSION}/assets/minecraft"

OUT_DIR    = Path(__file__).parent.resolve() / f"mc-assets-{MC_VERSION}"
ZIP_PATH   = Path(__file__).parent.resolve() / f"mc-assets-{MC_VERSION}.zip"


# Список текстур (синхронизирован с installer.py)
ASSET_FILES: list[str] = [
    # Items
    "textures/item/iron_sword.png",
    "textures/item/diamond_sword.png",
    "textures/item/netherite_sword.png",
    "textures/item/golden_sword.png",
    "textures/item/wooden_sword.png",
    "textures/item/stone_sword.png",
    "textures/item/iron_pickaxe.png",
    "textures/item/diamond_pickaxe.png",
    "textures/item/netherite_pickaxe.png",
    "textures/item/iron_axe.png",
    "textures/item/diamond_axe.png",
    "textures/item/iron_shovel.png",
    "textures/item/bow.png",
    "textures/item/arrow.png",
    "textures/item/compass_00.png",
    "textures/item/clock_00.png",
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
    "textures/item/wheat.png",
    "textures/item/bread.png",
    "textures/item/apple.png",
    "textures/item/golden_apple.png",
    "textures/item/enchanted_golden_apple.png",
    "textures/item/cooked_beef.png",
    "textures/item/cooked_porkchop.png",
    "textures/item/cooked_chicken.png",
    "textures/item/cake.png",
    "textures/item/book.png",
    "textures/item/enchanted_book.png",
    "textures/item/writable_book.png",
    "textures/item/map.png",
    "textures/item/iron_helmet.png",
    "textures/item/iron_chestplate.png",
    "textures/item/iron_leggings.png",
    "textures/item/iron_boots.png",
    "textures/item/diamond_helmet.png",
    "textures/item/diamond_chestplate.png",
    "textures/item/diamond_leggings.png",
    "textures/item/diamond_boots.png",
    "textures/item/netherite_helmet.png",
    "textures/item/netherite_chestplate.png",
    "textures/item/netherite_leggings.png",
    "textures/item/netherite_boots.png",
    "textures/item/shield.png",
    "textures/item/totem_of_undying.png",
    "textures/item/ender_pearl.png",
    "textures/item/ender_eye.png",
    "textures/item/nether_star.png",
    "textures/item/dragon_breath.png",
    "textures/item/spyglass.png",
    "textures/item/recovery_compass_00.png",

    # Blocks
    "textures/block/furnace_front_on.png",
    "textures/block/furnace_front.png",
    "textures/block/furnace_side.png",
    "textures/block/furnace_top.png",
    "textures/block/crafting_table_front.png",
    "textures/block/crafting_table_side.png",
    "textures/block/crafting_table_top.png",
    "textures/block/diamond_block.png",
    "textures/block/iron_block.png",
    "textures/block/gold_block.png",
    "textures/block/emerald_block.png",
    "textures/block/redstone_block.png",
    "textures/block/redstone_ore.png",
    "textures/block/redstone_lamp.png",
    "textures/block/redstone_lamp_on.png",
    "textures/block/lapis_block.png",
    "textures/block/netherite_block.png",
    "textures/block/copper_block.png",
    "textures/block/amethyst_block.png",
    "textures/block/quartz_block_top.png",
    "textures/block/quartz_block_side.png",
    "textures/block/obsidian.png",
    "textures/block/glowstone.png",
    "textures/block/sea_lantern.png",
    "textures/block/end_stone.png",
    "textures/block/netherrack.png",
    "textures/block/grass_block_side.png",
    "textures/block/grass_block_top.png",
    "textures/block/dirt.png",
    "textures/block/stone.png",
    "textures/block/cobblestone.png",
    "textures/block/oak_planks.png",
    "textures/block/oak_log.png",
    "textures/block/oak_log_top.png",
    "textures/block/oak_leaves.png",
    "textures/block/bedrock.png",
    "textures/block/tnt_side.png",
    "textures/block/tnt_top.png",
    "textures/block/beacon.png",
    "textures/block/enchanting_table_top.png",
    "textures/block/ender_chest_front.png",
    "textures/block/anvil.png",
    "textures/block/anvil_top.png",
    "textures/block/loom_front.png",
    "textures/block/grindstone_pivot.png",
    "textures/block/stonecutter_top.png",
    "textures/block/cartography_table_top.png",

    # GUI
    "textures/gui/title/minecraft.png",
    "textures/gui/title/mojangstudios.png",

    # Misc
    "textures/misc/pumpkinblur.png",
    "textures/misc/vignette.png",
]


def download_one(url: str, target: Path, retries: int = 2,
                 timeout: float = 12.0) -> bool:
    """Скачивает один файл с ретраями. True если ОК."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ExelentLauncher-Asset-Downloader/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if len(data) < 32:
                raise RuntimeError("файл слишком маленький")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return True
        except urllib.error.HTTPError as e:
            print(f"  [HTTP {e.code}] {url}")
            return False  # 404 не имеет смысла ретраить
        except Exception as e:
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            print(f"  [FAIL] {url}: {e}")
            return False
    return False


def main() -> int:
    print(f"Скачивание ассетов Minecraft {MC_VERSION}")
    print(f"Источник:    {BASE_URL}")
    print(f"Папка:       {OUT_DIR}")
    print(f"ZIP:         {ZIP_PATH}")
    print(f"Файлов:      {len(ASSET_FILES)}")
    print("─" * 60)

    # Чистим старую папку
    if OUT_DIR.exists():
        print(f"Удаляю старую папку: {OUT_DIR}")
        shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0
    for i, rel in enumerate(ASSET_FILES, 1):
        url    = f"{BASE_URL}/{rel}"
        target = OUT_DIR / rel
        prefix = f"[{i:>3}/{len(ASSET_FILES):>3}]"
        if download_one(url, target):
            print(f"{prefix} OK   {rel}")
            ok += 1
        else:
            print(f"{prefix} FAIL {rel}")
            fail += 1

    print("─" * 60)
    print(f"Готово: ok={ok}  fail={fail}  total={len(ASSET_FILES)}")

    if ok == 0:
        print("Ничего не скачалось — ZIP создавать не буду.")
        return 1

    # Упаковываем в zip
    print(f"\nСоздаю архив: {ZIP_PATH}")
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in OUT_DIR.rglob("*"):
            if f.is_file():
                arc = f.relative_to(OUT_DIR.parent)  # включаем папку верхнего уровня
                zf.write(f, arc)

    size_mb = ZIP_PATH.stat().st_size / 1024 / 1024
    print(f"ZIP готов: {ZIP_PATH}  ({size_mb:.2f} MB)")
    print()
    print("Что делать дальше:")
    print(f"  1. Открой папку '{OUT_DIR.name}' и проверь текстуры — всё ли на месте.")
    print(f"  2. Можно загрузить '{ZIP_PATH.name}' на GitHub")
    print( "     (например в Releases твоего репозитория).")
    print(f"  3. Если структура другая — используй mcasset.cloud напрямую:")
    print(f"     https://assets.mcasset.cloud/{MC_VERSION}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
