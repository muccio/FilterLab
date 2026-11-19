"""FilterLab Pro-Audio Dark Console QSS Stylesheet."""

DARK_THEME_QSS = """
QWidget {
    background-color: #12141a;
    color: #e2e6f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}

QMainWindow {
    background-color: #0d0f14;
}

/* Header & Cards */
QFrame#GlobalHeader {
    background-color: #161922;
    border-bottom: 1px solid #282d3c;
    padding: 8px 16px;
}

QFrame.card-frame, QGroupBox {
    background-color: #161922;
    border: 1px solid #262c3d;
    border-radius: 8px;
}

QGroupBox {
    margin-top: 10px;
    padding-top: 14px;
    font-weight: 600;
    color: #94a3b8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #00d2ff;
    font-size: 12px;
    font-weight: 700;
}

/* Main Tab Widget */
QTabWidget::pane {
    border: 1px solid #262b3a;
    background-color: #12141a;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #161922;
    color: #8c93a8;
    border: 1px solid #262b3a;
    border-bottom: none;
    padding: 9px 18px;
    margin-right: 3px;
    font-weight: 600;
    font-size: 13px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #1c2230;
    color: #00d2ff;
    border-top: 2px solid #00d2ff;
    border-bottom: 1px solid #1c2230;
}

QTabBar::tab:hover:!selected {
    background-color: #1a1e29;
    color: #d0d7e8;
}

/* Buttons */
QPushButton {
    background-color: #202636;
    color: #e6ebf5;
    border: 1px solid #333c52;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2a3246;
    border-color: #00d2ff;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #181d2a;
}

QPushButton:checked {
    background-color: #0e3a4d;
    border-color: #00d2ff;
    color: #00f2fe;
}

QPushButton:disabled {
    background-color: #181b24;
    color: #555e73;
    border-color: #232836;
}

QPushButton#StartAudioBtn {
    background-color: #0e4a38;
    border-color: #10b981;
    color: #a7f3d0;
    font-weight: 700;
}

QPushButton#StartAudioBtn:checked {
    background-color: #4c1d24;
    border-color: #ef4444;
    color: #fecaca;
}

QPushButton#ExperimentBtn {
    background-color: #0d3a4f;
    border: 1px solid #00d2ff;
    color: #e0f9ff;
    padding: 8px 16px;
    font-weight: 700;
}

QPushButton#ExperimentBtn:hover {
    background-color: #124c66;
}

QPushButton#MuteBtn:checked {
    background-color: #5b1b22;
    border-color: #ef4444;
    color: #fecaca;
}

QPushButton#PflBtn:checked {
    background-color: #4f3a0e;
    border-color: #f59e0b;
    color: #fde68a;
}

QPushButton#BypassBtn:checked {
    background-color: #3b2458;
    border-color: #a855f7;
    color: #e9d5ff;
}

/* Inputs, Combos, SpinBoxes */
QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #191e2b;
    color: #e2e6f0;
    border: 1px solid #2e364a;
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 22px;
}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #00d2ff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #181c26;
    color: #e2e6f0;
    border: 1px solid #333d54;
    selection-background-color: #0e3a4d;
    selection-color: #00f2fe;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #222838;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #00a8cc;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #00d2ff;
    border: 2px solid #0d0f14;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::groove:vertical {
    width: 6px;
    background: #222838;
    border-radius: 3px;
}

QSlider::add-page:vertical {
    background: #00a8cc;
    border-radius: 3px;
}

QSlider::handle:vertical {
    background: #00d2ff;
    border: 2px solid #0d0f14;
    width: 16px;
    height: 12px;
    margin: 0 -5px;
    border-radius: 4px;
}

/* Lists & ScrollAreas */
QListWidget {
    background-color: #141720;
    border: 1px solid #252b3b;
    border-radius: 6px;
    outline: none;
}

QListWidget::item {
    padding: 9px 10px;
    border-bottom: 1px solid #1e2330;
    color: #b4bcd0;
}

QListWidget::item:selected {
    background-color: #182c3f;
    color: #00f2fe;
    border-left: 3px solid #00d2ff;
    font-weight: 700;
}

QListWidget::item:hover:!selected {
    background-color: #191e2b;
    color: #e2e6f0;
}

QTextBrowser {
    background-color: #141720;
    border: 1px solid #252b3b;
    border-radius: 8px;
    padding: 12px;
    color: #e2e6f0;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #10131a;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #2c3448;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #3d4863;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Labels & Badges */
QLabel.muted-label {
    color: #94a3b8;
    font-size: 12px;
}

QLabel.mono-badge {
    font-family: "JetBrains Mono", "SF Mono", "Consolas", monospace;
    background-color: #192130;
    color: #00f2fe;
    border: 1px solid #28364d;
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 12px;
}

QFrame#GuideBanner {
    background-color: #132230;
    border: 1px solid #1e4b66;
    border-radius: 6px;
    padding: 6px 10px;
}

QFrame#FeedbackWarn {
    background-color: #2d2010;
    border: 1px solid #b45309;
    border-radius: 6px;
    padding: 5px 10px;
}
"""
