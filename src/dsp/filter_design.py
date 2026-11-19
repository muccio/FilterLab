"""Pure mathematical digital filter design, frequency/phase analysis, and impulse response."""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

import numpy as np
from scipy import signal

# ISO standard Graphic EQ center frequencies (Slide 13)
ISO_10_BANDS: tuple[int, ...] = (
    31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000,
)

ISO_20_BANDS: tuple[int, ...] = (
    31, 45, 63, 90, 125, 180, 250, 355, 500, 710,
    1000, 1400, 2000, 2800, 4000, 5600, 8000, 11200, 16000, 20000,
)

# Exact 30 third-octave center frequencies listed on Slide 13
ISO_30_BANDS: tuple[int, ...] = (
    25, 31, 40, 50, 63, 80, 100, 125, 160, 200,
    250, 315, 400, 500, 630, 800, 1000, 1200, 1600, 2000,
    2500, 3200, 4000, 5000, 6300, 8000, 10000, 12000, 16000, 20000,
)

IDENTITY_SOS = np.array([[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]], dtype=np.float64)


def clamp_freq(freq: float, fs: float) -> float:
    """Clamp cutoff/center frequency safely inside [20 Hz, min(20 kHz, 0.48*fs)]."""
    if fs <= 0:
        raise ValueError("Sample rate fs must be positive.")
    upper = min(20000.0, 0.48 * float(fs))
    return float(max(20.0, min(upper, float(freq))))


def exact_third_octave_freq(iso_hz: float) -> float:
    """Compute exact 1/3-octave geometric frequency anchored at 1000 Hz.

    Demonstrates Slide 13 NB: e.g. 800 Hz ISO corresponds to 1000 * 2^(-1/3) = 793.70 Hz.
    """
    if iso_hz <= 0:
        raise ValueError("Frequency must be positive.")
    step = round(3.0 * math.log2(float(iso_hz) / 1000.0))
    return 1000.0 * (2.0 ** (step / 3.0))


def compute_band_metrics(fc: float, q: float) -> dict[str, float]:
    """Compute bandwidth and geometric -3 dB cutoffs f_low, f_high from (fc, Q)."""
    fc_safe = max(20.0, float(fc))
    q_safe = max(0.1, float(q))
    bw = fc_safe / q_safe
    f_low = (-bw + math.sqrt(bw * bw + 4.0 * fc_safe * fc_safe)) * 0.5
    f_high = f_low + bw
    return {
        "fc": fc_safe,
        "q": q_safe,
        "bw": bw,
        "f_low": f_low,
        "f_high": f_high,
    }


def from_cutoffs(f_low: float, f_high: float) -> dict[str, float]:
    """Compute geometric center frequency, bandwidth, and Q from lower/upper cutoffs."""
    fl = max(10.0, float(f_low))
    fh = max(fl + 1.0, float(f_high))
    fc = math.sqrt(fl * fh)
    bw = fh - fl
    q = fc / bw
    return {
        "fc": fc,
        "bw": bw,
        "q": q,
        "f_low": fl,
        "f_high": fh,
    }


def _normalize_biquad(b0: float, b1: float, b2: float, a0: float, a1: float, a2: float) -> np.ndarray:
    """Return a normalized (1, 6) SOS matrix."""
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=np.float64)


def _design_first_order(filter_type: str, f0: float, fs: float) -> np.ndarray:
    """Design 1st-order bilinear prewarped LowPass or HighPass (-6 dB/oct, -3 dB @ f0)."""
    k = math.tan(math.pi * f0 / fs)
    denom = 1.0 + k
    a1 = (k - 1.0) / denom
    if filter_type == "lowpass":
        b0 = k / denom
        b1 = k / denom
    elif filter_type == "highpass":
        b0 = 1.0 / denom
        b1 = -1.0 / denom
    else:
        return IDENTITY_SOS.copy()
    return np.array([[b0, b1, 0.0, 1.0, a1, 0.0]], dtype=np.float64)


