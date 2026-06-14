"""Мониторинг Minecraft-серверов через mcstatus.io.

Новый API:
  https://api.mcstatus.io/v2/status/java/<host>[:port]

mcstatus.io делает обычный Java status ping, поэтому подходит не только для
premium-серверов, но и для offline-mode/российских серверов: авторизация
игрока для проверки статуса не требуется.

Кэш на 2 минуты — статус в UI обновляется быстро, но мы не спамим API.
"""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.parse
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal


MCSTATUS_URL = "https://api.mcstatus.io/v2/status/java/{addr}"
USER_AGENT   = "ExelentLauncher/1.4 (t.me/YAYRIRZ)"


# Простой in-memory кэш
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 120.0  # 2 минуты


_COLOR_RE = re.compile(r"§[0-9A-FK-ORa-fk-or]")


def _strip_mc_colors(text: str) -> str:
    return _COLOR_RE.sub("", str(text or "")).strip()


def normalize_addr(addr: str, default_port: int | str | None = 25565) -> str:
    """Нормализует адрес для подключения: host[:port] -> host:port.

    Убирает minecraft://, query/path, пробелы. IPv6 в квадратных скобках
    оставляет корректным: [::1]:25565.
    """
    addr = (addr or "").strip()
    if not addr:
        return ""
    for prefix in ("minecraft://", "mc://"):
        if addr.lower().startswith(prefix):
            addr = addr[len(prefix):]
            break
    addr = addr.strip().strip("/")
    # Если пользователь вставил URL со слешами/параметрами — берём только host:port
    addr = addr.split("/", 1)[0].split("?", 1)[0].strip()
    if not addr:
        return ""

    default_port = "" if default_port is None else str(default_port or 25565)

    # IPv6: [2001:db8::1] или [2001:db8::1]:25566
    if addr.startswith("["):
        if "]" in addr:
            host, rest = addr.split("]", 1)
            host = host + "]"
            if rest.startswith(":") and rest[1:]:
                return f"{host}:{rest[1:]}"
            return f"{host}:{default_port}" if default_port else host
        return addr

    # Обычный host:port. Если двоеточий несколько — скорее всего IPv6 без [];
    # для подключения оставим как есть, чтобы не портить адрес.
    if addr.count(":") == 1:
        host, port = addr.rsplit(":", 1)
        if host and port.isdigit():
            return f"{host}:{port}"
    if ":" not in addr:
        return f"{addr}:{default_port}" if default_port else addr
    return addr


# Старое внутреннее имя оставлено для совместимости с launcher.py.bak/плагинами.
def _normalize_addr(addr: str) -> str:
    return normalize_addr(addr)


def _mcstatus_to_legacy(data: dict, requested_addr: str) -> dict:
    """Приводит ответ mcstatus.io к формату, который уже ожидает UI."""
    if not isinstance(data, dict):
        return {}

    req_norm = normalize_addr(requested_addr)
    req_host, req_port = (req_norm.rsplit(":", 1) if ":" in req_norm else (requested_addr, "25565"))
    host = data.get("host") or req_host
    port = data.get("port") or req_port or 25565

    motd = data.get("motd") or {}
    if isinstance(motd, dict):
        clean = motd.get("clean") or motd.get("raw") or ""
    else:
        clean = motd
    if isinstance(clean, list):
        clean_list = [_strip_mc_colors(x) for x in clean if x]
    else:
        clean_list = [_strip_mc_colors(clean)] if clean else []

    version = data.get("version") or ""
    if isinstance(version, dict):
        version_text = (
            version.get("name_clean")
            or version.get("name_raw")
            or version.get("name")
            or ""
        )
    else:
        version_text = str(version or "")

    players = data.get("players") or {}
    if not isinstance(players, dict):
        players = {}

    icon = data.get("icon") or ""

    out = dict(data)
    out.update({
        "online": bool(data.get("online")),
        "ip": data.get("ip_address") or data.get("ip") or host,
        "port": int(port) if str(port).isdigit() else port,
        "hostname": host,
        "connect": normalize_addr(f"{host}:{port}"),
        "motd": {"clean": clean_list, "raw": clean_list},
        "players": {
            "online": players.get("online", 0),
            "max": players.get("max", "?"),
            "list": players.get("list") or [],
        },
        "version": version_text,
        "icon": icon,
    })
    return out


