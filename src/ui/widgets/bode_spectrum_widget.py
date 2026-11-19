"""Interactive Bode magnitude/phase + real-time dual FFT spectrum widget (HiDPI cached)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget


@dataclass
class BodeNode:
    node_id: int
    freq: float
    gain_db: float
    q: float
    color: str
    label: str
    supports_gain: bool = True
    supports_q: bool = True
    response_db: float | None = None


def _system_font(size: int, bold: bool = False, mono: bool = False) -> QFont:
    kind = (
        QFontDatabase.SystemFont.FixedFont
        if mono
        else QFontDatabase.SystemFont.GeneralFont
    )
    font = QFontDatabase.systemFont(kind)
    font.setPointSize(size)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font


class BodeSpectrumWidget(QWidget):
    """Pro-audio Bode response + live Pre/Post FFT analyzer with HiDPI static caching."""

    # Emits (node_id, new_freq, new_gain_db, new_q)
    node_changed = Signal(int, float, float, float)

    FREQ_MIN = 20.0
    FREQ_MAX = 20000.0
    LOG_MIN = math.log10(FREQ_MIN)
    LOG_MAX = math.log10(FREQ_MAX)
    LOG_SPAN = LOG_MAX - LOG_MIN

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.setMouseTracking(True)

        self.y_min_db: float = -48.0
        self.y_max_db: float = 24.0

        self.show_fft: bool = True
        self.show_phase: bool = False
        self.show_ideal: bool = False

        self.freqs: np.ndarray = np.geomspace(self.FREQ_MIN, self.FREQ_MAX, 300)
        self._bode_norm_x: np.ndarray = (np.log10(self.freqs) - self.LOG_MIN) / self.LOG_SPAN
        self.mag_db: np.ndarray = np.zeros_like(self.freqs)
        self.phase_deg: np.ndarray = np.zeros_like(self.freqs)
        self.indiv_curves: list[np.ndarray] = []
        self.ideal_db: np.ndarray | None = None
        self.ideal_cutoff: float | None = None

        self.nodes: list[BodeNode] = []
        self._dragging_idx: int | None = None
        self._hover_idx: int | None = None
        self._hover_pos: QPointF | None = None

        # Dedicated compact 160-point logarithmic FFT grid for ultra-fast rendering
        self._fft_freqs: np.ndarray = np.geomspace(self.FREQ_MIN, self.FREQ_MAX, 160)
        self._fft_norm_x: np.ndarray = (np.log10(self._fft_freqs) - self.LOG_MIN) / self.LOG_SPAN
        self._fft_pre_db: np.ndarray | None = None
        self._fft_post_db: np.ndarray | None = None

        # Pre-allocated FFT window/bins cache
        self._cached_n_fft: int = 0
        self._cached_sr: float = 0.0
        self._hann_win: np.ndarray | None = None
        self._win_norm: float = 1.0
        self._fft_bins_hz: np.ndarray | None = None
        self._fft_valid_mask: np.ndarray | None = None

        # HiDPI static backdrop + Bode curve pixmap cache
        self._static_cache: QPixmap | None = None
        self._static_dirty: bool = True

        # Pre-allocated fonts & pens (avoids CoreText font resolution inside paintEvent)
        self._font_axis = _system_font(9, mono=True)
        self._font_label = _system_font(9)
        self._font_node = _system_font(8, bold=True)
        self._font_tooltip = _system_font(9, mono=True)

        self._pen_fft_pre = QPen(QColor(245, 158, 11, 145), 1.3)
        self._pen_fft_post = QPen(QColor(0, 210, 255, 200), 1.5)
        self._brush_fft_fill = QColor(0, 210, 255, 34)
        self._pen_bode_glow = QPen(QColor(0, 210, 255, 65), 6.0)
        self._pen_bode_main = QPen(QColor("#00e5ff"), 2.4)
        self._pen_ideal = QPen(QColor(226, 232, 240, 150), 1.5, Qt.PenStyle.DashLine)
        self._pen_phase = QPen(QColor(168, 85, 247, 175), 1.4, Qt.PenStyle.DashLine)

    def invalidate_static_cache(self) -> None:
        self._static_dirty = True
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._static_dirty = True
        super().resizeEvent(event)

    def set_y_range(self, y_min_db: float, y_max_db: float) -> None:
        if self.y_min_db != float(y_min_db) or self.y_max_db != float(y_max_db):
            self.y_min_db = float(y_min_db)
            self.y_max_db = float(y_max_db)
            self._static_dirty = True
            self.update()

    def set_responses(
        self,
        freqs: np.ndarray,
        mag_db: np.ndarray,
        phase_deg: np.ndarray,
        indiv_curves: Sequence[np.ndarray] | None = None,
        ideal_db: np.ndarray | None = None,
        ideal_cutoff: float | None = None,
    ) -> None:
        freqs_arr = np.asarray(freqs, dtype=np.float64)
        if len(freqs_arr) != len(self.freqs) or not np.array_equal(freqs_arr, self.freqs):
            self.freqs = freqs_arr
            self._bode_norm_x = (
                np.log10(np.clip(freqs_arr, self.FREQ_MIN, self.FREQ_MAX)) - self.LOG_MIN
            ) / self.LOG_SPAN
        self.mag_db = np.asarray(mag_db, dtype=np.float64)
        self.phase_deg = np.asarray(phase_deg, dtype=np.float64)
        self.indiv_curves = [np.asarray(c, dtype=np.float64) for c in (indiv_curves or ())]
        self.ideal_db = np.asarray(ideal_db, dtype=np.float64) if ideal_db is not None else None
        self.ideal_cutoff = ideal_cutoff
        self._static_dirty = True
        self.update()

    def set_nodes(self, nodes: list[BodeNode]) -> None:
        self.nodes = list(nodes)
        self.update()

    def update_fft(self, pre_samples: np.ndarray, post_samples: np.ndarray, sample_rate: float) -> None:
        if not self.show_fft or len(pre_samples) < 1024:
            return
        n_fft = 2048 if len(pre_samples) >= 2048 else 1024
        sr = max(8000.0, float(sample_rate))

        if n_fft != self._cached_n_fft or sr != self._cached_sr or self._hann_win is None:
            self._cached_n_fft = n_fft
            self._cached_sr = sr
            self._hann_win = np.hanning(n_fft).astype(np.float32)
            self._win_norm = float(np.sum(self._hann_win)) * 0.5
            bins = np.fft.rfftfreq(n_fft, d=1.0 / sr)
            mask = bins >= self.FREQ_MIN
            self._fft_valid_mask = mask
            self._fft_bins_hz = bins[mask]

        win = self._hann_win
        pre_seg = pre_samples[-n_fft:] * win
        post_seg = post_samples[-n_fft:] * win

        inv_norm = 1.0 / max(self._win_norm, 1e-6)
        spec_pre = np.abs(np.fft.rfft(pre_seg))[self._fft_valid_mask] * inv_norm
        spec_post = np.abs(np.fft.rfft(post_seg))[self._fft_valid_mask] * inv_norm

        pre_db = 20.0 * np.log10(np.maximum(spec_pre, 1e-6))
        post_db = 20.0 * np.log10(np.maximum(spec_post, 1e-6))

        pre_interp = np.interp(self._fft_freqs, self._fft_bins_hz, pre_db)
        post_interp = np.interp(self._fft_freqs, self._fft_bins_hz, post_db)

        if self._fft_pre_db is None or len(self._fft_pre_db) != len(pre_interp):
            self._fft_pre_db = pre_interp
            self._fft_post_db = post_interp
        else:
            alpha = 0.35
            self._fft_pre_db = (1.0 - alpha) * self._fft_pre_db + alpha * pre_interp
            self._fft_post_db = (1.0 - alpha) * self._fft_post_db + alpha * post_interp
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(48.0, 14.0, max(120.0, self.width() - 72.0), max(80.0, self.height() - 40.0))

    def _freq_to_x(self, freq: float, r: QRectF) -> float:
        lf = math.log10(max(self.FREQ_MIN, min(self.FREQ_MAX, float(freq))))
        t = (lf - self.LOG_MIN) / self.LOG_SPAN
        return r.left() + t * r.width()

    def _x_to_freq(self, x: float, r: QRectF) -> float:
        t = max(0.0, min(1.0, (x - r.left()) / max(1.0, r.width())))
        lf = self.LOG_MIN + t * self.LOG_SPAN
        return float(10.0 ** lf)

    def _db_to_y(self, db: float, r: QRectF) -> float:
        span = max(1.0, self.y_max_db - self.y_min_db)
        t = (float(db) - self.y_min_db) / span
        t = max(-0.08, min(1.08, t))
        return r.bottom() - t * r.height()

    def _y_to_db(self, y: float, r: QRectF) -> float:
        t = max(0.0, min(1.0, (r.bottom() - y) / max(1.0, r.height())))
        return self.y_min_db + t * (self.y_max_db - self.y_min_db)

    def _build_polyline(self, norm_x: np.ndarray, y_vals: np.ndarray, r: QRectF) -> QPolygonF:
        """Vectorized conversion from (norm_x, dB) arrays to QPolygonF."""
        xs = r.left() + norm_x * r.width()
        span = max(1.0, self.y_max_db - self.y_min_db)
        t = np.clip((y_vals - self.y_min_db) / span, 0.0, 1.0)
        ys = r.bottom() - t * r.height()
        return QPolygonF([QPointF(x, y) for x, y in zip(xs.tolist(), ys.tolist())])

    def _node_point(self, node: BodeNode, r: QRectF) -> QPointF:
        y_val = (
            node.gain_db
            if node.supports_gain
            else (node.response_db if node.response_db is not None else 0.0)
        )
        return QPointF(self._freq_to_x(node.freq, r), self._db_to_y(y_val, r))

    def _hit_test_node(self, pos: QPointF) -> int | None:
        r = self._plot_rect()
        best_idx = None
        best_dist = 16.0
        for idx, node in enumerate(self.nodes):
            pt = self._node_point(node, r)
            dist = math.hypot(pos.x() - pt.x(), pos.y() - pt.y())
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test_node(event.position())
            if idx is not None:
                self._dragging_idx = idx
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        self._hover_pos = pos
        r = self._plot_rect()

        if self._dragging_idx is not None and 0 <= self._dragging_idx < len(self.nodes):
            node = self.nodes[self._dragging_idx]
            new_freq = max(20.0, min(20000.0, self._x_to_freq(pos.x(), r)))
            new_gain = node.gain_db
            new_q = node.q
            if node.supports_gain:
                new_gain = max(-18.0, min(18.0, self._y_to_db(pos.y(), r)))
            elif node.supports_q:
                rel_db = max(-24.0, min(24.0, self._y_to_db(pos.y(), r)))
                new_q = max(0.3, min(20.0, 0.7071 * (10.0 ** (rel_db / 28.0))))
            self.node_changed.emit(node.node_id, new_freq, new_gain, new_q)
            self.update()
            return

        hit = self._hit_test_node(pos)
        self._hover_idx = hit
        self.setCursor(Qt.CursorShape.OpenHandCursor if hit is not None else Qt.CursorShape.CrossCursor)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging_idx is not None:
            self._dragging_idx = None
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self._hover_idx is not None
                else Qt.CursorShape.CrossCursor
            )
            self.update()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_pos = None
        self._hover_idx = None
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        idx = self._dragging_idx if self._dragging_idx is not None else self._hover_idx
        if idx is None and self.nodes:
            idx = 0
        if idx is not None and 0 <= idx < len(self.nodes):
            node = self.nodes[idx]
            if node.supports_q:
                delta = event.angleDelta().y() / 120.0
                factor = 1.12 ** delta
                new_q = max(0.25, min(25.0, node.q * factor))
                self.node_changed.emit(node.node_id, node.freq, node.gain_db, new_q)
                event.accept()
                return
        super().wheelEvent(event)

    def _rebuild_static_cache(self) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        dpr = max(1.0, float(self.devicePixelRatioF()))
        pm = QPixmap(int(round(w * dpr)), int(round(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor("#0d0f14"))

        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self._plot_rect()
        p.fillRect(r, QColor("#10131b"))

        # Grid: logarithmic frequency lines
        grid_freqs = (20, 30, 50, 100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000, 20000)
        label_freqs = {20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000}
        p.setFont(self._font_axis)

        pen_major = QPen(QColor("#242c3d"), 1)
        pen_minor = QPen(QColor("#181e2b"), 1)
        for gf in grid_freqs:
            gx = self._freq_to_x(gf, r)
            p.setPen(pen_major if gf in (100, 1000, 10000) else pen_minor)
            p.drawLine(QPointF(gx, r.top()), QPointF(gx, r.bottom()))
            if gf in label_freqs:
                lbl = f"{gf // 1000}k" if gf >= 1000 else str(gf)
                p.setPen(QColor("#74829c"))
                p.drawText(QRectF(gx - 18, r.bottom() + 4, 36, 16), Qt.AlignmentFlag.AlignCenter, lbl)

        # Horizontal dB grid lines
        step_db = 6.0 if (self.y_max_db - self.y_min_db) <= 50.0 else 12.0
        db_tick = math.ceil(self.y_min_db / step_db) * step_db
        pen_zero = QPen(QColor("#475569"), 1.3)
        pen_db = QPen(QColor("#1a202e"), 1)
        while db_tick <= self.y_max_db + 0.1:
            gy = self._db_to_y(db_tick, r)
            p.setPen(pen_zero if abs(db_tick) < 0.01 else pen_db)
            p.drawLine(QPointF(r.left(), gy), QPointF(r.right(), gy))
            p.setPen(QColor("#74829c"))
            p.drawText(
                QRectF(4, gy - 8, 38, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{int(round(db_tick))}",
            )
            db_tick += step_db

        # -3 dB Cutoff reference line
        if self.y_min_db <= -3.0 <= self.y_max_db:
            y_3db = self._db_to_y(-3.0, r)
            p.setPen(QPen(QColor(16, 185, 129, 110), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(r.left(), y_3db), QPointF(r.right(), y_3db))
            p.setPen(QColor(16, 185, 129, 175))
            p.drawText(QPointF(r.left() + 6, y_3db - 4), "-3 dB")

        p.save()
        p.setClipRect(r)

        # Ideal Brick-wall Curve + Transition Zone (Slide 7)
        if self.show_ideal and self.ideal_db is not None:
            if self.ideal_cutoff is not None:
                x_low = self._freq_to_x(max(self.FREQ_MIN, self.ideal_cutoff * 0.7), r)
                x_high = self._freq_to_x(min(self.FREQ_MAX, self.ideal_cutoff * 1.4), r)
                p.fillRect(
                    QRectF(x_low, r.top(), max(6.0, x_high - x_low), r.height()),
                    QColor(148, 163, 184, 22),
                )
            p.setPen(self._pen_ideal)
            p.drawPolyline(self._build_polyline(self._bode_norm_x, self.ideal_db, r))

        # Individual curves (Series / Parallel / Parametric bands)
        palette = ("#f59e0b", "#10b981", "#a855f7", "#ec4899", "#38bdf8", "#f97316")
        for i, curve in enumerate(self.indiv_curves):
            col = QColor(palette[i % len(palette)])
            col.setAlpha(125)
            p.setPen(QPen(col, 1.2, Qt.PenStyle.DashLine))
            p.drawPolyline(self._build_polyline(self._bode_norm_x, curve, r))

        # Phase response curve (purple dashed, mapped -180..+180 deg)
        if self.show_phase and len(self.phase_deg) == len(self.freqs):
            wrapped = ((self.phase_deg + 180.0) % 360.0) - 180.0
            xs = r.left() + self._bode_norm_x * r.width()
            ys = r.bottom() - ((wrapped + 180.0) / 360.0) * r.height()
            p.setPen(self._pen_phase)
            p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(xs.tolist(), ys.tolist())]))

        # Composite Filter Magnitude Response Curve
        bode_poly = self._build_polyline(self._bode_norm_x, self.mag_db, r)
        p.setPen(self._pen_bode_glow)
        p.drawPolyline(bode_poly)
        p.setPen(self._pen_bode_main)
        p.drawPolyline(bode_poly)

        p.restore()

        # Frame border & Static Legend
        p.setPen(QColor("#273145"))
        p.drawRect(r)

        p.setFont(self._font_label)
        p.setPen(QColor("#94a3b8"))
        p.drawText(QPointF(r.left() + 6, r.top() + 15), "Risposta Bode (dB)")
        if self.show_fft:
            p.setPen(QColor("#f59e0b"))
            p.drawText(QPointF(r.left() + 135, r.top() + 15), "● FFT Pre")
            p.setPen(QColor("#00d2ff"))
            p.drawText(QPointF(r.left() + 205, r.top() + 15), "● FFT Post")
        if self.show_ideal and self.ideal_db is not None:
            p.setPen(QColor("#cbd5e1"))
            p.drawText(QPointF(r.left() + 280, r.top() + 15), "--- Ideale / Transition Zone")

        p.end()
        self._static_cache = pm
        self._static_dirty = False

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        if self._static_dirty or self._static_cache is None:
            self._rebuild_static_cache()

        p = QPainter(self)
        p.drawPixmap(0, 0, self._static_cache)

        r = self._plot_rect()
        p.save()
        p.setClipRect(r)

        # Dynamic Live FFT Spectra (no antialiasing -> 4-6x faster, crisp & vector-clean)
        if self.show_fft and self._fft_pre_db is not None and self._fft_post_db is not None:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            fft_offset = 12.0 if self.y_max_db >= 20.0 else 6.0
            pre_shifted = np.clip(self._fft_pre_db + fft_offset, self.y_min_db - 2.0, self.y_max_db)
            post_shifted = np.clip(self._fft_post_db + fft_offset, self.y_min_db - 2.0, self.y_max_db)

            pre_poly = self._build_polyline(self._fft_norm_x, pre_shifted, r)
            p.setPen(self._pen_fft_pre)
            p.drawPolyline(pre_poly)

            post_poly = self._build_polyline(self._fft_norm_x, post_shifted, r)
            fill_poly = QPolygonF(post_poly)
            fill_poly.append(QPointF(r.right(), r.bottom()))
            fill_poly.append(QPointF(r.left(), r.bottom()))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._brush_fft_fill)
            p.drawPolygon(fill_poly)

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(self._pen_fft_post)
            p.drawPolyline(post_poly)

        # Draggable Nodes (antialiased circles)
        if self.nodes:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setFont(self._font_node)
            for idx, node in enumerate(self.nodes):
                pt = self._node_point(node, r)
                is_active = (idx == self._dragging_idx) or (idx == self._hover_idx)
                col = QColor(node.color)
                rad = 9.0 if is_active else 7.0
                p.setBrush(QColor("#0d0f14"))
                p.setPen(QPen(col, 2.5 if is_active else 2.0))
                p.drawEllipse(pt, rad, rad)
                p.setBrush(col)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(pt, 3.2, 3.2)
                p.setPen(col)
                p.drawText(QPointF(pt.x() + 10, pt.y() - 6), node.label)

        # Floating cursor/node readout tooltip
        tooltip_text = ""
        if self._dragging_idx is not None and 0 <= self._dragging_idx < len(self.nodes):
            n = self.nodes[self._dragging_idx]
            tooltip_text = f"{n.label}: {n.freq:,.0f} Hz | {n.gain_db:+.1f} dB | Q={n.q:.2f}"
        elif self._hover_pos is not None and r.contains(self._hover_pos):
            hf = self._x_to_freq(self._hover_pos.x(), r)
            hdb = self._y_to_db(self._hover_pos.y(), r)
            cur_mag = float(np.interp(hf, self.freqs, self.mag_db))
            tooltip_text = f"{hf:,.0f} Hz  |  Curva: {cur_mag:+.1f} dB  |  Cursore: {hdb:+.1f} dB"

        if tooltip_text:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setFont(self._font_tooltip)
            box = QRectF(r.right() - 320, r.top() + 6, 312, 22)
            p.setBrush(QColor(15, 20, 30, 215))
            p.setPen(QPen(QColor("#2c3b57"), 1))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor("#e2e8f0"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, tooltip_text)

        p.restore()
