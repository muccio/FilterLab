#!/usr/bin/env python3
"""FilterLab Desktop Application Entry Point."""

from __future__ import annotations

import os
import sys

# Ensure repository root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _check_bundle() -> int:
    """Verify core imports inside source or frozen PyInstaller bundle."""
    import numpy  # noqa: F401
    import scipy.signal  # noqa: F401
    import sounddevice  # noqa: F401
    import soundfile  # noqa: F401
    from PySide6 import QtCore, QtGui, QtWidgets  # noqa: F401

    from src.audio.engine import AudioEngine  # noqa: F401
    from src.didactics.curriculum import DIDACTIC_MODULES  # noqa: F401
    from src.dsp.filter_design import design_filter  # noqa: F401

    print("FilterLab Standalone Bundle Verification: OK")
    print(
        f"Loaded {len(DIDACTIC_MODULES)} didactic modules; "
        "PySide6, NumPy, SciPy, sounddevice, soundfile available."
    )
    return 0


def main() -> int:
    clean_argv = [arg for arg in sys.argv[1:] if not arg.startswith("-psn")]

    if "--check-build" in clean_argv:
        return _check_bundle()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow

    app = QApplication([sys.argv[0]] + clean_argv)
    app.setApplicationName("FilterLab")
    app.setApplicationDisplayName("FilterLab")
    app.setOrganizationName("MusicaApplicata")
    app.setOrganizationDomain("filterlab.app")

    base_dir = getattr(sys, "_MEIPASS", SCRIPT_DIR)
    asset_candidates = [
        os.path.join(base_dir, "assets"),
        os.path.join(SCRIPT_DIR, "packaging", "assets"),
    ]
    for adir in asset_candidates:
        for fname in ("icon.png", "icon.ico", "icon.icns"):
            ip = os.path.join(adir, fname)
            if os.path.isfile(ip):
                app.setWindowIcon(QIcon(ip))
                break

    window = MainWindow()

    target_files = [arg for arg in clean_argv if not arg.startswith("-") and os.path.isfile(arg)]
    if target_files:
        window.open_file(os.path.abspath(target_files[0]))

    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        window.show()
        return app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
