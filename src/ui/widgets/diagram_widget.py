"""Interactive didactic diagrams paired with each lesson module (Slides 1-18)."""

from __future__ import annotations

import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from src.dsp.filter_design import compute_sos_response, design_filter, log_frequency_grid


class _DiagramCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(210)
        self.kind: str = "blackbox"
        self.param_a: float = 1000.0  # Cutoff / Center freq / Fader dB
        self.param_b: float = 2.0  # Q / Order / Aux send

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0e121a"))

        w, h = self.width(), self.height()
        p.setPen(QColor("#253047"))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        if self.kind == "blackbox":
            self._draw_blackbox_diagram(p, w, h)
        elif self.kind == "mixer_strip":
            self._draw_mixer_diagram(p, w, h)
        elif self.kind == "series_parallel":
            self._draw_series_parallel_diagram(p, w, h)
        elif self.kind == "filter_bank":
            self._draw_filter_bank_diagram(p, w, h)
        else:
            self._draw_interactive_bode(p, w, h)

    def _draw_blackbox_diagram(self, p: QPainter, w: int, h: int) -> None:
        cy = h * 0.45
        bw, bh = 160, 56
        bx, by = w * 0.5 - bw * 0.5, cy - bh * 0.5
        p.setPen(QPen(QColor("#64748b"), 2))
        p.drawLine(QPointF(40, cy), QPointF(bx - 10, cy))
        p.drawLine(QPointF(bx + bw + 10, cy), QPointF(w - 40, cy))

        p.setBrush(QColor("#142638"))
        p.setPen(QPen(QColor("#00d2ff"), 2))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
        p.setPen(QColor("#e0f9ff"))
        p.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        p.drawText(QRectF(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, "Digital Filter\n(Blackbox)")

        # Animated-style spectrum bars left vs right
        freqs_rel = [0.15, 0.30, 0.45, 0.62, 0.78, 0.92]
        cutoff_norm = max(0.15, min(0.9, math.log10(self.param_a / 20.0) / 3.0))
        for i, fr in enumerate(freqs_rel):
            col = QColor("#10b981") if fr <= cutoff_norm else QColor("#ef4444")
            p.fillRect(QRectF(48 + i * 16, cy + 44 - 28, 10, 28), col)
            atten = 1.0 if fr <= cutoff_norm else 0.15
            bh_out = 28 * atten
            p.fillRect(QRectF(w - 150 + i * 16, cy + 44 - bh_out, 10, bh_out), col)

        p.setFont(QFont("Sans", 9, QFont.Weight.Bold))
        p.setPen(QColor("#f59e0b"))
        p.drawText(QPointF(38, cy - 16), "Input x[n]  (Wanted + Unwanted)")
        p.setPen(QColor("#00d2ff"))
        p.drawText(QPointF(w - 225, cy - 16), "Output y[n]  (Frequenze Desiderate)")

    def _draw_series_parallel_diagram(self, p: QPainter, w: int, h: int) -> None:
        # Left: Serie (Channel Strip) | Right: Parallelo (+)
        mid = w * 0.5
        p.setPen(QPen(QColor("#253047"), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(mid, 14), QPointF(mid, h - 14))

        p.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        p.setPen(QColor("#00d2ff"))
        p.drawText(QPointF(24, 26), "Connessione in SERIE (Channel Strip)")
        y_s = h * 0.48
        box_w = 62
        gap = 18
        start_x = 26
        p.setPen(QPen(QColor("#64748b"), 2))
        p.drawLine(QPointF(12, y_s), QPointF(mid - 20, y_s))
        for i in range(3):
            rx = start_x + i * (box_w + gap)
            p.setBrush(QColor("#182538"))
            p.setPen(QPen(QColor("#00d2ff"), 1.5))
            p.drawRoundedRect(QRectF(rx, y_s - 18, box_w, 36), 6, 6)
            p.setPen(QColor("#e2e8f0"))
            p.drawText(QRectF(rx, y_s - 18, box_w, 36), Qt.AlignmentFlag.AlignCenter, f"Filter {i+1}")
        p.setPen(QColor("#94a3b8"))
        p.setFont(QFont("Sans", 9))
        p.drawText(QPointF(24, h - 24), "Ordini si sommano: 2° + 2° = 4° ordine (Slide 10)")

        p.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        p.setPen(QColor("#f59e0b"))
        p.drawText(QPointF(mid + 20, 26), "Connessione in PARALLELO (Sommatore +)")
        sum_x = w - 58
        p.setPen(QPen(QColor("#64748b"), 1.5))
        for i, dy in enumerate((-42, 0, 42)):
            py = y_s + dy
            p.drawLine(QPointF(mid + 26, y_s), QPointF(mid + 48, py))
            p.drawLine(QPointF(mid + 48, py), QPointF(sum_x, y_s))
            p.setBrush(QColor("#262015"))
            p.setPen(QPen(QColor("#f59e0b"), 1.5))
            p.drawRoundedRect(QRectF(mid + 58, py - 14, 72, 28), 6, 6)
            p.setPen(QColor("#fde68a"))
            p.drawText(QRectF(mid + 58, py - 14, 72, 28), Qt.AlignmentFlag.AlignCenter, f"BP {(i+1)*40} Hz")
            p.setPen(QPen(QColor("#64748b"), 1.5))
        p.setBrush(QColor("#1e293b"))
        p.setPen(QPen(QColor("#10b981"), 2))
        p.drawEllipse(QPointF(sum_x, y_s), 16, 16)
        p.drawText(QRectF(sum_x - 16, y_s - 16, 32, 32), Qt.AlignmentFlag.AlignCenter, "+")

    def _draw_filter_bank_diagram(self, p: QPainter, w: int, h: int) -> None:
        p.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        p.setPen(QColor("#00d2ff"))
        p.drawText(QPointF(20, 24), "Banco Parallelo con Inviluppi (Slide 12): White Noise → [BP → LP → HP] → +")
        y0 = 56
        step_y = 44
        sum_x = w - 55
        cy = h * 0.55
        for row in range(3):
            ry = y0 + row * step_y
            p.setPen(QPen(QColor("#64748b"), 1.5))
            p.drawLine(QPointF(78, cy), QPointF(110, ry))
            p.drawLine(QPointF(110, ry), QPointF(sum_x, cy))
            for c_idx, name in enumerate(("BandPass", "LowPass", "HighPass")):
                bx = 122 + c_idx * 96
                p.setBrush(QColor("#172334"))
                p.setPen(QPen(QColor("#38bdf8"), 1.3))
                p.drawRoundedRect(QRectF(bx, ry - 13, 82, 26), 5, 5)
                p.setPen(QColor("#e2e8f0"))
                p.setFont(QFont("Sans", 8, QFont.Weight.Bold))
                p.drawText(QRectF(bx, ry - 13, 82, 26), Qt.AlignmentFlag.AlignCenter, name)

        p.setBrush(QColor("#1e293b"))
        p.setPen(QPen(QColor("#f59e0b"), 2))
        p.drawRoundedRect(QRectF(14, cy - 18, 66, 36), 6, 6)
        p.setPen(QColor("#fde68a"))
        p.drawText(QRectF(14, cy - 18, 66, 36), Qt.AlignmentFlag.AlignCenter, "White\nNoise")

        p.setPen(QPen(QColor("#10b981"), 2))
        p.drawEllipse(QPointF(sum_x, cy), 16, 16)
        p.drawText(QRectF(sum_x - 16, cy - 16, 32, 32), Qt.AlignmentFlag.AlignCenter, "+")

    def _draw_mixer_diagram(self, p: QPainter, w: int, h: int) -> None:
        # Slide 16-18 routing flow: Trim/EQ -> [PRE Aux] -> Fader -> [POST Aux] -> Pan-Pot -> Master L/R
        fader_db = self.param_a  # [-60..+10]
        fader_norm = max(0.0, min(1.0, (fader_db + 60.0) / 70.0))
        cy = h * 0.45

        blocks = [
            ("Input Trim\n& EQ", "#00d2ff"),
            ("Fader\n(dB)", "#10b981"),
            ("Pan-Pot\nL ↔ R", "#a855f7"),
            ("Master\nStereo", "#38bdf8"),
        ]
        bw, bh = 86, 48
        gap = max(28, int((w - 80 - len(blocks) * bw) / 3))
        x0 = 32

        p.setPen(QPen(QColor("#64748b"), 2))
        p.drawLine(QPointF(x0, cy), QPointF(x0 + 3 * (bw + gap) + bw, cy))

        xs = []
        for idx, (label, col) in enumerate(blocks):
            bx = x0 + idx * (bw + gap)
            xs.append(bx)
            p.setBrush(QColor("#171e2c"))
            p.setPen(QPen(QColor(col), 2))
            p.drawRoundedRect(QRectF(bx, cy - bh * 0.5, bw, bh), 7, 7)
            p.setPen(QColor("#f1f5f9"))
            p.setFont(QFont("Sans", 9, QFont.Weight.Bold))
            p.drawText(QRectF(bx, cy - bh * 0.5, bw, bh), Qt.AlignmentFlag.AlignCenter, label)

        # Pre-Fader tap (before Fader) vs Post-Fader tap (after Fader)
        pre_x = xs[1] - gap * 0.5
        post_x = xs[1] + bw + gap * 0.5
        aux_y = cy + 58

        p.setPen(QPen(QColor("#00d2ff"), 2))
        p.drawLine(QPointF(pre_x, cy), QPointF(pre_x, aux_y))
        p.setPen(QPen(QColor("#f59e0b"), 2))
        p.drawLine(QPointF(post_x, cy), QPointF(post_x, aux_y))

        p.setFont(QFont("Sans", 8, QFont.Weight.Bold))
        p.setPen(QColor("#00d2ff"))
        p.drawText(QPointF(pre_x - 36, aux_y + 15), "PRE-FADER (Monitor)")
        p.setPen(QColor("#f59e0b"))
        p.drawText(QPointF(post_x - 30, aux_y + 15), f"POST-FADER (FX: {int(fader_norm*100)}%)")

        # Mono -> Stereo label
        p.setPen(QColor("#94a3b8"))
        p.drawText(QPointF(x0 + 10, cy - 36), "Segnale MONO ──────────────────────▶")
        p.setPen(QColor("#a855f7"))
        p.drawText(QPointF(xs[2] + 10, cy - 36), "Dopo Pan-Pot: STEREO L/R")

    def _draw_interactive_bode(self, p: QPainter, w: int, h: int) -> None:
        r = QRectF(44.0, 18.0, w - 64.0, h - 44.0)
        p.fillRect(r, QColor("#10141d"))
        freqs = log_frequency_grid(260)
        fs = 48000.0

        curves: list[tuple[np.ndarray, str, Qt.PenStyle]] = []
        if self.kind == "lp_hp":
            sos_lp = design_filter("lowpass", self.param_a, fs, q=0.7071, order=2)
            sos_hp = design_filter("highpass", self.param_a, fs, q=0.7071, order=2)
            m_lp, _, _ = compute_sos_response(sos_lp, freqs, fs)
            m_hp, _, _ = compute_sos_response(sos_hp, freqs, fs)
            curves = [(m_lp, "#00d2ff", Qt.PenStyle.SolidLine), (m_hp, "#f59e0b", Qt.PenStyle.SolidLine)]
            y_min, y_max = -42.0, 6.0
        elif self.kind == "bp_br":
            sos_bp = design_filter("bandpass", self.param_a, fs, q=self.param_b, order=2)
            sos_br = design_filter("bandreject", self.param_a, fs, q=self.param_b, order=2)
            m_bp, _, _ = compute_sos_response(sos_bp, freqs, fs)
            m_br, _, _ = compute_sos_response(sos_br, freqs, fs)
            curves = [(m_bp, "#00d2ff", Qt.PenStyle.SolidLine), (m_br, "#ef4444", Qt.PenStyle.SolidLine)]
            y_min, y_max = -42.0, 6.0
        elif self.kind == "q_ringing":
            sos_std = design_filter("bandpass", 1000.0, fs, q=self.param_b, order=2)
            sos_res = design_filter("resonant_bandpass", 1000.0, fs, q=self.param_b, order=2)
            m_std, _, _ = compute_sos_response(sos_std, freqs, fs)
            m_res, _, _ = compute_sos_response(sos_res, freqs, fs)
            curves = [(m_std, "#00d2ff", Qt.PenStyle.SolidLine), (m_res, "#10b981", Qt.PenStyle.SolidLine)]
            y_min, y_max = -36.0, 20.0
        elif self.kind == "order_rolloff":
            sos1 = design_filter("lowpass", self.param_a, fs, q=0.7071, order=1)
            sos2 = design_filter("lowpass", self.param_a, fs, q=0.7071, order=2)
            sos4 = design_filter("lowpass", self.param_a, fs, q=0.7071, order=4)
            m1, _, _ = compute_sos_response(sos1, freqs, fs)
            m2, _, _ = compute_sos_response(sos2, freqs, fs)
            m4, _, _ = compute_sos_response(sos4, freqs, fs)
            curves = [
                (m1, "#94a3b8", Qt.PenStyle.DotLine),
                (m2, "#f59e0b", Qt.PenStyle.DashLine),
                (m4, "#00d2ff", Qt.PenStyle.SolidLine),
            ]
            y_min, y_max = -48.0, 6.0
        elif self.kind == "graphic_eq":
            # Show multi-band bell envelope preview
            y_min, y_max = -15.0, 15.0
            bands = [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
            gains = [4.0, 2.0, -3.0, -4.0, 1.5, 4.5, 5.5, 3.0, 1.0]
            total = np.zeros_like(freqs)
            for fc, gd in zip(bands, gains):
                m_i, _, _ = compute_sos_response(design_filter("peak", float(fc), fs, 1.414, gd), freqs, fs)
                total += m_i
                curves.append((m_i, "#334155", Qt.PenStyle.DotLine))
            curves.append((total, "#00d2ff", Qt.PenStyle.SolidLine))
        else:  # shelving_parametric
            y_min, y_max = -18.0, 18.0
            m_ls, _, _ = compute_sos_response(design_filter("lowshelf", 120.0, fs, 0.7071, 6.0), freqs, fs)
            m_pk, _, _ = compute_sos_response(design_filter("peak", self.param_a, fs, self.param_b, 9.0), freqs, fs)
            m_hs, _, _ = compute_sos_response(design_filter("highshelf", 6000.0, fs, 0.7071, -6.0), freqs, fs)
            curves = [
                (m_ls, "#f59e0b", Qt.PenStyle.DashLine),
                (m_hs, "#a855f7", Qt.PenStyle.DashLine),
                (m_pk + m_ls + m_hs, "#00d2ff", Qt.PenStyle.SolidLine),
            ]

        log_min, log_max = math.log10(20.0), math.log10(20000.0)
        # 0 dB line
        y0 = r.bottom() - ((0.0 - y_min) / (y_max - y_min)) * r.height()
        p.setPen(QPen(QColor("#334155"), 1))
        p.drawLine(QPointF(r.left(), y0), QPointF(r.right(), y0))

        for mag, col_str, style in curves:
            path = QPainterPath()
            for i, (f, db) in enumerate(zip(freqs, mag)):
                x = r.left() + ((math.log10(float(f)) - log_min) / (log_max - log_min)) * r.width()
                t = max(0.0, min(1.0, (float(db) - y_min) / (y_max - y_min)))
                y = r.bottom() - t * r.height()
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.setPen(QPen(QColor(col_str), 2.0, style))
            p.drawPath(path)

        p.setPen(QColor("#74829c"))
        p.setFont(QFont("Monospace", 8))
        for gf in (20, 100, 1000, 10000, 20000):
            gx = r.left() + ((math.log10(gf) - log_min) / (log_max - log_min)) * r.width()
            lbl = f"{gf // 1000}k" if gf >= 1000 else str(gf)
            p.drawText(QRectF(gx - 18, r.bottom() + 2, 36, 16), Qt.AlignmentFlag.AlignCenter, lbl)


class DidacticDiagramWidget(QWidget):
    """Interactive didactic diagram with mini-sliders right inside each lesson."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._canvas = _DiagramCanvas(self)
        layout.addWidget(self._canvas)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        self._lbl_a = QLabel("Frequenza:")
        self._slider_a = QSlider(Qt.Orientation.Horizontal)
        self._slider_a.setRange(0, 1000)
        self._slider_a.setValue(560)
        self._val_a = QLabel("1000 Hz")
        self._val_a.setProperty("class", "mono-badge")

        self._lbl_b = QLabel("Q:")
        self._slider_b = QSlider(Qt.Orientation.Horizontal)
        self._slider_b.setRange(5, 120)
        self._slider_b.setValue(20)
        self._val_b = QLabel("2.0")
        self._val_b.setProperty("class", "mono-badge")

        ctrl.addWidget(self._lbl_a)
        ctrl.addWidget(self._slider_a, 2)
        ctrl.addWidget(self._val_a)
        ctrl.addWidget(self._lbl_b)
        ctrl.addWidget(self._slider_b, 1)
        ctrl.addWidget(self._val_b)
        layout.addLayout(ctrl)

        self._slider_a.valueChanged.connect(self._sync)
        self._slider_b.valueChanged.connect(self._sync)
        self._sync()

    def set_kind(self, kind: str) -> None:
        self._canvas.kind = kind
        is_mixer = kind == "mixer_strip"
        if is_mixer:
            self._lbl_a.setText("Fader (dB):")
            self._slider_a.setValue(850)
            self._lbl_b.setVisible(False)
            self._slider_b.setVisible(False)
            self._val_b.setVisible(False)
        else:
            self._lbl_a.setText("Cutoff / fc:")
            self._slider_a.setValue(566)  # ~1000 Hz
            show_q = kind in ("bp_br", "q_ringing", "shelving_parametric")
            self._lbl_b.setVisible(show_q)
            self._slider_b.setVisible(show_q)
            self._val_b.setVisible(show_q)
        self._sync()

    def _sync(self) -> None:
        if self._canvas.kind == "mixer_strip":
            fader_db = -60.0 + (self._slider_a.value() / 1000.0) * 70.0
            self._canvas.param_a = fader_db
            self._val_a.setText("-∞ dB" if fader_db <= -59.5 else f"{fader_db:+.1f} dB")
        else:
            freq = 20.0 * (1000.0 ** (self._slider_a.value() / 1000.0))
            q_val = self._slider_b.value() / 10.0
            self._canvas.param_a = freq
            self._canvas.param_b = q_val
            self._val_a.setText(f"{freq:,.0f} Hz")
            self._val_b.setText(f"Q={q_val:.1f}")
        self._canvas.update()
