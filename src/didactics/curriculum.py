"""Complete 10-module didactic curriculum and 10-question quiz mapped to Slides 1-18."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExperimentPreset:
    """Interactive experiment configuration pushed directly to the DSP Lab."""

    id: str
    label: str
    description: str
    what_to_observe: str
    workbench_mode: str  # "single" | "network" | "graphic_eq" | "parametric_eq"
    generator_type: str = "white_noise"
    generator_freq: float = 220.0
    impulse_rate_hz: float = 2.0
    single_params: dict[str, Any] = field(default_factory=dict)
    network_params: dict[str, Any] = field(default_factory=dict)
    graphic_params: dict[str, Any] = field(default_factory=dict)
    parametric_params: dict[str, Any] = field(default_factory=dict)
    channel_params: dict[str, Any] = field(default_factory=dict)
    show_ideal: bool = False
    time_view: str = "impulse"  # "impulse" | "scope" | "blackbox"


@dataclass
class DidacticModule:
    index: int
    title: str
    subtitle: str
    slides_ref: str
    diagram_kind: str
    html_content: str
    key_formulas: list[str]
    experiments: list[ExperimentPreset]


@dataclass
class QuizQuestion:
    id: int
    slides_ref: str
    question: str
    options: list[str]
    correct_index: int
    explanation: str


DIDACTIC_MODULES: list[DidacticModule] = [
    DidacticModule(
        index=1,
        title="1. Cosa sono i Filtri Digitali & Gli EQ",
        subtitle="Blackbox, flusso discreto di campioni Δt e selezione spettrale",
        slides_ref="Slide 1 – 2",
        diagram_kind="blackbox",
        key_formulas=[
            "x[n] = x(n · Δt),   Δt = 1 / fs   (es. a 48 kHz → Δt ≈ 20.8 µs)",
            "Y(f) = X(f) · H(f)   (Spettro Ingresso × Risposta del Filtro)",
        ],
        html_content="""
        <p>Un <b>filtro digitale</b> è uno strumento di elaborazione del suono che modifica il contenuto
        in frequenza di un segnale audio: permette di <b>eliminare o attenuare</b> le frequenze indesiderate
        (ad esempio rumore di fondo) oppure di <b>mettere in risalto</b> determinate bande per dare un timbro
        particolare o distinguere uno strumento nel mix.</p>

        <p>Possiamo immaginare il filtro come una <b>blackbox</b> con un ingresso ed un'uscita: il segnale audio
        digitale entra come flusso continuo di numeri equispaziati nel tempo (<b>i campioni</b>, separati da
        un intervallo costante <code>Δt = 1/fs</code>) e viene restituito all'uscita con ampiezza modificata in
        funzione della frequenza.</p>

        <h4>Applicazioni tipiche (Slide 1)</h4>
        <ul>
          <li><b>Equalizzatori (EQ)</b> grafici e parametrici su software DAW, mixer e console hardware.</li>
          <li><b>Rimozione rumore di fondo</b> o risonanze indesiderate (hiss, hum a 50/60 Hz).</li>
          <li><b>Effetti timbrici e sintetizzatori</b>, come il celebre filtro risonante <b>Moog Ladder</b> (24 dB/ottava).</li>
          <li><b>Sidechain e compressori</b> (filtri sul circuito di rilevazione per gestire le basse frequenze).</li>
        </ul>
        """,
        experiments=[
            ExperimentPreset(
                id="mod1_blackbox",
                label="Osserva Campioni Blackbox (Sinusoide + LowPass)",
                description="Mostra i numeri dei campioni in ingresso x[n] e uscita y[n] separati da Δt.",
                what_to_observe=(
                    "Attiva la vista 'Blackbox Campioni Δt' in basso e confronta lo spettro FFT pre-filtro "
                    "(ambra) e post-filtro (ciano) su Rumore Bianco."
                ),
                workbench_mode="single",
                generator_type="white_noise",
                single_params={"filter_type": "lowpass", "freq": 1000.0, "q": 0.7071, "order": 2},
                time_view="blackbox",
            ),
            ExperimentPreset(
                id="mod1_moog",
                label="Ascolta Effetto Timbrico: Moog Ladder su Synth",
                description="Filtro Ladder a 4 poli risonante (Slide 1) su onda a dente di sega.",
                what_to_observe=(
                    "Muovi la frequenza di taglio (Cutoff) tra 180 Hz e 4 kHz con Q alto (risonanza) e Drive > 1.0 "
                    "per ascoltare il caratteristico timbro analogico del Moog Ladder."
                ),
                workbench_mode="single",
                generator_type="sawtooth",
                generator_freq=110.0,
                single_params={"filter_type": "moog_ladder", "freq": 750.0, "q": 7.5, "order": 4, "drive": 1.6},
                time_view="scope",
            ),
        ],
    ),
    DidacticModule(
        index=2,
        title="2. Filtri Passa-Basso (LowPass) e Passa-Alto (HighPass)",
        subtitle="Frequenza di taglio (Cutoff @ -3 dB), banda passante e stopband",
        slides_ref="Slide 3 – 4",
        diagram_kind="lp_hp",
        key_formulas=[
            "Cutoff fc (-3 dB): punto in cui l'ampiezza scende a 1/√2 ≈ 0.707 (−3.01 dB, metà potenza)",
            "LowPass: passa f < fc, attenua f > fc   |   HighPass: passa f > fc, attenua f < fc",
        ],
        html_content="""
        <p>I due blocchi fondamentali dell'equalizzazione e della sintesi sottrattiva sono:</p>
        <ul>
          <li><b>Filtro Passa-Basso (LowPass / LPF — Slide 3):</b> lascia passare tutte le frequenze al di
          sotto della <i>cutoff frequency</i> e attenua progressivamente quelle superiori. È usato per scurire
          un suono, togliere fruscio (hiss) o scolpire armoniche acute.</li>
          <li><b>Filtro Passa-Alto (HighPass / HPF — Slide 4):</b> lascia passare le frequenze al di sopra
          della <i>cutoff frequency</i> e blocca le basse. È indispensabile per ripulire tracce vocali, chitarre
          e microfoni da rimbombi e rumble subsonico.</li>
        </ul>
        <p>Nelle Slide 3 e 4 il segnale di test classico è il <b>White Noise</b> (energia uniforme su tutto lo
        spettro) filtrato a <b>1.000 Hz</b>: all'ascolto e sullo spettro FFT si nota immediatamente quale metà
        dello spettro viene lasciata passare e quale attenuata.</p>
        """,
        experiments=[
            ExperimentPreset(
                id="mod2_lp1000",
                label="LowPass 1.000 Hz su White Noise (Slide 3)",
                description="Replica esatta dello schema white noise → lowpass 1000 Hz.",
                what_to_observe=(
                    "Osserva la linea -3 dB esattamente a 1.000 Hz sulla curva Bode e nota nello spettro FFT "
                    "come le frequenze sopra 1 kHz scendano mentre quelle sotto restino intatte."
                ),
                workbench_mode="single",
                generator_type="white_noise",
                single_params={"filter_type": "lowpass", "freq": 1000.0, "q": 0.7071, "order": 2},
                show_ideal=True,
            ),
            ExperimentPreset(
                id="mod2_hp1000",
                label="HighPass 1.000 Hz su White Noise (Slide 4)",
                description="Replica esatta dello schema HighPass cutoff 1000 Hz.",
                what_to_observe=(
                    "Nota l'attenuazione progressiva sotto 1.000 Hz e il suono più sottile e brillante del "
                    "rumore bianco filtrato."
                ),
                workbench_mode="single",
                generator_type="white_noise",
                single_params={"filter_type": "highpass", "freq": 1000.0, "q": 0.7071, "order": 2},
                show_ideal=True,
            ),
        ],
    ),
    DidacticModule(
        index=3,
        title="3. Passa-Banda (BandPass) & Elimina-Banda (BandReject)",
        subtitle="Cutoff inferiore/superiore, larghezza di banda e centro geometrico",
        slides_ref="Slide 5 – 6",
        diagram_kind="bp_br",
        key_formulas=[
            "BW = f_upper − f_lower   (Larghezza di banda a −3 dB)",
            "fc = √(f_lower · f_upper)   (Media geometrica — es. √(1600·2000) = 1788.85 Hz)",
            "BandReject Slide 6: f_L = 1900 Hz, f_H = 2000 Hz → fc = √(1900·2000) = 1949.36 Hz",
        ],
        html_content="""
        <p>Combinando l'azione di passa-alto e passa-basso attorno a una frequenza centrale <code>fc</code>
        otteniamo due filtri complementari:</p>
        <ul>
          <li><b>Passa-Banda (BandPass — Slide 5):</b> lascia passare solo una specifica fascia di frequenze
          compresa tra <i>lower cutoff</i> e <i>upper cutoff</i>, attenuando tutto ciò che è fuori banda.
          Esempio delle slide: <code>f_L = 1.600 Hz</code>, <code>f_H = 2.000 Hz</code>,
          <code>Bandwidth = 400 Hz</code>, centro geometrico <code>fc ≈ 1.789 Hz</code>.</li>
          <li><b>Elimina-Banda (BandReject / Notch — Slide 6):</b> lascia passare tutto lo spettro tranne una
          stretta banda centrata su <code>fc</code>, creando una profonda "tacca" (<i>notch</i>) per rimuovere
          fischi, risonanze o l'hum di rete a 50/60 Hz. Esempio Slide 6: <code>f_L = 1.900 Hz</code>,
          <code>f_H = 2.000 Hz</code> → <code>fc = 1.949,35 Hz</code>.</li>
        </ul>
        """,
        experiments=[
            ExperimentPreset(
                id="mod3_bp_slide5",
                label="BandPass Slide 5 (1.600 – 2.000 Hz, BW 400 Hz)",
                description="Passa-banda centrato a 1788.85 Hz con Q = 4.47.",
                what_to_observe=(
                    "Verifica nella barra informativa che fL = 1.600 Hz, fH = 2.000 Hz e BW = 400 Hz esatti!"
                ),
                workbench_mode="single",
                generator_type="white_noise",
                single_params={"filter_type": "bandpass", "freq": 1788.85, "q": 4.4721, "order": 2},
            ),
            ExperimentPreset(
                id="mod3_br_slide6",
                label="BandReject Slide 6 (1.900 – 2.000 Hz, fc 1949.35 Hz)",
                description="Elimina-banda chirurgico centrato a 1949.36 Hz con Q = 19.49.",
                what_to_observe=(
                    "Nota la profonda attenuazione a 1.949 Hz con punti a -3 dB esattamente a 1.900 e 2.000 Hz. "
                    "Prova anche con la Sorgente Sinusoide impostata a 1.949 Hz!"
                ),
                workbench_mode="single",
                generator_type="white_noise",
                single_params={"filter_type": "bandreject", "freq": 1949.36, "q": 19.4936, "order": 2},
            ),
        ],
    ),
    DidacticModule(
        index=4,
        title="4. Quality Factor (Q), Risposta nel Tempo e Ringing",
        subtitle="Relazione Q = fc / BW, transient ringing e filtri BP risonanti",
        slides_ref="Slide 7 & Slide 9",
        diagram_kind="q_ringing",
        key_formulas=[
            "Q = frequenza centrale / larghezza di banda = fc / BW",
            "Durata del Ringing nel tempo ∝ Q   (più Q è alto, più a lungo oscilla il transiente)",
            "Resonant BandPass (Slide 9): Guadagno di picco = 20·log10(Q)  (Q=2 → +6 dB, Q=6 → +15.6 dB)",
        ],
        html_content="""
        <p>Il <b>Quality Factor (Q)</b> misura la selettività di un filtro: è definito come il rapporto tra
        frequenza centrale e larghezza di banda (<code>Q = fc / BW</code>). Un valore di Q elevato produce una
        campana stretta e chirurgica, mentre un Q basso agisce su una regione ampia dello spettro.</p>

        <h4>Effetto nel dominio del tempo: il Ringing (Slide 7)</h4>
        <p>Maggiore è il valore di <b>Q</b>, più selettivo è il filtro in frequenza ma <b>più lunga è la sua
        risposta all'impulso nel tempo</b>. Quando un transiente rapido (come un impulso o un colpo di rullante)
        colpisce un filtro con Q molto alto, il filtro continua a "risuonare" attorno alla frequenza centrale:
        questo fenomeno è detto <b>ringing</b>.</p>

        <h4>BandPass Standard vs Risonante (Slide 9)</h4>
        <ul>
          <li><b>BandPass Standard (0 dB peak):</b> il picco alla frequenza centrale resta a 0 dB al crescere di Q.</li>
          <li><b>Resonant BandPass:</b> il filtro amplifica la frequenza centrale in proporzione a Q:
          a <code>Q = 2</code> il picco sale a circa <b>+6 dB</b>; a <code>Q = 6</code> raggiunge <b>+15,6 dB</b>!</li>
        </ul>
        """,
        experiments=[
            ExperimentPreset(
                id="mod4_ringing",
                label="Test Ringing su Treno di Impulsi (Q = 14)",
                description="Ascolta la coda risonante generata dai transienti su filtro ad alto Q.",
                what_to_observe=(
                    "Guarda il grafico della Risposta all'Impulso h[n] in basso e muovi lo slider Q da 0.7 a 20: "
                    "sentirai l'impulso trasformarsi in una nota intonata a 1.000 Hz!"
                ),
                workbench_mode="single",
                generator_type="impulse",
                impulse_rate_hz=2.0,
                single_params={"filter_type": "bandpass", "freq": 1000.0, "q": 14.0, "order": 2},
                time_view="impulse",
            ),
            ExperimentPreset(
                id="mod4_res_q6",
                label="Resonant BandPass 1.000 Hz, Q = 6 (Slide 9)",
                description="Amplificazione risonante a +15.56 dB esattamente come nella Slide 9.",
                what_to_observe=(
                    "Osserva il picco salire oltre +15 dB a 1.000 Hz e confronta con 'BandPass Standard' a Q=6."
                ),
                workbench_mode="single",
                generator_type="pink_noise",
                single_params={"filter_type": "resonant_bandpass", "freq": 1000.0, "q": 6.0, "order": 2},
                time_view="impulse",
            ),
        ],
    ),
    DidacticModule(
        index=5,
        title="5. Ordine del Filtro, Roll-Off e Butterworth",
        subtitle="Filtro ideale vs reale, transition zone, 6 / 12 / 24 dB per ottava",
        slides_ref="Slide 7 – 8",
        diagram_kind="order_rolloff",
        key_formulas=[
            "1° Ordine: pendenza asintotica 6 dB/ottava (20 dB/decade)",
            "2° Ordine (Butterworth, Q = 1/√2 ≈ 0.7071): pendenza 12 dB/ottava, banda passante maximally flat",
            "4° Ordine / Moog Ladder: pendenza 24 dB/ottava",
        ],
        html_content="""
        <p>Un <b>filtro ideale</b> (brick-wall) taglierebbe istantaneamente tutte le frequenze oltre la soglia
        di cutoff. Un <b>filtro digitale reale</b> presenta invece una <b>transition zone</b> e una pendenza
        graduale detta <b>roll-off</b>, determinata dall'<b>ordine</b> del filtro:</p>

        <table width="100%" cellspacing="0" cellpadding="4" border="1" style="border-color:#2c3448; margin:6px 0;">
          <tr style="background:#1c2333;">
            <th>Esempio Slide 7–8</th><th>1° Ordine (6 dB/oct)</th><th>2° Ordine Butterworth (12 dB/oct)</th>
          </tr>
          <tr>
            <td><b>LowPass 300 Hz</b></td>
            <td>0 dB ≤300 Hz | -6 dB @ 600 Hz | -12 dB @ 1.2 kHz | -18 dB @ 2.4 kHz</td>
            <td>0 dB ≤300 Hz | -12 dB @ 600 Hz | -24 dB @ 1.2 kHz | -36 dB @ 2.4 kHz</td>
          </tr>
          <tr>
            <td><b>HighPass 1.000 Hz</b></td>
            <td>0 dB ≥1 kHz | -6 dB @ 500 Hz | -12 dB @ 250 Hz | -18 dB @ 125 Hz</td>
            <td>0 dB ≥1 kHz | -12 dB @ 500 Hz | -24 dB @ 250 Hz | -36 dB @ 125 Hz</td>
          </tr>
          <tr>
            <td><b>BandPass 1.789 Hz</b></td>
            <td>—</td>
            <td>0 dB @ 1.789 Hz | -3 dB @ 1.6k & 2k | -12 dB @ 800 & 4k | -24 dB @ 400 & 8k</td>
          </tr>
        </table>
        """,
        experiments=[
            ExperimentPreset(
                id="mod5_lp_order1",
                label="Slide 7: LowPass 1° Ordine 300 Hz (6 dB/oct)",
                description="Verifica i valori della tabella Slide 7 su LowPass 300 Hz.",
                what_to_observe=(
                    "Confronta il filtro digitale con la curva ideale tratteggiata (Transition Zone). "
                    "Passa poi da '1° Ordine (6 dB/oct)' a '2° Ordine' e '4° Ordine'!"
                ),
                workbench_mode="single",
                generator_type="log_sweep",
                single_params={"filter_type": "lowpass", "freq": 300.0, "q": 0.7071, "order": 1},
                show_ideal=True,
            ),
            ExperimentPreset(
                id="mod5_hp_order2",
                label="Slide 8: HighPass 2° Ordine Butterworth 1.000 Hz",
                description="Massima piattezza in banda passante e -12 dB/oct sotto i 1.000 Hz.",
                what_to_observe=(
                    "Osserva l'attenuazione a 500 Hz (~ -12 dB), 250 Hz (~ -24 dB) e 125 Hz (~ -36 dB)."
                ),
                workbench_mode="single",
                generator_type="log_sweep",
                single_params={"filter_type": "highpass", "freq": 1000.0, "q": 0.7071, "order": 2},
                show_ideal=True,
            ),
        ],
    ),
    DidacticModule(
        index=6,
        title="6. Connessione in Serie vs Parallelo",
        subtitle="Channel Strip in cascata (ordine superiore) vs sommatore parallelo",
        slides_ref="Slide 10 – 11",
        diagram_kind="series_parallel",
        key_formulas=[
            "Serie (Cascata): H_tot(f) = H1(f) · H2(f) · ... · HN(f)   (in dB si SOMMANO)",
            "Parallelo (Somma): H_tot(f) = (H1(f) + H2(f) + ... + HN(f)) / N",
        ],
        html_content="""
        <p>Più filtri possono essere collegati secondo due architetture fondamentali (Slide 10 e 11):</p>
        <ul>
          <li><b>Connessione in Serie (Channel Strip):</b> l'uscita di un filtro entra nell'ingresso del
          successivo. Le risposte in dB si sommano (i poli si moltiplicano), permettendo di costruire filtri di
          <b>ordine superiore</b> o catene miste (es. HighPass → Peak → LowPass). Nella <b>Slide 10</b>,
          due BandPass del 2° ordine (1.000 Hz e 1.400 Hz, Q = 2) in serie formano un BandPass del 4° ordine!</li>
          <li><b>Connessione in Parallelo:</b> lo stesso segnale entra contemporaneamente in più filtri indipendenti
          le cui uscite vengono poi sommate (<code>+</code>). Nella <b>Slide 11</b>, quattro BandPass a 40, 80,
          120 e 160 Hz estraggono quattro strette bande armoniche dal White Noise!</li>
        </ul>
        """,
        experiments=[
            ExperimentPreset(
                id="mod6_series_slide10",
                label="Slide 10: 2× BP 2° Ordine in Serie (1000 + 1400 Hz)",
                description="Replica esatta dello schema della Slide 10: BP risultante del 4° ordine.",
                what_to_observe=(
                    "Osserva le curve individuali tratteggiate (1000 Hz e 1400 Hz) e la curva composita risultante "
                    "del 4° ordine con pendenza raddoppiata!"
                ),
                workbench_mode="network",
                generator_type="white_noise",
                network_params={
                    "topology": "series",
                    "stages": [
                        {"enabled": True, "filter_type": "bandpass", "freq": 1000.0, "q": 2.0, "gain_db": 0.0, "order": 2},
                        {"enabled": True, "filter_type": "bandpass", "freq": 1400.0, "q": 2.0, "gain_db": 0.0, "order": 2},
                        {"enabled": False, "filter_type": "lowpass", "freq": 4000.0, "q": 0.7071, "gain_db": 0.0, "order": 2},
                        {"enabled": False, "filter_type": "highpass", "freq": 120.0, "q": 0.7071, "gain_db": 0.0, "order": 2},
                    ],
                },
            ),
            ExperimentPreset(
                id="mod6_parallel_slide11",
                label="Slide 11: 4× BP Paralleli (40, 80, 120, 160 Hz)",
                description="Quattro bande parallele sommate su Rumore Bianco.",
                what_to_observe=(
                    "Guarda i 4 picchi armonici distinti nella zona grave del grafico Bode e nello spettro FFT "
                    "su White Noise."
                ),
                workbench_mode="network",
                generator_type="white_noise",
                network_params={
                    "topology": "parallel",
                    "stages": [
                        {"enabled": True, "filter_type": "bandpass", "freq": 40.0, "q": 10.0, "gain_db": 0.0, "order": 2},
                        {"enabled": True, "filter_type": "bandpass", "freq": 80.0, "q": 10.0, "gain_db": 0.0, "order": 2},
                        {"enabled": True, "filter_type": "bandpass", "freq": 120.0, "q": 10.0, "gain_db": 0.0, "order": 2},
                        {"enabled": True, "filter_type": "bandpass", "freq": 160.0, "q": 10.0, "gain_db": 0.0, "order": 2},
                    ],
                },
            ),
        ],
    ),
    DidacticModule(
        index=7,
        title="7. Banchi di Filtri e Inviluppi di Controllo",
        subtitle="Catene parallele BP → LP → HP e modulazione dinamica dello spettro",
        slides_ref="Slide 11 – 12",
        diagram_kind="filter_bank",
        key_formulas=[
            "Ramo i-esimo del banco: Input → BandPass → LowPass → HighPass → Sommatore (+)",
            "Modulazione temporale: fc(t) e BW(t) guidati da inviluppi / LFO → formanti e glissandi",
        ],
        html_content="""
        <p>Un <b>banco di filtri</b> (<i>filter bank</i> — Slide 12) estende l'architettura parallela creando
        molti rami simultanei, ciascuno formato da una catena <code>BandPass → LowPass → HighPass</code> sommata
        all'uscita.</p>
        <p>I parametri di ogni ramo — <b>frequenza centrale</b> del BandPass, <b>ampiezza della banda</b> (Q)
        e <b>cutoff</b> del LowPass — possono essere controllati nel tempo da <b>inviluppi</b> o LFO. In questo
        modo è possibile trasformare un semplice rumore bianco in tessiture vocali, formanti dinamiche o
        <b>glissandi spettrali</b> animati (come mostrato nei grafici della Slide 12).</p>
        """,
        experiments=[
            ExperimentPreset(
                id="mod7_bank_modulated",
                label="Slide 12: Banco Modulato (4 Rami BP→LP→HP)",
                description="Banco parallelo con inviluppi/LFO attivi sulle frequenze centrali.",
                what_to_observe=(
                    "Ascolta il White Noise prendere vita timbrica mentre le 4 bande oscillano dinamicamente "
                    "nello spazio frequenziale!"
                ),
                workbench_mode="network",
                generator_type="white_noise",
                network_params={
                    "topology": "bank",
                    "stages": [
                        {"enabled": True, "filter_type": "bandpass", "freq": 320.0, "q": 5.5, "gain_db": 0.0, "order": 2, "env_enabled": True, "env_rate_hz": 0.28, "env_depth_oct": 0.9},
                        {"enabled": True, "filter_type": "bandpass", "freq": 750.0, "q": 6.0, "gain_db": 0.0, "order": 2, "env_enabled": True, "env_rate_hz": 0.45, "env_depth_oct": 1.1},
                        {"enabled": True, "filter_type": "bandpass", "freq": 1600.0, "q": 6.5, "gain_db": 0.0, "order": 2, "env_enabled": True, "env_rate_hz": 0.19, "env_depth_oct": 0.8},
                        {"enabled": True, "filter_type": "bandpass", "freq": 3400.0, "q": 7.0, "gain_db": 0.0, "order": 2, "env_enabled": True, "env_rate_hz": 0.36, "env_depth_oct": 1.0},
                    ],
                },
                time_view="scope",
            ),
        ],
    ),
    DidacticModule(
        index=8,
        title="8. Equalizzatore Grafico (10, 20, 30 Bande ISO)",
        subtitle="Suddivisione a 1 ottava, 1/2 ottava e 1/3 di ottava",
        slides_ref="Slide 13",
        diagram_kind="graphic_eq",
        key_formulas=[
            "10 bande = 1 ottava (Q ≈ 1.41)  |  20 bande = 1/2 ottava (Q ≈ 2.87)  |  30 bande = 1/3 ottava (Q ≈ 4.32)",
            "NB Slide 13: 1000 · 2^(-1/3) = 793.70 Hz → arrotondato per standard ISO a 800 Hz",
        ],
        html_content="""
        <p>Un <b>equalizzatore grafico</b> suddivide l'intero spettro udibile (20 Hz – 20 kHz) in bande fisse
        controllabili tramite una schiera ordinata di fader verticali (che disegnano visivamente la "grafica"
        della curva di equalizzazione):</p>
        <ul>
          <li><b>10 bande (1 ottava):</b> controllo rapido e musicale.</li>
          <li><b>20 bande (mezza ottava):</b> maggiore risoluzione per interventi live/studio.</li>
          <li><b>30 bande (un terzo d'ottava):</b> il controllo più accurato sull'inviluppo spettrale, tipico
          degli EQ da mastering e taratura ambientale PA.</li>
        </ul>
        <p><b>Le 30 frequenze ISO della Slide 13:</b><br>
        <code>25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1200, 1600,
        2000, 2500, 3200, 4000, 5000, 6300, 8000, 10000, 12000, 16000, 20000 Hz</code>.</p>
        <p><i>Nota Slide 13:</i> l'esatto intervallo di un terzo di ottava al di sotto di 1.000 Hz collocherebbe
        la banda inferiore a <b>793,7 Hz</b>, ma gli equalizzatori standard la correggono a <b>800 Hz</b>.</p>
        """,
        experiments=[
            ExperimentPreset(
                id="mod8_geq_30",
                label="Slide 13: Apri EQ Grafico 30 Bande ISO (1/3 Ottava)",
                description="Tutti i 30 fader ISO da 25 Hz a 20.000 Hz pronti per essere scolpiti.",
                what_to_observe=(
                    "Passa col mouse sopra il fader 800 Hz per leggere il confronto esatto (793.70 Hz → 800 Hz) "
                    "e prova i preset o commuta tra 10, 20 e 30 bande!"
                ),
                workbench_mode="graphic_eq",
                generator_type="pink_noise",
                graphic_params={"band_count": 30, "preset": "smile"},
            ),
        ],
    ),
    DidacticModule(
        index=9,
        title="9. Shelving, Peak/Notch ed EQ Parametrico",
        subtitle="Low/High Shelf (emphasis & attenuation), filtri a campana e controllo totale",
        slides_ref="Slide 14 – 15",
        diagram_kind="shelving_parametric",
        key_formulas=[
            "Shelving: al punto di shelf (shelf point) il guadagno vale esattamente Gain_dB / 2",
            "EQ Parametrico (Slide 15): meno bande dell'EQ grafico, ma controllo di Freq, Gain e Q per banda",
        ],
        html_content="""
        <p>Oltre ai filtri passa-basso/passa-alto, gli equalizzatori moderni impiegano due famiglie chiave (Slide 14):</p>
        <ul>
          <li><b>Filtri Shelving (Low Shelf &amp; High Shelf):</b> alzano (<i>emphasis</i>) o abbassano
          (<i>attenuation</i>) uniformemente tutte le frequenze al di sotto (Low Shelf) o al di sopra (High Shelf)
          dello <i>shelf point</i> fino a raggiungere il guadagno impostato.</li>
          <li><b>Filtri Peak / Notch (Bell):</b> creano un picco (guadagno &gt; 0 dB) o un avvallamento
          (guadagno &lt; 0 dB) centrato attorno a una frequenza con ampiezza governata dal fattore Q.</li>
        </ul>
        <p>Un <b>equalizzatore parametrico</b> (Slide 15) lavora in genere con un numero ridotto di bande (ad es.
        <code>LowShelf + 4 Peak/Notch + LowPass</code>), ma consente di regolare con precisione continua
        <b>Frequenza</b>, <b>Guadagno (dB)</b> e <b>Quality Factor (Q / Slope)</b> di ciascuna banda.</p>
        """,
        experiments=[
            ExperimentPreset(
                id="mod9_parametric_slide15",
                label="Slide 15: EQ Parametrico Completo (LowShelf + 4 Peak + LowPass)",
                description="Ricostruzione interattiva della curva della Slide 15 con nodi trascinabili.",
                what_to_observe=(
                    "Trascina direttamente i nodi colorati sul grafico Bode (su/giù = Gain, sinistra/destra = "
                    "Frequenza, rotellina del mouse = Q)!"
                ),
                workbench_mode="parametric_eq",
                generator_type="synth_chord",
                generator_freq=110.0,
                parametric_params={"preset": "slide15"},
            ),
        ],
    ),
    DidacticModule(
        index=10,
        title="10. Il Contesto nel Mixer: Aux, Fader, PFL e Routing",
        subtitle="Mandate Pre/Post-Fader, Livello Nominale, PFL/Solo, VU Meter e Pan-Pot",
        slides_ref="Slide 16 – 18",
        diagram_kind="mixer_strip",
        key_formulas=[
            "Aux Pre-Fader → indipendente dal fader (Monitor / Foldback)",
            "Aux Post-Fader → proporzionale al fader (Effetti: Riverbero / Delay)",
            "Fader nominale = 0 dB (10 dB sotto il fine corsa +10 dB) | Mono → Pan-Pot → Stereo",
        ],
        html_content="""
        <p>In una DAW o su un mixer analogico/digitale, i filtri e l'EQ vivono dentro un <b>modulo di ingresso
        (Channel Strip)</b> assieme ai controlli di mandata, volume e routing (Slide 16–18):</p>
        <ul>
          <li><b>Mandate Ausiliarie (Aux Send — Slide 16):</b> inviano una quota del segnale verso un
          <i>Aux Buss</i>. In modalità <b>Pre-Fader</b> il prelievo avviene a monte del fader (usato per i monitor
          da palco/cuffia); in modalità <b>Post-Fader</b> avviene a valle e dipende dal fader (usato per effetti
          come riverbero e delay).<br>
          <i>Riferimenti DAW:</i> <b>Cubase</b> (ultimi 2 insert/send POST), <b>Logic</b> (riclicca sulla
          mandata al bus per scegliere Pre/Post), <b>Ableton Live</b> (toggle Pre/Post nella sezione Master).</li>
          <li><b>Fader, Gain, Mute &amp; PFL (Slide 17):</b> il fader è tarato in dB con il <b>livello operativo
          nominale</b> a circa 10 dB sotto la corsa massima, così da ottimizzare il rapporto S/N e la manualità.
          Vicino al fader troviamo <b>Mute</b> e <b>PFL (Pre-Fade Listening)</b>: il PFL invia il segnale a monte
          del fader sulla barra SOLO per ascoltarlo in cuffia e misurarlo sui <b>VU/Peak meter</b> anche a fader
          abbassato, insieme al <b>LED di Overload</b>.</li>
          <li><b>Routing &amp; Pan-Pot (Slide 18):</b> indirizza il canale verso <b>Master</b> o coppie di
          <b>Subgroup/Buss</b> (1-2, 3-4). Fino al <b>Pan-Pot</b> il segnale viaggia in forma <b>monofonica</b>;
          dopo il Pan-Pot prosegue in forma <b>stereofonica</b> tra canale Left e Right!</li>
        </ul>
        """,
        experiments=[
            ExperimentPreset(
                id="mod10_pre_post_aux",
                label="Test Live: Aux Pre-Fader vs Post-Fader & PFL (Slide 16–18)",
                description="Attiva una mandata Aux con riverbero e sperimenta fader, Mute, PFL e Pan-Pot.",
                what_to_observe=(
                    "Nel pannello destro 'Channel Strip', porta il Fader al minimo (-∞): con 'Pre-Fader' "
                    "l'Aux Meter e il riverbero continuano a suonare; passa a 'Post-Fader' e spariscono! "
                    "Prova poi Mute + PFL e sposta il Pan-Pot L↔R."
                ),
                workbench_mode="single",
                generator_type="impulse",
                impulse_rate_hz=1.5,
                single_params={"filter_type": "lowpass", "freq": 3500.0, "q": 0.7071, "order": 2},
                channel_params={
                    "aux_send": 0.65,
                    "aux_pre_fader": True,
                    "aux_fx_enabled": True,
                    "fader_db": 0.0,
                    "pan": 0.0,
                },
                time_view="scope",
            ),
        ],
    ),
]


QUIZ_QUESTIONS: list[QuizQuestion] = [
    QuizQuestion(
        id=1,
        slides_ref="Slide 2",
        question="Come viene rappresentato un segnale audio all'ingresso di un filtro digitale?",
        options=[
            "Come una tensione analogica continua a variazione infinita",
            "Come un flusso di numeri equispaziati nel tempo (campioni separati da Δt)",
            "Solo come pacchetti MIDI di note e velocità",
            "Come onde radio modulate in frequenza",
        ],
        correct_index=1,
        explanation=(
            "Slide 2: il segnale applicato alla blackbox è un flusso di numeri (campioni) solitamente "
            "distanziati uniformemente nel tempo Δt = 1/fs."
        ),
    ),
    QuizQuestion(
        id=2,
        slides_ref="Slide 3 – 4",
        question="Cosa accade alla frequenza di taglio (cutoff) di un filtro Butterworth Passa-Basso o Passa-Alto?",
        options=[
            "Il segnale è già completamente azzerato (-∞ dB)",
            "Il segnale subisce un boost di +6 dB",
            "L'ampiezza del segnale è attenuata di circa -3 dB rispetto alla banda passante",
            "La frequenza di taglio corrisponde a -24 dB",
        ],
        correct_index=2,
        explanation=(
            "Slide 3, 4 e 8: per definizione nei filtri Butterworth il punto di cutoff corrisponde a -3 dB "
            "(metà potenza rispetto alla banda passante)."
        ),
    ),
    QuizQuestion(
        id=3,
        slides_ref="Slide 6",
        question="Un filtro BandReject ha cutoff inferiore a 1.900 Hz e superiore a 2.000 Hz. Qual è la sua frequenza centrale?",
        options=[
            "1.950,00 Hz (media aritmetica)",
            "1.949,36 Hz (media geometrica √(1900 × 2000))",
            "1.850,00 Hz",
            "100,00 Hz",
        ],
        correct_index=1,
        explanation=(
            "Slide 6: la frequenza centrale di un filtro passa/elimina banda è la media geometrica "
            "√(f_L · f_H) = √(1900 · 2000) ≈ 1949,35 Hz, con larghezza di banda 100 Hz."
        ),
    ),
    QuizQuestion(
        id=4,
        slides_ref="Slide 7",
        question="Qual è la relazione corretta per il Quality Factor Q e il suo effetto nel dominio del tempo?",
        options=[
            "Q = BW / fc; Q più alto riduce il ringing",
            "Q = fc / BW; la risposta nel tempo (ringing sui transienti) è direttamente proporzionale a Q",
            "Q = fc × BW; non ha effetti sul dominio del tempo",
            "Q influenza solo la pendenza di un filtro del primo ordine",
        ],
        correct_index=1,
        explanation=(
            "Slide 7: Q = frequenza centrale / larghezza di banda. La risposta nel tempo è direttamente "
            "proporzionale a Q, producendo ringing sui transienti."
        ),
    ),
    QuizQuestion(
        id=5,
        slides_ref="Slide 7 – 8",
        question="Un LowPass con cutoff a 300 Hz attenua di -12 dB a 600 Hz e -24 dB a 1.200 Hz. Di che ordine è?",
        options=[
            "1° ordine (6 dB/ottava)",
            "2° ordine Butterworth (12 dB/ottava)",
            "4° ordine (24 dB/ottava)",
            "Filtro ideale brick-wall",
        ],
        correct_index=1,
        explanation=(
            "Slide 8: un filtro del 2° ordine (Butterworth) attenua di 12 dB per ogni ottava oltre la "
            "regione di taglio (-12 dB @ 600 Hz, -24 dB @ 1.200 Hz, -36 dB @ 2.400 Hz)."
        ),
    ),
    QuizQuestion(
        id=6,
        slides_ref="Slide 9",
        question="In un Resonant BandPass Filter a 1.000 Hz, cosa succede aumentando Q da 2 a 6?",
        options=[
            "Il picco rimane fisso a 0 dB ma la banda si allarga",
            "Il picco scende sotto 0 dB",
            "La banda si restringe e il guadagno al picco risonante cresce (da +6 dB a ~+15,6 dB)",
            "Il filtro si trasforma in un passa-basso",
        ],
        correct_index=2,
        explanation=(
            "Slide 9: al contrario del BandPass standard (0 dB al picco), nel Resonant BandPass il picco "
            "cresce con Q (+6 dB a Q=2, oltre +15 dB a Q=6)."
        ),
    ),
    QuizQuestion(
        id=7,
        slides_ref="Slide 10 – 11",
        question="Collegando in serie due BandPass del 2° ordine (1.000 Hz e 1.400 Hz, Q = 2), cosa si ottiene?",
        options=[
            "Un filtro risultante del 4° ordine con pendenza maggiore",
            "Un filtro che cancella entrambe le bande",
            "Un equalizzatore grafico a 30 bande",
            "Un banco parallelo a somma",
        ],
        correct_index=0,
        explanation=(
            "Slide 10: connettendo due filtri del 2° ordine in serie (cascata) le pendenze si sommano "
            "ottenendo una risposta risultante del 4° ordine."
        ),
    ),
    QuizQuestion(
        id=8,
        slides_ref="Slide 13",
        question="In un equalizzatore grafico a 30 bande (1/3 di ottava), perché troviamo 800 Hz invece di 793,7 Hz?",
        options=[
            "Perché i filtri non possono lavorare sotto gli 800 Hz",
            "Perché l'esatto intervallo 1000·2^(-1/3) = 793,7 Hz viene corretto per convenzione ISO a 800 Hz",
            "Perché 800 Hz è un quarto di ottava",
            "Solo nei filtri passa-alto",
        ],
        correct_index=1,
        explanation=(
            "Slide 13 NB: l'esatto intervallo di un terzo di ottava sotto 1.000 Hz sarebbe 793,7 Hz, ma gli "
            "equalizzatori lo arrotondano allo standard 800 Hz."
        ),
    ),
    QuizQuestion(
        id=9,
        slides_ref="Slide 14 – 15",
        question="Qual è la differenza principale tra un EQ grafico e un EQ parametrico?",
        options=[
            "L'EQ parametrico lavora sempre con più bande fisse (almeno 30)",
            "L'EQ parametrico usa di solito meno bande, ma permette di controllare Freq, Gain e Q per ciascuna",
            "L'EQ grafico usa solo filtri Shelving",
            "L'EQ parametrico non può attenuare le frequenze",
        ],
        correct_index=1,
        explanation=(
            "Slide 15: nell'equalizzatore parametrico si lavora con un numero di bande inferiore rispetto "
            "al grafico, controllando più parametri (frequenza, guadagno, Q/slope) per ciascuna banda."
        ),
    ),
    QuizQuestion(
        id=10,
        slides_ref="Slide 16 – 18",
        question="Quando usi una mandata Aux per il riverbero e una per i monitor da palco, come vanno impostate?",
        options=[
            "Entrambe Pre-Fader",
            "Entrambe Post-Fader",
            "Monitor in Pre-Fader (indipendente dal fader) ed Effetti in Post-Fader (dipendente dal fader)",
            "Dopo il Pan-Pot ma prima del guadagno d'ingresso",
        ],
        correct_index=2,
        explanation=(
            "Slide 16: la mandata monitor/foldback è generalmente Pre-Fader (così muovendo il fader di sala "
            "non cambi l'ascolto ai musicisti), mentre la mandata effetti è Post-Fader così il riverbero scala col fader."
        ),
    ),
]
