"""Общие виджеты: ProgressBar (6 стилей), BorderOverlay."""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient,
                         QBrush, QPen, QPainterPath, QConicalGradient)
from PyQt6.QtWidgets import QWidget


PROGRESS_STYLES = [
    ("snake", "Зигзаг /\\/\\/\\"),
    ("bar",   "Классическая полоса"),
    ("pulse", "Пульс"),
    ("dots",  "Бегущие точки"),
    ("wave",  "Синусоида"),
    ("glow",  "Неон с бликом"),
]


class ProgressBar(QWidget):
    def __init__(self, theme: dict, style_name: str = "bar", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.value = 0
        self._t    = 0.0
        self._indeterminate = False
        self._style_name = style_name if style_name in dict(PROGRESS_STYLES) else "bar"
        self.setFixedHeight(16)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def setValue(self, v: int) -> None:
        v = max(0, min(100, int(v)))
        self.value = v
        self._indeterminate = False
        self.update()

    def setIndeterminate(self, on: bool = True) -> None:
        self._indeterminate = bool(on)
        self.update()

    def setStyleName(self, name: str) -> None:
        if name in dict(PROGRESS_STYLES):
            self._style_name = name
            self.update()

    def styleName(self) -> str:
        return self._style_name

    def apply_theme(self, theme: dict) -> None:
        self.theme = theme
        self.update()

    def shutdown(self):
        try:
            if self._timer and self._timer.isActive():
                self._timer.stop()
        except Exception:
            pass

    def _tick(self) -> None:
        try:
            self._t = (self._t + 0.016) % 1000.0
            if self._indeterminate or 0 < self.value < 100 or self.value == 100:
                self.update()
        except (RuntimeError, Exception):
            pass

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        if w <= 6 or h <= 4:
            p.end()
            return

        r = h / 2.0
        rect = QRectF(0, 0, w, h)
        track = QPainterPath()
        track.addRoundedRect(rect, r, r)
        p.fillPath(track, QColor(0, 0, 0, 110))
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawPath(track)

        accent       = QColor(self.theme["accent"])
        accent_light = QColor(self.theme["accent_light"])
        primary      = QColor(self.theme["primary"])

        renderer = {
            "snake": self._draw_snake,
            "bar":   self._draw_bar,
            "pulse": self._draw_pulse,
            "dots":  self._draw_dots,
            "wave":  self._draw_wave,
            "glow":  self._draw_glow,
        }.get(self._style_name, self._draw_bar)

        clip = QPainterPath()
        clip.addRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5),
                            max(0, r - 1.5), max(0, r - 1.5))
        p.save()
        p.setClipPath(clip)
        renderer(p, w, h, accent, accent_light, primary)
        p.restore()
        p.end()

    def _fill_width(self, w: int) -> float:
        return max(0.0, (w - 4) * (self.value / 100.0))

    def _indeterminate_segment(self, w: int, seg_frac: float = 0.30,
                               cycle: float = 1.6):
        seg_w = max(40.0, (w - 4) * seg_frac)
        full_phase = self._t / cycle
        going_right = int(full_phase) % 2 == 0
        local = full_phase - int(full_phase)
        ease = 3 * local * local - 2 * local * local * local
        if not going_right:
            ease = 1.0 - ease
        head = 2 + ease * ((w - 4) + seg_w) - seg_w * 0.5
        if going_right:
            tail = head - seg_w
            return max(2.0, tail), min(float(w - 2), head)
        else:
            tail = head
            head = head + seg_w
            return max(2.0, tail), min(float(w - 2), head)

    TOOTH_W = 14

    def _build_zigzag(self, x_start, x_end, y_center, amp, phase_px):
        path = QPainterPath()
        if x_end <= x_start:
            return path
        tw = self.TOOTH_W
        offset = phase_px % (tw * 2)
        k0 = (x_start - offset) / tw

        def y_at(xx):
            t = (xx - offset) / tw
            t_mod = t - math.floor(t / 2.0) * 2.0
            if t_mod < 1.0:
                ry = -amp + t_mod * (2 * amp)
            else:
                ry = amp - (t_mod - 1.0) * (2 * amp)
            return y_center + ry

        path.moveTo(x_start, y_at(x_start))
        k = math.floor(k0) + 1
        while True:
            xv = k * tw + offset
            if xv >= x_end:
                break
            if xv > x_start:
                path.lineTo(xv, y_at(xv))
            k += 1
        path.lineTo(x_end, y_at(x_end))
        return path

    def _draw_snake(self, p, w, h, accent, accent_light, primary):
        y_c = h / 2.0
        amp = h * 0.42
        phase_px = self._t * 1.6 * self.TOOTH_W * 2
        full_path = self._build_zigzag(2, w - 2, y_c, amp, phase_px)
        guide_pen = QPen(QColor(255, 255, 255, 18), 2.0)
        guide_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        guide_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(guide_pen)
        p.drawPath(full_path)

        if self._indeterminate:
            x0, x1 = self._indeterminate_segment(w, 0.22)
            if x1 - x0 < 4:
                return
            seg = self._build_zigzag(x0, x1, y_c, amp, phase_px)
            grad = QLinearGradient(x0, 0, x1, 0)
            c0 = QColor(accent); c0.setAlpha(0)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(0.4, primary)
            grad.setColorAt(0.8, accent)
            grad.setColorAt(1.0, accent_light)
            pen = QPen(QBrush(grad), 3.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPath(seg)
            return

        if self.value <= 0:
            return
        x_end = 2 + self._fill_width(w)
        seg = self._build_zigzag(2, x_end, y_c, amp, phase_px)
        grad = QLinearGradient(0, 0, x_end, 0)
        grad.setColorAt(0.0, primary)
        grad.setColorAt(0.6, accent)
        grad.setColorAt(1.0, accent_light)
        pen = QPen(QBrush(grad), 3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(seg)

    def _draw_bar(self, p, w, h, accent, accent_light, primary):
        r = h / 2.0
        if self._indeterminate:
            x0, x1 = self._indeterminate_segment(w, 0.35, cycle=1.4)
            if x1 - x0 < 4:
                return
            body = QRectF(x0, 1.5, x1 - x0, h - 3)
            path = QPainterPath()
            path.addRoundedRect(body, r - 1.5, r - 1.5)
            grad = QLinearGradient(x0, 0, x1, 0)
            grad.setColorAt(0.0, primary)
            grad.setColorAt(0.5, accent)
            grad.setColorAt(1.0, accent_light)
            p.fillPath(path, QBrush(grad))
            gloss = QLinearGradient(0, 1.5, 0, h - 1.5)
            gloss.setColorAt(0.0, QColor(255, 255, 255, 90))
            gloss.setColorAt(0.55, QColor(255, 255, 255, 0))
            p.fillPath(path, QBrush(gloss))
            return

        fw = self._fill_width(w)
        if fw < 2:
            return
        body = QRectF(2, 1.5, fw, h - 3)
        path = QPainterPath()
        path.addRoundedRect(body, r - 1.5, r - 1.5)
        grad = QLinearGradient(0, 0, fw + 2, 0)
        grad.setColorAt(0.0, primary)
        grad.setColorAt(0.6, accent)
        grad.setColorAt(1.0, accent_light)
        p.fillPath(path, QBrush(grad))
        gloss = QLinearGradient(0, 1.5, 0, h - 1.5)
        gloss.setColorAt(0.0, QColor(255, 255, 255, 90))
        gloss.setColorAt(0.55, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(gloss))

        if self.value < 100:
            glow_w = max(20.0, h * 6)
            head_x = 2 + fw
            gl_x   = head_x - glow_w
            pulse  = 0.5 + 0.5 * math.sin(self._t * 2 * math.pi * 1.2)
            gl = QLinearGradient(gl_x, 0, head_x, 0)
            c = QColor(255, 255, 255, int(40 + 60 * pulse))
            c0 = QColor(c); c0.setAlpha(0)
            gl.setColorAt(0.0, c0)
            gl.setColorAt(1.0, c)
            clip = QPainterPath()
            clip.addRoundedRect(body, r - 1.5, r - 1.5)
            p.save()
            p.setClipPath(clip)
            p.fillRect(QRectF(gl_x, 1.5, glow_w, h - 3), QBrush(gl))
            p.restore()

    def _draw_pulse(self, p, w, h, accent, accent_light, primary):
        r = h / 2.0
        pulse = 0.5 + 0.5 * math.sin(self._t * 2 * math.pi * 1.0)

        if self._indeterminate:
            x0, x1 = self._indeterminate_segment(w, 0.5, cycle=2.0)
            if x1 - x0 < 4:
                return
            body = QRectF(x0, 1.5, x1 - x0, h - 3)
            path = QPainterPath()
            path.addRoundedRect(body, r - 1.5, r - 1.5)
            rg = QRadialGradient((x0 + x1) / 2, h / 2, (x1 - x0) / 2)
            ac = QColor(accent)
            al = QColor(accent_light)
            al.setAlpha(int(180 + 50 * pulse))
            rg.setColorAt(0.0, al)
            rg.setColorAt(0.6, ac)
            rg.setColorAt(1.0, QColor(primary))
            p.fillPath(path, QBrush(rg))
            return

        fw = self._fill_width(w)
        if fw < 2:
            return
        body = QRectF(2, 1.5, fw, h - 3)
        path = QPainterPath()
        path.addRoundedRect(body, r - 1.5, r - 1.5)
        grad = QLinearGradient(0, 0, fw + 2, 0)
        c1 = QColor(primary)
        c2 = QColor(accent);       c2.setAlpha(220 + int(35 * pulse))
        c3 = QColor(accent_light); c3.setAlpha(220 + int(35 * pulse))
        grad.setColorAt(0.0, c1)
        grad.setColorAt(0.5, c2)
        grad.setColorAt(1.0, c3)
        p.fillPath(path, QBrush(grad))
        if fw > 20:
            cx = 2 + fw / 2
            rr = fw / 2
            rg = QRadialGradient(cx, h / 2, rr)
            rg.setColorAt(0.0, QColor(255, 255, 255, int(60 + 60 * pulse)))
            rg.setColorAt(0.5, QColor(255, 255, 255, 0))
            p.fillPath(path, QBrush(rg))

    def _draw_dots(self, p, w, h, accent, accent_light, primary):
        if not self._indeterminate and self.value > 0:
            r = h / 2.0
            fw = self._fill_width(w)
            body = QRectF(2, h * 0.35, fw, h * 0.30)
            path = QPainterPath()
            path.addRoundedRect(body, h * 0.15, h * 0.15)
            grad = QLinearGradient(0, 0, fw + 2, 0)
            grad.setColorAt(0.0, primary)
            grad.setColorAt(1.0, accent_light)
            p.fillPath(path, QBrush(grad))

        n_dots = 5
        dot_r = h * 0.32
        spacing = dot_r * 2.4
        path_w = (n_dots - 1) * spacing
        cycle = 1.6
        full_phase = self._t / cycle
        going_right = int(full_phase) % 2 == 0
        local = full_phase - int(full_phase)
        ease = 3 * local * local - 2 * local * local * local
        if not going_right:
            ease = 1.0 - ease
        center_x = 2 + dot_r + ease * (w - 4 - 2 * dot_r - path_w)

        for i in range(n_dots):
            phase = self._t * 4.0 - i * 0.4
            scale = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(phase))
            rr = dot_r * scale
            x = center_x + i * spacing
            y = h / 2.0
            col = QColor(accent)
            col.setAlpha(int(200 * (0.4 + 0.6 * scale)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(x, y), rr, rr)

    def _draw_wave(self, p, w, h, accent, accent_light, primary):
        if self._indeterminate:
            self._draw_wave_filled(p, 2.0, w - 2.0, h,
                                   accent, accent_light, primary, alpha=200)
            return
        if self.value <= 0:
            return
        fw = self._fill_width(w)
        self._draw_wave_filled(p, 2.0, 2.0 + fw, h,
                               accent, accent_light, primary, alpha=220)

    def _draw_wave_filled(self, p, x0, x1, h, accent, accent_light, primary, alpha):
        if x1 - x0 < 4:
            return
        y_c = h / 2.0
        amp = h * 0.35
        phase = self._t * 4.0

        path = QPainterPath()
        path.moveTo(x0, h - 1.5)
        step = 1.5
        x = x0
        while x <= x1:
            y = y_c + math.sin(x * 0.08 + phase) * amp
            path.lineTo(x, y)
            x += step
        path.lineTo(x1, h - 1.5)
        path.closeSubpath()

        grad = QLinearGradient(x0, 0, x1, 0)
        c1 = QColor(primary);      c1.setAlpha(alpha)
        c2 = QColor(accent);       c2.setAlpha(alpha)
        c3 = QColor(accent_light); c3.setAlpha(alpha)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(0.6, c2)
        grad.setColorAt(1.0, c3)
        p.fillPath(path, QBrush(grad))

        crest = QPainterPath()
        x = x0
        first = True
        while x <= x1:
            y = y_c + math.sin(x * 0.08 + phase) * amp
            if first:
                crest.moveTo(x, y); first = False
            else:
                crest.lineTo(x, y)
            x += step
        pen = QPen(QColor(255, 255, 255, 140), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(crest)

    def _draw_glow(self, p, w, h, accent, accent_light, primary):
        r = h / 2.0
        if self._indeterminate:
            x0, x1 = self._indeterminate_segment(w, 0.45, cycle=1.8)
            if x1 - x0 < 4:
                return
            body = QRectF(x0, 1.5, x1 - x0, h - 3)
        else:
            fw = self._fill_width(w)
            if fw < 2:
                return
            body = QRectF(2, 1.5, fw, h - 3)

        path = QPainterPath()
        path.addRoundedRect(body, r - 1.5, r - 1.5)

        grad = QLinearGradient(body.left(), 0, body.right(), 0)
        grad.setColorAt(0.0, primary)
        grad.setColorAt(0.5, accent)
        grad.setColorAt(1.0, accent_light)
        p.fillPath(path, QBrush(grad))

        cx = body.center().x()
        cy = h / 2
        rr = body.width() / 1.5
        rg = QRadialGradient(cx, cy, max(rr, h))
        rg.setColorAt(0.0, QColor(255, 255, 255, 100))
        rg.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(rg))

        if body.width() > 20:
            phase = (self._t * 1.5) % 1.0
            bx = body.left() + phase * body.width()
            blink_w = body.width() * 0.18
            bgrad = QLinearGradient(bx - blink_w, 0, bx + blink_w, 0)
            c0 = QColor(255, 255, 255, 0)
            bgrad.setColorAt(0.0, c0)
            bgrad.setColorAt(0.5, QColor(255, 255, 255, 160))
            bgrad.setColorAt(1.0, c0)
            p.save()
            p.setClipPath(path)
            p.fillRect(QRectF(bx - blink_w, 1.5,
                              blink_w * 2, h - 3), QBrush(bgrad))
            p.restore()


class SnakeProgress(ProgressBar):
    """Алиас для обратной совместимости."""
    def __init__(self, theme: dict, parent=None):
        super().__init__(theme, style_name="snake", parent=parent)


# ═══════════════════════════════════════════════════════════════
#  BorderOverlay — толстая обводка ПОВЕРХ всего окна
# ═══════════════════════════════════════════════════════════════

class BorderOverlay(QWidget):
    """
    Накладывается на родителя; рисует ТОЛЬКО рамку (внутри прозрачно),
    не перехватывает мышь. Толщина и радиус — настраиваемые на лету.
    """

    def __init__(self, theme: dict, border: int = 6, radius: int = 18,
                 parent: QWidget = None):
        super().__init__(parent)
        self.theme = theme
        self.border = max(2, int(border))
        self.radius = max(4, int(radius))
        self._rb_phase = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        if theme.get("rainbow"):
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(28)
        else:
            self._timer = None

    def set_border(self, b: int) -> None:
        """Изменить ширину обводки (на лету)."""
        self.border = max(2, int(b))
        self.update()

    def set_radius(self, r: int) -> None:
        self.radius = max(4, int(r))
        self.update()

    def apply_theme(self, theme: dict) -> None:
        self.theme = theme
        if theme.get("rainbow"):
            if not self._timer:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._tick)
            if not self._timer.isActive():
                self._timer.start(28)
        else:
            if self._timer and self._timer.isActive():
                self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._rb_phase = (self._rb_phase + 1.6) % 360.0
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self.border
        half = b / 2.0
        rect = QRectF(half, half, self.width() - b, self.height() - b)

        if self.theme.get("rainbow"):
            cg = QConicalGradient(rect.center(), self._rb_phase)
            cols = [
                QColor(255, 0, 0), QColor(255, 165, 0), QColor(255, 255, 0),
                QColor(0, 255, 0), QColor(0, 150, 255), QColor(100, 0, 255),
                QColor(255, 0, 200), QColor(255, 0, 0),
            ]
            for i, c in enumerate(cols):
                cg.setColorAt(i / (len(cols) - 1), c)
            brush = QBrush(cg)
        else:
            bg = QLinearGradient(0, 0, self.width(), self.height())
            bg.setColorAt(0.0,  QColor(self.theme["primary"]))
            bg.setColorAt(0.35, QColor(self.theme["accent"]))
            bg.setColorAt(0.65, QColor(self.theme["accent_light"]))
            bg.setColorAt(1.0,  QColor(self.theme["primary"]))
            brush = QBrush(bg)

        pen = QPen(brush, float(b))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        p.drawPath(path)
        p.end()
