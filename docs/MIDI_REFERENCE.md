# MIDI Reference — K3 (entrada) y DDJ-SX2 emulado (salida)

## Cómo leer los códigos Pioneer (del CSV oficial)

Los `.midi.csv` de Rekordbox traen los códigos en hex de 4 dígitos, p. ej. `900B` o `B013`.
Se leen como **status byte + data byte**:

- `9x` = **Note On** en el canal `x`  → `900B` = Note On, canal 1, nota `0x0B` (11)
- `Bx` = **Control Change** en el canal `x` → `B013` = CC, canal 1, control `0x13` (19)

Y la clave del multi-deck Pioneer: **cada deck es un canal MIDI distinto**.
Un control "por deck" (deck1..deck4 = 0,1,2,3) usa el mismo número en canales 1..4:

| Deck | Note On | CC   |
|------|---------|------|
| 1    | `90`    | `B0` |
| 2    | `91`    | `B1` |
| 3    | `92`    | `B2` |
| 4    | `93`    | `B3` |

## Mapeo completo K3 → DDJ-SX2 (lo que emulamos)

### Capa normal (deck = canal MIDI; los de browser van en canal 7 / mido 6)

| Función K3              | K3 manda           | DDJ-SX2 emula          | Código SX2                |
|-------------------------|--------------------|------------------------|---------------------------|
| Play/Pause              | Note 24-27         | PlayPause              | Note `0x0B` (11)          |
| Cue                     | Note 28-31         | Cue                    | Note `0x0C` (12)          |
| Sync                    | Note 32-35         | Sync                   | Note `0x58` (88)          |
| EQ High                 | CC 4-7             | EQHigh                 | CC `0x07` (7)             |
| EQ Mid                  | CC 8-11            | EQMid                  | CC `0x0B` (11)            |
| EQ Low                  | CC 12-15           | EQLow                  | CC `0x0F` (15)            |
| Fader (Volumen)         | CC 16-19           | ChannelFader (HiRes)   | CC `0x13` (19)            |
| Encoder PUSH (Loop On)  | Note 52-55         | AutoLoop On/Off        | Note `0x14` (20)          |
| Encoder TURN (Loop Sz)  | CC 0-3 (relativo)  | LoopHalf / LoopDouble  | Note `0x12`/`0x13`        |
| Headphone Cue (fila 1)  | Note 36-39         | HeadphoneCue           | Note `0x54` (84)          |
| Browse (Scroll turn)    | CC 21 (relativo)   | Browse (Rotary)        | CC `0x40` (64), canal 7   |
| Scroll PUSH             | Note 14            | Forward (entrar carpeta)| Note `0x41` (65), canal 7 |

### Capa SHIFT (mantené el botón SHIFT = Note 15)

El K3 **no cambia sus códigos** con SHIFT: el bridge lleva `shift_pressed` como estado interno
(la Note 15 se intercepta y NO se reenvía a RB) y aplica el `shift_map`.

| Combo                        | DDJ-SX2 emula                    | Código SX2                          |
|------------------------------|---------------------------------|-------------------------------------|
| SHIFT + Encoder TURN (col X) | JogSearch (scrub en el tema) Deck X | CC `0x1F` (31), canal del deck  |
| SHIFT + Encoder PUSH (col X) | Load Track a Deck X             | Note `0x46`-`0x49` (70-73), canal 7 |
| SHIFT + Scroll PUSH          | Back (cerrar/subir carpeta)     | Note `0x65` (101), canal 7          |

> **JogSearch** es tipo "Difference" (relativo) e invierte el signo respecto al two's complement
> estándar: por eso `value 120` = adelante y `value 8` = atrás. El `value` regula la velocidad
> del scrub (más alto = más rápido).

> Los controles de **browser** (Browse, Forward, Back, Load) van en el **canal 7** (1-based;
> mido 0-based = 6), la sección "browser" del DDJ. En **Load**, el DECK lo define la NOTA
> (70-73), no el canal (a diferencia del resto, donde el deck = canal).

### Expandir la vista de biblioteca — NO es viable desde el K3
La función "BROWSE VIEW" (expandir/contraer la biblioteca) existe solo en DDJ-1000/400/800,
que Rekordbox detecta por **USB** (no por nombre de puerto MIDI, así que no se pueden emular);
el DDJ-SX2 no la tiene; y RB **ignora las teclas inyectadas** por software. Se hace con la
**barra espaciadora física** del teclado.

## FX en Rekordbox — hasta dónde llega el MIDI (importante)

Investigando los CSV oficiales, así modela Rekordbox 5 los efectos por MIDI:

**Beat FX** (unidad de efectos por deck/canal), expone SOLO:
- **Seleccionar** el efecto (REVERB es una opción entre ~15: echo, delay, flanger, etc.).
  En el CSV: `FX1-1Select.REVERB` = un botón que elige reverb.
- **Effect Depth**: UN knob continuo (`FX1-1` = "Effect Depth"). Es el "cuánto".
- **Beat / Time**: beat up/down (la división rítmica del efecto).
- **On/Off** y **Release FX**.

**Sound Color FX** (Noise / Echo / Pitch / Filter): un knob de "Depth" por canal (`CFXParameter`).

### Lo que NO existe en el MIDI de Rekordbox
No hay ningún target MIDI para **Room Size**, **Decay**, **Feedback** ni parámetros
internos de un efecto. Buscando `room` / `decay` en los 48 dispositivos oficiales: cero
resultados como parámetro. Esos knobs viven SOLO en la GUI de Rekordbox; el software no
los expone al protocolo MIDI. No es una traba del hardware que podamos esquivar con el
puente: Rekordbox simplemente no escucha MIDI para eso.

### El camino para Room Size / Decay de verdad: Ableton
Un reverb real (p. ej. el device Reverb de Ableton) SÍ expone Room Size, Decay Time,
Predelay, etc. como parámetros automatizables/MIDI-mapeables. Si querés esos knobs bajo
tus dedos, la jugada es rutear el audio por Ableton y que el puente mande MIDI a esos
parámetros. Encaja con tu extensión futura de "integración con Ableton" y con tu
experiencia previa (AbletonMCP).
