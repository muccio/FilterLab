"""Unit tests for FilterLab mathematical filter design and frequency/impulse analysis."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.dsp.filter_design import (
    ISO_10_BANDS,
    ISO_20_BANDS,
    ISO_30_BANDS,
    compute_band_metrics,
    compute_impulse_response,
    compute_parallel_response,
    compute_series_response,
    compute_sos_response,
    design_filter,
    exact_third_octave_freq,
    from_cutoffs,
    log_frequency_grid,
)
from src.dsp.processor import SingleFilterConfig

FS = 48000.0


def _mag_at(sos: np.ndarray, freq_hz: float, fs: float = FS) -> float:
    mag_db, _, _ = compute_sos_response(sos, np.array([freq_hz], dtype=np.float64), fs)
    return float(mag_db[0])


def test_cutoff_minus_3db_across_orders() -> None:
    """Slide 3, 4, 7, 8: LowPass & HighPass 1st, 2nd (Butterworth), 4th order hit -3.01 dB @ fc."""
    for ftype in ("lowpass", "highpass"):
        for order in (1, 2, 4):
            sos = design_filter(ftype, 1000.0, FS, q=0.70710678, order=order)
            mag = _mag_at(sos, 1000.0)
            assert math.isclose(mag, -3.0103, abs_tol=0.18), f"{ftype} order={order} -> {mag} dB"


def test_rolloff_slopes_slide7_slide8() -> None:
    """Slide 7 & 8: verify 6 dB/oct (1st), 12 dB/oct (2nd), and 24 dB/oct (4th) roll-off."""
    # Slide 7 LowPass 300 Hz 1st order: ~ -12 dB @ 1200 Hz, ~ -18 dB @ 2400 Hz
    sos_lp1 = design_filter("lowpass", 300.0, FS, order=1)
    assert math.isclose(_mag_at(sos_lp1, 1200.0), -12.3, abs_tol=0.5)
    assert math.isclose(_mag_at(sos_lp1, 2400.0), -18.1, abs_tol=0.5)

    # Slide 8 LowPass 300 Hz 2nd order Butterworth: ~ -24 dB @ 1200 Hz, ~ -36 dB @ 2400 Hz
    sos_lp2 = design_filter("lowpass", 300.0, FS, q=0.70710678, order=2)
    assert math.isclose(_mag_at(sos_lp2, 1200.0), -24.08, abs_tol=0.5)
    assert math.isclose(_mag_at(sos_lp2, 2400.0), -36.12, abs_tol=0.6)

    # 4th order: ~ -48 dB @ 1200 Hz
    sos_lp4 = design_filter("lowpass", 300.0, FS, q=0.70710678, order=4)
    slope_oct = _mag_at(sos_lp4, 1200.0) - _mag_at(sos_lp4, 2400.0)
    assert math.isclose(slope_oct, 24.0, abs_tol=1.0)


def test_bandpass_slide5_and_slide8() -> None:
    """Slide 5 & 8: fL=1600, fH=2000 -> fc ≈ 1788.85 Hz, 0 dB @ fc, -3 dB @ fL & fH."""
    metrics = from_cutoffs(1600.0, 2000.0)
    assert math.isclose(metrics["fc"], 1788.85438, abs_tol=0.01)
    assert math.isclose(metrics["bw"], 400.0, abs_tol=0.01)

    back = compute_band_metrics(metrics["fc"], metrics["q"])
    assert math.isclose(back["f_low"], 1600.0, abs_tol=0.05)
    assert math.isclose(back["f_high"], 2000.0, abs_tol=0.05)

    sos = design_filter("bandpass", metrics["fc"], FS, q=metrics["q"], order=2)
    assert math.isclose(_mag_at(sos, metrics["fc"]), 0.0, abs_tol=0.05)
    assert math.isclose(_mag_at(sos, 1600.0), -3.01, abs_tol=0.25)
    assert math.isclose(_mag_at(sos, 2000.0), -3.01, abs_tol=0.25)


def test_bandreject_slide6() -> None:
    """Slide 6: fL=1900, fH=2000 -> fc ≈ 1949.36 Hz, deep notch at fc, -3 dB at cutoffs."""
    metrics = from_cutoffs(1900.0, 2000.0)
    assert math.isclose(metrics["fc"], 1949.35887, abs_tol=0.01)
    sos = design_filter("bandreject", metrics["fc"], FS, q=metrics["q"], order=2)
    assert _mag_at(sos, metrics["fc"]) < -40.0
    assert math.isclose(_mag_at(sos, 1900.0), -3.01, abs_tol=0.35)
    assert math.isclose(_mag_at(sos, 2000.0), -3.01, abs_tol=0.35)


def test_resonant_bandpass_slide9() -> None:
    """Slide 9: Resonant BandPass peak gain = 20*log10(Q) (+6.02 dB @ Q=2, +15.56 dB @ Q=6)."""
    sos_q2 = design_filter("resonant_bandpass", 1000.0, FS, q=2.0)
    sos_q6 = design_filter("resonant_bandpass", 1000.0, FS, q=6.0)
    assert math.isclose(_mag_at(sos_q2, 1000.0), 6.02, abs_tol=0.2)
    assert math.isclose(_mag_at(sos_q6, 1000.0), 15.56, abs_tol=0.2)


def test_moog_ladder_stability_and_resonance() -> None:
    """Slide 1: Moog Ladder is stable across frequencies/Q, rolls off ~24 dB/oct, peaks at high Q."""
    freqs = log_frequency_grid(300)
    for fc in (60.0, 500.0, 2500.0, 10000.0):
        for q in (0.7, 5.0, 14.0):
            sos = design_filter("moog_ladder", fc, FS, q=q)
            assert sos.shape == (2, 6)
            assert np.all(np.isfinite(sos))
            mag, _, _ = compute_sos_response(sos, freqs, FS)
            assert np.all(np.isfinite(mag))
            # Check stability via pole radii < 1
            for sec in sos:
                roots = np.roots(sec[3:])
                assert np.all(np.abs(roots) < 1.0)

    # Low resonance roll-off in stopband (~24 dB/oct)
    sos_low_q = design_filter("moog_ladder", 400.0, FS, q=0.7)
    slope = _mag_at(sos_low_q, 1600.0) - _mag_at(sos_low_q, 3200.0)
    assert math.isclose(slope, 24.0, abs_tol=1.5)

    # High resonance exhibits prominent resonant peak near fc
    sos_hi_q = design_filter("moog_ladder", 800.0, FS, q=12.0)
    mag_hi, _, _ = compute_sos_response(sos_hi_q, freqs, FS)
    assert float(np.max(mag_hi)) > 10.0


def test_shelving_and_peak_notch_slide14() -> None:
    """Slide 14: Shelf point equals gain/2; Peak/Notch reaches target gain at center freq."""
    sos_ls = design_filter("lowshelf", 1000.0, FS, q=0.7071, gain_db=12.0)
    assert math.isclose(_mag_at(sos_ls, 40.0), 12.0, abs_tol=0.2)
    assert math.isclose(_mag_at(sos_ls, 1000.0), 6.0, abs_tol=0.2)
    assert math.isclose(_mag_at(sos_ls, 16000.0), 0.0, abs_tol=0.2)

    sos_hs = design_filter("highshelf", 1000.0, FS, q=0.7071, gain_db=-12.0)
    assert math.isclose(_mag_at(sos_hs, 40.0), 0.0, abs_tol=0.2)
    assert math.isclose(_mag_at(sos_hs, 1000.0), -6.0, abs_tol=0.2)
    assert math.isclose(_mag_at(sos_hs, 16000.0), -12.0, abs_tol=0.2)

    sos_pk = design_filter("peak", 1000.0, FS, q=2.0, gain_db=12.0)
    sos_nt = design_filter("peak", 1000.0, FS, q=2.0, gain_db=-12.0)
    assert math.isclose(_mag_at(sos_pk, 1000.0), 12.0, abs_tol=0.1)
    assert math.isclose(_mag_at(sos_nt, 1000.0), -12.0, abs_tol=0.1)


def test_series_and_parallel_slide10_slide11() -> None:
    """Slide 10: series doubles stopband slope; Slide 11: parallel shows 4 peaks at 40/80/120/160 Hz."""
    freqs = log_frequency_grid(600)
    s1 = design_filter("bandpass", 1000.0, FS, q=2.0)
    s2 = design_filter("bandpass", 1400.0, FS, q=2.0)
    mag_ser, _, indiv = compute_series_response([s1, s2], freqs, FS)
    # Series dB response equals sum of individual dB responses
    assert np.allclose(mag_ser, indiv[0] + indiv[1], atol=1e-4)

    par_sos = [design_filter("bandpass", float(f), FS, q=10.0) for f in (40, 80, 120, 160)]
    mag_par, _, _ = compute_parallel_response(par_sos, [0.25] * 4, freqs, FS)
    for pf in (40.0, 80.0, 120.0, 160.0):
        idx = int(np.argmin(np.abs(freqs - pf)))
        # Each center peak is clearly above valleys between adjacent peaks
        assert mag_par[idx] > -15.0
    # Valley around 60 Hz is lower than both 40 Hz and 80 Hz peaks
    val_60 = mag_par[int(np.argmin(np.abs(freqs - 60.0)))]
    pk_40 = mag_par[int(np.argmin(np.abs(freqs - 40.0)))]
    assert val_60 < pk_40 - 3.0


def test_iso_bands_and_ringing_proportional_to_q() -> None:
    """Slide 13 ISO bands + Slide 7 ringing duration increases monotonically with Q."""
    assert len(ISO_10_BANDS) == 10
    assert len(ISO_20_BANDS) == 20
    assert len(ISO_30_BANDS) == 30
    assert ISO_30_BANDS[0] == 25 and ISO_30_BANDS[-1] == 20000
    assert math.isclose(exact_third_octave_freq(800.0), 793.7005, abs_tol=0.01)

    imp_low_q = compute_impulse_response(
        "single", SingleFilterConfig("bandpass", 1000.0, q=1.0), FS, n_samples=4096
    )
    imp_mid_q = compute_impulse_response(
        "single", SingleFilterConfig("bandpass", 1000.0, q=5.0), FS, n_samples=4096
    )
    imp_hi_q = compute_impulse_response(
        "single", SingleFilterConfig("bandpass", 1000.0, q=15.0), FS, n_samples=4096
    )
    assert imp_low_q["ringing_ms"] < imp_mid_q["ringing_ms"] < imp_hi_q["ringing_ms"]
