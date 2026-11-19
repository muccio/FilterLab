"""Real-time DSP filter processor, multi-topology networks, EQ, and Channel Strip."""

from __future__ import annotations

import copy
import math
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import signal

from .filter_design import (
    IDENTITY_SOS,
    ISO_10_BANDS,
    ISO_20_BANDS,
    ISO_30_BANDS,
    clamp_freq,
    design_filter,
)


@dataclass
class SingleFilterConfig:
    filter_type: str = "lowpass"
    freq: float = 1000.0
    q: float = 0.70710678
    gain_db: float = 0.0
    order: int = 2
    drive: float = 1.0


@dataclass
class StageConfig:
    enabled: bool = True
    filter_type: str = "bandpass"
    freq: float = 1000.0
    q: float = 2.0
    gain_db: float = 0.0
    order: int = 2
    env_enabled: bool = False
    env_rate_hz: float = 0.5
    env_depth_oct: float = 1.0


def default_network_stages() -> list[StageConfig]:
    return [
        StageConfig(True, "bandpass", 1000.0, 2.0, 0.0, 2, False, 0.4, 1.0),
        StageConfig(True, "bandpass", 1400.0, 2.0, 0.0, 2, False, 0.6, 1.0),
        StageConfig(False, "lowpass", 4000.0, 0.7071, 0.0, 2, False, 0.5, 0.8),
        StageConfig(False, "highpass", 120.0, 0.7071, 0.0, 2, False, 0.3, 0.8),
    ]


@dataclass
class NetworkConfig:
    topology: str = "series"  # "series", "parallel", "bank"
    stages: list[StageConfig] = field(default_factory=default_network_stages)
    wet_mix: float = 1.0


@dataclass
class GraphicEQConfig:
    band_count: int = 10  # 10, 20, or 30
    gains_db: list[float] = field(default_factory=lambda: [0.0] * 30)

    def active_frequencies(self) -> tuple[int, ...]:
        if self.band_count == 10:
            return ISO_10_BANDS
        if self.band_count == 20:
            return ISO_20_BANDS
        return ISO_30_BANDS

    def active_q(self) -> float:
        if self.band_count == 10:
            return 1.41421356  # 1 octave
        if self.band_count == 20:
            return 2.87091722  # 1/2 octave
        return 4.31847254  # 1/3 octave


@dataclass
class ParametricBandConfig:
    enabled: bool = True
    filter_type: str = "peak"
    freq: float = 1000.0
    gain_db: float = 0.0
    q: float = 1.4
    order: int = 2


def default_parametric_bands() -> list[ParametricBandConfig]:
    """6-band structure matching Slide 15 (LowShelf + 4 Peak/Notch + LowPass)."""
    return [
        ParametricBandConfig(True, "lowshelf", 90.0, 0.0, 0.7071, 2),
        ParametricBandConfig(True, "peak", 250.0, 0.0, 1.4, 2),
        ParametricBandConfig(True, "peak", 1000.0, 0.0, 1.8, 2),
        ParametricBandConfig(True, "peak", 3200.0, 0.0, 1.6, 2),
        ParametricBandConfig(True, "peak", 8000.0, 0.0, 1.4, 2),
        ParametricBandConfig(False, "lowpass", 12000.0, 0.0, 0.7071, 2),
    ]


@dataclass
class ParametricEQConfig:
    bands: list[ParametricBandConfig] = field(default_factory=default_parametric_bands)


@dataclass
class ChannelStripConfig:
    input_trim_db: float = 0.0
    bypass: bool = False
    aux_send: float = 0.0
    aux_pre_fader: bool = True
    aux_fx_enabled: bool = True
    pfl_solo: bool = False
    mute: bool = False
    pan: float = 0.0  # -1.0 (L) .. +1.0 (R)
    fader_db: float = 0.0  # 0.0 dB = nominal operating level (-10 dB below +10 dB max)
    safety_limiter: bool = True


