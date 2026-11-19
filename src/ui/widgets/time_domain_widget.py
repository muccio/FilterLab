"""Time-domain inspection widget: Impulse Response (Ringing), Oscilloscope, and Blackbox Δt."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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


class _TimeCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.mode: str = "impulse"
        self.times_ms: np.ndarray = np.linspace(0.0, 40.0, 1024)
        self.impulse: np.ndarray = np.zeros(1024)
        self.ringing_ms: float = 0.0

        self.pre_wave: np.ndarray = np.zeros(512, dtype=np.float32)
        self.post_wave: np.ndarray = np.zeros(512, dtype=np.float32)
        self.sample_rate: float = 48000.0

        self._impulse_cache: QPixmap | None = None
        self._impulse_dirty: bool = True
        self._scope_bg_cache: QPixmap | None = None
        self._scope_bg_dirty: bool = True

        self._font_axis = _system_font(8, mono=True)
        self._font_label_bold = _system_font(8, bold=True)
        self._font_title_bold = _system_font(9, bold=True)
        self._font_box_title = _system_font(10, bold=True)

        self._pen_grid = QPen(QColor("#232b3d"), 1)
        self._pen_pre = QPen(QColor(245, 158, 11, 165), 1.3)
        self._pen_post = QPen(QColor("#00d2ff"), 1.8)
        self._pen_border = QPen(QColor("#273145"), 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._impulse_dirty = True
        self._scope_bg_dirty = True
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        if self.mode == "impulse":
            if self._impulse_dirty or self._impulse_cache is None:
                self._rebuild_impulse_cache()
            p = QPainter(self)
            p.drawPixmap(0, 0, self._impulse_cache)
            return

        p = QPainter(self)
        if self.mode == "scope":
            self._paint_scope(p)
        else:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_blackbox(p)

    def _rebuild_impulse_cache(self) -> None:
        w = max(1, self.width())
        h_px = max(1, self.height())
        dpr = max(1.0, float(self.devicePixelRatioF()))
        pm = QPixmap(int(round(w * dpr)), int(round(h_px * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor("#0d0f14"))

        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        r = QRectF(42.0, 8.0, max(100.0, w - 56.0), max(60.0, h_px - 28.0))
        p.fillRect(r, QColor("#10131b"))

        max_ms = max(25.0, min(80.0, self.ringing_ms * 1.45 if self.ringing_ms > 15.0 else 30.0))
        mask = self.times_ms <= max_ms
        t = self.times_ms[mask]
        h = self.impulse[mask]
        peak = float(np.max(np.abs(h))) if len(h) else 1.0
        peak = max(peak, 1e-6)
        h_norm = h / peak

        mid_y = r.center().y()
        p.setPen(self._pen_grid)
        p.drawLine(QPointF(r.left(), mid_y), QPointF(r.right(), mid_y))

        if self.ringing_ms > 0.1 and max_ms > 0:
            rx = r.left() + min(1.0, self.ringing_ms / max_ms) * r.width()
            p.fillRect(QRectF(r.left(), r.top(), rx - r.left(), r.height()), QColor(0, 210, 255, 16))
            p.setPen(QPen(QColor(245, 158, 11, 160), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(rx, r.top()), QPointF(rx, r.bottom()))

        if len(t) > 1:
            step = max(1, len(t) // 360)
            t_dec = t[::step]
            h_dec = h_norm[::step]
            xs = r.left() + (t_dec / max_ms) * r.width()
            ys = mid_y - h_dec * (r.height() * 0.44)
            poly = QPolygonF([QPointF(x, y) for x, y in zip(xs.tolist(), ys.tolist())])
            p.setPen(self._pen_post)
            p.drawPolyline(poly)

        p.setPen(QColor("#74829c"))
        p.setFont(self._font_axis)
        for ms in np.linspace(0.0, max_ms, 5):
            tx = r.left() + (ms / max_ms) * r.width()
            p.drawText(QRectF(tx - 20, r.bottom() + 2, 40, 14), Qt.AlignmentFlag.AlignCenter, f"{ms:.0f} ms")
        p.drawText(QPointF(4, r.top() + 12), "+1")
        p.drawText(QPointF(4, mid_y + 4), "0")
        p.drawText(QPointF(4, r.bottom() - 4), "-1")

        p.setPen(self._pen_border)
        p.drawRect(r)
        p.end()
        self._impulse_cache = pm
        self._impulse_dirty = False

    def _rebuild_scope_bg_cache(self) -> None:
        w = max(1, self.width())
        h_px = max(1, self.height())
        dpr = max(1.0, float(self.devicePixelRatioF()))
        pm = QPixmap(int(round(w * dpr)), int(round(h_px * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor("#0d0f14"))

        p = QPainter(pm)
        r = QRectF(42.0, 8.0, max(100.0, w - 56.0), max(60.0, h_px - 24.0))
        p.fillRect(r, QColor("#10131b"))
        mid_y = r.center().y()
        p.setPen(self._pen_grid)
        p.drawLine(QPointF(r.left(), mid_y), QPointF(r.right(), mid_y))

        p.setFont(self._font_label_bold)
        p.setPen(QColor("#f59e0b"))
        p.drawText(QPointF(r.left() + 8, r.top() + 14), "Ingresso x[n]")
        p.setPen(QColor("#00d2ff"))
        p.drawText(QPointF(r.left() + 92, r.top() + 14), "Uscita Filtrata y[n]")

        p.setPen(self._pen_border)
        p.drawRect(r)
        p.end()
        self._scope_bg_cache = pm
        self._scope_bg_dirty = False

    def _paint_scope(self, p: QPainter) -> None:
        if self._scope_bg_dirty or self._scope_bg_cache is None:
            self._rebuild_scope_bg_cache()
        p.drawPixmap(0, 0, self._scope_bg_cache)

        r = QRectF(42.0, 8.0, max(100.0, self.width() - 56.0), max(60.0, self.height() - 24.0))
        mid_y = r.center().y()

        n = min(512, len(self.pre_wave), len(self.post_wave))
        if n > 4:
            pre = self.pre_wave[-n:]
            post = self.post_wave[-n:]
            search_limit = min(n // 2, 200)
            crossings = np.flatnonzero((pre[: search_limit - 1] < 0.0) & (pre[1:search_limit] >= 0.0))
            start = int(crossings[0]) + 1 if len(crossings) > 0 else 0

            pre_seg = pre[start:]
            post_seg = post[start:]
            seg_len = len(pre_seg)
            if seg_len > 1:
                step = max(1, seg_len // 180)
                pre_dec = np.clip(pre_seg[::step], -1.0, 1.0)
                post_dec = np.clip(post_seg[::step], -1.0, 1.0)
                m = len(pre_dec)
                xs = np.linspace(r.left(), r.right(), m)
                half_h = r.height() * 0.44
                ys_pre = mid_y - pre_dec * half_h
                ys_post = mid_y - post_dec * half_h

                xs_l = xs.tolist()
                p.setPen(self._pen_pre)
                p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(xs_l, ys_pre.tolist())]))
                p.setPen(self._pen_post)
                p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(xs_l, ys_post.tolist())]))

    def _paint_blackbox(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#10131b"))

        cy = h * 0.52
        box_w = min(155.0, w * 0.22)
        box_h = 50.0
        bx = (w - box_w) * 0.5
        by = cy - box_h * 0.5

        p.setPen(QPen(QColor("#64748b"), 2))
        p.drawLine(QPointF(16, cy), QPointF(bx - 6, cy))
        p.drawLine(QPointF(bx + box_w + 6, cy), QPointF(w - 16, cy))

        p.setBrush(QColor("#162638"))
        p.setPen(QPen(QColor("#00d2ff"), 2))
        p.drawRoundedRect(QRectF(bx, by, box_w, box_h), 10, 10)
        p.setPen(QColor("#e0f9ff"))
        p.setFont(self._font_box_title)
        p.drawText(QRectF(bx, by, box_w, box_h), Qt.AlignmentFlag.AlignCenter, "Digital Filter\nH(z)")

        n_samp = 8
        pre_s = self.pre_wave[-n_samp:] if len(self.pre_wave) >= n_samp else np.zeros(n_samp)
        post_s = self.post_wave[-n_samp:] if len(self.post_wave) >= n_samp else np.zeros(n_samp)

        left_span = max(120.0, bx - 28.0)
        right_start = bx + box_w + 18.0
        right_span = max(120.0, w - right_start - 12.0)

        cell_w_l = min(44.0, left_span / n_samp - 3.0)
        cell_w_r = min(44.0, right_span / n_samp - 3.0)
        dt_us = 1e6 / max(8000.0, self.sample_rate)

        p.setFont(self._font_axis)
        pen_in = QPen(QColor("#f59e0b"), 1)
        pen_out = QPen(QColor("#00d2ff"), 1)
        for i in range(n_samp):
            x_l = 14.0 + i * (cell_w_l + 3.0)
            val_in = int(round(float(pre_s[i]) * 127.0))
            p.setBrush(QColor("#241f14"))
            p.setPen(pen_in)
            p.drawRect(QRectF(x_l, cy + 16, cell_w_l, 22))
            p.setPen(QColor("#fde68a"))
            p.drawText(QRectF(x_l, cy + 16, cell_w_l, 22), Qt.AlignmentFlag.AlignCenter, f"{val_in}")

            x_r = right_start + i * (cell_w_r + 3.0)
            val_out = int(round(float(post_s[i]) * 127.0))
            p.setBrush(QColor("#112533"))
            p.setPen(pen_out)
            p.drawRect(QRectF(x_r, cy + 16, cell_w_r, 22))
            p.setPen(QColor("#bae6fd"))
            p.drawText(QRectF(x_r, cy + 16, cell_w_r, 22), Qt.AlignmentFlag.AlignCenter, f"{val_out}")

        p.setFont(self._font_title_bold)
        p.setPen(QColor("#f59e0b"))
        p.drawText(QPointF(16, cy - 26), f"Input: Campioni x[n]  (Δt = {dt_us:.1f} µs)")
        p.setPen(QColor("#00d2ff"))
        p.drawText(QPointF(right_start, cy - 26), "Output: Campioni filtrati y[n]")

        p.setPen(QColor("#94a3b8"))
        p.setFont(self._font_axis)
        p.drawText(QPointF(16, cy + 54), "Valori quantizzati [-127..+127] distanziati di Δt = 1/fs")


class TimeDomainWidget(QWidget):
    """Switchable time-domain analyzer (Impulse Ringing / Oscilloscope / Blackbox)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._group = QButtonGroup(self)
        self._btn_impulse = QPushButton("Risposta Impulso h[n] (Ringing)")
        self._btn_scope = QPushButton("Oscilloscopio Live (In vs Out)")
        self._btn_blackbox = QPushButton("Blackbox Campioni Δt (Slide 2)")

        for idx, (btn, mode_name) in enumerate(
            (
                (self._btn_impulse, "impulse"),
                (self._btn_scope, "scope"),
                (self._btn_blackbox, "blackbox"),
            )
        ):
            btn.setCheckable(True)
            btn.setProperty("mode_name", mode_name)
            self._group.addButton(btn, idx)
            bar.addWidget(btn)
        self._btn_impulse.setChecked(True)

        bar.addStretch()
        self._info_badge = QLabel("Ringing (-40 dB): 0.0 ms")
        self._info_badge.setProperty("class", "mono-badge")
        self._info_badge.setObjectName("TimeInfoBadge")
        bar.addWidget(self._info_badge)

        self._canvas = _TimeCanvas(self)
        layout.addLayout(bar)
        layout.addWidget(self._canvas)

        self._group.idClicked.connect(self._on_mode_btn)

    @property
    def view_mode(self) -> str:
        return self._canvas.mode

    def _on_mode_btn(self, idx: int) -> None:
        btn = self._group.button(idx)
        if btn is not None:
            self.set_view_mode(str(btn.property("mode_name")))

    def set_view_mode(self, mode: str) -> None:
        mode_l = mode if mode in ("impulse", "scope", "blackbox") else "impulse"
        self._canvas.mode = mode_l
        for btn in self._group.buttons():
            if btn.property("mode_name") == mode_l:
                btn.setChecked(True)
                break
        self._refresh_badge()
        self._canvas.update()

    def set_impulse(self, times_ms: np.ndarray, impulse: np.ndarray, ringing_ms: float) -> None:
        self._canvas.times_ms = np.asarray(times_ms, dtype=np.float64)
        self._canvas.impulse = np.asarray(impulse, dtype=np.float64)
        self._canvas.ringing_ms = float(ringing_ms)
        self._canvas._impulse_dirty = True
        self._refresh_badge()
        if self._canvas.mode == "impulse":
            self._canvas.update()

    def update_live_waves(self, pre: np.ndarray, post: np.ndarray, sample_rate: float) -> None:
        if self._canvas.mode not in ("scope", "blackbox"):
            return
        self._canvas.pre_wave = np.asarray(pre, dtype=np.float32)
        self._canvas.post_wave = np.asarray(post, dtype=np.float32)
        self._canvas.sample_rate = float(sample_rate)
        self._canvas.update()

    def _refresh_badge(self) -> None:
        if self._canvas.mode == "impulse":
            self._info_badge.setText(f"Ringing (-40 dB): {self._canvas.ringing_ms:.2f} ms")
        elif self._canvas.mode == "blackbox":
            dt_us = 1e6 / max(8000.0, self._canvas.sample_rate)
            self._info_badge.setText(f"Δt = {dt_us:.1f} µs @ {self._canvas.sample_rate:.0f} Hz")
        else:
            self._info_badge.setText("Dominio del Tempo Live")
