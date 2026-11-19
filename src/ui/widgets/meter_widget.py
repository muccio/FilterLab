"""Stereo Peak Meters, Overload LED, Aux Bus Meter, and Waveform Seek Widget."""

from __future__ import annotations

import time
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class StereoMeterWidget(QWidget):
    """Vertical stereo dBFS Peak Meter (-60..0 dB) with Peak Hold and Overload LED."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(64, 150)
        self.setMaximumWidth(86)
        self._l_db = -60.0
        self._r_db = -60.0
        self._hold_l = -60.0
        self._hold_r = -60.0
        self._overload_until = 0.0

    def update_levels(self, l_db: float, r_db: float, overload: bool) -> None:
        self._l_db = max(-60.0, min(0.0, float(l_db)))
        self._r_db = max(-60.0, min(0.0, float(r_db)))
        self._hold_l = max(self._l_db, self._hold_l - 0.45)
        self._hold_r = max(self._r_db, self._hold_r - 0.45)
        if overload:
            self._overload_until = time.monotonic() + 1.2
        self.update()

    def _db_to_ratio(self, db: float) -> float:
        return max(0.0, min(1.0, (db + 60.0) / 60.0))

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#0d0f14"))

        # Overload LED header
        led_on = time.monotonic() < self._overload_until
        led_rect_h = 16
        led_col = QColor("#ef4444") if led_on else QColor("#2a161b")
        p.setPen(QPen(QColor("#522630"), 1))
        p.setBrush(led_col)
        p.drawRoundedRect(6, 4, w - 12, led_rect_h, 4, 4)
        p.setPen(QColor("#ffffff") if led_on else QColor("#8f5e66"))
        p.setFont(QFont("Sans", 8, QFont.Weight.Bold))
        p.drawText(6, 4, w - 12, led_rect_h, Qt.AlignmentFlag.AlignCenter, "OL")

        top = 26
        bot = h - 18
        bar_h = max(20, bot - top)

        bar_w = 14
        lx = 10
        rx = 10 + bar_w + 5

        grad = QLinearGradient(0, bot, 0, top)
        grad.setColorAt(0.0, QColor("#10b981"))
        grad.setColorAt(0.75, QColor("#10b981"))
        grad.setColorAt(0.85, QColor("#f59e0b"))
        grad.setColorAt(1.0, QColor("#ef4444"))

        for x_pos, val_db, hold_db in ((lx, self._l_db, self._hold_l), (rx, self._r_db, self._hold_r)):
            p.fillRect(x_pos, top, bar_w, bar_h, QColor("#171b24"))
            fill_h = int(self._db_to_ratio(val_db) * bar_h)
            if fill_h > 0:
                p.fillRect(x_pos, bot - fill_h, bar_w, fill_h, grad)
            hy = bot - int(self._db_to_ratio(hold_db) * bar_h)
            p.setPen(QPen(QColor("#e2e8f0"), 2))
            p.drawLine(x_pos, hy, x_pos + bar_w, hy)

        # dB ticks on right
        p.setPen(QColor("#64748b"))
        p.setFont(QFont("Monospace", 8))
        scale_x = rx + bar_w + 4
        for tick_db in (0, -6, -12, -24, -48):
            ty = bot - int(self._db_to_ratio(float(tick_db)) * bar_h)
            p.drawText(scale_x, ty - 5, w - scale_x - 2, 12, Qt.AlignmentFlag.AlignLeft, f"{tick_db}")

        p.setPen(QColor("#94a3b8"))
        p.setFont(QFont("Sans", 8, QFont.Weight.Bold))
        p.drawText(lx, bot + 2, bar_w, 14, Qt.AlignmentFlag.AlignCenter, "L")
        p.drawText(rx, bot + 2, bar_w, 14, Qt.AlignmentFlag.AlignCenter, "R")


class AuxMeterBar(QWidget):
    """Compact horizontal meter showing Aux Send signal level (Pre vs Post fader)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(14)
        self._db = -60.0

    def set_level_db(self, db: float) -> None:
        self._db = max(-60.0, min(0.0, float(db)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#151923"))
        ratio = max(0.0, min(1.0, (self._db + 60.0) / 60.0))
        fill_w = int(ratio * w)
        if fill_w > 0:
            col = QColor("#00d2ff") if self._db < -6.0 else QColor("#f59e0b")
            p.fillRect(0, 0, fill_w, h, col)
        p.setPen(QColor("#2c3448"))
        p.drawRect(0, 0, w - 1, h - 1)


class WaveformSeekWidget(QWidget):
    """Clickable waveform overview bar for audio file seek and playhead display."""

    seek_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(34)
        self.setMaximumHeight(42)
        self._peaks = np.zeros(200, dtype=np.float32)
        self._pos_ratio = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_waveform(self, peaks: np.ndarray | None) -> None:
        if peaks is None or len(peaks) == 0:
            self._peaks = np.zeros(200, dtype=np.float32)
        else:
            self._peaks = np.asarray(peaks, dtype=np.float32)
        self.update()

    def set_position(self, ratio: float) -> None:
        self._pos_ratio = max(0.0, min(1.0, float(ratio)))
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.width() > 0:
            ratio = max(0.0, min(1.0, event.position().x() / float(self.width())))
            self.seek_requested.emit(ratio)

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#11151e"))

        n = len(self._peaks)
        mid = h * 0.5
        if n > 0:
            step = w / float(n)
            for i in range(n):
                amp = float(self._peaks[i]) * (h * 0.44)
                x = i * step
                played = (i / float(n)) <= self._pos_ratio
                col = QColor("#00d2ff") if played else QColor("#3a4761")
                p.setPen(QPen(col, max(1.0, step * 0.7)))
                p.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))

        px = int(self._pos_ratio * w)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawLine(px, 0, px, h)

        p.setPen(QColor("#283145"))
        p.drawRect(0, 0, w - 1, h - 1)
