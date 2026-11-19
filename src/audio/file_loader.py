"""Audio file loading, resampling, stereo conversion, and waveform peak extraction."""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
import soundfile as sf
from scipy import signal


@dataclass
class LoadedAudio:
    path: str
    filename: str
    sample_rate: int
    orig_sample_rate: int
    orig_channels: int
    duration_s: float
    samples: np.ndarray  # shape (N, 2), dtype float32
    waveform_peaks: np.ndarray  # shape (num_bins,), dtype float32


def _compute_waveform_peaks(samples: np.ndarray, num_bins: int = 600) -> np.ndarray:
    """Compute peak envelope bins in [0, 1] for waveform timeline rendering."""
    n = samples.shape[0]
    if n == 0:
        return np.zeros(num_bins, dtype=np.float32)
    mono_abs = np.max(np.abs(samples), axis=1)
    if n <= num_bins:
        peaks = np.zeros(num_bins, dtype=np.float32)
        idx = np.linspace(0, num_bins - 1, n).astype(int)
        peaks[idx] = mono_abs
        return np.clip(peaks, 0.0, 1.0)
    edges = np.linspace(0, n, num_bins + 1, dtype=int)
    peaks = np.empty(num_bins, dtype=np.float32)
    for i in range(num_bins):
        seg = mono_abs[edges[i] : edges[i + 1]]
        peaks[i] = float(np.max(seg)) if len(seg) > 0 else 0.0
    return np.clip(peaks, 0.0, 1.0)


def _convert_to_stereo(data: np.ndarray) -> np.ndarray:
    """Convert (N, C) audio array into (N, 2) float32 stereo."""
    if data.ndim == 1:
        return np.column_stack((data, data)).astype(np.float32)
    channels = data.shape[1]
    if channels == 1:
        return np.column_stack((data[:, 0], data[:, 0])).astype(np.float32)
    if channels == 2:
        return data.astype(np.float32)
    # Mix multi-channel audio cleanly down to stereo
    left = data[:, 0::2].mean(axis=1)
    right = data[:, 1::2].mean(axis=1)
    stereo = np.column_stack((left, right))
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if peak > 1.0:
        stereo = stereo / peak
    return stereo.astype(np.float32)


def _resample_stereo(stereo: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample (N, 2) float32 stereo using polyphase FIR resampling."""
    if orig_sr == target_sr or stereo.shape[0] == 0:
        return stereo
    frac = Fraction(int(target_sr), int(orig_sr)).limit_denominator(512)
    up, down = frac.numerator, frac.denominator
    left = signal.resample_poly(stereo[:, 0], up, down)
    right = signal.resample_poly(stereo[:, 1], up, down)
    return np.column_stack((left, right)).astype(np.float32)


def _read_via_afconvert(path: str) -> tuple[np.ndarray, int]:
    """macOS fallback using /usr/bin/afconvert for M4A, AAC, and CAF containers."""
    if sys.platform != "darwin" or not os.path.isfile("/usr/bin/afconvert"):
        raise RuntimeError("Conversione afconvert disponibile solo su macOS.")

    fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="filterlab_")
    os.close(fd)
    try:
        proc = subprocess.run(
            ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEF32", path, tmp_wav],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Impossibile decodificare il file audio con afconvert: {proc.stderr.strip()}"
            )
        data, sr = sf.read(tmp_wav, dtype="float32", always_2d=True)
        return data, int(sr)
    finally:
        if os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except OSError:
                pass


def load_audio_file(path: str, target_sr: int = 48000, num_peak_bins: int = 600) -> LoadedAudio:
    """Load an audio file into float32 stereo resampled to target_sr."""
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File audio non trovato: {abs_path}")

    ext = os.path.splitext(abs_path)[1].lower()
    try:
        data, orig_sr = sf.read(abs_path, dtype="float32", always_2d=True)
    except Exception as exc:
        if sys.platform == "darwin" and ext in (".m4a", ".aac", ".caf", ".mp4", ".alac"):
            data, orig_sr = _read_via_afconvert(abs_path)
        else:
            raise RuntimeError(f"Formato audio non supportato o file danneggiato: {exc}") from exc

    orig_channels = int(data.shape[1]) if data.ndim > 1 else 1
    stereo = _convert_to_stereo(data)
    if int(orig_sr) != int(target_sr):
        stereo = _resample_stereo(stereo, int(orig_sr), int(target_sr))

    duration_s = float(stereo.shape[0]) / float(target_sr) if target_sr > 0 else 0.0
    peaks = _compute_waveform_peaks(stereo, num_bins=num_peak_bins)

    return LoadedAudio(
        path=abs_path,
        filename=os.path.basename(abs_path),
        sample_rate=int(target_sr),
        orig_sample_rate=int(orig_sr),
        orig_channels=orig_channels,
        duration_s=duration_s,
        samples=stereo,
        waveform_peaks=peaks,
    )
