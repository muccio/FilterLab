"""Phase-continuous internal test signal generators for real-time audio DSP."""

from __future__ import annotations

import math
from enum import Enum

import numpy as np


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

        # Paul Kellet 7-pole pink noise state
        self._b = np.zeros(7, dtype=np.float64)

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
        self._b.fill(0.0)

    def _generate_white(self, n: int) -> np.ndarray:
        # Unit variance Gaussian scaled so RMS ~ 0.35 (-9 dBFS before level_db trim)
        x = self.rng.standard_normal(n) * 0.32
        return np.clip(x, -0.95, 0.95)

    def _generate_pink(self, n: int) -> np.ndarray:
        white = self.rng.standard_normal(n) * 0.25
        out = np.empty(n, dtype=np.float64)
        b0, b1, b2, b3, b4, b5, b6 = self._b
        for i in range(n):
            w = white[i]
            b0 = 0.99886 * b0 + w * 0.0555179
            b1 = 0.99332 * b1 + w * 0.0750759
            b2 = 0.96900 * b2 + w * 0.1538520
            b3 = 0.86650 * b3 + w * 0.3104856
            b4 = 0.55000 * b4 + w * 0.5329522
            b5 = -0.7616 * b5 - w * 0.0168980
            out[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11
            b6 = w * 0.115926
        self._b[:] = [b0, b1, b2, b3, b4, b5, b6]
        return np.clip(out, -0.95, 0.95)

    def _generate_impulse(self, n: int) -> np.ndarray:
        out = np.zeros(n, dtype=np.float64)
        period = max(16, int(round(self.sample_rate / self.impulse_rate_hz)))
        cnt = self._impulse_counter
        for i in range(n):
            if cnt == 0:
                out[i] = 0.95
            cnt = (cnt + 1) % period
        self._impulse_counter = cnt
        return out

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

        out = np.empty(n, dtype=np.float64)
        t_el = self._sweep_elapsed
        ph = self._sweep_phase
        for i in range(n):
            frac = t_el / dur
            inst_freq = f_start * math.exp(ln_ratio * frac)
            ph += 2.0 * math.pi * inst_freq * inv_fs
            if ph > 2.0 * math.pi:
                ph -= 2.0 * math.pi
            # Short 20 ms fade-in/out at sweep boundaries to avoid clicks on loop
            env = 1.0
            if t_el < 0.02:
                env = t_el / 0.02
            elif t_el > dur - 0.02:
                env = max(0.0, (dur - t_el) / 0.02)
            out[i] = math.sin(ph) * env
            t_el += inv_fs
            if t_el >= dur:
                t_el -= dur
        self._sweep_elapsed = t_el
        self._sweep_phase = ph
        return out

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
