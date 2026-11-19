"""Phase-continuous internal test signal generators for real-time audio DSP."""

from __future__ import annotations

import math
from enum import Enum

import numpy as np
from scipy import signal

# 3rd-order -3 dB/oct Pink Noise shaping IIR filter (Julius O. Smith III)
_PINK_B = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786], dtype=np.float64)
_PINK_A = np.array([1.0, -2.494956002, 2.017265875, -0.522189400], dtype=np.float64)


class GeneratorType(str, Enum):
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    IMPULSE = "impulse"
    SAWTOOTH = "sawtooth"
    SQUARE = "square"
    SINE = "sine"
    LOG_SWEEP = "log_sweep"
    SYNTH_CHORD = "synth_chord"


def _polyblep(t: np.ndarray, dt: float) -> np.ndarray:
    """Vectorized 2nd-order Polynomial Bandlimited Step (PolyBLEP) residual."""
    out = np.zeros_like(t)
    m1 = t < dt
    if np.any(m1):
        x = t[m1] / dt
        out[m1] = x + x - x * x - 1.0
    m2 = t > (1.0 - dt)
    if np.any(m2):
        x = (t[m2] - 1.0) / dt
        out[m2] = x * x + x + x + 1.0
    return out


class SignalGenerator:
    """Phase-continuous signal generator producing stereo float32 blocks."""

    def __init__(self, sample_rate: float = 48000.0, seed: int = 42) -> None:
        self.sample_rate = float(sample_rate)
        self.rng = np.random.default_rng(seed)

        self.gen_type: GeneratorType = GeneratorType.WHITE_NOISE
        self.freq_hz: float = 220.0
        self.impulse_rate_hz: float = 2.0
        self.level_db: float = -12.0

        # Persistent oscillator phases
        self._phase: float = 0.0
        self._chord_phases: np.ndarray = np.zeros(4, dtype=np.float64)
        self._sweep_elapsed: float = 0.0
        self._sweep_phase: float = 0.0
        self._sweep_duration_s: float = 6.0
        self._impulse_counter: int = 0

        # 3rd-order pink noise IIR state
        self._pink_zi: np.ndarray = np.zeros(3, dtype=np.float64)

    def set_sample_rate(self, sample_rate: float) -> None:
        self.sample_rate = max(8000.0, float(sample_rate))

    def set_params(
        self,
        gen_type: GeneratorType | str | None = None,
        freq_hz: float | None = None,
        impulse_rate_hz: float | None = None,
        level_db: float | None = None,
    ) -> None:
        if gen_type is not None:
            self.gen_type = GeneratorType(gen_type)
        if freq_hz is not None:
            self.freq_hz = max(20.0, min(16000.0, float(freq_hz)))
        if impulse_rate_hz is not None:
            self.impulse_rate_hz = max(0.5, min(8.0, float(impulse_rate_hz)))
        if level_db is not None:
            self.level_db = max(-60.0, min(0.0, float(level_db)))

    def reset_state(self) -> None:
        self._phase = 0.0
        self._chord_phases.fill(0.0)
        self._sweep_elapsed = 0.0
        self._sweep_phase = 0.0
        self._impulse_counter = 0
        self._pink_zi.fill(0.0)

    def _generate_white(self, n: int) -> np.ndarray:
        # Unit variance Gaussian scaled so RMS ~ 0.32
        x = self.rng.standard_normal(n) * 0.32
        return np.clip(x, -0.95, 0.95)

    def _generate_pink(self, n: int) -> np.ndarray:
        white = self.rng.standard_normal(n) * 1.4
        out, self._pink_zi = signal.lfilter(_PINK_B, _PINK_A, white, zi=self._pink_zi)
        return np.clip(out, -0.95, 0.95)

    def _generate_impulse(self, n: int) -> np.ndarray:
        period = max(16, int(round(self.sample_rate / self.impulse_rate_hz)))
        indices = (self._impulse_counter + np.arange(n, dtype=np.int64)) % period
        self._impulse_counter = int((self._impulse_counter + n) % period)
        return np.where(indices == 0, 0.95, 0.0)

    def _advance_phase(self, n: int, freq: float) -> tuple[np.ndarray, float]:
        dt = freq / self.sample_rate
        idx = np.arange(n, dtype=np.float64)
        phases = (self._phase + idx * dt) % 1.0
        self._phase = float((self._phase + n * dt) % 1.0)
        return phases, dt

    def _generate_sine(self, n: int) -> np.ndarray:
        phases, _ = self._advance_phase(n, self.freq_hz)
        return np.sin(2.0 * math.pi * phases)

    def _generate_sawtooth(self, n: int) -> np.ndarray:
        phases, dt = self._advance_phase(n, self.freq_hz)
        naive = 2.0 * phases - 1.0
        return naive - _polyblep(phases, dt)

    def _generate_square(self, n: int) -> np.ndarray:
        phases, dt = self._advance_phase(n, self.freq_hz)
        naive = np.where(phases < 0.5, 1.0, -1.0)
        p2 = (phases + 0.5) % 1.0
        return naive + _polyblep(phases, dt) - _polyblep(p2, dt)

    def _generate_log_sweep(self, n: int) -> np.ndarray:
        f_start = 20.0
        f_end = min(20000.0, 0.45 * self.sample_rate)
        dur = self._sweep_duration_s
        ln_ratio = math.log(f_end / f_start)
        inv_fs = 1.0 / self.sample_rate

        t_vec = (self._sweep_elapsed + np.arange(n, dtype=np.float64) * inv_fs) % dur
        inst_freqs = f_start * np.exp((ln_ratio / dur) * t_vec)
        d_phases = (2.0 * math.pi * inv_fs) * inst_freqs
        phases = self._sweep_phase + np.cumsum(d_phases)
        self._sweep_phase = float(phases[-1] % (2.0 * math.pi))
        self._sweep_elapsed = float((self._sweep_elapsed + n * inv_fs) % dur)

        env = np.clip(np.minimum(t_vec / 0.02, (dur - t_vec) / 0.02), 0.0, 1.0)
        return np.sin(phases) * env

    def _generate_synth_chord(self, n: int) -> np.ndarray:
        # Warm Am7 chord centered around base freq (default 110 Hz -> A2, C3, E3, G3)
        base = max(40.0, min(440.0, self.freq_hz))
        ratios = (1.0, 1.1892, 1.4983, 1.7818)  # Minor 7th with slight organic detune
        detunes = (0.998, 1.002, 0.999, 1.003)
        idx = np.arange(n, dtype=np.float64)
        mix = np.zeros(n, dtype=np.float64)
        for v in range(4):
            f_v = base * ratios[v] * detunes[v]
            dt = f_v / self.sample_rate
            ph = (self._chord_phases[v] + idx * dt) % 1.0
            self._chord_phases[v] = float((self._chord_phases[v] + n * dt) % 1.0)
            saw = (2.0 * ph - 1.0) - _polyblep(ph, dt)
            mix += saw * 0.25
        return mix

    def generate(self, num_frames: int) -> np.ndarray:
        """Generate (num_frames, 2) float32 stereo audio block."""
        n = int(num_frames)
        g = self.gen_type
        if g == GeneratorType.WHITE_NOISE:
            mono = self._generate_white(n)
        elif g == GeneratorType.PINK_NOISE:
            mono = self._generate_pink(n)
        elif g == GeneratorType.IMPULSE:
            mono = self._generate_impulse(n)
        elif g == GeneratorType.SINE:
            mono = self._generate_sine(n)
        elif g == GeneratorType.SAWTOOTH:
            mono = self._generate_sawtooth(n)
        elif g == GeneratorType.SQUARE:
            mono = self._generate_square(n)
        elif g == GeneratorType.LOG_SWEEP:
            mono = self._generate_log_sweep(n)
        elif g == GeneratorType.SYNTH_CHORD:
            mono = self._generate_synth_chord(n)
        else:
            mono = np.zeros(n, dtype=np.float64)

        gain = 10.0 ** (self.level_db / 20.0)
        # Keep impulse peak crisp without pulling down transient too aggressively
        if g == GeneratorType.IMPULSE:
            gain = max(gain, 10.0 ** (max(self.level_db, -12.0) / 20.0))
        scaled = (mono * gain).astype(np.float32)
        return np.column_stack((scaled, scaled))