def fetch_server_status(addr: str, timeout: float = 8.0) -> dict | None:
    """
    Возвращает dict со статусом или None.
    Главные поля для UI:
      online (bool)
      ip, port, hostname, connect
      motd: {clean: [str]}
      players: {online, max, list}
      version (str)
      icon (str: 'data:image/png;base64,...')
    """
    # Для запроса к API не подставляем 25565 насильно: так mcstatus.io сможет
    # корректно обработать SRV-записи. Для запуска игры host:port собирается
    # позже через get_connect_address().
    addr = normalize_addr(addr, default_port=None)
    if not addr:
        return None

    now = time.time()
    cached = _CACHE.get(addr)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    # В path безопасно оставляем ':' для host:port и квадратные скобки для IPv6.
    url = MCSTATUS_URL.format(addr=urllib.parse.quote(addr, safe=":[]"))
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict):
            data = _mcstatus_to_legacy(data, addr)
            _CACHE[addr] = (now, data)
            return data
    except Exception:
        return None
    return None


def get_icon_bytes(server_data: dict) -> bytes | None:
    """Декодирует base64 PNG-иконку сервера из ответа API. None если нет."""
    if not server_data:
        return None
    icon = server_data.get("icon") or ""
    if not icon:
        return None
    if "," in icon:
        b64 = icon.split(",", 1)[1]
    else:
        b64 = icon
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def get_icon_pixmap(server_data: dict, size: int = 64):
    """QPixmap from base64 server icon."""
    from PyQt6.QtGui import QPixmap
    data = get_icon_bytes(server_data)
    if not data:
        return None
    pix = QPixmap()
    pix.loadFromData(data)
    if pix.isNull():
        return None
    return pix.scaled(size, size)


def get_motd_text(server_data: dict) -> str:
    """Извлекает чистый MOTD (без цветовых кодов §)."""
    if not server_data:
        return ""
    motd = server_data.get("motd") or {}
    clean = motd.get("clean") if isinstance(motd, dict) else motd
    if isinstance(clean, list):
        return "\n".join(_strip_mc_colors(s) for s in clean if s).strip()
    if isinstance(clean, str):
        return _strip_mc_colors(clean)
    return ""


def get_version_text(server_data: dict) -> str:
    if not server_data:
        return ""
    ver = server_data.get("version") or ""
    if isinstance(ver, dict):
        return ver.get("name_clean") or ver.get("name_raw") or ver.get("name", "")
    return str(ver)


def get_players_text(server_data: dict) -> str:
    """Возвращает '5 / 100' или 'offline' если оффлайн."""
    if not server_data or not server_data.get("online"):
        return "offline"
    pl = server_data.get("players") or {}
    on = pl.get("online", "?")
    mx = pl.get("max", "?")
    return f"{on} / {mx}"


def get_connect_address(server_data: dict, fallback: str = "") -> str:
    """Адрес для запуска Minecraft: host:port."""
    if server_data:
        connect = server_data.get("connect")
        if connect:
            return normalize_addr(str(connect))
        host = server_data.get("hostname") or server_data.get("host") or server_data.get("ip")
        port = server_data.get("port") or 25565
        if host:
            return normalize_addr(f"{host}:{port}")
    return normalize_addr(fallback)


# ═══════════════════════════════════════════════════════════════
#  Фоновый поток для запроса статуса
# ═══════════════════════════════════════════════════════════════

class ServerStatusThread(QThread):
    """
    Фоновый запрос к mcstatus.io — не блокирует UI.
    Сигнал done(addr, data_dict_or_None).
    """
    done = pyqtSignal(str, object)

    def __init__(self, addr: str, parent=None):
        super().__init__(parent)
        self.addr = addr
        self._alive = True

    def cancel(self):
        self._alive = False

    def run(self):
        data = fetch_server_status(self.addr)
        if self._alive:
            try:
                self.done.emit(self.addr, data)
            except Exception:
                pass
