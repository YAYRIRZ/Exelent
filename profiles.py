"""Управление custom-профилями (модификациями).

Каждый профиль хранит свою папку с модами/текстурпаками/шейдерами,
чтобы не смешивать моды от разных версий/сборок.

Структура:
  <mc_dir>/profiles/<name>/
        profile.json             {name, base, loader, created_at, ...}
        mods/
        resourcepacks/
        shaderpacks/

profile.json — единственный источник правды по типу лоадера и MC-версии.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


PROFILES_DIRNAME = "profiles"


def profiles_root(mc_dir: Path) -> Path:
    return Path(mc_dir) / PROFILES_DIRNAME


def list_profiles(mc_dir: Path) -> list[dict]:
    """Возвращает список профилей с метаданными (отсортирован по name)."""
    root = profiles_root(mc_dir)
    if not root.exists():
        return []
    out: list[dict] = []
    for d in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir():
            continue
        meta = read_profile(d)
        if meta:
            out.append(meta)
    return out


def read_profile(profile_dir: Path) -> dict | None:
    """Читает profile.json. Возвращает dict или None если нет."""
    f = profile_dir / "profile.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        # обогащаем путём
        data["_path"] = str(profile_dir)
        data.setdefault("name", profile_dir.name)
        data.setdefault("base", "")
        data.setdefault("loader", "vanilla")
        return data
    except Exception:
        return None


def get_profile(mc_dir: Path, name: str) -> dict | None:
    """По имени профиля → его метаданные."""
    p = profiles_root(mc_dir) / name
    return read_profile(p) if p.is_dir() else None


def profile_dir(mc_dir: Path, name: str) -> Path:
    return profiles_root(mc_dir) / name


def mods_dir(mc_dir: Path, name: str) -> Path:
    d = profile_dir(mc_dir, name) / "mods"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resourcepacks_dir(mc_dir: Path, name: str) -> Path:
    d = profile_dir(mc_dir, name) / "resourcepacks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def shaderpacks_dir(mc_dir: Path, name: str) -> Path:
    d = profile_dir(mc_dir, name) / "shaderpacks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_name(raw: str) -> str:
    cleaned = "".join(c for c in raw.strip()
                      if c.isalnum() or c in "._- ").strip()
    cleaned = cleaned.replace(" ", "_")
    return cleaned[:64]


def create_profile(mc_dir: Path, name: str, base_version: str,
                   loader: str, version_id: str) -> dict:
    """
    Создаёт папку профиля + profile.json.
      • name         — отображаемое имя
      • base_version — оригинальная MC-версия (1.21.4, 1.20.1 ...)
      • loader       — "fabric" / "vanilla" (можно расширить)
      • version_id   — ID версии в Minecraft (то что в .minecraft/versions/)
                       — для fabric это что-то типа "fabric-loader-0.16.0-1.21.4"
                       — для vanilla = base_version
    """
    name = sanitize_name(name)
    if not name:
        raise ValueError("Пустое имя профиля")

    root = profile_dir(mc_dir, name)
    if root.exists():
        raise FileExistsError(f"Профиль {name} уже существует")

    root.mkdir(parents=True, exist_ok=True)
    (root / "mods").mkdir(exist_ok=True)
    (root / "resourcepacks").mkdir(exist_ok=True)
    (root / "shaderpacks").mkdir(exist_ok=True)

    meta = {
        "name":         name,
        "base":         base_version,
        "loader":       loader,
        "version_id":   version_id,
        "created_at":   int(time.time()),
    }
    (root / "profile.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    meta["_path"] = str(root)
    return meta


def delete_profile(mc_dir: Path, name: str) -> None:
    import shutil
    p = profile_dir(mc_dir, name)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def supports_mods(profile: dict) -> bool:
    """Моды поддерживают только лоадеры (fabric/forge/quilt/neoforge)."""
    return (profile or {}).get("loader", "vanilla").lower() in (
        "fabric", "forge", "quilt", "neoforge")


def has_any_profile(mc_dir: Path) -> bool:
    root = profiles_root(mc_dir)
    if not root.exists():
        return False
    for d in root.iterdir():
        if d.is_dir() and (d / "profile.json").exists():
            return True
    return False
