"""Main application window for FilterLab combining Didactic Course and Live DSP Lab."""

from __future__ import annotations

import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src import __app_name__, __version__
from src.audio.engine import AudioEngine, list_audio_devices
from src.didactics.curriculum import ExperimentPreset
from src.ui.didactic_view import DidacticView
from src.ui.lab_view import LabView
from src.ui.styles import DARK_THEME_QSS


class MainWindow(QMainWindow):
    """Top-level FilterLab console window."""

    SUPPORTED_AUDIO_EXTS = {
        ".wav", ".aif", ".aiff", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".caf",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} v{__version__} — Digital Filter & EQ Lab")
        self.resize(1340, 860)
        self.setMinimumSize(1060, 700)
        self.setAcceptDrops(True)
        self.setStyleSheet(DARK_THEME_QSS)

        self.engine = AudioEngine(sample_rate=48000, block_size=512)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body_wrap = QWidget()
        body_lay = QVBoxLayout(body_wrap)
        body_lay.setContentsMargins(10, 8, 10, 10)

        self.main_tabs = QTabWidget()
        self.didactic_view = DidacticView()
        self.lab_view = LabView(self.engine)
        self.lab_view.audio_state_changed = self._update_audio_status_pill

        self.main_tabs.addTab(self.didactic_view, "📚 Percorso Didattico (Slide 1–18)")
        self.main_tabs.addTab(self.lab_view, "🎛️ Laboratorio Pratico DSP")
        body_lay.addWidget(self.main_tabs)
        root.addWidget(body_wrap, 1)

        self.didactic_view.experiment_requested.connect(self._on_experiment_requested)

        self._refresh_output_devices()
        self._update_audio_status_pill()

    def _build_header(self) -> QFrame:
        hdr = QFrame()
        hdr.setObjectName("GlobalHeader")
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(12)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        title = QLabel("🎛️ FilterLab")
        title.setStyleSheet("font-size:18px; font-weight:800; color:#00e5ff;")
        sub = QLabel("Teoria e Laboratorio Interattivo sui Filtri Digitali (macOS & Windows)")
        sub.setStyleSheet("font-size:11.5px; color:#94a3b8;")
        brand_col.addWidget(title)
        brand_col.addWidget(sub)
        lay.addLayout(brand_col)

        lay.addStretch()

        out_lbl = QLabel("Uscita Audio:")
        out_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._cmb_out_dev = QComboBox()
        self._cmb_out_dev.setMinimumWidth(220)
        self._cmb_out_dev.currentIndexChanged.connect(self._on_output_device_changed)

        btn_refresh = QPushButton("↻")
        btn_refresh.setToolTip("Aggiorna elenco periferiche audio")
        btn_refresh.setFixedWidth(32)
        btn_refresh.clicked.connect(self._on_refresh_devices)

        self._lbl_status_pill = QLabel("● Motore in Pausa")
        self._lbl_status_pill.setProperty("class", "mono-badge")

        lay.addWidget(out_lbl)
        lay.addWidget(self._cmb_out_dev)
        lay.addWidget(btn_refresh)
        lay.addWidget(self._lbl_status_pill)
        return hdr

    def _refresh_output_devices(self) -> None:
        info = list_audio_devices()
        self._cmb_out_dev.blockSignals(True)
        self._cmb_out_dev.clear()
        self._cmb_out_dev.addItem("Uscita Predefinita di Sistema", None)
        for dev in info["outputs"]:
            self._cmb_out_dev.addItem(f"{dev.name} ({dev.max_output_channels}ch)", dev.index)
        self._cmb_out_dev.blockSignals(False)

    def _on_refresh_devices(self) -> None:
        self._refresh_output_devices()
        self.lab_view.refresh_audio_devices()

    def _on_output_device_changed(self) -> None:
        out_id = self._cmb_out_dev.currentData()
        self.engine.set_devices(self.engine.input_device, out_id)

    def _update_audio_status_pill(self) -> None:
        if self.engine.is_running:
            self._lbl_status_pill.setText(f"● Audio Attivo • {self.engine.sample_rate} Hz")
            self._lbl_status_pill.setStyleSheet(
                "font-family:monospace; background:#0f2e24; color:#34d399; "
                "border:1px solid #10b981; border-radius:5px; padding:3px 9px; font-size:12px;"
            )
        else:
            self._lbl_status_pill.setText("● Motore in Pausa")
            self._lbl_status_pill.setStyleSheet(
                "font-family:monospace; background:#192130; color:#94a3b8; "
                "border:1px solid #28364d; border-radius:5px; padding:3px 9px; font-size:12px;"
            )

    def _on_experiment_requested(self, preset: ExperimentPreset) -> None:
        self.main_tabs.setCurrentIndex(1)
        self.lab_view.apply_experiment_preset(preset)
        self._update_audio_status_pill()

    def open_file(self, path: str) -> None:
        self.main_tabs.setCurrentIndex(1)
        self.lab_view.load_audio_file_path(path)
        self._update_audio_status_pill()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local and os.path.splitext(local)[1].lower() in self.SUPPORTED_AUDIO_EXTS:
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local and os.path.isfile(local):
                self.open_file(local)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.lab_view.stop_timers()
        self.engine.stop()
        super().closeEvent(event)
