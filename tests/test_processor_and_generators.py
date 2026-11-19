"""Tests for real-time DSP processor, Channel Strip routing, generators, and file loader."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import soundfile as sf

from src.audio.file_loader import load_audio_file
from src.dsp.generators import GeneratorType, SignalGenerator
from src.dsp.processor import (
    ChannelStripConfig,
    FilterDSPProcessor,
    GraphicEQConfig,
    NetworkConfig,
    ParametricEQConfig,
    SingleFilterConfig,
    StageConfig,
)


def test_all_generators_finite_and_non_empty() -> None:
    gen = SignalGenerator(sample_rate=48000.0, seed=123)
    for gtype in GeneratorType:
        gen.reset_state()
        gen.set_params(gen_type=gtype, freq_hz=440.0, impulse_rate_hz=4.0, level_db=-6.0)
        # Generate several blocks (especially for impulse & log sweep)
        blocks = [gen.generate(512) for _ in range(30)]
        cat = np.concatenate(blocks, axis=0)
        assert cat.shape == (512 * 30, 2)
        assert cat.dtype == np.float32
        assert np.all(np.isfinite(cat))
        assert float(np.max(np.abs(cat))) > 0.01


def test_processor_modes_stability_and_realtime_speed() -> None:
    """Every DSP mode processes 512-sample blocks cleanly without NaNs and well under 5 ms."""
    proc = FilterDSPProcessor(sample_rate=48000.0)
    gen = SignalGenerator(sample_rate=48000.0)
    gen.set_params(GeneratorType.WHITE_NOISE, level_db=-10.0)
    block = gen.generate(512)

    configs: list[tuple[str, callable]] = [
        ("single", lambda: proc.update_single(SingleFilterConfig("moog_ladder", 800.0, 9.0, 0.0, 4, 2.0))),
        (
            "network",
            lambda: proc.update_network(
                NetworkConfig(
                    topology="bank",
                    stages=[
                        StageConfig(True, "bandpass", 300.0, 4.0, 0.0, 2, True, 0.5, 1.0),
                        StageConfig(True, "bandpass", 900.0, 4.0, 0.0, 2, True, 0.7, 1.0),
                        StageConfig(True, "bandpass", 2200.0, 4.0, 0.0, 2, True, 0.4, 1.0),
                        StageConfig(True, "bandpass", 5000.0, 4.0, 0.0, 2, True, 0.9, 1.0),
                    ],
                )
            ),
        ),
        (
            "graphic_eq",
            lambda: proc.update_graphic_eq(
                GraphicEQConfig(band_count=30, gains_db=[3.0 if i % 2 == 0 else -2.0 for i in range(30)])
            ),
        ),
        ("parametric_eq", lambda: proc.update_parametric_eq(ParametricEQConfig())),
    ]

    for mode, setup_fn in configs:
        proc.set_mode(mode)
        setup_fn()
        t0 = time.perf_counter()
        n_iters = 50
        for _ in range(n_iters):
            out, tel = proc.process_block(block)
            assert out.shape == (512, 2)
            assert np.all(np.isfinite(out))
            assert "out_peak_l_db" in tel
        avg_ms = ((time.perf_counter() - t0) / n_iters) * 1000.0
        assert avg_ms < 5.0, f"Mode {mode} took {avg_ms:.2f} ms/block (> 5 ms)"


def test_aux_pre_vs_post_fader_and_pfl_and_pan(tmp_path: Path) -> None:
    """Slide 16-18: Aux Pre vs Post Fader, PFL Solo, and Pan-Pot L/R behavior."""
    proc = FilterDSPProcessor(sample_rate=48000.0)
    proc.set_mode("single")
    proc.update_single(SingleFilterConfig("lowpass", 18000.0, 0.7071, 0.0, 2))

    gen = SignalGenerator(sample_rate=48000.0)
    gen.set_params(GeneratorType.SINE, freq_hz=1000.0, level_db=-6.0)
    blk = gen.generate(512)

    # 1. Aux Pre-Fader with fader closed (-60 dB): Aux remains active while main output is silent
    proc.update_channel_strip(
        ChannelStripConfig(aux_send=0.8, aux_pre_fader=True, aux_fx_enabled=False, fader_db=-60.0)
    )
    _, tel_pre = proc.process_block(blk)
    assert tel_pre["aux_peak_db"] > -15.0

    # 2. Aux Post-Fader with fader closed (-60 dB): Aux drops to -60 dB
    proc.update_channel_strip(
        ChannelStripConfig(aux_send=0.8, aux_pre_fader=False, aux_fx_enabled=False, fader_db=-60.0)
    )
    _, tel_post = proc.process_block(blk)
    assert tel_post["aux_peak_db"] <= -59.0

    # 3. Mute active without PFL -> output muted; Mute active WITH PFL -> signal audible
    proc.update_channel_strip(ChannelStripConfig(mute=True, pfl_solo=False, fader_db=0.0))
    out_muted, _ = proc.process_block(blk)
    assert float(np.max(np.abs(out_muted))) < 1e-6

    proc.update_channel_strip(ChannelStripConfig(mute=True, pfl_solo=True, fader_db=-60.0))
    out_pfl, _ = proc.process_block(blk)
    assert float(np.max(np.abs(out_pfl))) > 0.2

    # 4. Pan-Pot Hard Left (-1.0) and Hard Right (+1.0)
    proc.update_channel_strip(ChannelStripConfig(pan=-1.0, fader_db=0.0, mute=False, pfl_solo=False))
    out_l, _ = proc.process_block(blk)
    assert float(np.max(np.abs(out_l[:, 0]))) > 0.3
    assert float(np.max(np.abs(out_l[:, 1]))) < 1e-6

    proc.update_channel_strip(ChannelStripConfig(pan=1.0, fader_db=0.0, mute=False, pfl_solo=False))
    out_r, _ = proc.process_block(blk)
    assert float(np.max(np.abs(out_r[:, 0]))) < 1e-6
    assert float(np.max(np.abs(out_r[:, 1]))) > 0.3

    # 5. File loader round-trip (44.1 kHz mono WAV -> resampled to 48 kHz stereo)
    wav_path = tmp_path / "test_mono_44100.wav"
    t = np.arange(4410, dtype=np.float32) / 44100.0
    mono = 0.5 * np.sin(2.0 * np.pi * 440.0 * t)
    sf.write(str(wav_path), mono, 44100)

    loaded = load_audio_file(str(wav_path), target_sr=48000)
    assert loaded.sample_rate == 48000
    assert loaded.orig_sample_rate == 44100
    assert loaded.orig_channels == 1
    assert loaded.samples.ndim == 2 and loaded.samples.shape[1] == 2
    assert len(loaded.waveform_peaks) > 100
