"""Real-time DSP Filter Workbench, Audio Sources, Bode/FFT, and Mixer Channel Strip."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.audio.engine import AudioEngine, SourceMode, list_audio_devices
from src.didactics.curriculum import ExperimentPreset
from src.dsp.filter_design import (
    ISO_10_BANDS,
    ISO_20_BANDS,
    ISO_30_BANDS,
    compute_band_metrics,
    compute_ideal_response,
    compute_impulse_response,
    compute_parallel_response,
    compute_series_response,
    compute_sos_response,
    design_filter,
    exact_third_octave_freq,
    log_frequency_grid,
)
from src.dsp.generators import GeneratorType
from src.dsp.processor import (
    ChannelStripConfig,
    GraphicEQConfig,
    NetworkConfig,
    ParametricBandConfig,
    ParametricEQConfig,
    SingleFilterConfig,
    StageConfig,
    default_network_stages,
    default_parametric_bands,
)
from src.ui.widgets.bode_spectrum_widget import BodeNode, BodeSpectrumWidget
from src.ui.widgets.meter_widget import AuxMeterBar, StereoMeterWidget, WaveformSeekWidget
from src.ui.widgets.time_domain_widget import TimeDomainWidget

FILTER_TYPE_ITEMS: list[tuple[str, str]] = [
    ("Passa-Basso (LowPass)", "lowpass"),
    ("Passa-Alto (HighPass)", "highpass"),
    ("Passa-Banda (BandPass)", "bandpass"),
    ("Passa-Banda Risonante", "resonant_bandpass"),
    ("Elimina-Banda (BandReject)", "bandreject"),
    ("Low Shelf", "lowshelf"),
    ("High Shelf", "highshelf"),
    ("Peak / Notch (Bell)", "peak"),
    ("Moog Ladder (24 dB/oct)", "moog_ladder"),
]

STAGE_FILTER_ITEMS: list[tuple[str, str]] = [
    ("BandPass", "bandpass"),
    ("LowPass", "lowpass"),
    ("HighPass", "highpass"),
    ("BandReject", "bandreject"),
    ("Peak / Bell", "peak"),
    ("Low Shelf", "lowshelf"),
    ("High Shelf", "highshelf"),
    ("Resonant BP", "resonant_bandpass"),
]

GENERATOR_ITEMS: list[tuple[str, str]] = [
    ("Rumore Bianco (White Noise)", GeneratorType.WHITE_NOISE.value),
    ("Rumore Rosa (Pink Noise -3 dB/oct)", GeneratorType.PINK_NOISE.value),
    ("Treno di Impulsi (Test Ringing)", GeneratorType.IMPULSE.value),
    ("Onda Dente di Sega (Saw PolyBLEP)", GeneratorType.SAWTOOTH.value),
    ("Onda Quadra (Square PolyBLEP)", GeneratorType.SQUARE.value),
    ("Sinusoide Pura (Misura dB)", GeneratorType.SINE.value),
    ("Sweep Logaritmico (20 Hz → 20 kHz)", GeneratorType.LOG_SWEEP.value),
    ("Accordo Synth Polifonico", GeneratorType.SYNTH_CHORD.value),
]

BAND_COLORS = ["#f59e0b", "#10b981", "#00d2ff", "#a855f7", "#ec4899", "#38bdf8"]


def _freq_to_slider(freq: float) -> int:
    f = max(20.0, min(20000.0, float(freq)))
    return int(round(math.log10(f / 20.0) / 3.0 * 1000.0))


def _slider_to_freq(val: int) -> float:
    return 20.0 * (1000.0 ** (max(0, min(1000, val)) / 1000.0))


class LabView(QWidget):
    """Full real-time DSP Laboratory view."""

    audio_state_changed = None  # optional callback set by MainWindow

    def __init__(self, engine: AudioEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._syncing = False
        self._bode_freqs = log_frequency_grid(480)

        # Config models
        self._single_cfg = SingleFilterConfig()
        self._net_cfg = NetworkConfig()
        self._geq_cfg = GraphicEQConfig()
        self._peq_cfg = ParametricEQConfig()
        self._ch_cfg = ChannelStripConfig()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # 1. Top Audio Source & Transport Bar
        root.addWidget(self._build_source_bar())

        # 2. Optional Experiment Guide Banner
        self._guide_banner = QFrame()
        self._guide_banner.setObjectName("GuideBanner")
        self._guide_banner.setVisible(False)
        gb_lay = QHBoxLayout(self._guide_banner)
        gb_lay.setContentsMargins(10, 6, 10, 6)
        self._lbl_guide = QLabel("")
        self._lbl_guide.setWordWrap(True)
        self._lbl_guide.setStyleSheet("color:#e0f9ff; font-size:12.5px;")
        btn_close_guide = QPushButton("✕")
        btn_close_guide.setFixedSize(24, 24)
        btn_close_guide.clicked.connect(lambda: self._guide_banner.setVisible(False))
        gb_lay.addWidget(self._lbl_guide, 1)
        gb_lay.addWidget(btn_close_guide)
        root.addWidget(self._guide_banner)

        # 3. Main Body: Left (Graphs + 4 Workbenches) | Right (Channel Strip)
        body = QHBoxLayout()
        body.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.bode_widget = BodeSpectrumWidget()
        self.time_widget = TimeDomainWidget()
        splitter.addWidget(self.bode_widget)
        splitter.addWidget(self.time_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        left_col.addWidget(splitter, 1)

        self.workbench_tabs = QTabWidget()
        self.workbench_tabs.setMaximumHeight(295)
        self.workbench_tabs.setMinimumHeight(235)
        self.workbench_tabs.addTab(self._build_single_tab(), "1. Singolo Filtro")
        self.workbench_tabs.addTab(self._build_network_tab(), "2. Serie, Parallelo & Banco")
        self.workbench_tabs.addTab(self._build_graphic_eq_tab(), "3. EQ Grafica (10/20/30 Bande)")
        self.workbench_tabs.addTab(self._build_parametric_eq_tab(), "4. EQ Parametrica")
        left_col.addWidget(self.workbench_tabs)

        body.addLayout(left_col, 1)
        body.addWidget(self._build_channel_strip_panel())
        root.addLayout(body, 1)

        # Wire signals
        self.workbench_tabs.currentChanged.connect(self._on_workbench_tab_changed)
        self.bode_widget.node_changed.connect(self._on_bode_node_changed)

        # Refresh plots & devices initially
        self.refresh_audio_devices()
        self._apply_all_configs_to_dsp()
        self._refresh_visual_curves()

        # 30 ms timer for live FFT, scope, blackbox, meters, and file position
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(30)

    # ------------------------------------------------------------------
    # Source Bar
    # ------------------------------------------------------------------
    def _build_source_bar(self) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card-frame")
        card.setStyleSheet(
            "QFrame { background:#161922; border:1px solid #262c3d; border-radius:8px; padding:4px; }"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_src = QLabel("Sorgente:")
        lbl_src.setStyleSheet("font-weight:700; color:#94a3b8; border:none;")
        top_row.addWidget(lbl_src)

        self._src_group = QButtonGroup(self)
        self._btn_src_int = QPushButton("Generatore Interno")
        self._btn_src_file = QPushButton("File Audio")
        self._btn_src_mic = QPushButton("Microfono Live")
        for idx, (btn, mode) in enumerate(
            (
                (self._btn_src_int, SourceMode.INTERNAL.value),
                (self._btn_src_file, SourceMode.FILE.value),
                (self._btn_src_mic, SourceMode.MIC.value),
            )
        ):
            btn.setCheckable(True)
            btn.setProperty("src_mode", mode)
            self._src_group.addButton(btn, idx)
            top_row.addWidget(btn)
        self._btn_src_int.setChecked(True)
        self._src_group.idClicked.connect(self._on_source_btn_clicked)

        top_row.addStretch()

        self._chk_fft = QCheckBox("Spettro FFT")
        self._chk_fft.setChecked(True)
        self._chk_fft.toggled.connect(self._on_graph_toggles)
        self._chk_phase = QCheckBox("Curva Fase")
        self._chk_phase.setChecked(False)
        self._chk_phase.toggled.connect(self._on_graph_toggles)
        self._chk_ideal = QCheckBox("Ideale (-3 dB)")
        self._chk_ideal.setChecked(False)
        self._chk_ideal.toggled.connect(self._on_graph_toggles)

        top_row.addWidget(self._chk_fft)
        top_row.addWidget(self._chk_phase)
        top_row.addWidget(self._chk_ideal)

        self._btn_bypass_top = QPushButton("Bypass A/B")
        self._btn_bypass_top.setObjectName("BypassBtn")
        self._btn_bypass_top.setCheckable(True)
        self._btn_bypass_top.toggled.connect(self._on_bypass_toggled)
        top_row.addWidget(self._btn_bypass_top)

        self._btn_audio_power = QPushButton("▶ Avvia Audio")
        self._btn_audio_power.setObjectName("StartAudioBtn")
        self._btn_audio_power.setCheckable(True)
        self._btn_audio_power.setMinimumWidth(130)
        self._btn_audio_power.clicked.connect(self._on_audio_power_clicked)
        top_row.addWidget(self._btn_audio_power)

        outer.addLayout(top_row)

        # Source-specific sub-controls stack
        self._src_stack = QStackedWidget()
        self._src_stack.setMaximumHeight(58)

        # 0: Internal Generator
        w_int = QWidget()
        l_int = QHBoxLayout(w_int)
        l_int.setContentsMargins(2, 2, 2, 2)
        l_int.setSpacing(10)
        l_int.addWidget(QLabel("Segnale:"))
        self._cmb_gen = QComboBox()
        for label, val in GENERATOR_ITEMS:
            self._cmb_gen.addItem(label, val)
        self._cmb_gen.currentIndexChanged.connect(self._on_gen_changed)
        l_int.addWidget(self._cmb_gen)

        self._lbl_gen_freq = QLabel("Nota/Freq:")
        self._sld_gen_freq = QSlider(Qt.Orientation.Horizontal)
        self._sld_gen_freq.setRange(0, 1000)
        self._sld_gen_freq.setValue(_freq_to_slider(220.0))
        self._sld_gen_freq.setMaximumWidth(160)
        self._lbl_gen_freq_val = QLabel("220 Hz")
        self._lbl_gen_freq_val.setProperty("class", "mono-badge")
        self._sld_gen_freq.valueChanged.connect(self._on_gen_changed)
        l_int.addWidget(self._lbl_gen_freq)
        l_int.addWidget(self._sld_gen_freq)
        l_int.addWidget(self._lbl_gen_freq_val)

        self._lbl_imp_rate = QLabel("Rate Impulsi:")
        self._spn_imp_rate = QDoubleSpinBox()
        self._spn_imp_rate.setRange(0.5, 8.0)
        self._spn_imp_rate.setSingleStep(0.5)
        self._spn_imp_rate.setValue(2.0)
        self._spn_imp_rate.setSuffix(" Hz")
        self._spn_imp_rate.valueChanged.connect(self._on_gen_changed)
        l_int.addWidget(self._lbl_imp_rate)
        l_int.addWidget(self._spn_imp_rate)

        l_int.addWidget(QLabel("Livello:"))
        self._sld_gen_lvl = QSlider(Qt.Orientation.Horizontal)
        self._sld_gen_lvl.setRange(-48, 0)
        self._sld_gen_lvl.setValue(-12)
        self._sld_gen_lvl.setMaximumWidth(110)
        self._lbl_gen_lvl = QLabel("-12 dB")
        self._lbl_gen_lvl.setProperty("class", "mono-badge")
        self._sld_gen_lvl.valueChanged.connect(self._on_gen_changed)
        l_int.addWidget(self._sld_gen_lvl)
        l_int.addWidget(self._lbl_gen_lvl)
        l_int.addStretch()
        self._src_stack.addWidget(w_int)

        # 1: Audio File Player
        w_file = QWidget()
        l_file = QHBoxLayout(w_file)
        l_file.setContentsMargins(2, 2, 2, 2)
        l_file.setSpacing(8)
        btn_open = QPushButton("📂 Apri File Audio...")
        btn_open.clicked.connect(self._on_open_file_dialog)
        self._lbl_file_name = QLabel("Nessun file caricato (trascina qui WAV/AIFF/FLAC/MP3/M4A)")
        self._lbl_file_name.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._btn_file_play = QPushButton("▶")
        self._btn_file_play.setFixedWidth(34)
        self._btn_file_pause = QPushButton("⏸")
        self._btn_file_pause.setFixedWidth(34)
        self._btn_file_stop = QPushButton("⏹")
        self._btn_file_stop.setFixedWidth(34)
        self._chk_file_loop = QCheckBox("Loop")
        self._chk_file_loop.setChecked(True)

        self._btn_file_play.clicked.connect(self._on_file_play)
        self._btn_file_pause.clicked.connect(self.engine.file_pause)
        self._btn_file_stop.clicked.connect(self.engine.file_stop)
        self._chk_file_loop.toggled.connect(self.engine.set_file_loop)

        self._waveform_seek = WaveformSeekWidget()
        self._waveform_seek.setMinimumWidth(200)
        self._waveform_seek.seek_requested.connect(self.engine.file_seek)

        l_file.addWidget(btn_open)
        l_file.addWidget(self._lbl_file_name)
        l_file.addWidget(self._btn_file_play)
        l_file.addWidget(self._btn_file_pause)
        l_file.addWidget(self._btn_file_stop)
        l_file.addWidget(self._chk_file_loop)
        l_file.addWidget(self._waveform_seek, 1)
        self._src_stack.addWidget(w_file)

        # 2: Live Microphone
        w_mic = QWidget()
        l_mic = QHBoxLayout(w_mic)
        l_mic.setContentsMargins(2, 2, 2, 2)
        l_mic.setSpacing(10)
        l_mic.addWidget(QLabel("Ingresso Mic:"))
        self._cmb_mic_in = QComboBox()
        self._cmb_mic_in.setMinimumWidth(190)
        self._cmb_mic_in.currentIndexChanged.connect(self._on_mic_device_changed)
        l_mic.addWidget(self._cmb_mic_in)

        l_mic.addWidget(QLabel("Gain Mic:"))
        self._sld_mic_gain = QSlider(Qt.Orientation.Horizontal)
        self._sld_mic_gain.setRange(-24, 24)
        self._sld_mic_gain.setValue(0)
        self._sld_mic_gain.setMaximumWidth(120)
        self._lbl_mic_gain = QLabel("+0 dB")
        self._lbl_mic_gain.setProperty("class", "mono-badge")
        self._sld_mic_gain.valueChanged.connect(self._on_mic_gain_changed)
        l_mic.addWidget(self._sld_mic_gain)
        l_mic.addWidget(self._lbl_mic_gain)

        warn = QFrame()
        warn.setObjectName("FeedbackWarn")
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(8, 2, 8, 2)
        wlbl = QLabel("⚠ Usa le cuffie per evitare feedback (Larsen) con il microfono attivo")
        wlbl.setStyleSheet("color:#fbbf24; font-size:11.5px; border:none;")
        wl.addWidget(wlbl)
        l_mic.addWidget(warn, 1)
        self._src_stack.addWidget(w_mic)

        outer.addWidget(self._src_stack)
        self._update_gen_visibility()
        return card

    # ------------------------------------------------------------------
    # Tab 1: Singolo Filtro
    # ------------------------------------------------------------------
    def _build_single_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tipo Filtro:"))
        self._cmb_s_type = QComboBox()
        for lbl, val in FILTER_TYPE_ITEMS:
            self._cmb_s_type.addItem(lbl, val)
        self._cmb_s_type.currentIndexChanged.connect(self._on_single_ui_changed)
        row1.addWidget(self._cmb_s_type, 1)

        row1.addWidget(QLabel("Ordine / Pendenza:"))
        self._cmb_s_order = QComboBox()
        self._cmb_s_order.addItem("1° Ordine (6 dB/oct)", 1)
        self._cmb_s_order.addItem("2° Ordine Butterworth (12 dB/oct)", 2)
        self._cmb_s_order.addItem("4° Ordine (24 dB/oct)", 4)
        self._cmb_s_order.setCurrentIndex(1)
        self._cmb_s_order.currentIndexChanged.connect(self._on_single_ui_changed)
        row1.addWidget(self._cmb_s_order, 1)

        self._lbl_s_metrics = QLabel("Cutoff -3 dB: 1,000 Hz | 12 dB/oct")
        self._lbl_s_metrics.setProperty("class", "mono-badge")
        row1.addWidget(self._lbl_s_metrics)
        lay.addLayout(row1)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Frequency
        grid.addWidget(QLabel("Cutoff / Centro (Hz):"), 0, 0)
        self._sld_s_freq = QSlider(Qt.Orientation.Horizontal)
        self._sld_s_freq.setRange(0, 1000)
        self._sld_s_freq.setValue(_freq_to_slider(1000.0))
        self._spn_s_freq = QDoubleSpinBox()
        self._spn_s_freq.setRange(20.0, 20000.0)
        self._spn_s_freq.setDecimals(1)
        self._spn_s_freq.setValue(1000.0)
        self._spn_s_freq.setSuffix(" Hz")
        grid.addWidget(self._sld_s_freq, 0, 1)
        grid.addWidget(self._spn_s_freq, 0, 2)

        # Q
        grid.addWidget(QLabel("Quality Factor (Q):"), 1, 0)
        self._sld_s_q = QSlider(Qt.Orientation.Horizontal)
        self._sld_s_q.setRange(25, 2500)
        self._sld_s_q.setValue(71)
        self._spn_s_q = QDoubleSpinBox()
        self._spn_s_q.setRange(0.25, 25.0)
        self._spn_s_q.setSingleStep(0.1)
        self._spn_s_q.setDecimals(2)
        self._spn_s_q.setValue(0.71)
        grid.addWidget(self._sld_s_q, 1, 1)
        grid.addWidget(self._spn_s_q, 1, 2)

        # Gain dB (Shelving / Peak)
        grid.addWidget(QLabel("Gain (Shelving/Peak):"), 0, 3)
        self._sld_s_gain = QSlider(Qt.Orientation.Horizontal)
        self._sld_s_gain.setRange(-180, 180)
        self._sld_s_gain.setValue(0)
        self._spn_s_gain = QDoubleSpinBox()
        self._spn_s_gain.setRange(-18.0, 18.0)
        self._spn_s_gain.setDecimals(1)
        self._spn_s_gain.setSuffix(" dB")
        grid.addWidget(self._sld_s_gain, 0, 4)
        grid.addWidget(self._spn_s_gain, 0, 5)

        # Drive (Moog Ladder)
        grid.addWidget(QLabel("Drive (Moog Ladder):"), 1, 3)
        self._sld_s_drive = QSlider(Qt.Orientation.Horizontal)
        self._sld_s_drive.setRange(10, 40)
        self._sld_s_drive.setValue(10)
        self._spn_s_drive = QDoubleSpinBox()
        self._spn_s_drive.setRange(1.0, 4.0)
        self._spn_s_drive.setSingleStep(0.1)
        self._spn_s_drive.setDecimals(2)
        self._spn_s_drive.setValue(1.0)
        grid.addWidget(self._sld_s_drive, 1, 4)
        grid.addWidget(self._spn_s_drive, 1, 5)
        lay.addLayout(grid)

        # Quick Slide Presets
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Preset Slide:"))
        presets = [
            ("LP 1kHz (Slide 3)", {"filter_type": "lowpass", "freq": 1000.0, "q": 0.7071, "order": 2}),
            ("HP 1kHz (Slide 4)", {"filter_type": "highpass", "freq": 1000.0, "q": 0.7071, "order": 2}),
            ("BP 1.6k–2k (Slide 5)", {"filter_type": "bandpass", "freq": 1788.85, "q": 4.4721, "order": 2}),
            ("Notch 1.9k–2k (Slide 6)", {"filter_type": "bandreject", "freq": 1949.36, "q": 19.4936, "order": 2}),
            ("Res BP Q=6 (Slide 9)", {"filter_type": "resonant_bandpass", "freq": 1000.0, "q": 6.0, "order": 2}),
            ("Moog Ladder (Slide 1)", {"filter_type": "moog_ladder", "freq": 650.0, "q": 8.0, "order": 4, "drive": 1.8}),
        ]
        for label, cfg_dict in presets:
            b = QPushButton(label)
            b.clicked.connect(lambda _c=False, d=cfg_dict: self._apply_single_dict(d))
            prow.addWidget(b)
        prow.addStretch()
        lay.addLayout(prow)
        lay.addStretch()

        self._sld_s_freq.valueChanged.connect(self._on_single_slider_freq)
        self._spn_s_freq.valueChanged.connect(self._on_single_ui_changed)
        self._sld_s_q.valueChanged.connect(self._on_single_slider_q)
        self._spn_s_q.valueChanged.connect(self._on_single_ui_changed)
        self._sld_s_gain.valueChanged.connect(self._on_single_slider_gain)
        self._spn_s_gain.valueChanged.connect(self._on_single_ui_changed)
        self._sld_s_drive.valueChanged.connect(self._on_single_slider_drive)
        self._spn_s_drive.valueChanged.connect(self._on_single_ui_changed)

        self._sync_single_controls_enable()
        return w

    # ------------------------------------------------------------------
    # Tab 2: Serie, Parallelo & Banco
    # ------------------------------------------------------------------
    def _build_network_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(QLabel("Topologia:"))
        self._cmb_net_topo = QComboBox()
        self._cmb_net_topo.addItem("Serie — Channel Strip (Slide 10–11)", "series")
        self._cmb_net_topo.addItem("Parallelo — Sommatore + (Slide 11)", "parallel")
        self._cmb_net_topo.addItem("Banco Modulato — BP→LP→HP + Inviluppi (Slide 12)", "bank")
        self._cmb_net_topo.currentIndexChanged.connect(self._on_network_ui_changed)
        top.addWidget(self._cmb_net_topo, 1)

        b_s10 = QPushButton("Preset Slide 10 (2× BP Serie)")
        b_s11 = QPushButton("Preset Slide 11 (4× BP Paralleli)")
        b_s12 = QPushButton("Preset Slide 12 (Banco Modulato)")
        b_s10.clicked.connect(lambda: self._apply_network_preset("slide10"))
        b_s11.clicked.connect(lambda: self._apply_network_preset("slide11"))
        b_s12.clicked.connect(lambda: self._apply_network_preset("slide12"))
        top.addWidget(b_s10)
        top.addWidget(b_s11)
        top.addWidget(b_s12)
        lay.addLayout(top)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        self._stage_widgets: list[dict[str, Any]] = []
        for idx in range(4):
            grp = QGroupBox(f"Stadio {idx + 1}")
            gl = QGridLayout(grp)
            gl.setContentsMargins(6, 12, 6, 6)
            gl.setSpacing(4)

            chk = QCheckBox("Attivo")
            cmb = QComboBox()
            for lbl, val in STAGE_FILTER_ITEMS:
                cmb.addItem(lbl, val)
            spn_f = QDoubleSpinBox()
            spn_f.setRange(25.0, 18000.0)
            spn_f.setDecimals(0)
            spn_f.setSuffix(" Hz")
            spn_q = QDoubleSpinBox()
            spn_q.setRange(0.3, 20.0)
            spn_q.setDecimals(2)
            spn_q.setSingleStep(0.2)
            chk_env = QCheckBox("Inviluppo LFO")
            spn_rate = QDoubleSpinBox()
            spn_rate.setRange(0.05, 4.0)
            spn_rate.setDecimals(2)
            spn_rate.setSingleStep(0.05)
            spn_rate.setSuffix(" Hz")

            gl.addWidget(chk, 0, 0, 1, 2)
            gl.addWidget(cmb, 1, 0, 1, 2)
            gl.addWidget(QLabel("Freq:"), 2, 0)
            gl.addWidget(spn_f, 2, 1)
            gl.addWidget(QLabel("Q:"), 3, 0)
            gl.addWidget(spn_q, 3, 1)
            gl.addWidget(chk_env, 4, 0)
            gl.addWidget(spn_rate, 4, 1)

            for sig_widget in (chk, chk_env):
                sig_widget.toggled.connect(self._on_network_ui_changed)
            cmb.currentIndexChanged.connect(self._on_network_ui_changed)
            spn_f.valueChanged.connect(self._on_network_ui_changed)
            spn_q.valueChanged.connect(self._on_network_ui_changed)
            spn_rate.valueChanged.connect(self._on_network_ui_changed)

            self._stage_widgets.append(
                {
                    "chk": chk,
                    "cmb": cmb,
                    "freq": spn_f,
                    "q": spn_q,
                    "env": chk_env,
                    "rate": spn_rate,
                }
            )
            cards_row.addWidget(grp)

        lay.addLayout(cards_row)
        self._sync_network_to_ui()
        return w

    # ------------------------------------------------------------------
    # Tab 3: EQ Grafica (10 / 20 / 30 Bande ISO)
    # ------------------------------------------------------------------
    def _build_graphic_eq_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Risoluzione Bande (Slide 13):"))
        self._cmb_geq_bands = QComboBox()
        self._cmb_geq_bands.addItem("10 Bande (1 Ottava — Q=1.41)", 10)
        self._cmb_geq_bands.addItem("20 Bande (1/2 Ottava — Q=2.87)", 20)
        self._cmb_geq_bands.addItem("30 Bande ISO (1/3 Ottava — Q=4.32)", 30)
        self._cmb_geq_bands.currentIndexChanged.connect(self._on_geq_band_count_changed)
        bar.addWidget(self._cmb_geq_bands)

        btn_flat = QPushButton("Reset Flat (0 dB)")
        btn_smile = QPushButton("Smile / Loudness")
        btn_vocal = QPushButton("Vocal Presence")
        btn_demud = QPushButton("De-Mud")
        btn_phone = QPushButton("Telefono (Band-Limit)")
        btn_flat.clicked.connect(lambda: self._apply_geq_preset("flat"))
        btn_smile.clicked.connect(lambda: self._apply_geq_preset("smile"))
        btn_vocal.clicked.connect(lambda: self._apply_geq_preset("vocal"))
        btn_demud.clicked.connect(lambda: self._apply_geq_preset("demud"))
        btn_phone.clicked.connect(lambda: self._apply_geq_preset("phone"))

        bar.addWidget(btn_flat)
        bar.addWidget(btn_smile)
        bar.addWidget(btn_vocal)
        bar.addWidget(btn_demud)
        bar.addWidget(btn_phone)
        bar.addStretch()
        lay.addLayout(bar)

        self._geq_scroll = QScrollArea()
        self._geq_scroll.setWidgetResizable(True)
        self._geq_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._geq_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._geq_container = QWidget()
        self._geq_layout = QHBoxLayout(self._geq_container)
        self._geq_layout.setContentsMargins(4, 4, 4, 4)
        self._geq_layout.setSpacing(4)
        self._geq_scroll.setWidget(self._geq_container)
        lay.addWidget(self._geq_scroll, 1)

        self._geq_sliders: list[QSlider] = []
        self._geq_val_labels: list[QLabel] = []
        self._rebuild_geq_sliders()
        return w

    def _rebuild_geq_sliders(self) -> None:
        while self._geq_layout.count():
            item = self._geq_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._geq_sliders.clear()
        self._geq_val_labels.clear()

        freqs = self._geq_cfg.active_frequencies()
        for idx, fc in enumerate(freqs):
            col = QWidget()
            v = QVBoxLayout(col)
            v.setContentsMargins(2, 2, 2, 2)
            v.setSpacing(2)

            g_db = self._geq_cfg.gains_db[idx] if idx < len(self._geq_cfg.gains_db) else 0.0
            lbl_val = QLabel(f"{g_db:+.1f}")
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val.setStyleSheet("font-family:monospace; font-size:10px; color:#00d2ff;")

            sld = QSlider(Qt.Orientation.Vertical)
            sld.setRange(-120, 120)
            sld.setValue(int(round(g_db * 10.0)))
            sld.setMinimumHeight(105)
            exact_f = exact_third_octave_freq(float(fc))
            if self._geq_cfg.band_count == 30 and fc == 800:
                sld.setToolTip(
                    f"800 Hz (ISO Slide 13)\nFrequenza 1/3 ottava esatta: {exact_f:.2f} Hz → corretta a 800 Hz"
                )
            else:
                sld.setToolTip(f"{fc} Hz  |  1/3 ottava teorica: {exact_f:.1f} Hz")

            sld.valueChanged.connect(lambda val, i=idx: self._on_geq_slider_moved(i, val))

            f_text = f"{fc // 1000}k" if fc >= 1000 and fc % 1000 == 0 else (
                f"{fc / 1000:.1f}k" if fc >= 1000 else str(fc)
            )
            lbl_f = QLabel(f_text)
            lbl_f.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_f.setStyleSheet("font-family:monospace; font-size:10px; color:#94a3b8;")

            v.addWidget(lbl_val)
            v.addWidget(sld, 1, Qt.AlignmentFlag.AlignHCenter)
            v.addWidget(lbl_f)
            col.setMinimumWidth(34)
            self._geq_layout.addWidget(col)
            self._geq_sliders.append(sld)
            self._geq_val_labels.append(lbl_val)

    # ------------------------------------------------------------------
    # Tab 4: EQ Parametrica (6 Bande come Slide 15)
    # ------------------------------------------------------------------
    def _build_parametric_eq_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("6 Bande Parametriche (trascinabili anche sul grafico Bode):"))
        btn_s15 = QPushButton("Preset Slide 15")
        btn_flat = QPushButton("Reset Flat")
        btn_warm = QPushButton("Mastering Warmth")
        btn_s15.clicked.connect(lambda: self._apply_peq_preset("slide15"))
        btn_flat.clicked.connect(lambda: self._apply_peq_preset("flat"))
        btn_warm.clicked.connect(lambda: self._apply_peq_preset("warm"))
        bar.addWidget(btn_s15)
        bar.addWidget(btn_flat)
        bar.addWidget(btn_warm)
        bar.addStretch()
        lay.addLayout(bar)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._peq_widgets: list[dict[str, Any]] = []
        band_titles = ["B1 Low", "B2 Peak", "B3 Peak", "B4 Peak", "B5 Peak", "B6 High"]
        for idx in range(6):
            grp = QGroupBox(band_titles[idx])
            grp.setStyleSheet(
                f"QGroupBox::title {{ color:{BAND_COLORS[idx]}; font-weight:700; }}"
            )
            gl = QGridLayout(grp)
            gl.setContentsMargins(6, 12, 6, 6)
            gl.setSpacing(3)

            chk = QCheckBox("On")
            cmb = QComboBox()
            if idx == 0:
                cmb.addItem("LowShelf", "lowshelf")
                cmb.addItem("HighPass", "highpass")
            elif idx == 5:
                cmb.addItem("LowPass", "lowpass")
                cmb.addItem("HighShelf", "highshelf")
            else:
                cmb.addItem("Peak/Bell", "peak")
                cmb.addItem("Notch", "bandreject")

            spn_f = QDoubleSpinBox()
            spn_f.setRange(20.0, 20000.0)
            spn_f.setDecimals(0)
            spn_f.setSuffix(" Hz")

            spn_g = QDoubleSpinBox()
            spn_g.setRange(-18.0, 18.0)
            spn_g.setDecimals(1)
            spn_g.setSingleStep(0.5)
            spn_g.setSuffix(" dB")

            spn_q = QDoubleSpinBox()
            spn_q.setRange(0.25, 16.0)
            spn_q.setDecimals(2)
            spn_q.setSingleStep(0.1)

            gl.addWidget(chk, 0, 0)
            gl.addWidget(cmb, 0, 1)
            gl.addWidget(QLabel("Hz:"), 1, 0)
            gl.addWidget(spn_f, 1, 1)
            gl.addWidget(QLabel("dB:"), 2, 0)
            gl.addWidget(spn_g, 2, 1)
            gl.addWidget(QLabel("Q:"), 3, 0)
            gl.addWidget(spn_q, 3, 1)

            chk.toggled.connect(self._on_peq_ui_changed)
            cmb.currentIndexChanged.connect(self._on_peq_ui_changed)
            spn_f.valueChanged.connect(self._on_peq_ui_changed)
            spn_g.valueChanged.connect(self._on_peq_ui_changed)
            spn_q.valueChanged.connect(self._on_peq_ui_changed)

            self._peq_widgets.append(
                {"chk": chk, "cmb": cmb, "freq": spn_f, "gain": spn_g, "q": spn_q}
            )
            row.addWidget(grp)

        lay.addLayout(row)
        self._sync_peq_to_ui()
        return w

    # ------------------------------------------------------------------
    # Right Panel: Channel Strip & Mixer (Slides 16-18)
    # ------------------------------------------------------------------
    def _build_channel_strip_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(262)

        panel = QFrame()
        panel.setStyleSheet(
            "QFrame#StripRoot { background:#151822; border:1px solid #262c3d; border-radius:8px; }"
        )
        panel.setObjectName("StripRoot")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        title = QLabel("Channel Strip & Mixer")
        title.setStyleSheet("font-weight:800; font-size:14px; color:#00d2ff;")
        subtitle = QLabel("Mandate Aux, PFL, Fader & Pan (Slide 16–18)")
        subtitle.setStyleSheet("color:#94a3b8; font-size:11px;")
        lay.addWidget(title)
        lay.addWidget(subtitle)

        # Input Trim (Slide 17)
        trim_hdr = QHBoxLayout()
        trim_hdr.addWidget(QLabel("Input Trim:"))
        self._lbl_trim_val = QLabel("+0.0 dB")
        self._lbl_trim_val.setProperty("class", "mono-badge")
        trim_hdr.addStretch()
        trim_hdr.addWidget(self._lbl_trim_val)
        lay.addLayout(trim_hdr)
        self._sld_trim = QSlider(Qt.Orientation.Horizontal)
        self._sld_trim.setRange(-240, 120)
        self._sld_trim.setValue(0)
        self._sld_trim.valueChanged.connect(self._on_channel_ui_changed)
        lay.addWidget(self._sld_trim)

        # Aux Send (Slide 16)
        aux_box = QGroupBox("Mandata Aux (Slide 16)")
        al = QVBoxLayout(aux_box)
        al.setContentsMargins(8, 12, 8, 8)
        al.setSpacing(5)
        aux_top = QHBoxLayout()
        aux_top.addWidget(QLabel("Send:"))
        self._lbl_aux_val = QLabel("0%")
        self._lbl_aux_val.setProperty("class", "mono-badge")
        aux_top.addStretch()
        aux_top.addWidget(self._lbl_aux_val)
        al.addLayout(aux_top)

        self._sld_aux = QSlider(Qt.Orientation.Horizontal)
        self._sld_aux.setRange(0, 100)
        self._sld_aux.setValue(0)
        self._sld_aux.valueChanged.connect(self._on_channel_ui_changed)
        al.addWidget(self._sld_aux)

        mode_row = QHBoxLayout()
        self._btn_aux_pre = QPushButton("Pre-Fader")
        self._btn_aux_post = QPushButton("Post-Fader")
        self._btn_aux_pre.setCheckable(True)
        self._btn_aux_post.setCheckable(True)
        self._btn_aux_pre.setChecked(True)
        self._aux_grp = QButtonGroup(self)
        self._aux_grp.addButton(self._btn_aux_pre, 0)
        self._aux_grp.addButton(self._btn_aux_post, 1)
        self._aux_grp.idClicked.connect(self._on_channel_ui_changed)
        mode_row.addWidget(self._btn_aux_pre)
        mode_row.addWidget(self._btn_aux_post)
        al.addLayout(mode_row)

        self._chk_aux_fx = QCheckBox("Aux FX (Riverbero Test)")
        self._chk_aux_fx.setChecked(True)
        self._chk_aux_fx.toggled.connect(self._on_channel_ui_changed)
        al.addWidget(self._chk_aux_fx)

        self._aux_meter = AuxMeterBar()
        al.addWidget(self._aux_meter)
        lay.addWidget(aux_box)

        # Pan-Pot & Routing (Slide 18)
        pan_box = QGroupBox("Routing & Pan-Pot (Slide 18)")
        pl = QVBoxLayout(pan_box)
        pl.setContentsMargins(8, 12, 8, 8)
        pl.setSpacing(5)
        lbl_mono_stereo = QLabel("Mono ──▶ Pan-Pot ──▶ Stereo")
        lbl_mono_stereo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_mono_stereo.setStyleSheet("font-size:11px; color:#a855f7; font-weight:700;")
        pl.addWidget(lbl_mono_stereo)

        pan_r = QHBoxLayout()
        self._sld_pan = QSlider(Qt.Orientation.Horizontal)
        self._sld_pan.setRange(-100, 100)
        self._sld_pan.setValue(0)
        self._sld_pan.valueChanged.connect(self._on_channel_ui_changed)
        self._lbl_pan_val = QLabel("C")
        self._lbl_pan_val.setProperty("class", "mono-badge")
        btn_pan_c = QPushButton("C")
        btn_pan_c.setFixedWidth(26)
        btn_pan_c.clicked.connect(lambda: self._sld_pan.setValue(0))
        pan_r.addWidget(self._sld_pan, 1)
        pan_r.addWidget(self._lbl_pan_val)
        pan_r.addWidget(btn_pan_c)
        pl.addLayout(pan_r)

        self._cmb_routing = QComboBox()
        self._cmb_routing.addItems(["Master Stereo", "Subgroup 1-2", "Master + Sub 1-2"])
        pl.addWidget(self._cmb_routing)
        lay.addWidget(pan_box)

        # PFL / Mute
        pm_row = QHBoxLayout()
        self._btn_pfl = QPushButton("PFL (Solo)")
        self._btn_pfl.setObjectName("PflBtn")
        self._btn_pfl.setCheckable(True)
        self._btn_mute = QPushButton("MUTE")
        self._btn_mute.setObjectName("MuteBtn")
        self._btn_mute.setCheckable(True)
        self._btn_pfl.toggled.connect(self._on_channel_ui_changed)
        self._btn_mute.toggled.connect(self._on_channel_ui_changed)
        pm_row.addWidget(self._btn_pfl)
        pm_row.addWidget(self._btn_mute)
        lay.addLayout(pm_row)

        # Fader & Stereo Peak Meter (Slide 17)
        fader_box = QGroupBox("Volume Fader & VU Meter")
        fl = QHBoxLayout(fader_box)
        fl.setContentsMargins(8, 12, 8, 8)

        f_col = QVBoxLayout()
        self._lbl_fader_val = QLabel("0.0 dB\n(Nominale)")
        self._lbl_fader_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_fader_val.setStyleSheet("font-family:monospace; font-size:11px; color:#10b981; font-weight:700;")

        self._sld_fader = QSlider(Qt.Orientation.Vertical)
        self._sld_fader.setRange(-600, 100)  # -60.0 to +10.0 dB
        self._sld_fader.setValue(0)
        self._sld_fader.setMinimumHeight(145)
        self._sld_fader.valueChanged.connect(self._on_channel_ui_changed)

        btn_nom = QPushButton("0 dB Nom.")
        btn_nom.clicked.connect(lambda: self._sld_fader.setValue(0))
        f_col.addWidget(self._lbl_fader_val)
        f_col.addWidget(self._sld_fader, 1, Qt.AlignmentFlag.AlignHCenter)
        f_col.addWidget(btn_nom)

        self._stereo_meter = StereoMeterWidget()
        fl.addLayout(f_col, 1)
        fl.addWidget(self._stereo_meter)
        lay.addWidget(fader_box)

        self._chk_limiter = QCheckBox("Safety Limiter (-0.5 dBFS)")
        self._chk_limiter.setChecked(True)
        self._chk_limiter.toggled.connect(self._on_channel_ui_changed)
        lay.addWidget(self._chk_limiter)

        self._lbl_io_peaks = QLabel("In: -60.0 dB | Out: -60.0 dB")
        self._lbl_io_peaks.setStyleSheet("font-family:monospace; font-size:10.5px; color:#94a3b8;")
        lay.addWidget(self._lbl_io_peaks)

        lay.addStretch()
        scroll.setWidget(panel)
        return scroll

    # ------------------------------------------------------------------
    # Handlers & Synchronization
    # ------------------------------------------------------------------
    def refresh_audio_devices(self) -> None:
        info = list_audio_devices()
        self._syncing = True
        self._cmb_mic_in.clear()
        self._cmb_mic_in.addItem("Dispositivo Ingresso Predefinito", None)
        for dev in info["inputs"]:
            self._cmb_mic_in.addItem(f"{dev.name} ({dev.max_input_channels}ch)", dev.index)
        self._syncing = False

    def _on_source_btn_clicked(self, btn_id: int) -> None:
        btn = self._src_group.button(btn_id)
        if btn is None:
            return
        mode_str = str(btn.property("src_mode"))
        self._src_stack.setCurrentIndex(btn_id)
        self.engine.set_source_mode(mode_str)

    def _on_audio_power_clicked(self, checked: bool) -> None:
        if checked:
            ok = self.engine.start()
            if not ok:
                self._btn_audio_power.setChecked(False)
                self._btn_audio_power.setText("▶ Avvia Audio")
                QMessageBox.warning(self, "Errore Audio", self.engine.last_error or "Stream audio non disponibile.")
            else:
                self._btn_audio_power.setText("⏹ Ferma Audio")
        else:
            self.engine.stop()
            self._btn_audio_power.setText("▶ Avvia Audio")
        if self.audio_state_changed:
            self.audio_state_changed()

    def _on_bypass_toggled(self, checked: bool) -> None:
        self._ch_cfg.bypass = bool(checked)
        self.engine.processor.update_channel_strip(self._ch_cfg)

    def _on_graph_toggles(self) -> None:
        self.bode_widget.show_fft = self._chk_fft.isChecked()
        self.bode_widget.show_phase = self._chk_phase.isChecked()
        self.bode_widget.show_ideal = self._chk_ideal.isChecked()
        self._refresh_visual_curves()

    def _update_gen_visibility(self) -> None:
        g = str(self._cmb_gen.currentData() or "white_noise")
        has_freq = g in ("sine", "sawtooth", "square", "synth_chord")
        is_imp = g == "impulse"
        self._lbl_gen_freq.setVisible(has_freq)
        self._sld_gen_freq.setVisible(has_freq)
        self._lbl_gen_freq_val.setVisible(has_freq)
        self._lbl_imp_rate.setVisible(is_imp)
        self._spn_imp_rate.setVisible(is_imp)

    def _on_gen_changed(self) -> None:
        if self._syncing:
            return
        g = str(self._cmb_gen.currentData() or "white_noise")
        freq = _slider_to_freq(self._sld_gen_freq.value())
        rate = float(self._spn_imp_rate.value())
        lvl = float(self._sld_gen_lvl.value())
        self._lbl_gen_freq_val.setText(f"{freq:,.0f} Hz")
        self._lbl_gen_lvl.setText(f"{lvl:.0f} dB")
        self._update_gen_visibility()
        self.engine.generator.set_params(gen_type=g, freq_hz=freq, impulse_rate_hz=rate, level_db=lvl)

    def _on_open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona File Audio",
            "",
            "File Audio (*.wav *.aif *.aiff *.flac *.ogg *.mp3 *.m4a *.aac *.caf);;Tutti i file (*)",
        )
        if path:
            self.load_audio_file_path(path)

    def load_audio_file_path(self, path: str) -> None:
        try:
            loaded = self.engine.load_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Errore Caricamento File", str(exc))
            return

        self._btn_src_file.setChecked(True)
        self._src_stack.setCurrentIndex(1)
        self.engine.set_source_mode(SourceMode.FILE)
        self._lbl_file_name.setText(
            f"{loaded.filename} ({loaded.orig_sample_rate} Hz, {loaded.duration_s:.1f}s)"
        )
        self._waveform_seek.set_waveform(loaded.waveform_peaks)
        self._waveform_seek.set_position(0.0)
        if not self.engine.is_running:
            self._btn_audio_power.setChecked(True)
            self._on_audio_power_clicked(True)

    def _on_file_play(self) -> None:
        self.engine.file_play()
        if not self.engine.is_running:
            self._btn_audio_power.setChecked(True)
            self._on_audio_power_clicked(True)

    def _on_mic_device_changed(self) -> None:
        if self._syncing:
            return
        dev_id = self._cmb_mic_in.currentData()
        self.engine.set_devices(dev_id, self.engine.output_device)

    def _on_mic_gain_changed(self, val: int) -> None:
        self._lbl_mic_gain.setText(f"{val:+d} dB")
        self.engine.set_mic_gain_db(float(val))

    def _on_workbench_tab_changed(self, idx: int) -> None:
        modes = ("single", "network", "graphic_eq", "parametric_eq")
        mode = modes[idx] if 0 <= idx < len(modes) else "single"
        self.engine.processor.set_mode(mode)
        if mode in ("graphic_eq", "parametric_eq"):
            self.bode_widget.set_y_range(-24.0, 24.0)
        else:
            self.bode_widget.set_y_range(-48.0, 24.0)
        self._refresh_visual_curves()

    # --- Single filter handlers ---
    def _sync_single_controls_enable(self) -> None:
        ft = self._single_cfg.filter_type
        has_gain = ft in ("lowshelf", "highshelf", "peak")
        is_moog = ft == "moog_ladder"
        has_order = ft in ("lowpass", "highpass", "bandpass", "bandreject")
        self._sld_s_gain.setEnabled(has_gain)
        self._spn_s_gain.setEnabled(has_gain)
        self._sld_s_drive.setEnabled(is_moog)
        self._spn_s_drive.setEnabled(is_moog)
        self._cmb_s_order.setEnabled(has_order)
        if not has_order and not is_moog:
            # Show 2nd order when relevant
            pass

    def _on_single_slider_freq(self, val: int) -> None:
        if self._syncing:
            return
        f = _slider_to_freq(val)
        self._syncing = True
        self._spn_s_freq.setValue(f)
        self._syncing = False
        self._on_single_ui_changed()

    def _on_single_slider_q(self, val: int) -> None:
        if self._syncing:
            return
        q = val / 100.0
        self._syncing = True
        self._spn_s_q.setValue(q)
        self._syncing = False
        self._on_single_ui_changed()

    def _on_single_slider_gain(self, val: int) -> None:
        if self._syncing:
            return
        g = val / 10.0
        self._syncing = True
        self._spn_s_gain.setValue(g)
        self._syncing = False
        self._on_single_ui_changed()

    def _on_single_slider_drive(self, val: int) -> None:
        if self._syncing:
            return
        d = val / 10.0
        self._syncing = True
        self._spn_s_drive.setValue(d)
        self._syncing = False
        self._on_single_ui_changed()

    def _on_single_ui_changed(self) -> None:
        if self._syncing:
            return
        ft = str(self._cmb_s_type.currentData() or "lowpass")
        ord_val = int(self._cmb_s_order.currentData() or 2)
        if ft == "moog_ladder":
            ord_val = 4
        elif ft in ("bandpass", "bandreject") and ord_val == 1:
            ord_val = 2

        self._single_cfg = SingleFilterConfig(
            filter_type=ft,
            freq=float(self._spn_s_freq.value()),
            q=float(self._spn_s_q.value()),
            gain_db=float(self._spn_s_gain.value()),
            order=ord_val,
            drive=float(self._spn_s_drive.value()),
        )
        self._syncing = True
        self._sld_s_freq.setValue(_freq_to_slider(self._single_cfg.freq))
        self._sld_s_q.setValue(int(round(self._single_cfg.q * 100)))
        self._sld_s_gain.setValue(int(round(self._single_cfg.gain_db * 10)))
        self._sld_s_drive.setValue(int(round(self._single_cfg.drive * 10)))
        self._syncing = False

        self._sync_single_controls_enable()
        self._update_single_metrics_label()
        self.engine.processor.update_single(self._single_cfg)
        self._refresh_visual_curves()

    def _update_single_metrics_label(self) -> None:
        c = self._single_cfg
        if c.filter_type in ("bandpass", "resonant_bandpass", "bandreject"):
            m = compute_band_metrics(c.freq, c.q)
            self._lbl_s_metrics.setText(
                f"fc={m['fc']:.0f} Hz | fL={m['f_low']:.0f} | fH={m['f_high']:.0f} | BW={m['bw']:.0f} Hz"
            )
        elif c.filter_type in ("lowpass", "highpass", "moog_ladder"):
            slope = 24 if (c.order == 4 or c.filter_type == "moog_ladder") else (6 if c.order == 1 else 12)
            self._lbl_s_metrics.setText(f"Cutoff -3 dB: {c.freq:,.0f} Hz | Roll-off: {slope} dB/oct")
        else:
            self._lbl_s_metrics.setText(f"fc={c.freq:,.0f} Hz | Gain={c.gain_db:+.1f} dB | Q={c.q:.2f}")

    def _apply_single_dict(self, params: dict[str, Any]) -> None:
        self._syncing = True
        ft = str(params.get("filter_type", "lowpass"))
        for i in range(self._cmb_s_type.count()):
            if self._cmb_s_type.itemData(i) == ft:
                self._cmb_s_type.setCurrentIndex(i)
                break
        ord_val = int(params.get("order", 2))
        for i in range(self._cmb_s_order.count()):
            if self._cmb_s_order.itemData(i) == ord_val:
                self._cmb_s_order.setCurrentIndex(i)
                break
        self._spn_s_freq.setValue(float(params.get("freq", 1000.0)))
        self._spn_s_q.setValue(float(params.get("q", 0.7071)))
        self._spn_s_gain.setValue(float(params.get("gain_db", 0.0)))
        self._spn_s_drive.setValue(float(params.get("drive", 1.0)))
        self._syncing = False
        self._on_single_ui_changed()

    # --- Network handlers ---
    def _sync_network_to_ui(self) -> None:
        self._syncing = True
        for i in range(self._cmb_net_topo.count()):
            if self._cmb_net_topo.itemData(i) == self._net_cfg.topology:
                self._cmb_net_topo.setCurrentIndex(i)
                break
        for st, w in zip(self._net_cfg.stages, self._stage_widgets):
            w["chk"].setChecked(st.enabled)
            for j in range(w["cmb"].count()):
                if w["cmb"].itemData(j) == st.filter_type:
                    w["cmb"].setCurrentIndex(j)
                    break
            w["freq"].setValue(st.freq)
            w["q"].setValue(st.q)
            w["env"].setChecked(st.env_enabled)
            w["rate"].setValue(st.env_rate_hz)
            is_bank = self._net_cfg.topology == "bank"
            w["env"].setEnabled(is_bank)
            w["rate"].setEnabled(is_bank)
        self._syncing = False

    def _on_network_ui_changed(self) -> None:
        if self._syncing:
            return
        topo = str(self._cmb_net_topo.currentData() or "series")
        stages: list[StageConfig] = []
        for idx, w in enumerate(self._stage_widgets):
            old = self._net_cfg.stages[idx]
            is_bank = topo == "bank"
            w["env"].setEnabled(is_bank)
            w["rate"].setEnabled(is_bank)
            stages.append(
                StageConfig(
                    enabled=w["chk"].isChecked(),
                    filter_type=str(w["cmb"].currentData() or "bandpass"),
                    freq=float(w["freq"].value()),
                    q=float(w["q"].value()),
                    gain_db=0.0,
                    order=2,
                    env_enabled=w["env"].isChecked(),
                    env_rate_hz=float(w["rate"].value()),
                    env_depth_oct=old.env_depth_oct,
                )
            )
        self._net_cfg = NetworkConfig(topology=topo, stages=stages)
        self.engine.processor.update_network(self._net_cfg)
        self._refresh_visual_curves()

    def _apply_network_preset(self, preset_name: str) -> None:
        if preset_name == "slide10":
            self._net_cfg = NetworkConfig(
                topology="series",
                stages=[
                    StageConfig(True, "bandpass", 1000.0, 2.0),
                    StageConfig(True, "bandpass", 1400.0, 2.0),
                    StageConfig(False, "lowpass", 4000.0, 0.7071),
                    StageConfig(False, "highpass", 120.0, 0.7071),
                ],
            )
        elif preset_name == "slide11":
            self._net_cfg = NetworkConfig(
                topology="parallel",
                stages=[
                    StageConfig(True, "bandpass", 40.0, 10.0),
                    StageConfig(True, "bandpass", 80.0, 10.0),
                    StageConfig(True, "bandpass", 120.0, 10.0),
                    StageConfig(True, "bandpass", 160.0, 10.0),
                ],
            )
        elif preset_name == "slide12":
            self._net_cfg = NetworkConfig(
                topology="bank",
                stages=[
                    StageConfig(True, "bandpass", 320.0, 5.5, 0.0, 2, True, 0.28, 0.9),
                    StageConfig(True, "bandpass", 750.0, 6.0, 0.0, 2, True, 0.45, 1.1),
                    StageConfig(True, "bandpass", 1600.0, 6.5, 0.0, 2, True, 0.19, 0.8),
                    StageConfig(True, "bandpass", 3400.0, 7.0, 0.0, 2, True, 0.36, 1.0),
                ],
            )
        self._sync_network_to_ui()
        self.engine.processor.update_network(self._net_cfg)
        self._refresh_visual_curves()

    # --- Graphic EQ handlers ---
    def _on_geq_band_count_changed(self) -> None:
        if self._syncing:
            return
        count = int(self._cmb_geq_bands.currentData() or 10)
        self._geq_cfg.band_count = count
        self._geq_cfg.gains_db = [0.0] * 30
        self._rebuild_geq_sliders()
        self.engine.processor.update_graphic_eq(self._geq_cfg)
        self._refresh_visual_curves()

    def _on_geq_slider_moved(self, band_idx: int, raw_val: int) -> None:
        if self._syncing:
            return
        g_db = raw_val / 10.0
        self._geq_cfg.gains_db[band_idx] = g_db
        if band_idx < len(self._geq_val_labels):
            self._geq_val_labels[band_idx].setText(f"{g_db:+.1f}")
        self.engine.processor.update_graphic_eq(self._geq_cfg)
        self._refresh_visual_curves()

    def _apply_geq_preset(self, name: str) -> None:
        freqs = self._geq_cfg.active_frequencies()
        gains = [0.0] * 30
        for i, f in enumerate(freqs):
            if name == "smile":
                if f <= 100:
                    gains[i] = 5.0
                elif 400 <= f <= 1200:
                    gains[i] = -3.5
                elif f >= 6000:
                    gains[i] = 5.5
            elif name == "vocal":
                if f <= 80:
                    gains[i] = -8.0
                elif 200 <= f <= 400:
                    gains[i] = -3.0
                elif 2000 <= f <= 5000:
                    gains[i] = 4.5
            elif name == "demud":
                if 160 <= f <= 450:
                    gains[i] = -6.0
            elif name == "phone":
                if f < 300 or f > 3400:
                    gains[i] = -12.0
                elif 800 <= f <= 2000:
                    gains[i] = 4.0
        self._geq_cfg.gains_db = gains
        self._syncing = True
        for i, sld in enumerate(self._geq_sliders):
            sld.setValue(int(round(gains[i] * 10)))
            self._geq_val_labels[i].setText(f"{gains[i]:+.1f}")
        self._syncing = False
        self.engine.processor.update_graphic_eq(self._geq_cfg)
        self._refresh_visual_curves()

    # --- Parametric EQ handlers ---
    def _sync_peq_to_ui(self) -> None:
        self._syncing = True
        for b, w in zip(self._peq_cfg.bands, self._peq_widgets):
            w["chk"].setChecked(b.enabled)
            for j in range(w["cmb"].count()):
                if w["cmb"].itemData(j) == b.filter_type:
                    w["cmb"].setCurrentIndex(j)
                    break
            w["freq"].setValue(b.freq)
            w["gain"].setValue(b.gain_db)
            w["q"].setValue(b.q)
            has_gain = b.filter_type not in ("lowpass", "highpass")
            w["gain"].setEnabled(has_gain)
        self._syncing = False

    def _on_peq_ui_changed(self) -> None:
        if self._syncing:
            return
        bands: list[ParametricBandConfig] = []
        for w in self._peq_widgets:
            ft = str(w["cmb"].currentData() or "peak")
            w["gain"].setEnabled(ft not in ("lowpass", "highpass"))
            bands.append(
                ParametricBandConfig(
                    enabled=w["chk"].isChecked(),
                    filter_type=ft,
                    freq=float(w["freq"].value()),
                    gain_db=float(w["gain"].value()),
                    q=float(w["q"].value()),
                    order=2,
                )
            )
        self._peq_cfg = ParametricEQConfig(bands=bands)
        self.engine.processor.update_parametric_eq(self._peq_cfg)
        self._refresh_visual_curves()

    def _apply_peq_preset(self, name: str) -> None:
        if name == "slide15":
            self._peq_cfg = ParametricEQConfig(
                bands=[
                    ParametricBandConfig(True, "lowshelf", 95.0, 3.0, 0.75, 2),
                    ParametricBandConfig(True, "peak", 250.0, 5.5, 2.2, 2),
                    ParametricBandConfig(True, "peak", 900.0, 9.5, 2.8, 2),
                    ParametricBandConfig(True, "peak", 1600.0, 4.0, 5.0, 2),
                    ParametricBandConfig(True, "peak", 6800.0, 3.5, 2.6, 2),
                    ParametricBandConfig(True, "lowpass", 13000.0, 0.0, 0.7071, 2),
                ]
            )
        elif name == "warm":
            self._peq_cfg = ParametricEQConfig(
                bands=[
                    ParametricBandConfig(True, "lowshelf", 110.0, 3.5, 0.70, 2),
                    ParametricBandConfig(True, "peak", 320.0, -2.5, 1.5, 2),
                    ParametricBandConfig(True, "peak", 1200.0, 0.0, 1.4, 2),
                    ParametricBandConfig(True, "peak", 3800.0, 2.5, 1.8, 2),
                    ParametricBandConfig(True, "peak", 9500.0, 3.0, 0.9, 2),
                    ParametricBandConfig(True, "lowpass", 17500.0, 0.0, 0.7071, 2),
                ]
            )
        else:
            self._peq_cfg = ParametricEQConfig(bands=default_parametric_bands())
        self._sync_peq_to_ui()
        self.engine.processor.update_parametric_eq(self._peq_cfg)
        self._refresh_visual_curves()

    # --- Bode Node Dragging Handler ---
    def _on_bode_node_changed(self, node_id: int, new_freq: float, new_gain: float, new_q: float) -> None:
        mode = self.engine.processor.mode
        if mode == "single":
            self._syncing = True
            self._spn_s_freq.setValue(new_freq)
            if self._single_cfg.filter_type in ("lowshelf", "highshelf", "peak"):
                self._spn_s_gain.setValue(new_gain)
            else:
                self._spn_s_q.setValue(new_q)
            self._syncing = False
            self._on_single_ui_changed()
        elif mode == "network" and 0 <= node_id < len(self._stage_widgets):
            w = self._stage_widgets[node_id]
            self._syncing = True
            w["freq"].setValue(new_freq)
            w["q"].setValue(new_q)
            self._syncing = False
            self._on_network_ui_changed()
        elif mode == "parametric_eq" and 0 <= node_id < len(self._peq_widgets):
            w = self._peq_widgets[node_id]
            self._syncing = True
            w["freq"].setValue(new_freq)
            if self._peq_cfg.bands[node_id].filter_type not in ("lowpass", "highpass"):
                w["gain"].setValue(new_gain)
            w["q"].setValue(new_q)
            self._syncing = False
            self._on_peq_ui_changed()

    # --- Channel Strip Handler ---
    def _on_channel_ui_changed(self) -> None:
        if self._syncing:
            return
        trim_db = self._sld_trim.value() / 10.0
        aux_send = self._sld_aux.value() / 100.0
        aux_pre = self._btn_aux_pre.isChecked()
        aux_fx = self._chk_aux_fx.isChecked()
        pan = self._sld_pan.value() / 100.0
        fader_db = self._sld_fader.value() / 10.0
        pfl = self._btn_pfl.isChecked()
        mute = self._btn_mute.isChecked()
        limiter = self._chk_limiter.isChecked()

        self._lbl_trim_val.setText(f"{trim_db:+.1f} dB")
        self._lbl_aux_val.setText(f"{int(round(aux_send * 100))}%")
        if abs(pan) < 0.03:
            self._lbl_pan_val.setText("C")
        elif pan < 0:
            self._lbl_pan_val.setText(f"{int(abs(pan) * 100)}L")
        else:
            self._lbl_pan_val.setText(f"{int(pan * 100)}R")

        if fader_db <= -59.5:
            self._lbl_fader_val.setText("-∞ dB\n(Chiuso)")
        elif abs(fader_db) < 0.25:
            self._lbl_fader_val.setText("0.0 dB\n(Nominale)")
        else:
            self._lbl_fader_val.setText(f"{fader_db:+.1f} dB")

        self._ch_cfg = ChannelStripConfig(
            input_trim_db=trim_db,
            bypass=self._btn_bypass_top.isChecked(),
            aux_send=aux_send,
            aux_pre_fader=aux_pre,
            aux_fx_enabled=aux_fx,
            pfl_solo=pfl,
            mute=mute,
            pan=pan,
            fader_db=fader_db,
            safety_limiter=limiter,
        )
        self.engine.processor.update_channel_strip(self._ch_cfg)

    def _apply_all_configs_to_dsp(self) -> None:
        self.engine.processor.update_single(self._single_cfg)
        self.engine.processor.update_network(self._net_cfg)
        self.engine.processor.update_graphic_eq(self._geq_cfg)
        self.engine.processor.update_parametric_eq(self._peq_cfg)
        self.engine.processor.update_channel_strip(self._ch_cfg)

    # ------------------------------------------------------------------
    # Refresh Bode Curve, Ideal Curve, Nodes, and Impulse Response
    # ------------------------------------------------------------------
    def _refresh_visual_curves(self) -> None:
        fs = float(self.engine.sample_rate)
        freqs = self._bode_freqs
        mode = self.engine.processor.mode

        indiv: list[np.ndarray] = []
        ideal_db: np.ndarray | None = None
        ideal_fc: float | None = None
        nodes: list[BodeNode] = []

        if mode == "single":
            c = self._single_cfg
            sos = design_filter(c.filter_type, c.freq, fs, c.q, c.gain_db, c.order, c.drive)
            mag_db, phase_deg, _ = compute_sos_response(sos, freqs, fs)
            if c.filter_type in ("lowpass", "highpass", "bandpass", "resonant_bandpass", "bandreject", "moog_ladder"):
                ideal_db = compute_ideal_response(c.filter_type, c.freq, c.q, freqs)
                ideal_fc = c.freq
            supports_gain = c.filter_type in ("lowshelf", "highshelf", "peak")
            resp_at_f = float(np.interp(c.freq, freqs, mag_db))
            nodes = [
                BodeNode(
                    node_id=0,
                    freq=c.freq,
                    gain_db=c.gain_db if supports_gain else resp_at_f,
                    q=c.q,
                    color="#00e5ff",
                    label=c.filter_type.upper(),
                    supports_gain=supports_gain,
                    supports_q=True,
                    response_db=resp_at_f,
                )
            ]
            imp_cfg: Any = c

        elif mode == "network":
            active = [(i, st) for i, st in enumerate(self._net_cfg.stages) if st.enabled]
            sos_list = []
            for _, st in active:
                if self._net_cfg.topology == "bank":
                    s_bp = design_filter("bandpass", st.freq, fs, st.q, 0.0, 2)
                    s_lp = design_filter("lowpass", min(19500.0, st.freq * 2.5), fs, 0.7071, 0.0, 2)
                    s_hp = design_filter("highpass", max(25.0, st.freq * 0.4), fs, 0.7071, 0.0, 2)
                    sos_list.append(np.vstack([s_bp, s_lp, s_hp]))
                else:
                    sos_list.append(design_filter(st.filter_type, st.freq, fs, st.q, st.gain_db, st.order))
            if not sos_list:
                mag_db = np.zeros_like(freqs)
                phase_deg = np.zeros_like(freqs)
            elif self._net_cfg.topology == "series":
                mag_db, phase_deg, indiv = compute_series_response(sos_list, freqs, fs)
            else:
                gains = [1.0 / len(sos_list)] * len(sos_list)
                mag_db, phase_deg, indiv = compute_parallel_response(sos_list, gains, freqs, fs)

            for i, st in active:
                resp_f = float(np.interp(st.freq, freqs, mag_db))
                nodes.append(
                    BodeNode(
                        node_id=i,
                        freq=st.freq,
                        gain_db=resp_f,
                        q=st.q,
                        color=BAND_COLORS[i % len(BAND_COLORS)],
                        label=f"S{i+1}",
                        supports_gain=False,
                        supports_q=True,
                        response_db=resp_f,
                    )
                )
            imp_cfg = self._net_cfg

        elif mode == "graphic_eq":
            g_freqs = self._geq_cfg.active_frequencies()
            q_val = self._geq_cfg.active_q()
            sos_list = [
                design_filter("peak", float(fc), fs, q_val, float(self._geq_cfg.gains_db[i]))
                for i, fc in enumerate(g_freqs)
                if abs(self._geq_cfg.gains_db[i]) >= 0.02
            ]
            if sos_list:
                mag_db, phase_deg, _ = compute_series_response(sos_list, freqs, fs)
            else:
                mag_db = np.zeros_like(freqs)
                phase_deg = np.zeros_like(freqs)
            imp_cfg = self._geq_cfg

        else:  # parametric_eq
            active_bands = [(i, b) for i, b in enumerate(self._peq_cfg.bands) if b.enabled]
            sos_list = [
                design_filter(b.filter_type, b.freq, fs, b.q, b.gain_db, b.order)
                for _, b in active_bands
            ]
            if sos_list:
                mag_db, phase_deg, indiv = compute_series_response(sos_list, freqs, fs)
            else:
                mag_db = np.zeros_like(freqs)
                phase_deg = np.zeros_like(freqs)
            for i, b in active_bands:
                supports_g = b.filter_type not in ("lowpass", "highpass")
                resp_f = float(np.interp(b.freq, freqs, mag_db))
                nodes.append(
                    BodeNode(
                        node_id=i,
                        freq=b.freq,
                        gain_db=b.gain_db if supports_g else resp_f,
                        q=b.q,
                        color=BAND_COLORS[i % len(BAND_COLORS)],
                        label=f"B{i+1}",
                        supports_gain=supports_g,
                        supports_q=True,
                        response_db=resp_f,
                    )
                )
            imp_cfg = self._peq_cfg

        self.bode_widget.set_responses(freqs, mag_db, phase_deg, indiv, ideal_db, ideal_fc)
        self.bode_widget.set_nodes(nodes)

        imp = compute_impulse_response(mode, imp_cfg, fs, n_samples=2048)
        self.time_widget.set_impulse(imp["times_ms"], imp["impulse"], imp["ringing_ms"])

    # ------------------------------------------------------------------
    # Experiment Preset Application (from Didactics)
    # ------------------------------------------------------------------
    def apply_experiment_preset(self, preset: ExperimentPreset) -> None:
        # 1. Configure Internal Generator
        self._btn_src_int.setChecked(True)
        self._src_stack.setCurrentIndex(0)
        self.engine.set_source_mode(SourceMode.INTERNAL)

        self._syncing = True
        for i in range(self._cmb_gen.count()):
            if self._cmb_gen.itemData(i) == preset.generator_type:
                self._cmb_gen.setCurrentIndex(i)
                break
        self._sld_gen_freq.setValue(_freq_to_slider(preset.generator_freq))
        self._spn_imp_rate.setValue(preset.impulse_rate_hz)
        self._syncing = False
        self._on_gen_changed()

        # 2. Configure Workbench Mode & Parameters
        self.engine.processor.set_mode(preset.workbench_mode)
        if preset.workbench_mode in ("graphic_eq", "parametric_eq"):
            self.bode_widget.set_y_range(-24.0, 24.0)
        else:
            self.bode_widget.set_y_range(-48.0, 24.0)

        if preset.workbench_mode == "single":
            self.workbench_tabs.setCurrentIndex(0)
            self._apply_single_dict(preset.single_params)
        elif preset.workbench_mode == "network":
            self.workbench_tabs.setCurrentIndex(1)
            np_cfg = preset.network_params
            stages = []
            for st_d in np_cfg.get("stages", []):
                stages.append(
                    StageConfig(
                        enabled=bool(st_d.get("enabled", True)),
                        filter_type=str(st_d.get("filter_type", "bandpass")),
                        freq=float(st_d.get("freq", 1000.0)),
                        q=float(st_d.get("q", 2.0)),
                        gain_db=float(st_d.get("gain_db", 0.0)),
                        order=int(st_d.get("order", 2)),
                        env_enabled=bool(st_d.get("env_enabled", False)),
                        env_rate_hz=float(st_d.get("env_rate_hz", 0.5)),
                        env_depth_oct=float(st_d.get("env_depth_oct", 1.0)),
                    )
                )
            while len(stages) < 4:
                stages.append(StageConfig(enabled=False))
            self._net_cfg = NetworkConfig(
                topology=str(np_cfg.get("topology", "series")),
                stages=stages[:4],
            )
            self._sync_network_to_ui()
            self.engine.processor.update_network(self._net_cfg)
        elif preset.workbench_mode == "graphic_eq":
            self.workbench_tabs.setCurrentIndex(2)
            gp = preset.graphic_params
            count = int(gp.get("band_count", 30))
            for i in range(self._cmb_geq_bands.count()):
                if self._cmb_geq_bands.itemData(i) == count:
                    self._cmb_geq_bands.setCurrentIndex(i)
                    break
            self._geq_cfg.band_count = count
            self._rebuild_geq_sliders()
            self._apply_geq_preset(str(gp.get("preset", "smile")))
        elif preset.workbench_mode == "parametric_eq":
            self.workbench_tabs.setCurrentIndex(3)
            self._apply_peq_preset(str(preset.parametric_params.get("preset", "slide15")))

        # 3. Apply Channel Strip overrides (e.g. Module 10 Aux Pre/Post)
        cp = preset.channel_params
        self._syncing = True
        self._sld_aux.setValue(int(round(float(cp.get("aux_send", 0.0)) * 100)))
        if cp.get("aux_pre_fader", True):
            self._btn_aux_pre.setChecked(True)
        else:
            self._btn_aux_post.setChecked(True)
        self._chk_aux_fx.setChecked(bool(cp.get("aux_fx_enabled", True)))
        self._sld_fader.setValue(int(round(float(cp.get("fader_db", 0.0)) * 10)))
        self._sld_pan.setValue(int(round(float(cp.get("pan", 0.0)) * 100)))
        self._btn_mute.setChecked(bool(cp.get("mute", False)))
        self._btn_pfl.setChecked(bool(cp.get("pfl_solo", False)))
        self._syncing = False
        self._on_channel_ui_changed()

        # 4. Graph & Time Domain view toggles
        self._chk_ideal.setChecked(bool(preset.show_ideal))
        self.time_widget.set_view_mode(preset.time_view)

        # 5. Guide banner
        self._lbl_guide.setText(f"<b>{preset.label}:</b> {preset.what_to_observe}")
        self._guide_banner.setVisible(True)
        self._refresh_visual_curves()

        # 6. Auto-start audio safely if not already running (only Internal source)
        if not self.engine.is_running and self.engine.source_mode == SourceMode.INTERNAL:
            ok = self.engine.start()
            if ok:
                self._btn_audio_power.setChecked(True)
                self._btn_audio_power.setText("⏹ Ferma Audio")
                if self.audio_state_changed:
                    self.audio_state_changed()

    # ------------------------------------------------------------------
    # Live UI Tick (30 ms)
    # ------------------------------------------------------------------
    def _on_tick(self) -> None:
        snap = self.engine.get_visual_snapshot()
        self._stereo_meter.update_levels(
            snap["out_peak_l_db"], snap["out_peak_r_db"], snap["overload"]
        )
        self._aux_meter.set_level_db(snap["aux_peak_db"])
        self._lbl_io_peaks.setText(
            f"In: {snap['in_peak_db']:+.1f} dB | Out: {max(snap['out_peak_l_db'], snap['out_peak_r_db']):+.1f} dB"
        )

        if self.engine.source_mode == SourceMode.FILE:
            self._waveform_seek.set_position(snap["file_pos_ratio"])

        if snap["running"]:
            self.bode_widget.update_fft(
                snap["pre_samples"], snap["post_samples"], snap["sample_rate"]
            )
            self.time_widget.update_live_waves(
                snap["pre_samples"], snap["post_samples"], snap["sample_rate"]
            )
            # In modulated bank mode, refresh Bode curve smoothly to show LFO filter movement
            if self.engine.processor.mode == "network" and self._net_cfg.topology == "bank":
                info = self.engine.processor.get_active_bode_sos()
                mag_db, phase_deg, indiv = compute_parallel_response(
                    info["sos_list"], info.get("gains"), self._bode_freqs, snap["sample_rate"]
                )
                self.bode_widget.set_responses(self._bode_freqs, mag_db, phase_deg, indiv)
        elif self._btn_audio_power.isChecked():
            self._btn_audio_power.setChecked(False)
            self._btn_audio_power.setText("▶ Avvia Audio")
            if self.audio_state_changed:
                self.audio_state_changed()

    def stop_timers(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