def _design_rbj_biquad(
    filter_type: str, f0: float, fs: float, q: float, gain_db: float
) -> np.ndarray:
    """Design Robert Bristow-Johnson Audio EQ Cookbook biquad section."""
    w0 = 2.0 * math.pi * f0 / fs
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    q_safe = max(0.1, float(q))
    alpha = sin_w0 / (2.0 * q_safe)

    if filter_type == "lowpass":
        b0 = (1.0 - cos_w0) * 0.5
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    if filter_type == "highpass":
        b0 = (1.0 + cos_w0) * 0.5
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    if filter_type == "bandpass":
        # Constant 0 dB peak gain (Slide 5 & Slide 9 left)
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    if filter_type == "resonant_bandpass":
        # Constant skirt gain -> peak gain = 20*log10(Q) (Slide 9 right)
        b0 = sin_w0 * 0.5
        b1 = 0.0
        b2 = -sin_w0 * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    if filter_type == "bandreject":
        # Notch / BandReject (Slide 6)
        b0 = 1.0
        b1 = -2.0 * cos_w0
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    A = 10.0 ** (float(gain_db) / 40.0)
    if filter_type == "peak":
        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / A
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    if filter_type == "lowshelf":
        sqrt_a = math.sqrt(A)
        # Map Q onto shelf slope parameter S cleanly
        slope = max(0.15, min(4.0, q_safe / 0.70710678))
        alpha_s = sin_w0 * 0.5 * math.sqrt(max(1e-4, (A + 1.0 / A) * (1.0 / slope - 1.0) + 2.0))
        two_sqrt_a_alpha = 2.0 * sqrt_a * alpha_s
        b0 = A * ((A + 1.0) - (A - 1.0) * cos_w0 + two_sqrt_a_alpha)
        b1 = 2.0 * A * ((A - 1.0) - (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) - (A - 1.0) * cos_w0 - two_sqrt_a_alpha)
        a0 = (A + 1.0) + (A - 1.0) * cos_w0 + two_sqrt_a_alpha
        a1 = -2.0 * ((A - 1.0) + (A + 1.0) * cos_w0)
        a2 = (A + 1.0) + (A - 1.0) * cos_w0 - two_sqrt_a_alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    if filter_type == "highshelf":
        sqrt_a = math.sqrt(A)
        slope = max(0.15, min(4.0, q_safe / 0.70710678))
        alpha_s = sin_w0 * 0.5 * math.sqrt(max(1e-4, (A + 1.0 / A) * (1.0 / slope - 1.0) + 2.0))
        two_sqrt_a_alpha = 2.0 * sqrt_a * alpha_s
        b0 = A * ((A + 1.0) + (A - 1.0) * cos_w0 + two_sqrt_a_alpha)
        b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) + (A - 1.0) * cos_w0 - two_sqrt_a_alpha)
        a0 = (A + 1.0) - (A - 1.0) * cos_w0 + two_sqrt_a_alpha
        a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cos_w0)
        a2 = (A + 1.0) - (A - 1.0) * cos_w0 - two_sqrt_a_alpha
        return _normalize_biquad(b0, b1, b2, a0, a1, a2)

    return IDENTITY_SOS.copy()


def _design_moog_ladder(f0: float, fs: float, q: float) -> np.ndarray:
    """Design a 4-pole 24 dB/oct resonant Moog-style ladder filter in SOS form.

    Uses prewarped analog 4-pole ladder poles with negative feedback k in [0, 3.85]
    and bilinear transformation into two unconditionally stable 2nd-order sections.
    """
    resonance = max(0.0, min(1.0, (float(q) - 0.5) / 14.5))
    k = 3.85 * resonance

    # Prewarp analog cutoff so resonance peaks right around f0
    wc = 2.0 * fs * math.tan(math.pi * f0 / fs)
    k_root4 = k ** 0.25 if k > 0.0 else 0.0
    angles = (math.pi / 4.0, 3.0 * math.pi / 4.0, 5.0 * math.pi / 4.0, 7.0 * math.pi / 4.0)
    poles = np.array(
        [wc * (-1.0 + k_root4 * complex(math.cos(a), math.sin(a))) for a in angles],
        dtype=np.complex128,
    )
    # Classic passband normalization (0 dB at DC)
    gain = (1.0 + k) * (wc ** 4)
    z, p, g = signal.bilinear_zpk([], poles, gain, fs)
    sos = signal.zpk2sos(z, p, g)
    return np.asarray(sos, dtype=np.float64)


