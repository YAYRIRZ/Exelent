"""Мониторинг Minecraft-серверов через api.mcsrvstat.us.

Запросы:
  https://api.mcsrvstat.us/3/<host>[:port]   -> JSON со статусом
    {online, ip, port, motd, players: {online, max, list},
     version, icon (base64 PNG data:image/png;base64,...),
     hostname, debug: {...}, ...}

Кэш на 5 минут — больше частить не имеет смысла, mcsrvstat.us тоже кэширует.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal


MCSRVSTAT_URL = "https://api.mcsrvstat.us/3/{addr}"
USER_AGENT    = "ExelentLauncher/1.2 (t.me/YAYRIRZ)"


# Простой in-memory кэш
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300.0  # 5 минут


def _normalize_addr(addr: str) -> str:
    """'mc.hypixel.net' / 'play.example.com:25566' → нормализованный адрес."""
    addr = (addr or "").strip()
    # Убираем minecraft://
    if addr.startswith("minecraft://"):
        addr = addr[len("minecraft://"):]
    # Убираем trailing slash
    addr = addr.rstrip("/")
    return addr


def fetch_server_status(addr: str, timeout: float = 8.0) -> dict | None:
    """
    Возвращает dict со статусом или None.
    Главные поля:
      online (bool)
      ip, port (str/int)
      motd: {raw: [str], clean: [str], html: [str]}
      players: {online, max, list: [{name, uuid}, ...]}
      version (str)
      icon (str: 'data:image/png;base64,...')
      hostname (str)
    """
    addr = _normalize_addr(addr)
    if not addr:
        return None

    # Кэш
    now = time.time()
    cached = _CACHE.get(addr)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    url = MCSRVSTAT_URL.format(addr=urllib.parse.quote(addr, safe=":/"))
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
    # формат: 'data:image/png;base64,<base64>'
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
    clean = motd.get("clean") or []
    if isinstance(clean, list):
        return "\n".join(s for s in clean if s).strip()
    if isinstance(clean, str):
        return clean.strip()
    return ""


def get_version_text(server_data: dict) -> str:
    if not server_data:
        return ""
    ver = server_data.get("version") or ""
    if isinstance(ver, dict):
        return ver.get("name", "")
    return str(ver)

def get_players_text(server_data: dict) -> str:
    """Возвращает '5 / 100' или '? / ?' если оффлайн."""
    if not server_data or not server_data.get("online"):
        return "offline"
    pl = server_data.get("players") or {}
    on  = pl.get("online", "?")
    mx  = pl.get("max", "?")
    return f"{on} / {mx}"


# ═══════════════════════════════════════════════════════════════
#  Фоновый поток для запроса статуса
# ═══════════════════════════════════════════════════════════════

class ServerStatusThread(QThread):
    """
    Фоновый запрос к mcsrvstat.us — не блокирует UI.
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
