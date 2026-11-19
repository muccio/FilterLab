# 🎛️ FilterLab — Digital Filter & EQ Didactic Lab

**FilterLab** è un'applicazione desktop multipiattaforma per **macOS e Windows** dedicata all'apprendimento e alla sperimentazione pratica in tempo reale dei **filtri digitali**, dell'**equalizzazione** e del **routing nel mixer audio** (*Channel Strip*).

Sviluppato all'interno della suite **Musica Applicata**, il software traduce fedelmente il percorso teorico completo delle **18 slide didattiche** in moduli interattivi collegati direttamente a un motore DSP real-time.

---

## 📚 Componente Didattica (10 Moduli + Quiz — Slide 1–18)

| Modulo | Argomento | Slide di Riferimento | Concetti & Esperimenti |
| :---: | :--- | :---: | :--- |
| **1** | **Cosa sono i Filtri Digitali & Gli EQ** | Slide 1 – 2 | Blackbox, campioni discreti $\Delta t$, prodotto spettri, timbro & Moog Ladder |
| **2** | **LowPass e HighPass** | Slide 3 – 4 | Frequenza di taglio (Cutoff @ −3 dB), passband/stopband su White Noise 1 kHz |
| **3** | **BandPass & BandReject (Notch)** | Slide 5 – 6 | $BW = f_H - f_L$, centro geometrico $f_c = \sqrt{f_L \cdot f_H}$ (es. 1789 Hz, 1949.35 Hz) |
| **4** | **Quality Factor ($Q$) & Ringing** | Slide 7 & 9 | $Q = f_c/BW$, risposta nel tempo proporzionale a $Q$, BandPass Standard vs Risonante |
| **5** | **Ordine del Filtro, Roll-Off e Butterworth** | Slide 7 – 8 | Filtro ideale vs reale (*transition zone*), 1° ord (6 dB/oct), 2° ord Butterworth (12 dB/oct), 4° ord (24 dB/oct) |
| **6** | **Connessione in Serie vs Parallelo** | Slide 10 – 11 | Channel Strip in cascata (BP 4° ordine da due 2° ordine) e sommatore parallelo (`40, 80, 120, 160 Hz`) |
| **7** | **Banchi di Filtri & Inviluppi** | Slide 11 – 12 | Rami paralleli `BP → LP → HP` con modulazione dinamica (LFO/inviluppi) |
| **8** | **EQ Grafica (10, 20, 30 Bande ISO)** | Slide 13 | Bande a 1 ottava, 1/2 ottava, 1/3 di ottava (`25 Hz – 20 kHz`), correzione ISO `793.7 Hz → 800 Hz` |
| **9** | **Shelving, Peak/Notch ed EQ Parametrico** | Slide 14 – 15 | Low/High Shelf (*emphasis/attenuation*, *shelf point*), Peak/Notch, EQ a 6 bande parametriche |
| **10** | **Mixer Channel Strip: Aux, Fader, PFL & Routing** | Slide 16 – 18 | Mandate Aux Pre/Post-Fader, Fader nominale (−10 dB dal max), Mute, PFL/Solo, VU/Overload, Pan-Pot (`Mono → Stereo`) |

Include inoltre un **Quiz di Verifica a 10 domande** con correzione immediata e spiegazioni legate alle slide, oltre a pulsanti **"🧪 Prova nel Laboratorio ▶"** per caricare all'istante ogni configurazione sperimentale nel laboratorio audio.

---

## 🔬 Laboratorio Pratico DSP Real-Time

### 3 Sorgenti Audio Selezionabili
- **Sorgente Interna (Generatore di Segnali):**
  - *Rumore Bianco* (Gaussiano) e *Rumore Rosa* (-3 dB/oct, filtro di Paul Kellet)
  - *Treno di Impulsi Dirac* (0.5–8 Hz) per ascoltare e misurare il **ringing** al variare di $Q$
  - *Onda Dente di Sega (Saw)* e *Onda Quadra (Square)* anti-aliased (PolyBLEP)
  - *Sinusoide Pura* (20–16000 Hz) e *Sweep Logaritmico* continuo (20 Hz → 20 kHz)
  - *Accordo Synth Polifonico* per prove musicali e su *Moog Ladder*
- **File Audio Esterni:** caricamento diretto o Drag & Drop di `WAV`, `AIFF`, `FLAC`, `OGG`, `MP3` (e `M4A`/`AAC`/`CAF` su macOS), con player Play/Pause/Stop/Loop e waveform click-to-seek.
- **Microfono Live (Ingresso Hardware):** elaborazione full-duplex a bassa latenza con selettore periferica e controlli di gain.