def design_filter(
    filter_type: str,
    freq: float,
    fs: float,
    q: float = 0.70710678,
    gain_db: float = 0.0,
    order: int = 2,
    drive: float = 1.0,
) -> np.ndarray:
    """Design a digital filter returning SciPy SOS array of shape (N, 6)."""
    _ = drive  # Nonlinear drive is applied in time-domain processing for Moog Ladder
    ftype = str(filter_type).lower().strip()
    if ftype in ("bypass", "flat", "none"):
        return IDENTITY_SOS.copy()

    f0 = clamp_freq(freq, fs)
    q_safe = max(0.1, min(30.0, float(q)))
    ord_int = int(order)

    if ftype == "moog_ladder":
        return _design_moog_ladder(f0, fs, q_safe)

    if ftype in ("lowpass", "highpass"):
        if ord_int == 1:
            return _design_first_order(ftype, f0, fs)
        if ord_int == 4:
            q_scale = max(q_safe / 0.70710678, 0.35)
            q1 = 0.5411961 * math.sqrt(q_scale)
            q2 = 1.3065630 * q_scale
            s1 = _design_rbj_biquad(ftype, f0, fs, q1, 0.0)
            s2 = _design_rbj_biquad(ftype, f0, fs, q2, 0.0)
            return np.vstack([s1, s2])
        return _design_rbj_biquad(ftype, f0, fs, q_safe, 0.0)

    if ftype == "bandpass" and ord_int == 4:
        metrics = compute_band_metrics(f0, q_safe)
        fl = max(10.0, metrics["f_low"])
        fh = min(0.49 * float(fs), max(fl + 5.0, metrics["f_high"]))
        if fh > fl + 2.0:
            sos = signal.butter(2, [fl, fh], btype="bandpass", fs=float(fs), output="sos")
            return np.asarray(sos, dtype=np.float64)

    if ftype == "bandreject" and ord_int == 4:
        metrics = compute_band_metrics(f0, q_safe)
        fl = max(10.0, metrics["f_low"])
        fh = min(0.49 * float(fs), max(fl + 5.0, metrics["f_high"]))
        if fh > fl + 2.0:
            sos = signal.butter(2, [fl, fh], btype="bandstop", fs=float(fs), output="sos")
            return np.asarray(sos, dtype=np.float64)

    return _design_rbj_biquad(ftype, f0, fs, q_safe, gain_db)


def _eval_sos_freqz(sos: np.ndarray, freqs: np.ndarray, fs: float) -> np.ndarray:
    """Evaluate complex frequency response H(e^{jw}) over frequency vector in Hz."""
    if hasattr(signal, "freqz_sos"):
        _, h = signal.freqz_sos(sos, worN=freqs, fs=float(fs))
    else:
        _, h = signal.sosfreqz(sos, worN=freqs, fs=float(fs))
    return np.asarray(h, dtype=np.complex128)


