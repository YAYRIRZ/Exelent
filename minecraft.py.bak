"""Интеграция с Minecraft: версии, установка, запуск, Fabric, Modrinth, портативная Java."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Any

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile


try:
    import minecraft_launcher_lib as mll
    HAS_MLL = True
except Exception:
    mll = None
    HAS_MLL = False


# ═══════════════════════════════════════════════════════════════
#  Mojang / версии
# ═══════════════════════════════════════════════════════════════

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

FALLBACK_RELEASES = [
    "1.21.5", "1.21.4", "1.21.3", "1.21.1", "1.21", "1.20.6", "1.20.4", "1.20.2", "1.20.1",
    "1.19.4", "1.19.2", "1.18.2", "1.17.1", "1.16.5", "1.12.2", "1.8.9", "1.7.10"
]


def fetch_version_list(include_snapshots: bool = False) -> list[dict]:
    try:
        with urllib.request.urlopen(MOJANG_MANIFEST_URL, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        versions = data.get("versions", [])
        if include_snapshots:
            return versions
        return [v for v in versions if v.get("type") == "release" and v.get("id", "").startswith("1.")]
    except Exception:
        return [{"id": v, "type": "release"} for v in FALLBACK_RELEASES]


def get_installed_versions(mc_dir: Path) -> set[str]:
    versions_dir = Path(mc_dir) / "versions"
    if not versions_dir.exists():
        return set()
    result: set[str] = set()
    for d in versions_dir.iterdir():
        if d.is_dir() and (d / f"{d.name}.json").exists():
            result.add(d.name)
    return result


def is_version_installed(mc_dir: Path, version: str) -> bool:
    return version in get_installed_versions(Path(mc_dir))


class _ProgressCallback:
    def __init__(self, cb: Callable[[int, str], None]):
        self.cb = cb
        self.max = 100
        self.value = 0
        self.status = "Подготовка..."

    def set_status(self, status: str):
        self.status = status
        self._emit()

    def set_progress(self, value: int):
        self.value = value
        self._emit()

    def set_max(self, value: int):
        self.max = max(1, value)
        self._emit()

    def _emit(self):
        self.cb(max(0, min(100, int(self.value / self.max * 100))), self.status)


def install_version(version: str, mc_dir: Path, on_progress: Callable[[int, str], None]) -> None:
    if not HAS_MLL:
        raise RuntimeError("Не установлена minecraft-launcher-lib. Установите: pip install minecraft-launcher-lib")
    mc_dir = Path(mc_dir)
    mc_dir.mkdir(parents=True, exist_ok=True)
    cb = _ProgressCallback(on_progress)
    on_progress(0, f"Скачивание Minecraft {version}...")
    mll.install.install_minecraft_version(version, str(mc_dir), callback={
        "setStatus":   cb.set_status,
        "setProgress": cb.set_progress,
        "setMax":      cb.set_max,
    })
    on_progress(100, f"Версия {version} установлена")


def install_fabric(mc_version: str, mc_dir: Path, on_progress: Callable[[int, str], None]) -> str:
    if not HAS_MLL:
        raise RuntimeError("Нет minecraft-launcher-lib")
    if not hasattr(mll, "fabric"):
        raise RuntimeError("Эта версия minecraft-launcher-lib не поддерживает Fabric. Обновите: pip install -U minecraft-launcher-lib")
    on_progress(5, "Установка Fabric Loader...")
    try:
        mll.fabric.install_fabric(mc_version, str(mc_dir))
    except TypeError:
        mll.fabric.install_fabric(mc_version, str(mc_dir), callback={})
    installed = sorted(
        [v for v in get_installed_versions(mc_dir) if "fabric" in v.lower() and mc_version in v],
        reverse=True)
    version_id = installed[0] if installed else f"fabric-loader-{mc_version}"
    on_progress(100, f"Fabric готов: {version_id}")
    return version_id


def offline_uuid(username: str) -> str:
    return str(uuid.uuid3(uuid.NAMESPACE_DNS, "OfflinePlayer:" + username))


# ═══════════════════════════════════════════════════════════════
#  Java: поиск + портативная
# ═══════════════════════════════════════════════════════════════

def find_java(custom_path: Optional[str] = None) -> Optional[str]:
    if custom_path and Path(custom_path).exists():
        return custom_path
    if HAS_MLL:
        try:
            p = mll.utils.get_java_executable()
            if p and Path(p).exists():
                return p
        except Exception:
            pass
    for name in ("javaw", "java"):
        p = shutil.which(name)
        if p:
            return p
    return None


def get_java_major(java_path: str) -> Optional[int]:
    """Возвращает мажорную версию Java (8, 17, 21, ...) или None."""
    if not java_path:
        return None
    try:
        kw: dict = {}
        if sys.platform == "win32":
            kw["creationflags"] = 0x08000000
        r = subprocess.run([java_path, "-version"],
                           capture_output=True, text=True, timeout=5, **kw)
        out = (r.stderr or "") + (r.stdout or "")
        m = re.search(r'version\s+"([^"]+)"', out)
        if not m:
            return None
        v = m.group(1)
        if v.startswith("1."):
            return int(v.split(".")[1])  # "1.8.0_xxx" -> 8
        return int(v.split(".")[0])
    except Exception:
        return None


# ─── Портативная Java через Adoptium API ───────────────────────

ADOPTIUM_API = (
    "https://api.adoptium.net/v3/binary/latest/"
    "{feature}/ga/{os}/{arch}/jdk/hotspot/normal/eclipse"
)


def _adoptium_url(major: int) -> str:
    """Собирает URL прямого скачивания JDK с Adoptium для текущей OS."""
    # OS
    plat = sys.platform
    if plat == "win32":
        os_name = "windows"
        arch = "x64"
    elif plat == "darwin":
        os_name = "mac"
        arch = "x64"  # на ARM-маках лучше aarch64, но x64 работает через Rosetta
    else:
        os_name = "linux"
        arch = "x64"
    return ADOPTIUM_API.format(feature=major, os=os_name, arch=arch)


def _java_install_root(launcher_root: Path) -> Path:
    """Папка для портативных Java: <launcher>/java_runtimes/"""
    return Path(launcher_root) / "java_runtimes"


def find_portable_java(launcher_root: Path, major: int) -> Optional[str]:
    """
    Ищет уже скачанную портативную Java нужной версии.
    Структура: <launcher>/java_runtimes/jdk-<major>/bin/java(w).exe
    """
    root = _java_install_root(launcher_root) / f"jdk-{major}"
    if not root.exists():
        return None
    exe_name = "javaw.exe" if sys.platform == "win32" else "java"
    # Ищем рекурсивно — Adoptium кладёт под jdk-21.0.4+7/bin/java
    for p in root.rglob(exe_name):
        try:
            if p.is_file():
                mj = get_java_major(str(p))
                if mj == major:
                    return str(p)
        except Exception:
            continue
    return None


def download_portable_java(launcher_root: Path, major: int,
                           on_progress: Callable[[int, str], None] = lambda *_: None
                           ) -> Optional[str]:
    """
    Скачивает портативный JDK с Adoptium и распаковывает в
    <launcher>/java_runtimes/jdk-<major>/.
    Возвращает путь к java.exe / javaw.exe или None.
    """
    # Проверяем что уже не скачано
    existing = find_portable_java(launcher_root, major)
    if existing:
        return existing

    target_root = _java_install_root(launcher_root) / f"jdk-{major}"
    target_root.mkdir(parents=True, exist_ok=True)

    url = _adoptium_url(major)
    on_progress(2, f"Запрос Adoptium API (Java {major})...")

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ExelentLauncher/1.2"})
        # Adoptium делает 307 redirect на github
        with urllib.request.urlopen(req, timeout=30) as r:
            # Угадываем расширение из URL после редиректа
            real_url = r.geturl()
            content_disposition = r.headers.get("Content-Disposition", "")
            name_match = re.search(r'filename="?([^";]+)"?', content_disposition)
            if name_match:
                filename = name_match.group(1)
            else:
                filename = real_url.split("/")[-1].split("?")[0] or f"jdk-{major}.zip"

            archive_path = target_root / filename
            total = 0
            try:
                total = int(r.headers.get("Content-Length") or 0)
            except Exception:
                total = 0
            done = 0
            on_progress(5, f"Скачивание Java {major}: 0 MB")
            with archive_path.open("wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total > 0:
                        pct = 5 + int(done / total * 70)
                        mb = done / 1024 / 1024
                        mb_t = total / 1024 / 1024
                        on_progress(pct, f"Скачивание Java {major}: {mb:.1f} / {mb_t:.1f} MB")
                    else:
                        on_progress(40, f"Скачивание Java {major}: {done/1024/1024:.1f} MB")
    except Exception as ex:
        on_progress(0, f"Ошибка скачивания Java: {ex}")
        return None

    # Распаковка
    on_progress(80, f"Распаковка Java {major}...")
    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(target_root)
        elif filename.endswith(".tar.gz") or filename.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(target_root)
        else:
            on_progress(0, f"Неизвестный формат: {filename}")
            return None
    except Exception as ex:
        on_progress(0, f"Ошибка распаковки: {ex}")
        return None

    # Удаляем архив
    try:
        archive_path.unlink()
    except Exception:
        pass

    # Ищем java(w).exe в распакованной папке
    on_progress(95, "Поиск исполняемого файла Java...")
    java_path = find_portable_java(launcher_root, major)
    if java_path:
        on_progress(100, f"Java {major} установлена: {java_path}")
        # Для Linux/macOS — выставляем +x
        if sys.platform != "win32":
            try:
                os.chmod(java_path, 0o755)
            except Exception:
                pass
        return java_path

    on_progress(0, "Java скачана, но исполняемый файл не найден")
    return None


def find_or_install_java(launcher_root: Path, required_major: int,
                         user_java_path: str = "",
                         on_progress: Callable[[int, str], None] = lambda *_: None
                         ) -> Optional[str]:
    """
    Главная функция: возвращает путь к Java нужной мажорной версии.

    Логика:
      1. user_java_path (если задан и подходит) — используем
      2. Системная Java (find_java) — если >= required_major, используем
      3. Уже скачанная портативная Java (требуемой версии) — используем
      4. Скачиваем портативную с Adoptium
    """
    # 1. Пользовательский путь
    if user_java_path and Path(user_java_path).exists():
        mj = get_java_major(user_java_path)
        if mj and mj >= required_major:
            return user_java_path

    # 2. Системная Java
    sys_java = find_java()
    if sys_java:
        mj = get_java_major(sys_java)
        if mj and mj >= required_major:
            return sys_java

    # 3. Уже скачанная портативная
    portable = find_portable_java(launcher_root, required_major)
    if portable:
        return portable

    # 4. Скачиваем
    on_progress(0, f"Скачиваю портативную Java {required_major}...")
    return download_portable_java(launcher_root, required_major, on_progress)


# ═══════════════════════════════════════════════════════════════
#  Запуск + переименование окна Minecraft
# ═══════════════════════════════════════════════════════════════

WINDOW_TITLE   = "Exelent Client 1.2"
LAUNCHER_BRAND = "Exelent Client"
LAUNCHER_VER   = "1.2"


def _get_child_pids(root_pid: int) -> set[int]:
    pids = {root_pid}
    if sys.platform != "win32":
        return pids
    try:
        import ctypes
        from ctypes import wintypes
        TH32CS_SNAPPROCESS = 0x00000002
        kernel32 = ctypes.windll.kernel32

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize",              wintypes.DWORD),
                ("cntUsage",            wintypes.DWORD),
                ("th32ProcessID",       wintypes.DWORD),
                ("th32DefaultHeapID",   ctypes.c_void_p),
                ("th32ModuleID",        wintypes.DWORD),
                ("cntThreads",          wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase",      ctypes.c_long),
                ("dwFlags",             wintypes.DWORD),
                ("szExeFile",           ctypes.c_char * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == -1:
            return pids
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            all_procs: list[tuple[int, int]] = []
            if kernel32.Process32First(snap, ctypes.byref(entry)):
                while True:
                    all_procs.append((entry.th32ProcessID, entry.th32ParentProcessID))
                    if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                        break
            added = True
            while added:
                added = False
                for pid, ppid in all_procs:
                    if ppid in pids and pid not in pids:
                        pids.add(pid)
                        added = True
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass
    return pids


def _rename_minecraft_window(root_pid: int, new_title: str = WINDOW_TITLE,
                             total_timeout: float = 3600.0,
                             scan_interval: float = 0.4) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return

    debug = os.environ.get("EXELENT_DEBUG_RENAME") == "1"

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        EnumWindows = user32.EnumWindows
        EnumWindows.restype = wintypes.BOOL
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]

        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

        IsWindowVisible = user32.IsWindowVisible
        IsWindowVisible.argtypes = [wintypes.HWND]

        GetWindowTextLengthW = user32.GetWindowTextLengthW
        GetWindowTextLengthW.argtypes = [wintypes.HWND]

        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        SetWindowTextW = user32.SetWindowTextW
        SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]

        GetClassNameW = user32.GetClassNameW
        GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        OpenProcess = kernel32.OpenProcess
        OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        OpenProcess.restype  = wintypes.HANDLE
        CloseHandle = kernel32.CloseHandle
        GetExitCodeProcess = kernel32.GetExitCodeProcess
        GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        STILL_ACTIVE = 259
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    except Exception:
        return

    deadline = time.time() + total_timeout

    def proc_alive(pid: int) -> bool:
        h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            if not GetExitCodeProcess(h, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            CloseHandle(h)

    known_mc_hwnds: set[int] = set()
    blacklist: set[int] = set()

    while time.time() < deadline:
        if not proc_alive(root_pid):
            break

        target_pids = _get_child_pids(root_pid)

        def callback(hwnd, _lp):
            hwnd_i = int(hwnd)
            if hwnd_i in blacklist:
                return True

            wpid = wintypes.DWORD()
            GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value not in target_pids:
                return True

            if not IsWindowVisible(hwnd):
                return True

            cls_buf = ctypes.create_unicode_buffer(256)
            GetClassNameW(hwnd, cls_buf, 256)
            cls_name = cls_buf.value or ""

            length = GetWindowTextLengthW(hwnd)
            if length < 0:
                length = 0
            buf = ctypes.create_unicode_buffer(length + 2)
            GetWindowTextW(hwnd, buf, length + 2)
            title = (buf.value or "").strip()
            low = title.lower()

            is_mc_class = "glfw" in cls_name.lower()
            is_mc_title = ("minecraft" in low and "launcher" not in low)

            if not is_mc_class and not is_mc_title and hwnd_i not in known_mc_hwnds:
                if title and not is_mc_title:
                    blacklist.add(hwnd_i)
                return True

            known_mc_hwnds.add(hwnd_i)

            if title == new_title:
                return True

            try:
                SetWindowTextW(hwnd, new_title)
                if debug:
                    print(f"[rename] hwnd={hwnd_i} '{title}' -> '{new_title}'")
            except Exception:
                pass
            return True

        try:
            EnumWindows(EnumWindowsProc(callback), 0)
        except Exception:
            pass

        time.sleep(scan_interval)


def launch_minecraft(version: str, username: str, mc_dir: Path, ram_mb: int = 2048,
                     java_path: Optional[str] = None, dev_mode: bool = False,
                     game_dir: Optional[Path] = None,
                     server: Optional[str] = None) -> subprocess.Popen:
    """
    Запуск Minecraft.

    game_dir — если задан, используется как gameDirectory (туда смотрит игра
               за mods/, saves/, resourcepacks/...). По умолчанию = mc_dir.
               Для профиля передавай profiles/<name>/.
    server   — если задан, запуск с автоподключением (host или host:port).
    """
    if not HAS_MLL:
        raise RuntimeError("minecraft-launcher-lib не установлена. pip install minecraft-launcher-lib")
    mc_dir = Path(mc_dir)
    if not is_version_installed(mc_dir, version):
        raise RuntimeError(f"Версия {version} не установлена")

    game_directory = str(Path(game_dir) if game_dir else mc_dir)

    options: dict = {
        "username": username,
        "uuid": offline_uuid(username),
        "token": "0",
        "launcherName":    LAUNCHER_BRAND,
        "launcherVersion": LAUNCHER_VER,
        "gameDirectory":   game_directory,
        "jvmArguments": (
            jvm_args if jvm_args else [
                f"-Xmx{ram_mb}M",
                f"-Xms{min(512, ram_mb)}M",
                f"-Dminecraft.launcher.brand={LAUNCHER_BRAND}",
                f"-Dminecraft.launcher.version={LAUNCHER_VER}",
            ]
        ),
    }
    if java_path:
        options["executablePath"] = java_path

    # Автоподключение к серверу
    if server:
        host = server.strip()
        port = "25565"
        if ":" in host:
            host, port = host.rsplit(":", 1)
        options["server"] = host
        options["port"]   = port

    cmd = mll.command.get_minecraft_command(version, str(mc_dir), options)

    stdout = None if dev_mode else subprocess.DEVNULL
    stderr = None if dev_mode else subprocess.DEVNULL
    kwargs: dict[str, Any] = {"cwd": game_directory, "stdout": stdout, "stderr": stderr}
    if sys.platform == "win32" and not dev_mode:
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

    proc = subprocess.Popen(cmd, **kwargs)

    if sys.platform == "win32":
        threading.Thread(
            target=_rename_minecraft_window,
            args=(proc.pid, WINDOW_TITLE, 3600.0, 0.4),
            daemon=True,
        ).start()

    return proc


def ensure_mc_dirs(mc_dir: Path) -> None:
    for sub in ("mods", "versions", "saves", "resourcepacks", "shaderpacks", "libraries", "assets"):
        (Path(mc_dir) / sub).mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  Modrinth API
# ═══════════════════════════════════════════════════════════════

MODRINTH_API = "https://api.modrinth.com/v2"
USER_AGENT   = "YAYRIRZ/ExelentLauncher (t.me/YAYRIRZ)"


MOD_CATEGORIES: list[tuple[str, str]] = [
    ("adventure",      "Приключения"),
    ("decoration",     "Декорации"),
    ("economy",        "Экономика"),
    ("equipment",      "Снаряжение"),
    ("food",           "Еда"),
    ("game-mechanics", "Геймплей"),
    ("library",        "Библиотеки"),
    ("magic",          "Магия"),
    ("management",     "Управление"),
    ("minigame",       "Мини-игры"),
    ("mobs",           "Мобы"),
    ("optimization",   "Оптимизация"),
    ("social",         "Социальные"),
    ("storage",        "Хранение"),
    ("technology",     "Технологии"),
    ("transportation", "Транспорт"),
    ("utility",        "Утилиты"),
    ("worldgen",       "Генерация мира"),
]

RESOURCEPACK_CATEGORIES: list[tuple[str, str]] = [
    ("8x-",          "8x и меньше"),
    ("16x",          "16x"),
    ("32x",          "32x"),
    ("48x",          "48x"),
    ("64x",          "64x"),
    ("128x",         "128x"),
    ("256x",         "256x"),
    ("512x+",        "512x и больше"),
    ("realistic",    "Реалистичные"),
    ("simplistic",   "Простые"),
    ("themed",       "Тематические"),
    ("cartoon",      "Мультяшные"),
    ("vanilla-like", "Vanilla-like"),
    ("combat",       "Боевые"),
    ("decoration",   "Декоративные"),
    ("modded",       "Для модов"),
]

SHADER_CATEGORIES: list[tuple[str, str]] = [
    ("vanilla-like",   "Vanilla-like"),
    ("cartoon",        "Мультяшные"),
    ("realistic",      "Реалистичные"),
    ("fantasy",        "Фэнтези"),
    ("semi-realistic", "Полу-реалистичные"),
    ("potato",         "Слабый ПК"),
    ("low",            "Низкие"),
    ("medium",         "Средние"),
    ("high",           "Высокие"),
    ("screenshot",     "Скриншот-качество"),
]


def _http_get_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _facets(project_type: str, categories: Optional[list[str]] = None,
            game_version: str = "", loader: str = "") -> str:
    facets: list[list[str]] = []
    if project_type:
        facets.append([f"project_type:{project_type}"])
    if categories:
        facets.append([f"categories:{c}" for c in categories])
    if game_version:
        facets.append([f"versions:{game_version}"])
    if loader:
        facets.append([f"categories:{loader}"])
    return json.dumps(facets)


def search_modrinth(query: str = "",
                    project_type: str = "mod",
                    categories: Optional[list[str]] = None,
                    game_version: str = "",
                    loader: str = "",
                    index: str = "relevance",
                    limit: int = 20,
                    offset: int = 0) -> list[dict]:
    params = {
        "query":  query or "",
        "facets": _facets(project_type, categories, game_version, loader),
        "index":  index or "relevance",
        "limit":  int(limit),
        "offset": int(offset),
    }
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v != ""})
    url = f"{MODRINTH_API}/search?{qs}"
    try:
        data = _http_get_json(url, timeout=15)
        return data.get("hits", []) or []
    except Exception:
        return []


def get_modrinth_project_versions(project_id: str,
                                  mc_version: str = "",
                                  loader: str = "") -> list[dict]:
    if not project_id:
        return []
    qs_parts = []
    if loader:
        qs_parts.append("loaders=" + urllib.parse.quote(json.dumps([loader])))
    if mc_version:
        qs_parts.append("game_versions=" + urllib.parse.quote(json.dumps([mc_version])))
    qs = ("?" + "&".join(qs_parts)) if qs_parts else ""
    url = f"{MODRINTH_API}/project/{project_id}/version{qs}"
    try:
        data = _http_get_json(url, timeout=15)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def download_modrinth_file(project_id: str, version_id: str,
                           target_dir: Path,
                           on_progress: Optional[Callable[[int, str], None]] = None
                           ) -> Optional[Path]:
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if on_progress is None:
        on_progress = lambda *_: None

    on_progress(5, "Получение метаданных версии...")

    try:
        if version_id:
            url = f"{MODRINTH_API}/version/{version_id}"
            ver = _http_get_json(url, timeout=15)
        else:
            vs = get_modrinth_project_versions(project_id)
            if not vs:
                return None
            ver = vs[0]
    except Exception as ex:
        on_progress(0, f"Ошибка метаданных: {ex}")
        return None

    files = ver.get("files") or []
    if not files:
        on_progress(0, "В версии нет файлов")
        return None

    f_meta = next((f for f in files if f.get("primary")), files[0])
    file_url = f_meta.get("url") or ""
    file_name = f_meta.get("filename") or "download.jar"
    if not file_url:
        on_progress(0, "Нет URL файла")
        return None

    target = target_dir / file_name
    on_progress(10, f"Скачивание: {file_name}")

    try:
        req = urllib.request.Request(file_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = 0
            try:
                total = int(r.headers.get("Content-Length") or 0)
            except Exception:
                total = 0
            done = 0
            chunks: list[bytes] = []
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                done += len(chunk)
                if total > 0:
                    pct = 10 + int(done / total * 88)
                    on_progress(pct, f"{file_name}: {done/1024/1024:.1f} / {total/1024/1024:.1f} MB")
                else:
                    on_progress(50, f"{file_name}: {done/1024/1024:.1f} MB")
            target.write_bytes(b"".join(chunks))
    except urllib.error.HTTPError as e:
        on_progress(0, f"HTTP {e.code}")
        return None
    except Exception as ex:
        on_progress(0, f"Ошибка скачивания: {ex}")
        return None

    on_progress(100, f"Сохранено: {file_name}")
    return target
