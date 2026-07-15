# Xone:K3 controller configuration / Configuración del controlador

**English**

`Xone-K3-Factory-Map1.xml` is the **Xone:K3 configuration this bridge expects**. The bridge
translates *specific* MIDI notes/CCs (see `config/xone_k3_input.yaml`), so your K3 must be set
up to send exactly those. This file does that for you — it's a **required prerequisite**, not
something the Python script runs.

### How to load it

1. Download the free **Xone Controller Editor** from Allen & Heath:
   https://www.allen-heath.com/hardware/xone-series/xonek3/ (Resources / Downloads).
2. Connect your Xone:K3 by USB and open the editor.
3. Open / import **`Xone-K3-Factory-Map1.xml`** and **send / write** it to the unit.
4. Done — your K3 now sends the mapping the bridge understands.

### What it configures

- **MIDI channel 15** for everything.
- **Layer 1** mapping used by the bridge (see the table in the main [README](../README.md)):
  faders, EQ, encoders, Play/Cue/Sync and the pad grid.
- **LED colours** per button and per layer (the bridge lights these via feedback; the colour
  is defined here, not chosen by the script).
- Layers 2 and 3 are also mapped (free for future features).

> If you prefer to configure your K3 by hand instead of loading this file, replicate the
> mapping table in the main README. As long as the notes/CCs and channel 15 match
> `config/xone_k3_input.yaml`, the bridge will work.

---

**Español**

`Xone-K3-Factory-Map1.xml` es la **configuración del Xone:K3 que este bridge espera**. El
bridge traduce notas/CCs MIDI *específicos* (ver `config/xone_k3_input.yaml`), así que tu K3
tiene que estar configurado para mandar exactamente esos. Este archivo lo hace por vos — es un
**prerrequisito obligatorio**, no algo que corra el script de Python.

### Cómo cargarlo

1. Descargá el **Xone Controller Editor** (gratis) de Allen & Heath:
   https://www.allen-heath.com/hardware/xone-series/xonek3/ (Recursos / Descargas).
2. Conectá tu Xone:K3 por USB y abrí el editor.
3. Abrí / importá **`Xone-K3-Factory-Map1.xml`** y **enviálo / escribílo** a la unidad.
4. Listo — tu K3 ya manda el mapeo que el bridge entiende.

### Qué configura

- **Canal MIDI 15** para todo.
- El mapeo del **Layer 1** que usa el bridge (ver la tabla en el [README](../README.md)
  principal): faders, EQ, encoders, Play/Cue/Sync y la grilla de pads.
- **Colores de LED** por botón y por layer (el bridge los prende vía feedback; el color se
  define acá, no lo elige el script).
- Los Layers 2 y 3 también están mapeados (libres para futuras features).

> Si preferís configurar el K3 a mano en vez de cargar este archivo, replicá la tabla de
> mapeo del README principal. Mientras las notas/CCs y el canal 15 coincidan con
> `config/xone_k3_input.yaml`, el bridge va a funcionar.