class _SimpleAuxFX:
    """Lightweight feedback delay/comb reverb on Aux return to make Pre/Post-Fader audible."""

    def __init__(self, sample_rate: float = 48000.0) -> None:
        self.sample_rate = float(sample_rate)
        self._build_buffers()

    def _build_buffers(self) -> None:
        delays_ms = (37.0, 59.0, 89.0, 131.0)
        self._bufs = [
            np.zeros(max(32, int(self.sample_rate * ms / 1000.0)), dtype=np.float64)
            for ms in delays_ms
        ]
        self._idx = [0, 0, 0, 0]
        self._fb = (0.58, 0.52, 0.48, 0.42)
        self._lp_zi = np.zeros(1, dtype=np.float64)

    def set_sample_rate(self, fs: float) -> None:
        if abs(fs - self.sample_rate) > 1.0:
            self.sample_rate = float(fs)
            self._build_buffers()

    def reset(self) -> None:
        for b in self._bufs:
            b.fill(0.0)
        self._idx = [0, 0, 0, 0]
        self._lp_zi.fill(0.0)

    def process_mono(self, x_mono: np.ndarray) -> np.ndarray:
        n = len(x_mono)
        acc = np.zeros(n, dtype=np.float64)
        for c in range(len(self._bufs)):
            buf = self._bufs[c]
            blen = len(buf)
            idx = self._idx[c]
            fb = self._fb[c]
            offset = 0
            while offset < n:
                chunk = min(n - offset, blen)
                if idx + chunk <= blen:
                    delayed = buf[idx : idx + chunk].copy()
                    acc[offset : offset + chunk] += delayed * 0.35
                    buf[idx : idx + chunk] = x_mono[offset : offset + chunk] + delayed * fb
                    idx = (idx + chunk) % blen
                else:
                    first = blen - idx
                    rem = chunk - first
                    d1 = buf[idx:].copy()
                    d2 = buf[:rem].copy()
                    acc[offset : offset + first] += d1 * 0.35
                    acc[offset + first : offset + chunk] += d2 * 0.35
                    buf[idx:] = x_mono[offset : offset + first] + d1 * fb
                    buf[:rem] = x_mono[offset + first : offset + chunk] + d2 * fb
                    idx = rem
                offset += chunk
            self._idx[c] = idx
        out, self._lp_zi = signal.lfilter([0.35], [1.0, -0.65], acc, zi=self._lp_zi)
        return out


def _fill_bank_branch(branch_sos: np.ndarray, freq: float, q: float, fs: float) -> None:
    """Populate a pre-allocated (3, 6) SOS array [BandPass, LowPass, HighPass] in place."""
    fs_f = float(fs)
    upper = min(20000.0, 0.48 * fs_f)
    two_pi_inv_fs = (2.0 * math.pi) / fs_f

    f_bp = max(20.0, min(upper, float(freq)))
    q_bp = max(0.1, min(30.0, float(q)))
    w0 = f_bp * two_pi_inv_fs
    c = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * q_bp)
    inv_a0 = 1.0 / (1.0 + alpha)
    branch_sos[0, 0] = alpha * inv_a0
    branch_sos[0, 1] = 0.0
    branch_sos[0, 2] = -alpha * inv_a0
    branch_sos[0, 3] = 1.0
    branch_sos[0, 4] = (-2.0 * c) * inv_a0
    branch_sos[0, 5] = (1.0 - alpha) * inv_a0

    inv_sqrt2_x2 = 1.0 / (2.0 * 0.7071067811865476)
    f_lp = max(20.0, min(upper, f_bp * 2.5))
    w0_l = f_lp * two_pi_inv_fs
    c_l = math.cos(w0_l)
    a_l = math.sin(w0_l) * inv_sqrt2_x2
    inv_a0_l = 1.0 / (1.0 + a_l)
    b0_l = ((1.0 - c_l) * 0.5) * inv_a0_l
    branch_sos[1, 0] = b0_l
    branch_sos[1, 1] = 2.0 * b0_l
    branch_sos[1, 2] = b0_l
    branch_sos[1, 3] = 1.0
    branch_sos[1, 4] = (-2.0 * c_l) * inv_a0_l
    branch_sos[1, 5] = (1.0 - a_l) * inv_a0_l

    f_hp = max(20.0, min(upper, f_bp * 0.4))
    w0_h = f_hp * two_pi_inv_fs
    c_h = math.cos(w0_h)
    a_h = math.sin(w0_h) * inv_sqrt2_x2
    inv_a0_h = 1.0 / (1.0 + a_h)
    b0_h = ((1.0 + c_h) * 0.5) * inv_a0_h
    branch_sos[2, 0] = b0_h
    branch_sos[2, 1] = -2.0 * b0_h
    branch_sos[2, 2] = b0_h
    branch_sos[2, 3] = 1.0
    branch_sos[2, 4] = (-2.0 * c_h) * inv_a0_h
    branch_sos[2, 5] = (1.0 - a_h) * inv_a0_h


