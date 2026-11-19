"""Headless UI smoke tests for FilterLab MainWindow, Didactic modules, Quiz, and Lab."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import run
from src.didactics.curriculum import DIDACTIC_MODULES, QUIZ_QUESTIONS
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
