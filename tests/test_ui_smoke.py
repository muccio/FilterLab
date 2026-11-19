"""Headless UI smoke tests for FilterLab MainWindow, Didactic modules, Quiz, and Lab."""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

import run
from src.didactics.curriculum import DIDACTIC_MODULES, QUIZ_QUESTIONS
from src.dsp.generators import GeneratorType, SignalGenerator
from src.dsp.processor import ChannelStripConfig, FilterDSPProcessor
from src.ui.main_window import MainWindow


def _get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_check_build_entrypoint() -> None:
    assert run._check_bundle() == 0


def test_mainwindow_didactics_quiz_and_all_lab_experiments(monkeypatch) -> None:
    _get_qapp()
    win = MainWindow()
    # Prevent audio device opening during CI headless smoke test
    monkeypatch.setattr(win.engine, "start", lambda: False)

    # Walk through all 10 didactic modules, render diagram, and trigger every experiment preset
    for idx, mod in enumerate(DIDACTIC_MODULES):
        win.didactic_view.select_module(idx)
        assert win.didactic_view._lbl_title.text() == mod.title
        win.didactic_view._diagram._canvas.grab()
        for preset in mod.experiments:
            win._on_experiment_requested(preset)
            assert win.main_tabs.currentIndex() == 1
            assert win.engine.processor.mode == preset.workbench_mode
            win.lab_view.bode_widget.grab()
            for t_mode in ("impulse", "scope", "blackbox"):
                win.lab_view.time_widget.set_view_mode(t_mode)
                win.lab_view.time_widget._canvas.grab()

    # Test Quiz scoring with all correct answers selected
    win.didactic_view.show_quiz()
    for q, grp in zip(QUIZ_QUESTIONS, win.didactic_view._quiz_groups):
        btn = grp.button(q.correct_index)
        assert btn is not None
        btn.setChecked(True)
    score = win.didactic_view.evaluate_quiz()
    assert score == len(QUIZ_QUESTIONS)

    win.didactic_view.reset_quiz()
    score_after_reset = win.didactic_view.evaluate_quiz()
    assert score_after_reset == 0

    # Switch through all 4 Lab workbench tabs
    for tab_idx in range(4):
        win.lab_view.workbench_tabs.setCurrentIndex(tab_idx)

    win.close()


def test_ui_and_dsp_realtime_performance() -> None:
    """Regression guard: cached Bode/Scope rendering and vectorized DSP stay fast for audio."""
    _get_qapp()
    win = MainWindow()
    win.resize(1340, 860)
    win.main_tabs.setCurrentIndex(1)
    win.lab_view.workbench_tabs.setCurrentIndex(3)
    win.lab_view._apply_peq_preset("slide15")

    t_vec = np.arange(4096, dtype=np.float32) / 48000.0
    pre = (0.35 * np.sin(2.0 * np.pi * 440.0 * t_vec)).astype(np.float32)
    post = (0.25 * np.sin(2.0 * np.pi * 440.0 * t_vec)).astype(np.float32)

    bw = win.lab_view.bode_widget
    bw.update_fft(pre, post, 48000.0)
    pm_b = QPixmap(bw.size())
    bw.render(pm_b)  # warm up static cache
    t0 = time.perf_counter()
    for _ in range(30):
        bw.render(pm_b)
    bode_ms = ((time.perf_counter() - t0) / 30) * 1000.0
    assert bode_ms < 5.0, f"Bode cached paint too slow: {bode_ms:.2f} ms"

    tw = win.lab_view.time_widget
    tw.set_view_mode("scope")
    tw.update_live_waves(pre, post, 48000.0)
    sc = tw._canvas
    pm_s = QPixmap(sc.size())
    sc.render(pm_s)
    t0 = time.perf_counter()
    for _ in range(30):
        sc.render(pm_s)
    scope_ms = ((time.perf_counter() - t0) / 30) * 1000.0
    assert scope_ms < 4.0, f"Scope paint too slow: {scope_ms:.2f} ms"
    win.close()

    gen = SignalGenerator(48000.0)
    proc = FilterDSPProcessor(48000.0)
    proc.update_channel_strip(ChannelStripConfig(aux_send=0.7, aux_pre_fader=True, aux_fx_enabled=True))
    for gt in (GeneratorType.PINK_NOISE, GeneratorType.LOG_SWEEP):
        gen.set_params(gen_type=gt)
        t0 = time.perf_counter()
        for _ in range(40):
            blk = gen.generate(1024)
            out, _ = proc.process_block(blk)
            assert np.all(np.isfinite(out))
        dsp_ms = ((time.perf_counter() - t0) / 40) * 1000.0
        assert dsp_ms < 2.0, f"{gt.value} + AuxFX 1024-sample block too slow: {dsp_ms:.2f} ms"