def _h_to_mag_phase(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mag_db = 20.0 * np.log10(np.maximum(np.abs(h), 1e-6))
    phase_deg = np.rad2deg(np.unwrap(np.angle(h)))
    return mag_db, phase_deg


def compute_sos_response(
    sos: np.ndarray, freqs: np.ndarray, fs: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (magnitude_db, phase_deg, H_complex) for a single SOS filter."""
    h = _eval_sos_freqz(sos, freqs, fs)
    mag_db, phase_deg = _h_to_mag_phase(h)
    return mag_db, phase_deg, h


def compute_series_response(
    sos_list: Sequence[np.ndarray], freqs: np.ndarray, fs: float
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Return composite magnitude_db, phase_deg, and individual dB curves for series chain."""
    h_total = np.ones(len(freqs), dtype=np.complex128)
    indiv_db: list[np.ndarray] = []
    for sos in sos_list:
        h_i = _eval_sos_freqz(sos, freqs, fs)
        h_total *= h_i
        mag_i, _ = _h_to_mag_phase(h_i)
        indiv_db.append(mag_i)
    mag_db, phase_deg = _h_to_mag_phase(h_total)
    return mag_db, phase_deg, indiv_db


def compute_parallel_response(
    sos_list: Sequence[np.ndarray],
    gains_lin: Sequence[float] | None,
    freqs: np.ndarray,
    fs: float,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Return composite magnitude_db, phase_deg, and individual dB curves for parallel bank."""
    if not sos_list:
        zeros = np.zeros(len(freqs), dtype=np.float64)
        return zeros, zeros, []

    if gains_lin is None:
        gains = [1.0] * len(sos_list)
    else:
        gains = list(gains_lin)

    h_total = np.zeros(len(freqs), dtype=np.complex128)
    indiv_db: list[np.ndarray] = []
    for sos, g in zip(sos_list, gains):
        h_i = _eval_sos_freqz(sos, freqs, fs) * float(g)
        h_total += h_i
        mag_i, _ = _h_to_mag_phase(h_i)
        indiv_db.append(mag_i)

    mag_db, phase_deg = _h_to_mag_phase(h_total)
    return mag_db, phase_deg, indiv_db


def compute_ideal_response(
    filter_type: str, freq: float, q: float, freqs: np.ndarray
) -> np.ndarray:
    """Compute brick-wall ideal filter curve for Slide 7 transition-zone visualization."""
    ftype = str(filter_type).lower().strip()
    freqs_arr = np.asarray(freqs, dtype=np.float64)
    out = np.full_like(freqs_arr, 0.0)

    if ftype in ("lowpass", "moog_ladder"):
        out[freqs_arr > freq] = -72.0
    elif ftype == "highpass":
        out[freqs_arr < freq] = -72.0
    elif ftype in ("bandpass", "resonant_bandpass"):
        m = compute_band_metrics(freq, q)
        out[(freqs_arr < m["f_low"]) | (freqs_arr > m["f_high"])] = -72.0
    elif ftype == "bandreject":
        m = compute_band_metrics(freq, q)
        out[(freqs_arr >= m["f_low"]) & (freqs_arr <= m["f_high"])] = -72.0
    return out


def _estimate_ringing_ms(h: np.ndarray, fs: float, threshold_db: float = -40.0) -> float:
    """Estimate impulse decay (ringing) duration in ms down to threshold_db below peak."""
    abs_h = np.abs(h)
    peak = float(np.max(abs_h))
    if peak < 1e-9:
        return 0.0
    thresh = peak * (10.0 ** (threshold_db / 20.0))
    above = np.where(abs_h >= thresh)[0]
    if len(above) == 0:
        return 0.0
    last_idx = int(above[-1])
    return (last_idx / float(fs)) * 1000.0


def compute_impulse_response(
    mode: str,
    config: Any,
    fs: float,
    n_samples: int = 2048,
) -> dict[str, Any]:
    """Compute time-domain impulse response h[n] and ringing decay estimate in ms."""
    delta = np.zeros(n_samples, dtype=np.float64)
    delta[0] = 1.0
    h = np.zeros(n_samples, dtype=np.float64)

    mode_l = str(mode).lower().strip()
    if mode_l == "sos":
        sos = np.asarray(config, dtype=np.float64)
        h = signal.sosfilt(sos, delta)
    elif mode_l == "single":
        sos = design_filter(
            config.filter_type,
            config.freq,
            fs,
            q=config.q,
            gain_db=config.gain_db,
            order=config.order,
            drive=getattr(config, "drive", 1.0),
        )
        h = signal.sosfilt(sos, delta)
    elif mode_l == "network":
        active = [st for st in config.stages if st.enabled]
        if not active:
            h = delta.copy()
        elif config.topology == "series":
            sig = delta.copy()
            for st in active:
                sos = design_filter(st.filter_type, st.freq, fs, st.q, st.gain_db, st.order)
                sig = signal.sosfilt(sos, sig)
            h = sig
        elif config.topology == "parallel":
            acc = np.zeros(n_samples, dtype=np.float64)
            for st in active:
                sos = design_filter(st.filter_type, st.freq, fs, st.q, st.gain_db, st.order)
                acc += signal.sosfilt(sos, delta)
            h = acc / max(1, len(active))
        else:  # bank: each stage is BandPass -> LowPass -> HighPass branch
            acc = np.zeros(n_samples, dtype=np.float64)
            for st in active:
                sos_bp = design_filter("bandpass", st.freq, fs, st.q, 0.0, 2)
                sos_lp = design_filter("lowpass", min(19500.0, st.freq * 2.5), fs, 0.7071, 0.0, 2)
                sos_hp = design_filter("highpass", max(25.0, st.freq * 0.4), fs, 0.7071, 0.0, 2)
                branch = signal.sosfilt(sos_bp, delta)
                branch = signal.sosfilt(sos_lp, branch)
                branch = signal.sosfilt(sos_hp, branch)
                acc += branch
            h = acc / max(1, len(active))
    elif mode_l == "graphic_eq":
        freqs = (
            ISO_10_BANDS
            if config.band_count == 10
            else ISO_20_BANDS if config.band_count == 20 else ISO_30_BANDS
        )
        q_val = 1.414 if config.band_count == 10 else 2.871 if config.band_count == 20 else 4.318
        sections = [
            design_filter("peak", float(f_c), fs, q_val, float(g_db), 2)
            for f_c, g_db in zip(freqs, config.gains_db)
            if abs(g_db) > 0.02
        ]
        h = signal.sosfilt(np.vstack(sections), delta) if sections else delta.copy()
    elif mode_l == "parametric_eq":
        sections = [
            design_filter(band.filter_type, band.freq, fs, band.q, band.gain_db, band.order)
            for band in config.bands
            if band.enabled
        ]
        h = signal.sosfilt(np.vstack(sections), delta) if sections else delta.copy()
    else:
        h = delta.copy()

    times_ms = (np.arange(n_samples, dtype=np.float64) / float(fs)) * 1000.0
    return {
        "times_ms": times_ms,
        "impulse": h,
        "ringing_ms": _estimate_ringing_ms(h, fs, threshold_db=-40.0),
    }


def log_frequency_grid(n_points: int = 512, f_min: float = 20.0, f_max: float = 20000.0) -> np.ndarray:
    """Return logarithmically spaced frequency grid in Hz."""
    return np.geomspace(float(f_min), float(f_max), int(n_points), dtype=np.float64)