class FilterDSPProcessor:
    """Thread-safe real-time DSP filter & mixer processor."""

    def __init__(self, sample_rate: float = 48000.0) -> None:
        self.sample_rate = float(sample_rate)
        self._lock = threading.RLock()

        self.mode: str = "single"  # "single", "network", "graphic_eq", "parametric_eq"
        self.single_cfg = SingleFilterConfig()
        self.network_cfg = NetworkConfig()
        self.graphic_cfg = GraphicEQConfig()
        self.parametric_cfg = ParametricEQConfig()
        self.channel_cfg = ChannelStripConfig()

        # Cached SOS & stereo persistent states of shape (n_sections, 2, 2)
        self._single_sos: np.ndarray = IDENTITY_SOS.copy()
        self._single_zi: np.ndarray = np.zeros((1, 2, 2), dtype=np.float64)

        self._net_sos: list[np.ndarray] = []
        self._net_series_sos: np.ndarray = IDENTITY_SOS.copy()
        self._net_series_zi: np.ndarray = np.zeros((1, 2, 2), dtype=np.float64)
        self._net_par_zi: list[np.ndarray] = []
        self._bank_branch_sos: list[np.ndarray] = [np.zeros((3, 6), dtype=np.float64) for _ in range(4)]
        self._bank_branch_zi: list[np.ndarray] = [np.zeros((3, 2, 2), dtype=np.float64) for _ in range(4)]
        self._lfo_phases: np.ndarray = np.zeros(4, dtype=np.float64)

        self._geq_sos: list[np.ndarray] = []
        self._geq_stacked_sos: np.ndarray = IDENTITY_SOS.copy()
        self._geq_is_identity: bool = True
        self._geq_zi: np.ndarray = np.zeros((1, 2, 2), dtype=np.float64)

        self._peq_sos: list[np.ndarray] = []
        self._peq_stacked_sos: np.ndarray = IDENTITY_SOS.copy()
        self._peq_is_identity: bool = True
        self._peq_zi: np.ndarray = np.zeros((1, 2, 2), dtype=np.float64)

        self._aux_fx = _SimpleAuxFX(self.sample_rate)
        self.rebuild_all()

    def set_sample_rate(self, sample_rate: float) -> None:
        with self._lock:
            self.sample_rate = max(8000.0, float(sample_rate))
            self._aux_fx.set_sample_rate(self.sample_rate)
            self.rebuild_all()

    def reset_states(self) -> None:
        with self._lock:
            self._single_zi = np.zeros((self._single_sos.shape[0], 2, 2), dtype=np.float64)
            self._net_series_zi = np.zeros((self._net_series_sos.shape[0], 2, 2), dtype=np.float64)
            self._net_par_zi = [
                np.zeros((s.shape[0], 2, 2), dtype=np.float64) for s in self._net_sos
            ]
            for bzi in self._bank_branch_zi:
                bzi.fill(0.0)
            self._geq_zi = np.zeros((self._geq_stacked_sos.shape[0], 2, 2), dtype=np.float64)
            self._peq_zi = np.zeros((self._peq_stacked_sos.shape[0], 2, 2), dtype=np.float64)
            self._aux_fx.reset()

    def set_mode(self, mode: str) -> None:
        with self._lock:
            if mode != self.mode:
                self.mode = mode
                self.reset_states()

    def update_single(self, cfg: SingleFilterConfig) -> None:
        with self._lock:
            self.single_cfg = copy.deepcopy(cfg)
            new_sos = design_filter(
                cfg.filter_type, cfg.freq, self.sample_rate, cfg.q, cfg.gain_db, cfg.order, cfg.drive
            )
            if new_sos.shape != self._single_sos.shape:
                self._single_zi = np.zeros((new_sos.shape[0], 2, 2), dtype=np.float64)
            self._single_sos = new_sos

    def update_network(self, cfg: NetworkConfig) -> None:
        with self._lock:
            self.network_cfg = copy.deepcopy(cfg)
            self._rebuild_network(preserve_zi=True)

    def update_graphic_eq(self, cfg: GraphicEQConfig) -> None:
        with self._lock:
            self.graphic_cfg = copy.deepcopy(cfg)
            self._rebuild_graphic_eq(preserve_zi=True)

    def update_parametric_eq(self, cfg: ParametricEQConfig) -> None:
        with self._lock:
            self.parametric_cfg = copy.deepcopy(cfg)
            self._rebuild_parametric_eq(preserve_zi=True)

    def update_channel_strip(self, cfg: ChannelStripConfig) -> None:
        with self._lock:
            self.channel_cfg = copy.deepcopy(cfg)

    def rebuild_all(self) -> None:
        self.update_single(self.single_cfg)
        self._rebuild_network(preserve_zi=False)
        self._rebuild_graphic_eq(preserve_zi=False)
        self._rebuild_parametric_eq(preserve_zi=False)

    def _rebuild_network(self, preserve_zi: bool) -> None:
        new_sos: list[np.ndarray] = []
        active_sos: list[np.ndarray] = []
        for idx, st in enumerate(self.network_cfg.stages):
            _fill_bank_branch(self._bank_branch_sos[idx], st.freq, st.q, self.sample_rate)
            if not st.enabled:
                s = IDENTITY_SOS.copy()
            elif self.network_cfg.topology == "bank":
                s = self._bank_branch_sos[idx][0:1].copy()
            else:
                s = design_filter(
                    st.filter_type, st.freq, self.sample_rate, st.q, st.gain_db, st.order
                )
                active_sos.append(s)
            new_sos.append(s)

        series_stacked = np.vstack(active_sos) if active_sos else IDENTITY_SOS.copy()
        if not preserve_zi or series_stacked.shape != self._net_series_sos.shape:
            self._net_series_zi = np.zeros((series_stacked.shape[0], 2, 2), dtype=np.float64)
        self._net_series_sos = series_stacked

        if not preserve_zi or len(new_sos) != len(self._net_sos) or any(
            a.shape != b.shape for a, b in zip(new_sos, self._net_sos)
        ):
            self._net_par_zi = [np.zeros((s.shape[0], 2, 2), dtype=np.float64) for s in new_sos]
            if not preserve_zi:
                for bzi in self._bank_branch_zi:
                    bzi.fill(0.0)
        self._net_sos = new_sos

    def _rebuild_graphic_eq(self, preserve_zi: bool) -> None:
        freqs = self.graphic_cfg.active_frequencies()
        q_val = self.graphic_cfg.active_q()
        new_sos: list[np.ndarray] = []
        active_sos: list[np.ndarray] = []
        for idx, fc in enumerate(freqs):
            g_db = self.graphic_cfg.gains_db[idx] if idx < len(self.graphic_cfg.gains_db) else 0.0
            if abs(g_db) < 0.02:
                new_sos.append(IDENTITY_SOS.copy())
            else:
                sec = design_filter("peak", float(fc), self.sample_rate, q_val, float(g_db), 2)
                new_sos.append(sec)
                active_sos.append(sec)
        stacked = np.vstack(active_sos) if active_sos else IDENTITY_SOS.copy()
        if not preserve_zi or stacked.shape != self._geq_stacked_sos.shape:
            self._geq_zi = np.zeros((stacked.shape[0], 2, 2), dtype=np.float64)
        self._geq_sos = new_sos
        self._geq_stacked_sos = stacked
        self._geq_is_identity = not active_sos

    def _rebuild_parametric_eq(self, preserve_zi: bool) -> None:
        new_sos: list[np.ndarray] = []
        active_sos: list[np.ndarray] = []
        for b in self.parametric_cfg.bands:
            if not b.enabled:
                new_sos.append(IDENTITY_SOS.copy())
            else:
                sec = design_filter(b.filter_type, b.freq, self.sample_rate, b.q, b.gain_db, b.order)
                new_sos.append(sec)
                active_sos.append(sec)
        stacked = np.vstack(active_sos) if active_sos else IDENTITY_SOS.copy()
        if not preserve_zi or stacked.shape != self._peq_stacked_sos.shape:
            self._peq_zi = np.zeros((stacked.shape[0], 2, 2), dtype=np.float64)
        self._peq_sos = new_sos
        self._peq_stacked_sos = stacked
        self._peq_is_identity = not active_sos

    def get_active_bode_sos(self) -> dict[str, Any]:
        """Snapshot active filter SOS & topology for Bode plot rendering."""
        with self._lock:
            if self.mode == "single":
                return {"topology": "series", "sos_list": [self._single_sos.copy()]}
            if self.mode == "network":
                topo = self.network_cfg.topology
                active_sos = []
                for idx, st in enumerate(self.network_cfg.stages):
                    if st.enabled:
                        if topo == "bank":
                            active_sos.append(self._bank_branch_sos[idx].copy())
                        else:
                            active_sos.append(self._net_sos[idx].copy())
                if not active_sos:
                    active_sos = [IDENTITY_SOS.copy()]
                gains = (
                    [1.0 / len(active_sos)] * len(active_sos)
                    if topo in ("parallel", "bank")
                    else None
                )
                return {
                    "topology": "parallel" if topo in ("parallel", "bank") else "series",
                    "sos_list": active_sos,
                    "gains": gains,
                }
            if self.mode == "graphic_eq":
                return {"topology": "series", "sos_list": [s.copy() for s in self._geq_sos]}
            if self.mode == "parametric_eq":
                sos_list = [s.copy() for s in self._peq_sos]
                return {"topology": "series", "sos_list": sos_list or [IDENTITY_SOS.copy()]}
            return {"topology": "series", "sos_list": [IDENTITY_SOS.copy()]}

    def _process_filter_block(self, x: np.ndarray) -> np.ndarray:
        """Process (N, 2) float64 stereo audio through the active filter stage in C."""
        n = x.shape[0]

        if self.mode == "single":
            work = x
            is_moog = self.single_cfg.filter_type == "moog_ladder"
            drive = max(1.0, float(self.single_cfg.drive))
            if is_moog and drive > 1.01:
                work = np.tanh(work * drive) / math.tanh(drive)
            y, self._single_zi = signal.sosfilt(
                self._single_sos, work, axis=0, zi=self._single_zi
            )
            return y

        if self.mode == "network":
            topo = self.network_cfg.topology
            active_indices = [i for i, st in enumerate(self.network_cfg.stages) if st.enabled]
            if not active_indices:
                return x.copy()

            if topo == "series":
                y, self._net_series_zi = signal.sosfilt(
                    self._net_series_sos, x, axis=0, zi=self._net_series_zi
                )
                return y

            if topo == "parallel":
                acc = np.zeros_like(x)
                scale = 1.0 / len(active_indices)
                for idx in active_indices:
                    out_i, self._net_par_zi[idx] = signal.sosfilt(
                        self._net_sos[idx], x, axis=0, zi=self._net_par_zi[idx]
                    )
                    acc += out_i
                acc *= scale
                return acc

            # "bank" — modulated parallel chains (BP -> LP -> HP) stacked per branch
            block_dt = n / self.sample_rate
            acc = np.zeros_like(x)
            scale = 1.0 / len(active_indices)
            for idx in active_indices:
                st = self.network_cfg.stages[idx]
                if st.env_enabled:
                    self._lfo_phases[idx] = (self._lfo_phases[idx] + st.env_rate_hz * block_dt) % 1.0
                    lfo = math.sin(2.0 * math.pi * self._lfo_phases[idx])
                    mod_freq = st.freq * (2.0 ** (lfo * st.env_depth_oct))
                    mod_q = max(0.3, st.q * (1.0 + 0.35 * lfo))
                    _fill_bank_branch(self._bank_branch_sos[idx], mod_freq, mod_q, self.sample_rate)

                out_i, self._bank_branch_zi[idx] = signal.sosfilt(
                    self._bank_branch_sos[idx], x, axis=0, zi=self._bank_branch_zi[idx]
                )
                acc += out_i
            acc *= scale
            return acc

        if self.mode == "graphic_eq":
            if self._geq_is_identity:
                return x.copy()
            y, self._geq_zi = signal.sosfilt(
                self._geq_stacked_sos, x, axis=0, zi=self._geq_zi
            )
            return y

        if self.mode == "parametric_eq":
            if self._peq_is_identity:
                return x.copy()
            y, self._peq_zi = signal.sosfilt(
                self._peq_stacked_sos, x, axis=0, zi=self._peq_zi
            )
            return y

        return x.copy()

    @staticmethod
    def _lin_to_db(peak: float) -> float:
        return 20.0 * math.log10(max(float(peak), 1e-6))

    def process_block(self, stereo_in: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        """Process a (N, 2) float32 block through Input Trim -> Filter -> Channel Strip."""
        with self._lock:
            x = np.asarray(stereo_in, dtype=np.float64)
            if x.ndim == 1:
                x = np.column_stack((x, x))
            x = np.nan_to_num(x, nan=0.0, posinf=1.0, neginf=-1.0)

            ch_cfg = self.channel_cfg

            # 1. Input Trim (Slide 17: adjust input level around nominal operating level)
            trim_lin = 10.0 ** (ch_cfg.input_trim_db / 20.0)
            x_trimmed = x * trim_lin
            in_peak = float(np.max(np.abs(x_trimmed)))

            # 2. Filter stage (with A/B Bypass)
            if ch_cfg.bypass:
                filtered = x_trimmed
            else:
                filtered = self._process_filter_block(x_trimmed)
                filtered = np.nan_to_num(filtered, nan=0.0, posinf=1.0, neginf=-1.0)

            # 3. Channel Fader (Slide 17: -60 dB acts as -inf closed fader; 0 dB = nominal)
            fader_lin = 0.0 if ch_cfg.fader_db <= -59.5 else (10.0 ** (ch_cfg.fader_db / 20.0))

            # 4. Aux Send Pre-Fader vs Post-Fader (Slide 16)
            mono_pre = 0.5 * (filtered[:, 0] + filtered[:, 1])
            if ch_cfg.aux_pre_fader:
                # Pre-fader is independent of fader & mute
                aux_send_sig = mono_pre * ch_cfg.aux_send
            else:
                # Post-fader depends on fader and mute
                mute_mul = 0.0 if ch_cfg.mute else 1.0
                aux_send_sig = mono_pre * (fader_lin * mute_mul) * ch_cfg.aux_send

            aux_peak = float(np.max(np.abs(aux_send_sig)))
            if ch_cfg.aux_fx_enabled and ch_cfg.aux_send > 0.001:
                aux_return = self._aux_fx.process_mono(aux_send_sig)
            else:
                aux_return = aux_send_sig

            # 5. Pan-Pot (Slide 18: signal travels mono in strip, becomes stereo after pan-pot)
            # Constant-power pan law with unity gain at center (pan=0 -> L=1.0, R=1.0)
            pan = max(-1.0, min(1.0, float(ch_cfg.pan)))
            theta = (pan + 1.0) * (math.pi * 0.25)
            pan_l = math.cos(theta) * math.sqrt(2.0)
            pan_r = math.sin(theta) * math.sqrt(2.0)
            if pan_l < 1e-12:
                pan_l = 0.0
            if pan_r < 1e-12:
                pan_r = 0.0

            if ch_cfg.pfl_solo:
                # PFL (Slide 17): sends pre-fader signal directly to SOLO/monitoring bus, overriding Mute & Fader
                main_l = filtered[:, 0] * pan_l
                main_r = filtered[:, 1] * pan_r
                out_stereo = np.column_stack((main_l + aux_return, main_r + aux_return))
            else:
                mute_mul = 0.0 if ch_cfg.mute else 1.0
                dry_l = filtered[:, 0] * (fader_lin * mute_mul * pan_l)
                dry_r = filtered[:, 1] * (fader_lin * mute_mul * pan_r)
                out_stereo = np.column_stack((dry_l + aux_return, dry_r + aux_return))

            # Overload indicator (Slide 17 LED) before safety limiter
            pre_lim_peak = float(np.max(np.abs(out_stereo)))
            overload = pre_lim_peak > 1.0

            if ch_cfg.safety_limiter:
                # Soft-knee limiter above 0.94 (-0.5 dBFS) to protect hardware output
                thresh = 0.94
                abs_o = np.abs(out_stereo)
                over = abs_o > thresh
                if np.any(over):
                    excess = abs_o[over] - thresh
                    limited = thresh + 0.055 * np.tanh(excess / 0.055)
                    out_stereo[over] = np.sign(out_stereo[over]) * limited

            out_peak_l = float(np.max(np.abs(out_stereo[:, 0])))
            out_peak_r = float(np.max(np.abs(out_stereo[:, 1])))

            telemetry = {
                "in_peak_db": self._lin_to_db(in_peak),
                "out_peak_l_db": self._lin_to_db(out_peak_l),
                "out_peak_r_db": self._lin_to_db(out_peak_r),
                "aux_peak_db": self._lin_to_db(aux_peak),
                "overload": overload,
                "pre_block_mono": (0.5 * (x_trimmed[:, 0] + x_trimmed[:, 1])).astype(np.float32),
                "post_block_mono": (0.5 * (out_stereo[:, 0] + out_stereo[:, 1])).astype(np.float32),
            }
            return out_stereo.astype(np.float32), telemetry
