"""Interactive Didactic Module browser and 10-question Quiz aligned to Slides 1-18."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.didactics.curriculum import (
    DIDACTIC_MODULES,
    QUIZ_QUESTIONS,
    DidacticModule,
    ExperimentPreset,
)
from src.ui.widgets.diagram_widget import DidacticDiagramWidget


class DidacticView(QWidget):
    """Two-column didactic view with 10 interactive lessons, experiments, and quiz."""

    experiment_requested = Signal(object)  # emits ExperimentPreset

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_index: int = 0
        self._quiz_groups: list[QButtonGroup] = []
        self._quiz_feedbacks: list[QLabel] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)

        # Left Sidebar
        sidebar = QVBoxLayout()
        sidebar.setSpacing(8)
        side_title = QLabel("Moduli del Corso (Slide 1–18)")
        side_title.setStyleSheet("font-weight:700; font-size:13px; color:#00d2ff;")
        sidebar.addWidget(side_title)

        self._module_list = QListWidget()
        self._module_list.setMinimumWidth(270)
        self._module_list.setMaximumWidth(310)
        for mod in DIDACTIC_MODULES:
            item = QListWidgetItem(f"{mod.title}\n   [{mod.slides_ref}]")
            self._module_list.addItem(item)
        sidebar.addWidget(self._module_list, 1)

        self._btn_quiz = QPushButton("📝 Quiz di Verifica (10 Domande)")
        self._btn_quiz.setCheckable(True)
        self._btn_quiz.setMinimumHeight(38)
        sidebar.addWidget(self._btn_quiz)
        root.addLayout(sidebar)

        # Right Stacked Area (0 = Lesson, 1 = Quiz)
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._build_lesson_page()
        self._build_quiz_page()

        self._module_list.currentRowChanged.connect(self._on_module_selected)
        self._btn_quiz.clicked.connect(self._on_quiz_toggled)

        self._module_list.setCurrentRow(0)

    def _build_lesson_page(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 4, 12, 16)
        layout.setSpacing(10)

        # Header row
        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        self._lbl_title = QLabel()
        self._lbl_title.setStyleSheet("font-size:20px; font-weight:800; color:#f1f5f9;")
        self._lbl_subtitle = QLabel()
        self._lbl_subtitle.setStyleSheet("font-size:13px; color:#94a3b8;")
        title_col.addWidget(self._lbl_title)
        title_col.addWidget(self._lbl_subtitle)
        hdr.addLayout(title_col, 1)

        self._lbl_slides = QLabel()
        self._lbl_slides.setProperty("class", "mono-badge")
        hdr.addWidget(self._lbl_slides, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(hdr)

        # Lesson HTML body
        self._browser = QTextBrowser()
        self._browser.setMinimumHeight(200)
        self._browser.setMaximumHeight(285)
        self._browser.setStyleSheet(
            "QTextBrowser { font-size:13.5px; line-height:1.45; background:#141822; }"
        )
        layout.addWidget(self._browser)

        # Formulas Card
        self._formulas_frame = QFrame()
        self._formulas_frame.setObjectName("GuideBanner")
        f_lay = QVBoxLayout(self._formulas_frame)
        f_lay.setContentsMargins(10, 8, 10, 8)
        f_lay.setSpacing(4)
        f_hdr = QLabel("Formule e Regole Chiave")
        f_hdr.setStyleSheet("font-weight:700; color:#00d2ff; font-size:12px;")
        f_lay.addWidget(f_hdr)
        self._lbl_formulas = QLabel()
        self._lbl_formulas.setWordWrap(True)
        self._lbl_formulas.setStyleSheet(
            "font-family:'JetBrains Mono','SF Mono',Consolas,monospace; font-size:12px; color:#e2e8f0;"
        )
        f_lay.addWidget(self._lbl_formulas)
        layout.addWidget(self._formulas_frame)

        # Interactive Diagram
        diag_lbl = QLabel("Schema & Simulatore Rapido")
        diag_lbl.setStyleSheet("font-weight:700; color:#94a3b8; font-size:12px;")
        layout.addWidget(diag_lbl)
        self._diagram = DidacticDiagramWidget()
        layout.addWidget(self._diagram)

        # Experiments container
        exp_lbl = QLabel("Esperimenti Guidati nel Laboratorio Reale")
        exp_lbl.setStyleSheet("font-weight:700; color:#00d2ff; font-size:13px;")
        layout.addWidget(exp_lbl)
        self._exp_container = QVBoxLayout()
        self._exp_container.setSpacing(8)
        layout.addLayout(self._exp_container)

        # Bottom Navigation
        nav = QHBoxLayout()
        self._btn_prev = QPushButton("◀ Modulo Precedente")
        self._btn_next = QPushButton("Modulo Successivo ▶")
        nav.addWidget(self._btn_prev)
        nav.addStretch()
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)
        layout.addStretch()

        self._btn_prev.clicked.connect(lambda: self.select_module(self._current_index - 1))
        self._btn_next.clicked.connect(lambda: self.select_module(self._current_index + 1))

        scroll.setWidget(container)
        self._stack.addWidget(scroll)

    def _build_quiz_page(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 6, 14, 20)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        q_title = QLabel("Quiz di Verifica — Teoria dei Filtri Digitali & Mixer")
        q_title.setStyleSheet("font-size:19px; font-weight:800; color:#f1f5f9;")
        hdr.addWidget(q_title, 1)
        self._lbl_quiz_score = QLabel("Rispondi alle 10 domande e premi Verifica")
        self._lbl_quiz_score.setProperty("class", "mono-badge")
        hdr.addWidget(self._lbl_quiz_score)
        layout.addLayout(hdr)

        self._quiz_groups.clear()
        self._quiz_feedbacks.clear()

        for q in QUIZ_QUESTIONS:
            card = QFrame()
            card.setProperty("class", "card-frame")
            card.setStyleSheet(
                "QFrame { background:#161922; border:1px solid #262c3d; border-radius:8px; padding:10px; }"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(6)

            q_hdr = QLabel(f"Domanda {q.id}  [{q.slides_ref}] — {q.question}")
            q_hdr.setWordWrap(True)
            q_hdr.setStyleSheet("font-weight:700; font-size:13.5px; color:#f1f5f9; border:none;")
            c_lay.addWidget(q_hdr)

            grp = QButtonGroup(self)
            for opt_idx, opt_txt in enumerate(q.options):
                rb = QRadioButton(opt_txt)
                rb.setStyleSheet("border:none; padding:2px;")
                grp.addButton(rb, opt_idx)
                c_lay.addWidget(rb)
            self._quiz_groups.append(grp)

            fb = QLabel("")
            fb.setWordWrap(True)
            fb.setVisible(False)
            fb.setStyleSheet("border:none; font-size:12px; padding-top:4px;")
            c_lay.addWidget(fb)
            self._quiz_feedbacks.append(fb)

            layout.addWidget(card)

        btn_row = QHBoxLayout()
        self._btn_check_quiz = QPushButton("✔ Verifica Risposte")
        self._btn_check_quiz.setObjectName("ExperimentBtn")
        self._btn_reset_quiz = QPushButton("↺ Ricomincia Quiz")
        btn_row.addWidget(self._btn_check_quiz)
        btn_row.addWidget(self._btn_reset_quiz)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._btn_check_quiz.clicked.connect(self.evaluate_quiz)
        self._btn_reset_quiz.clicked.connect(self.reset_quiz)

        scroll.setWidget(container)
        self._stack.addWidget(scroll)

    def select_module(self, index: int) -> None:
        idx = max(0, min(len(DIDACTIC_MODULES) - 1, int(index)))
        self._btn_quiz.setChecked(False)
        self._stack.setCurrentIndex(0)
        self._module_list.setCurrentRow(idx)

    def show_quiz(self) -> None:
        self._btn_quiz.setChecked(True)
        self._stack.setCurrentIndex(1)

    def _on_quiz_toggled(self, checked: bool) -> None:
        if checked:
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    def _on_module_selected(self, row: int) -> None:
        if row < 0 or row >= len(DIDACTIC_MODULES):
            return
        self._current_index = row
        self._btn_quiz.setChecked(False)
        self._stack.setCurrentIndex(0)
        self._render_module(DIDACTIC_MODULES[row])

    def _render_module(self, mod: DidacticModule) -> None:
        self._lbl_title.setText(mod.title)
        self._lbl_subtitle.setText(mod.subtitle)
        self._lbl_slides.setText(mod.slides_ref)
        self._browser.setHtml(
            f"<style>p, li {{ color:#dce3f0; }} code {{ color:#00e5ff; font-family:monospace; }}</style>{mod.html_content}"
        )
        self._lbl_formulas.setText("\n".join(mod.key_formulas))
        self._diagram.set_kind(mod.diagram_kind)

        # Rebuild experiment cards
        while self._exp_container.count():
            item = self._exp_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for exp in mod.experiments:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background:#151c28; border:1px solid #26354d; border-radius:8px; padding:8px; }"
            )
            h = QHBoxLayout(card)
            h.setSpacing(12)
            txt_col = QVBoxLayout()
            lbl_n = QLabel(exp.label)
            lbl_n.setStyleSheet("font-weight:700; color:#e0f9ff; border:none;")
            lbl_d = QLabel(exp.description)
            lbl_d.setWordWrap(True)
            lbl_d.setStyleSheet("color:#94a3b8; font-size:12px; border:none;")
            txt_col.addWidget(lbl_n)
            txt_col.addWidget(lbl_d)
            h.addLayout(txt_col, 1)

            btn = QPushButton("🧪 Prova nel Laboratorio ▶")
            btn.setObjectName("ExperimentBtn")
            btn.clicked.connect(lambda _chk=False, p=exp: self.experiment_requested.emit(p))
            h.addWidget(btn)
            self._exp_container.addWidget(card)

        self._btn_prev.setEnabled(self._current_index > 0)
        self._btn_next.setEnabled(self._current_index < len(DIDACTIC_MODULES) - 1)

    def evaluate_quiz(self) -> int:
        score = 0
        for q, grp, fb in zip(QUIZ_QUESTIONS, self._quiz_groups, self._quiz_feedbacks):
            sel = grp.checkedId()
            fb.setVisible(True)
            if sel == q.correct_index:
                score += 1
                fb.setStyleSheet("color:#34d399; border:none; font-size:12px; padding-top:4px;")
                fb.setText(f"✔ Corretto! {q.explanation}")
            elif sel < 0:
                fb.setStyleSheet("color:#fbbf24; border:none; font-size:12px; padding-top:4px;")
                fb.setText(f"⚠ Nessuna risposta selezionata. {q.explanation}")
            else:
                fb.setStyleSheet("color:#f87171; border:none; font-size:12px; padding-top:4px;")
                fb.setText(f"✖ Errato. {q.explanation}")
        self._lbl_quiz_score.setText(f"Punteggio: {score} / {len(QUIZ_QUESTIONS)}")
        return score

    def reset_quiz(self) -> None:
        for grp, fb in zip(self._quiz_groups, self._quiz_feedbacks):
            grp.setExclusive(False)
            for btn in grp.buttons():
                btn.setChecked(False)
            grp.setExclusive(True)
            fb.setVisible(False)
            fb.setText("")
        self._lbl_quiz_score.setText("Rispondi alle 10 domande e premi Verifica")
