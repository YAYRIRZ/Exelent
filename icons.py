"""SVG-иконки для Exelent Launcher (Material Design 3, inline).

Все иконки 24x24, currentColor-style: подкрашиваются через параметр color.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QByteArray, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QIcon, QColor
from PyQt6.QtSvg import QSvgRenderer


_SVG_TEMPLATE = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">{body}</svg>'


def _ic(body: str) -> str:
    return _SVG_TEMPLATE.format(body=body)


SVG: dict[str, str] = {
    # ─── Действия ───
    "close":     _ic('<path d="M19 6.4L17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z" fill="{C}"/>'),
    "minimize":  _ic('<rect x="5" y="11" width="14" height="2" fill="{C}"/>'),
    "maximize":  _ic('<path d="M4 4h16v16H4V4zm2 4v10h12V8H6z" fill="{C}"/>'),
    "check":     _ic('<path d="M9 16.2L4.8 12 3.4 13.4 9 19 21 7 19.6 5.6z" fill="{C}"/>'),
    "back":      _ic('<path d="M20 11H7.8l5.6-5.6L12 4l-8 8 8 8 1.4-1.4L7.8 13H20z" fill="{C}"/>'),
    "arrow_right": _ic('<path d="M4 13h12.2l-5.6 5.6L12 20l8-8-8-8-1.4 1.4L16.2 11H4z" fill="{C}"/>'),
    "arrow_down": _ic('<path d="M7 10l5 5 5-5z" fill="{C}"/>'),
    "refresh":   _ic('<path d="M17.65 6.35A7.96 7.96 0 0012 4a8 8 0 108 8h-2a6 6 0 11-6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" fill="{C}"/>'),
    "play":      _ic('<path d="M8 5v14l11-7z" fill="{C}"/>'),
    "pause":     _ic('<path d="M6 5h4v14H6zm8 0h4v14h-4z" fill="{C}"/>'),
    "stop":      _ic('<rect x="6" y="6" width="12" height="12" rx="1.5" fill="{C}"/>'),
    "search":    _ic('<path d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 10-.7.7l.27.28v.79l5 5L20.49 19l-5-5zM10 14a4 4 0 110-8 4 4 0 010 8z" fill="{C}"/>'),
    "download":  _ic('<path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" fill="{C}"/>'),
    "upload":    _ic('<path d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z" fill="{C}"/>'),
    "trash":     _ic('<path d="M6 19a2 2 0 002 2h8a2 2 0 002-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="{C}"/>'),
    "plus":      _ic('<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z" fill="{C}"/>'),
    "minus":     _ic('<path d="M19 13H5v-2h14v2z" fill="{C}"/>'),
    "edit":      _ic('<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="{C}"/>'),
    "copy":      _ic('<path d="M16 1H4a2 2 0 00-2 2v14h2V3h12V1zm3 4H8a2 2 0 00-2 2v14a2 2 0 002 2h11a2 2 0 002-2V7a2 2 0 00-2-2zm0 16H8V7h11v14z" fill="{C}"/>'),
    "open_link": _ic('<path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z" fill="{C}"/>'),

    # ─── Интерфейс ───
    "settings":  _ic('<path d="M19.43 12.98a7.78 7.78 0 000-1.96l2.11-1.65a.5.5 0 00.12-.64l-2-3.46a.5.5 0 00-.61-.22l-2.49 1a7.7 7.7 0 00-1.69-.98l-.38-2.65A.5.5 0 0014 2h-4a.5.5 0 00-.49.42l-.38 2.65a7.7 7.7 0 00-1.69.98l-2.49-1a.5.5 0 00-.61.22l-2 3.46a.5.5 0 00.12.64l2.11 1.65a7.78 7.78 0 000 1.96L2.46 14.6a.5.5 0 00-.12.64l2 3.46a.5.5 0 00.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65a.5.5 0 00.49.42h4a.5.5 0 00.49-.42l.38-2.65a7.7 7.7 0 001.69-.98l2.49 1a.5.5 0 00.61-.22l2-3.46a.5.5 0 00-.12-.64l-2.11-1.65zM12 15.5a3.5 3.5 0 110-7 3.5 3.5 0 010 7z" fill="{C}"/>'),
    "menu":      _ic('<path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" fill="{C}"/>'),
    "folder":    _ic('<path d="M10 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2h-8l-2-2z" fill="{C}"/>'),
    "folder_open": _ic('<path d="M20 6h-8l-2-2H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2zm0 12H4V8h16v10z" fill="{C}"/>'),
    "image":     _ic('<path d="M21 19V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" fill="{C}"/>'),
    "palette":   _ic('<path d="M12 22A10 10 0 012 12 10 10 0 0112 2c5.52 0 10 4.04 10 9 0 3.31-2.69 6-6 6h-1.77c-.28 0-.5.22-.5.5 0 .12.05.23.13.33.41.47.64 1.06.64 1.67A2.5 2.5 0 0112 22zm0-18a8 8 0 00-8 8 8 8 0 008 8c.28 0 .5-.22.5-.5a.54.54 0 00-.14-.35c-.41-.46-.63-1.05-.63-1.65a2.5 2.5 0 012.5-2.5H16a4 4 0 004-4c0-3.86-3.59-7-8-7zm-5.5 6c.83 0 1.5.67 1.5 1.5S7.33 13 6.5 13 5 12.33 5 11.5 5.67 10 6.5 10zm3-4c.83 0 1.5.67 1.5 1.5S10.33 9 9.5 9 8 8.33 8 7.5 8.67 6 9.5 6zm5 0c.83 0 1.5.67 1.5 1.5S15.33 9 14.5 9 13 8.33 13 7.5 13.67 6 14.5 6zm3 4c.83 0 1.5.67 1.5 1.5S18.33 13 17.5 13 16 12.33 16 11.5s.67-1.5 1.5-1.5z" fill="{C}"/>'),
    "sliders":   _ic('<path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z" fill="{C}"/>'),
    "info":      _ic('<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" fill="{C}"/>'),
    "warning":   _ic('<path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" fill="{C}"/>'),
    "error":     _ic('<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" fill="{C}"/>'),
    "wifi":      _ic('<path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3a4.24 4.24 0 00-6 0zm-4-4l2 2a7.07 7.07 0 0110 0l2-2C14.14 9.14 9.87 9.14 5 13z" fill="{C}"/>'),

    # ─── Контент ───
    "sparkles":  _ic('<path d="M12 2L9.5 9.5 2 12l7.5 2.5L12 22l2.5-7.5L22 12l-7.5-2.5L12 2zm7 12l-1.25 3.75L14 19l3.75 1.25L19 24l1.25-3.75L24 19l-3.75-1.25L19 14z" fill="{C}"/>'),
    "rocket":    _ic('<path d="M21 3a1 1 0 0 0-1-1h-2.5c-3.2 0-7 2.3-8.8 5.2L7 9.1l-2.6-.9c-.6-.2-1.3 0-1.7.5L2 9.4c-.4.5-.4 1.2.1 1.6l4.9 3.9 1 1 3.9 4.9c.4.5 1.1.5 1.6.1l.7-.7c.5-.4.7-1.1.5-1.7l-.9-2.6 1.9-1.7c2.9-1.8 5.2-5.6 5.2-8.8V3zm-5 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm-11.8 9a1 1 0 0 0-1.4 0l-1.5 1.5a1 1 0 0 0 0 1.4L4 22l2.7-2.7-1.5-1.3z" fill="{C}"/>'),
    "puzzle":    _ic('<path d="M20.5 11h-1.7v-4.6c0-.9-.7-1.6-1.6-1.6h-4.6v-1.7c0-1.2-1-2.1-2.1-2.1S8.4 2 8.4 3.1v1.7h-4.6c-.9 0-1.6.7-1.6 1.6v4.4h1.7c1.4 0 2.5 1.1 2.5 2.5s-1.1 2.5-2.5 2.5h-1.7v4.4c0 .9.7 1.6 1.6 1.6h4.4v-1.7c0-1.4 1.1-2.5 2.5-2.5s2.5 1.1 2.5 2.5v1.7h4.4c.9 0 1.6-.7 1.6-1.6v-4.6h1.7c1.2 0 2.1-1 2.1-2.1S21.7 11 20.5 11z" fill="{C}"/>'),
    "star":      _ic('<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z" fill="{C}"/>'),
    "heart":     _ic('<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09A6.04 6.04 0 0116.5 3C19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="{C}"/>'),
    "fire":      _ic('<path d="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14a8 8 0 0016 0c0-4.1-1.97-7.77-5-10.05a18 18 0 00-1.5-3.28zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z" fill="{C}"/>'),
    "trending":  _ic('<path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z" fill="{C}"/>'),
    "category":  _ic('<path d="M12 2l-5.5 9h11zm5.5 17a4.5 4.5 0 110-9 4.5 4.5 0 010 9zM3 21.5h8v-8H3z" fill="{C}"/>'),
    "news":      _ic('<path d="M20 3H4a2 2 0 00-2 2v14a2 2 0 002 2h16a2 2 0 002-2V5a2 2 0 00-2-2zM5 7h7v6H5V7zm0 8h14v2H5v-2zm14-2h-5v-2h5v2zm0-4h-5V7h5v2z" fill="{C}"/>'),
    "server":    _ic('<path d="M4 1h16a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2V3a2 2 0 012-2zm0 12h16a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4a2 2 0 012-2zm2-7v2h2V6H6zm0 12v2h2v-2H6z" fill="{C}"/>'),
    "globe":     _ic('<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm-1 17.93A8.01 8.01 0 014 12c0-.61.07-1.21.19-1.79L9 15v1a2 2 0 002 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3a1 1 0 00-1-1H8v-2h2a1 1 0 001-1V7h2a2 2 0 002-2v-.41A7.98 7.98 0 0117.9 17.39z" fill="{C}"/>'),
    "user":      _ic('<path d="M12 12a4 4 0 100-8 4 4 0 000 8zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="{C}"/>'),
    "users":     _ic('<path d="M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" fill="{C}"/>'),
    "mods":      _ic('<path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16zM12 4.15L18.04 7.5 12 10.85 5.96 7.5 12 4.15zM5 9.23l6 3.36V19.6l-6-3.36V9.23zm14 7L13 19.6v-7l6-3.36v7z" fill="{C}"/>'),
    "package":   _ic('<path d="M12 2L4 6v12l8 4 8-4V6l-8-4zm0 2.18l5.97 2.98L12 10.14 6.03 7.16 12 4.18zM6 9.27l5 2.5v7.46l-5-2.5V9.27zm12 7.46l-5 2.5v-7.46l5-2.5v7.46z" fill="{C}"/>'),
    "terminal":  _ic('<path d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm0 14H4V8h16v10zm-9-2h6v-2h-6v2zm-3.5-3l2-2-2-2L6 10l1.5 1.5L6 13l1.5 2z" fill="{C}"/>'),

    # КНОПКА PLAY В КВАДРАТЕ (для быстрого захода на сервер)
    "server_play": _ic('<path d="M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2zm5 5.5v7l6-3.5-6-3.5z" fill="{C}"/>'),

    # ─── Minecraft-themed ───
    "sword":     _ic('<path d="M6.92 5L5 6.92 16.34 18.27 17 19l3-3-.73-.66L8 4l-1.08 1zm10.6 11.55l-1.41 1.42-9.9-9.9 1.41-1.42 9.9 9.9z" fill="{C}"/>'),
    "pickaxe":   _ic('<path d="M14 6l-2 2-7 7-3 3 2 2 3-3 7-7 2-2 4-4-2-2-4 4zm-9 13l-1-1 8-8 1 1-8 8z" fill="{C}"/>'),
    "shield":    _ic('<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" fill="{C}"/>'),
    "diamond":   _ic('<path d="M6 2l-4 6 10 14L22 8l-4-6H6zm.2 2h11.6l2.5 4H3.7l2.5-4zM12 19L4.2 9h15.6L12 19z" fill="{C}"/>'),
    "compass":   _ic('<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm2.83 7.17L9 15l5.83-5.83zm0 5.66L9 9l5.83 5.83z" fill="{C}"/>'),
    "map":       _ic('<path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9a.5.5 0 00-.36.5V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9a.5.5 0 00.36-.5V3.5c0-.28-.22-.5-.5-.5zM10 5.47l4 1.4v11.66l-4-1.4V5.47zM5 6.46l3-1.01v11.7l-3 1.16V6.46zm14 11.08l-3 1.01V6.86l3-1.16v11.84z" fill="{C}"/>'),
    "potion":    _ic('<path d="M19.07 10.93L14 5.85V2h2V0H8v2h2v3.85l-5.07 5.08A2 2 0 003 12.36V20a2 2 0 002 2h14a2 2 0 002-2v-7.64c0-.55-.21-1.08-.93-1.43zM12 7.5L7.5 12h9L12 7.5z" fill="{C}"/>'),
    "bow":       _ic('<path d="M19 4l-7 7 7 7-1.41 1.41L9 11l8.59-8.59L19 4zM5 21V3l7 7-7 11z" fill="{C}"/>'),
    "boots":     _ic('<path d="M5 4v9c0 .55.45 1 1 1h2V4H5zm14 11.41V11c0-1.66-1.34-3-3-3h-1V4h-5v12c0 1.1.9 2 2 2h7c1.1 0 2-.9 2-2v-1.59l-2 2v-1z" fill="{C}"/>'),
    "key":       _ic('<path d="M12.65 10A6 6 0 003 12a6 6 0 008.35 5.5L17 23h4v-4h2v-4h-2l-7.35-5zM7 16a3 3 0 110-6 3 3 0 010 6z" fill="{C}"/>'),
    "lock":      _ic('<path d="M18 8h-1V6a5 5 0 00-10 0v2H6a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V10a2 2 0 00-2-2zM9 6a3 3 0 016 0v2H9V6zm9 14H6V10h12v10zm-6-3a2 2 0 100-4 2 2 0 000 4z" fill="{C}"/>'),
    "block":     _ic('<path d="M12 2L4 6v12l8 4 8-4V6l-8-4zm6 5l-6 3-6-3 6-3 6 3zM5 8.27l6 3v7.45l-6-3V8.27zm14 7.46l-6 3v-7.45l6-3v7.45z" fill="{C}"/>'),

    # ─── Стрелки ───
    "chevron_up":   _ic('<path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z" fill="{C}"/>'),
    "chevron_down": _ic('<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" fill="{C}"/>'),
    "chevron_left": _ic('<path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z" fill="{C}"/>'),
    "chevron_right":_ic('<path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z" fill="{C}"/>'),

    # ─── Прочее ───
    "circle":     _ic('<circle cx="12" cy="12" r="10" fill="{C}"/>'),
    "circle_outline": _ic('<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 18a8 8 0 110-16 8 8 0 010 16z" fill="{C}"/>'),
    "dot":        _ic('<circle cx="12" cy="12" r="4" fill="{C}"/>'),
    "filter":     _ic('<path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z" fill="{C}"/>'),
    "sort":       _ic('<path d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z" fill="{C}"/>'),
    "more":       _ic('<path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" fill="{C}"/>'),
}


def _svg_bytes(name: str, color: str) -> bytes:
    raw = SVG.get(name, SVG["info"])
    return raw.replace("{C}", color).encode("utf-8")


def svg_pixmap(name: str, size: int = 24, color: str = "#ffffff") -> QPixmap:
    data = _svg_bytes(name, color)
    renderer = QSvgRenderer(QByteArray(data))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pix


def svg_icon(name: str, size: int = 24, color: str = "#ffffff") -> QIcon:
    return QIcon(svg_pixmap(name, size, color))


def svg_raw(name: str, color: str = "#ffffff") -> str:
    return SVG.get(name, SVG["info"]).replace("{C}", color)


def has_icon(name: str) -> bool:
    return name in SVG


def all_names() -> list[str]:
    return sorted(SVG.keys())