### Analisi & 4 Workbench
- **Grafico Bode & Spettro FFT Duale:** curva di risposta in frequenza composita e individuale, curva di fase, filtro ideale tratteggiato con *transition zone*, spettro FFT Pre-Filtro (ambra) vs Post-Filtro (ciano) in tempo reale e **nodi trascinabili direttamente col mouse** (Frequenza, Gain e rotellina per Q).
- **Analizzatore nel Dominio del Tempo:** commutabile tra *Risposta all'Impulso $h[n]$ (Ringing in ms)*, *Oscilloscopio Live In/Out* e *Vista Blackbox Campioni $\Delta t$* (Slide 2).
- **4 Workbench:** *Singolo Filtro* (incluso Moog Ladder 4 poli), *Serie / Parallelo / Banco Modulato*, *EQ Grafica ISO (10/20/30 bande)* ed *EQ Parametrica (6 bande)*.
- **Channel Strip & Output Mixer:** Input Trim, Bypass A/B, Aux Send Pre/Post-Fader con Aux Riverbero opzionale e Aux Meter, PFL (Solo), Mute, Pan-Pot (`Mono → Stereo`), Fader calibrato con livello nominale 0 dB, Peak Meter Stereo con LED Overload e Safety Limiter.

---

## 📦 Download & Installazione (Release)

Scarica i pacchetti precompilati dalla sezione **[GitHub Releases](https://github.com/muccio/FilterLab/releases)**:

- **macOS (Apple Silicon `arm64` / Intel `x86_64`):**
  - `FilterLab-1.0.1-macos-<arch>.dmg` — Apri il DMG e trascina `FilterLab.app` in `Applicazioni`.
  - `FilterLab-1.0.1-macos-<arch>.app.zip` — Archivio portatile pronto all'uso.
- **Windows (`x64`):**
  - `FilterLab-Setup-1.0.1-windows-x64.exe` — Installer guidato Inno Setup con collegamenti Start/Desktop.
  - `FilterLab-1.0.1-windows-x64-portable.zip` — Cartella portatile con `FilterLab.exe`.

---

## 🛠️ Avvio da Codice Sorgente & Sviluppo

Requisiti: Python 3.11+ (consigliato 3.12). Con [`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/muccio/FilterLab.git
cd FilterLab

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt pyinstaller pytest

# Avvio dell'applicazione
.venv/bin/python run.py
```

Su Windows (PowerShell):
```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt pyinstaller pytest
.venv\Scripts\python.exe run.py
```

### Esecuzione dei Test
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v tests/
```

### Build Locale Eseguibili
- **macOS:** `bash build_local.sh` (genera `dist/FilterLab.app`, `.app.zip` e `.dmg`)
- **Windows:** `powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1` (genera `dist/FilterLab/FilterLab.exe`, `.zip` portable e installer Setup `.exe` se Inno Setup 6 è installato)

---

## 📁 Struttura del Progetto

```text
FilterLab/
├── run.py                         # Entry point desktop & verifica bundle (--check-build)
├── pyproject.toml                 # Configurazione progetto & pytest
├── requirements.txt               # Dipendenze runtime
├── build_local.sh                 # Script rapido test + build macOS
├── src/
│   ├── dsp/
│   │   ├── filter_design.py       # Design filtri IIR/SOS, Moog Ladder, Bode, ISO EQ, Impulse/Ringing
│   │   ├── generators.py          # Generatori fase-continui (Noise, Impulsi, PolyBLEP, Sweep, Chord)
│   │   └── processor.py           # Processore real-time + Network/Bank/EQ + Channel Strip & Aux FX
│   ├── audio/
│   │   ├── file_loader.py         # Caricamento universale file audio, resampling, waveform peaks
│   │   └── engine.py              # Engine sounddevice (Internal, File, Mic) e ring buffers lock-safe
│   ├── didactics/
│   │   └── curriculum.py          # 10 moduli didattici (Slide 1-18), esperimenti guidati e 10 quiz
│   └── ui/
│       ├── styles.py              # Tema dark pro-audio QSS
│       ├── didactic_view.py       # Browser lezioni, schemi interattivi e quiz
│       ├── lab_view.py            # Laboratorio DSP, sorgenti, 4 workbench e Channel Strip
│       ├── main_window.py         # Finestra principale con Drag & Drop e selettore dispositivi
│       └── widgets/               # Bode/FFT, Dominio del Tempo, Diagrammi Didattici, Meters
├── tests/                         # Suite pytest (DSP, Processor/Routing, UI Smoke)
├── packaging/                     # Asset grafici, PyInstaller spec, runtime hook, script macOS/Win
└── .github/workflows/release.yml  # Pipeline CI/CD multi-OS & pubblicazione automatica Release
```

---

## 📄 Licenza

Distribuito sotto licenza **MIT** — vedi [LICENSE](LICENSE).
