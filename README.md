# XoneK3 → Rekordbox MIDI Bridge

A Python MIDI bridge that lets an **Allen & Heath Xone:K3** control **Rekordbox** with the
depth of an official Pioneer controller — LEDs, loops, EQ, and all — by presenting itself to
Rekordbox as a **Pioneer DDJ-SX2**.

**Un puente MIDI en Python que hace que un Allen & Heath Xone:K3 controle Rekordbox con la
profundidad de un controlador Pioneer oficial** — LEDs, loops, EQ y todo — haciéndose pasar
ante Rekordbox por un **Pioneer DDJ-SX2**.

🇬🇧 [English](#english) · 🇪🇸 [Español](#español)

> ⚠️ Windows only (for now) · Tested with Rekordbox 5.8.7 · Not affiliated with AlphaTheta /
> Pioneer DJ or Allen & Heath. Educational / personal project.

---

## English

### What is this?

Rekordbox reserves its richest features (native jog behaviour, proper LED feedback, deck
controls, etc.) for officially supported Pioneer / AlphaTheta hardware. Third‑party
controllers are limited to basic "MIDI Learn".

This project gets around that: it creates a **virtual MIDI device named `PIONEER DDJ-SX2`**.
Rekordbox recognises it by name and loads the **full native DDJ-SX2 control profile**. In the
middle sits a Python script that:

1. Reads the real MIDI messages coming from your Xone:K3.
2. Translates / enriches them with custom logic.
3. Forwards them to the virtual "Pioneer" device that Rekordbox is listening to.
4. Reads the LED feedback coming back from Rekordbox and lights up the K3.

The mapping lives in editable YAML files, versioned in Git — not trapped inside Rekordbox's
database.

### Why does this exist?

The Xone:K3 was released in **October 2025** — it's brand new, the successor to the legendary
K2. Rekordbox has **no native support** for it, and Rekordbox reserves its best behaviour
(reliable LED feedback, native deck control, advanced features) for officially supported
Pioneer / AlphaTheta hardware. A third‑party controller like the K3 is stuck with basic
**MIDI Learn**: flaky or no LED feedback, restricted control, and a mapping locked inside
Rekordbox's database instead of living in versionable files.

And you can't just hand Rekordbox a mapping file either: it **validates** its device mapping
files (`.midi` / CSV) beyond their format, so hand‑made mappings — even ones dressed up to
look like an official device — get rejected.

So this project flips the approach. Instead of trying to make Rekordbox accept the K3, it
makes the K3 **present itself as hardware Rekordbox already fully supports** — a Pioneer
DDJ‑SX2 — and does the translation in the middle. That unlocks the complete native profile
(LEDs, loops, 4‑deck control) for a controller Rekordbox would otherwise cripple.

### How it works

```
   Xone:K3 (real)                Python bridge                 Rekordbox
  ┌─────────────┐   MIDI in   ┌────────────────────┐  virtual  ┌──────────────┐
  │  faders,    │ ──────────► │  midi_router.py    │   MIDI    │  sees a real │
  │  EQ, pads,  │             │  translate K3↔SX2  │ ────────► │  DDJ-SX2 and │
  │  encoders   │ ◄────────── │  (teVirtualMIDI)   │ ◄──────── │  loads its   │
  └─────────────┘  LED feed   └────────────────────┘  feedback │  native map  │
                                                                └──────────────┘
```

The virtual port is created with **teVirtualMIDI** (the driver that ships with loopMIDI), so
the bridge *is* the device. That's important: a plain loopMIDI loopback port would echo
Rekordbox's own LED feedback back into Rekordbox, causing phantom plays / cues. With
teVirtualMIDI the feedback comes to us instead — no loop.

### Features

- ✅ Full deck control on 4 decks: Play/Pause, Cue, Sync, EQ (hi/mid/low), volume faders,
  loops (auto‑loop on/off + size half/double).
- ✅ **Library browsing & preview**: browse with the scroll encoder, enter/exit folders, **load
  to any deck** (SHIFT + that deck's encoder push), and **scrub/seek** the cued track for
  previewing (SHIFT + that deck's encoder turn).
- ✅ **Headphone cue** per deck (grid row 1), with LED.
- ✅ **SHIFT layer**: hold the K3's SHIFT button for alternate functions — the bridge tracks
  SHIFT as internal state (the K3 doesn't change its codes under SHIFT).
- ✅ **Bidirectional LED feedback**: the K3's buttons light up following Rekordbox's real
  state, in the colours you configured in the Xone Controller Editor.
- ✅ **Plug‑and‑play startup**: forces Master Tempo + Quantize ON across all decks when
  Rekordbox connects (gated by Rekordbox's real state, so it never fights you).
- ✅ **Fader/EQ position memory**: remembers where you left the controls and restores them in
  Rekordbox on restart (the K3 can't report positions by itself — see Limitations).
- ✅ 14‑bit **hi‑res** faders/EQ, clean button "taps", and a clean Ctrl+C shutdown.
- ✅ Mapping in editable **YAML**, versionable in Git.

### Requirements

- **Windows 10/11**.
- **Python 3.12** — ⚠️ *not* 3.14: `python-rtmidi` has no prebuilt wheel for 3.14 and won't
  compile without Visual Studio. 3.12 installs a ready wheel in seconds.
- **loopMIDI** (free, by Tobias Erichsen) — you don't need to create a port in it; installing
  it provides the **teVirtualMIDI** driver + DLL that the bridge uses.
- **Rekordbox 5.x** (tested on 5.8.7).
- An **Allen & Heath Xone:K3** configured to match `config/xone_k3_input.yaml` (see Setup).

### Setup

1. **Install Python 3.12** (alongside any other version):
   ```powershell
   winget install Python.Python.3.12
   ```
2. **Install loopMIDI** (for the teVirtualMIDI driver): https://www.tobias-erichsen.de/software/loopmidi.html
   You do **not** need to create a port — the bridge creates its own `PIONEER DDJ-SX2`.
3. **Clone this repo** and create the environment:
   ```powershell
   git clone https://github.com/FedericoRatcliffe/xone-k3-rekordbox-bridge.git
   cd xone-k3-rekordbox-bridge
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. **Configure your Xone:K3** so it sends the mapping the bridge expects. The easy way: open
   the free *Xone Controller Editor*, load **[`hardware/Xone-K3-Factory-Map1.xml`](hardware/Xone-K3-Factory-Map1.xml)**
   and write it to the unit (details in **[hardware/README.md](hardware/README.md)**). It sets
   Layer 1 to **MIDI channel 15** with this mapping (what `config/xone_k3_input.yaml` expects):

   | Function | Col 1 | Col 2 | Col 3 | Col 4 | Type |
   |---|---|---|---|---|---|
   | Encoder turn (loop size) | CC 0 | CC 1 | CC 2 | CC 3 | Relative |
   | Encoder push (loop on/off) | Note 52 | Note 53 | Note 54 | Note 55 | Trigger |
   | EQ High | CC 4 | CC 5 | CC 6 | CC 7 | Absolute |
   | EQ Mid | CC 8 | CC 9 | CC 10 | CC 11 | Absolute |
   | EQ Low | CC 12 | CC 13 | CC 14 | CC 15 | Absolute |
   | Volume fader | CC 16 | CC 17 | CC 18 | CC 19 | Absolute |
   | Play/Pause | Note 24 | Note 25 | Note 26 | Note 27 | Trigger |
   | Cue | Note 28 | Note 29 | Note 30 | Note 31 | Gate |
   | Sync | Note 32 | Note 33 | Note 34 | Note 35 | Trigger |
   | Headphone cue (grid row 1) | Note 36 | Note 37 | Note 38 | Note 39 | Trigger |

   Global controls (not per‑deck): **Scroll turn** → CC 21 (relative, browse) · **Scroll push**
   → Note 14 (folder forward/back) · **SHIFT** button → Note 15.

5. In **Rekordbox → Preferences → Audio**, make sure the audio device is **your real
   interface**, *not* the DDJ-SX2 (the emulated device is not a real sound card).
6. **Run the bridge first, then open Rekordbox** (order matters — the bridge must grab the K3
   before Rekordbox does):
   ```powershell
   python src\main.py
   ```
7. Open **Rekordbox**. It detects `PIONEER DDJ-SX2`. If it offers to install the audio driver,
   click **Skip**. Load a track and play. 🎛️

### Usage

```powershell
python src\main.py            # full bridge (controls + LEDs + startup enable + position memory)
python src\main.py --dry-run  # translate & print only, no virtual device (safe to try first)
python src\main.py --no-leds  # skip LED feedback
python src\main.py --list     # list MIDI ports and exit
```

- Always start the bridge **before** Rekordbox.
- **Ctrl+C** stops it cleanly and saves fader/EQ positions.

### Configuration

- `config/xone_k3_input.yaml` — what each K3 control sends (per column / deck).
- `config/rekordbox_target.yaml` — which DDJ-SX2 MIDI codes to emulate, plus `startup_enable`
  (Master Tempo / Quantize) and hi‑res flags.
- Edit these to remap or extend without touching code.

### Utilities (debugging / learning)

- `python src\monitor.py` — print raw MIDI from the K3, decoded and labelled.
- `python src\test_send.py` — send known DDJ-SX2 messages to Rekordbox (isolate reception).
- `python src\test_led.py --note 24` — light K3 LEDs to discover the note→LED→colour mapping.

### Limitations & notes

- **Windows only** for now (teVirtualMIDI is Windows‑specific). macOS/Linux would need a
  different virtual‑MIDI layer.
- Built and tested against **Rekordbox 5.8.7** and one specific K3 factory mapping. Other
  versions/mappings may need tweaks.
- The **Xone:K3 cannot report its knob/fader positions on startup** (firmware limitation, same
  as the K2). The bridge works around this by remembering positions between runs; if you move
  the physical controls while everything is off, they'll be out of sync until you touch them.
- Rekordbox does **not** expose effect sub‑parameters (e.g. reverb Room Size / Decay) over
  MIDI — only effect depth + beat/time. For fine FX‑parameter control, route audio through
  Ableton (where a real reverb exposes those as MIDI‑mappable parameters).
- This works by matching a supported Pioneer device **name** so Rekordbox loads its native
  MIDI profile. It does not modify or crack Rekordbox. Use at your own risk.

### Credits

- Inspired by [davr/xoneK2-rbox](https://github.com/davr/xoneK2-rbox) (same idea, for the K2).
- Virtual MIDI via **teVirtualMIDI** / **loopMIDI** by
  [Tobias Erichsen](https://www.tobias-erichsen.de/).
- Not affiliated with AlphaTheta / Pioneer DJ or Allen & Heath. All trademarks belong to their
  owners.

---

## Español

### ¿Qué es esto?

Rekordbox reserva sus funciones más ricas (comportamiento nativo de jog, feedback de LEDs
como la gente, controles de deck, etc.) para hardware Pioneer / AlphaTheta oficial. Los
controladores de terceros quedan limitados al "MIDI Learn" básico.

Este proyecto esquiva esa restricción: crea un **dispositivo MIDI virtual llamado
`PIONEER DDJ-SX2`**. Rekordbox lo reconoce por el nombre y carga el **perfil nativo completo
del DDJ-SX2**. En el medio hay un script de Python que:

1. Lee los mensajes MIDI reales que manda tu Xone:K3.
2. Los traduce / enriquece con lógica propia.
3. Los reenvía al dispositivo "Pioneer" virtual que Rekordbox está escuchando.
4. Lee el feedback de LEDs que devuelve Rekordbox y prende las luces del K3.

El mapeo vive en archivos YAML editables, versionados en Git — no atrapado dentro de la base
de datos de Rekordbox.

### ¿Por qué existe esto?

El Xone:K3 salió en **octubre de 2025** — es nuevísimo, el sucesor del legendario K2.
Rekordbox **no tiene soporte nativo** para él, y reserva su mejor comportamiento (feedback de
LEDs confiable, control nativo de deck, funciones avanzadas) para hardware Pioneer / AlphaTheta
oficial. Un controlador de terceros como el K3 queda atado al **MIDI Learn** básico: feedback
de LEDs pobre o inexistente, control restringido, y un mapeo encerrado en la base de datos de
Rekordbox en vez de vivir en archivos versionables.

Y tampoco podés simplemente pasarle a Rekordbox un archivo de mapeo: **valida** sus archivos
de mapeo de dispositivo (`.midi` / CSV) más allá del formato, así que los mapeos hechos a mano
— incluso disfrazados de un dispositivo oficial — son rechazados.

Por eso este proyecto invierte el enfoque. En vez de intentar que Rekordbox acepte el K3, hace
que el K3 **se presente como hardware que Rekordbox ya soporta completamente** — un Pioneer
DDJ‑SX2 — y hace la traducción en el medio. Eso desbloquea el perfil nativo completo (LEDs,
loops, control de 4 decks) para un controlador que Rekordbox de otra forma capa.

### Cómo funciona

```
   Xone:K3 (real)               Puente Python                 Rekordbox
  ┌─────────────┐   MIDI in   ┌────────────────────┐  MIDI    ┌──────────────┐
  │  faders,    │ ──────────► │  midi_router.py    │ virtual  │  ve un       │
  │  EQ, pads,  │             │  traduce K3↔SX2    │ ───────► │  DDJ-SX2 real│
  │  encoders   │ ◄────────── │  (teVirtualMIDI)   │ ◄─────── │  y carga su  │
  └─────────────┘  LED feed   └────────────────────┘ feedback │  mapa nativo │
                                                                └──────────────┘
```

El puerto virtual se crea con **teVirtualMIDI** (el driver que viene con loopMIDI), así el
puente *es* el dispositivo. Esto es clave: un puerto loopback común de loopMIDI reflejaría el
propio feedback de LEDs de Rekordbox de vuelta hacia Rekordbox, causando plays / cues
fantasma. Con teVirtualMIDI el feedback nos llega a nosotros — sin loop.

### Funciones

- ✅ Control completo de deck en 4 decks: Play/Pause, Cue, Sync, EQ (hi/mid/low), faders de
  volumen, loops (auto‑loop on/off + tamaño half/double).
- ✅ **Navegación y pre-escucha**: browse con el encoder SCROLL, entrar/salir de carpetas,
  **cargar a cualquier deck** (SHIFT + el push del encoder de ese deck), y **scrubbear/buscar**
  dentro del tema cueado para pre-escucharlo (SHIFT + el turn del encoder de ese deck).
- ✅ **Headphone cue** por deck (grilla fila 1), con LED.
- ✅ **Capa SHIFT**: mantené el botón SHIFT del K3 para funciones alternativas — el bridge
  lleva el SHIFT como estado interno (el K3 no cambia sus códigos con SHIFT).
- ✅ **Feedback de LEDs bidireccional**: los botones del K3 se prenden siguiendo el estado
  real de Rekordbox, en los colores que configuraste en el Xone Controller Editor.
- ✅ **Arranque plug‑and‑play**: fuerza Master Tempo + Quantize a ON en los 4 decks cuando
  Rekordbox conecta (gateado por el estado real de RB, así nunca pelea con vos).
- ✅ **Memoria de posiciones de faders/EQ**: recuerda dónde dejaste los controles y los
  restaura en Rekordbox al reiniciar (el K3 no puede reportar posiciones solo — ver
  Limitaciones).
- ✅ Faders/EQ **hi‑res** de 14 bits, "toques" de botón limpios, y apagado prolijo con Ctrl+C.
- ✅ Mapeo en **YAML** editable, versionable en Git.

### Requisitos

- **Windows 10/11**.
- **Python 3.12** — ⚠️ *no* 3.14: `python-rtmidi` no tiene wheel para 3.14 y no compila sin
  Visual Studio. 3.12 instala un wheel listo en segundos.
- **loopMIDI** (gratis, de Tobias Erichsen) — no hace falta crear un puerto; instalarlo provee
  el driver + DLL de **teVirtualMIDI** que usa el puente.
- **Rekordbox 5.x** (probado en 5.8.7).
- Un **Allen & Heath Xone:K3** configurado para coincidir con `config/xone_k3_input.yaml`
  (ver Instalación).

### Instalación

1. **Instalá Python 3.12** (puede convivir con otras versiones):
   ```powershell
   winget install Python.Python.3.12
   ```
2. **Instalá loopMIDI** (por el driver teVirtualMIDI): https://www.tobias-erichsen.de/software/loopmidi.html
   **No** hace falta crear un puerto — el puente crea el suyo (`PIONEER DDJ-SX2`).
3. **Cloná el repo** y creá el entorno:
   ```powershell
   git clone https://github.com/FedericoRatcliffe/xone-k3-rekordbox-bridge.git
   cd xone-k3-rekordbox-bridge
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
4. **Configurá tu Xone:K3** para que mande el mapeo que el bridge espera. La vía fácil: abrí
   el *Xone Controller Editor* (gratis), cargá **[`hardware/Xone-K3-Factory-Map1.xml`](hardware/Xone-K3-Factory-Map1.xml)**
   y escribílo a la unidad (detalles en **[hardware/README.md](hardware/README.md)**). Deja el
   Layer 1 en **canal MIDI 15** con este mapeo (lo que espera `config/xone_k3_input.yaml`):

   | Función | Col 1 | Col 2 | Col 3 | Col 4 | Tipo |
   |---|---|---|---|---|---|
   | Encoder turn (tamaño loop) | CC 0 | CC 1 | CC 2 | CC 3 | Relativo |
   | Encoder push (loop on/off) | Note 52 | Note 53 | Note 54 | Note 55 | Trigger |
   | EQ High | CC 4 | CC 5 | CC 6 | CC 7 | Absoluto |
   | EQ Mid | CC 8 | CC 9 | CC 10 | CC 11 | Absoluto |
   | EQ Low | CC 12 | CC 13 | CC 14 | CC 15 | Absoluto |
   | Fader de volumen | CC 16 | CC 17 | CC 18 | CC 19 | Absoluto |
   | Play/Pause | Note 24 | Note 25 | Note 26 | Note 27 | Trigger |
   | Cue | Note 28 | Note 29 | Note 30 | Note 31 | Gate |
   | Sync | Note 32 | Note 33 | Note 34 | Note 35 | Trigger |
   | Headphone cue (grilla fila 1) | Note 36 | Note 37 | Note 38 | Note 39 | Trigger |

   Controles globales (no por deck): **Scroll turn** → CC 21 (relativo, browse) · **Scroll
   push** → Note 14 (carpeta adelante/atrás) · botón **SHIFT** → Note 15.

5. En **Rekordbox → Preferencias → Audio**, asegurate de que el dispositivo de audio sea **tu
   interfaz real**, *no* el DDJ-SX2 (el dispositivo emulado no es una placa de sonido real).
6. **Corré el puente primero, después abrí Rekordbox** (el orden importa — el puente tiene que
   agarrar el K3 antes que Rekordbox):
   ```powershell
   python src\main.py
   ```
7. Abrí **Rekordbox**. Detecta `PIONEER DDJ-SX2`. Si te ofrece instalar el driver de audio,
   dale **Omitir**. Cargá un track y a mezclar. 🎛️

### Uso

```powershell
python src\main.py            # puente completo (controles + LEDs + enable de arranque + memoria)
python src\main.py --dry-run  # solo traduce e imprime, sin dispositivo virtual (probalo primero)
python src\main.py --no-leds  # sin feedback de LEDs
python src\main.py --list     # lista los puertos MIDI y sale
```

- Arrancá siempre el puente **antes** que Rekordbox.
- **Ctrl+C** lo corta prolijo y guarda las posiciones de faders/EQ.

### Configuración

- `config/xone_k3_input.yaml` — qué manda cada control del K3 (por columna / deck).
- `config/rekordbox_target.yaml` — qué códigos MIDI del DDJ-SX2 emular, más `startup_enable`
  (Master Tempo / Quantize) y los flags hi‑res.
- Editalos para remapear o extender sin tocar código.

### Utilidades (debug / aprender)

- `python src\monitor.py` — imprime el MIDI crudo del K3, decodificado y etiquetado.
- `python src\test_send.py` — manda mensajes conocidos del DDJ-SX2 a Rekordbox (aislar recepción).
- `python src\test_led.py --note 24` — prende LEDs del K3 para descubrir el mapeo nota→LED→color.

### Limitaciones y notas

- **Solo Windows** por ahora (teVirtualMIDI es específico de Windows). En macOS/Linux haría
  falta otra capa de MIDI virtual.
- Hecho y probado contra **Rekordbox 5.8.7** y un mapeo de fábrica específico del K3. Otras
  versiones/mapeos pueden necesitar ajustes.
- El **Xone:K3 no puede reportar las posiciones de sus knobs/faders al iniciar** (limitación de
  firmware, igual que el K2). El puente lo compensa recordando las posiciones entre sesiones;
  si movés los controles físicos con todo apagado, van a quedar desincronizados hasta que los
  toques.
- Rekordbox **no** expone por MIDI los sub‑parámetros de efectos (ej. Room Size / Decay del
  reverb) — solo el depth + beat/time. Para control fino de parámetros de FX, ruteá el audio
  por Ableton (donde un reverb real expone esos parámetros como mapeables por MIDI).
- Esto funciona haciendo coincidir el **nombre** de un dispositivo Pioneer soportado para que
  Rekordbox cargue su perfil MIDI nativo. No modifica ni crackea Rekordbox. Usalo bajo tu
  propia responsabilidad.

### Créditos

- Inspirado en [davr/xoneK2-rbox](https://github.com/davr/xoneK2-rbox) (misma idea, para el K2).
- MIDI virtual con **teVirtualMIDI** / **loopMIDI** de
  [Tobias Erichsen](https://www.tobias-erichsen.de/).
- Sin afiliación con AlphaTheta / Pioneer DJ ni Allen & Heath. Las marcas pertenecen a sus
  respectivos dueños.
