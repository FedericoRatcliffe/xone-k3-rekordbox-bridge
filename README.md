# XoneK3-Rekordbox MIDI Bridge

Puente MIDI en Python que se pone en el medio entre un **Allen & Heath Xone K3** y
**Rekordbox**, para desbloquear funciones que Rekordbox reserva al hardware Pioneer.

Inspirado en [davr/xoneK2-rbox](https://github.com/davr/xoneK2-rbox), adaptado al K3.

## La idea en una línea

Un puerto MIDI virtual con el **nombre de un controlador Pioneer soportado** hace que
Rekordbox lo trate como nativo (name-matching, RB no verifica hardware real). El script
Python lee el K3 real, traduce/enriquece los mensajes y los reenvía a ese puerto virtual;
y en el sentido inverso lleva el feedback (LEDs) de vuelta al K3.

```
K3 real  ──►  monitor/router (Python)  ──►  puerto virtual "Pioneer"  ──►  Rekordbox
   ▲                                                                            │
   └──────────────  feedback de LEDs  ◄────────────────────────────────────────┘
```

## Estado actual

- [x] Scaffold + config de entrada del K3 (`config/xone_k3_input.yaml`)
- [x] `src/monitor.py` — escuchar el K3 y decodificar sus mensajes (paso 3)
- [x] K3 leído y mapa de entrada validado (canal 15 / mido 14, todos los controles Col 1 OK)
- [x] Target elegido: **emular DDJ-SX2** (`config/rekordbox_target.yaml`) — controller completo, fader por MIDI
- [x] Forward escrito (`src/midi_router.py` + `src/main.py`)
- [x] **Rekordbox 5.8.7 detecta "PIONEER DDJ-SX2" como dispositivo nativo** (name-matching CONFIRMADO)
- [x] Puerto virtual con **teVirtualMIDI** (`src/te_virtualmidi.py`) — NO loopMIDI, para evitar el loop de feedback
- [x] Continuos **HiRes 14-bit** (MSB+LSB) y botones con "toque" limpio (on+off)
- [x] **FUNCIONA end-to-end**: Play/Cue/Sync, faders, EQ, loops (select + on/off) en los 4 decks ✅
- [x] **Feedback de LEDs bidireccional** (`src/test_led.py` + `translate_feedback` + `feedback_loop`): RB → K3, siguen el estado real en los colores del editor ✅
- [x] **Arranque plug-and-play**: fuerza Master Tempo + Quantize a ON en los 4 decks al conectar (gateado por el estado real de RB, no pelea)
- [x] **Persistencia de posiciones**: recuerda dónde dejaste faders/EQ y los restaura en RB al reiniciar (`src/positions.py`)
- [x] Apagado prolijo con Ctrl+C (sondeo no bloqueante) + versionado en Git
- [ ] Hot Cues (notas 40-43 libres del K3)
- [ ] Layers/shift custom, macros
- [ ] Layers/shift custom, macros

## Quickstart

Ver [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md). Resumen:

```powershell
py -3.12 -m venv .venv          # OJO: python-rtmidi no compila en 3.14, usar 3.12
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src\monitor.py           # enchufá el K3 y mové controles
```

## Estructura

```
xone-k3-bridge/
├── config/
│   └── xone_k3_input.yaml    # qué manda cada control del K3 (Layer 1 actual)
├── src/
│   └── monitor.py            # paso 3: escuchar y decodificar el K3
├── docs/
│   └── SETUP_WINDOWS.md      # loopMIDI + Python + validación
└── requirements.txt
```

A medida que avancemos se suman `midi_router.py`, `pioneer_emulator.py`,
`led_feedback.py`, `layers.py` y `config/rekordbox_target.yaml`.
