# Setup en Windows

## 1. Python 3.12 (importante)

`python-rtmidi` todavía **no tiene wheel precompilado para Python 3.14**. En 3.14 `pip`
intenta compilar desde C y falla si no tenés Visual Studio Build Tools. En vez de instalar
un compilador de varios GB, usá **Python 3.12** (tiene wheel listo, instala en segundos).

Instalá 3.12 en paralelo a tu 3.14 (conviven sin problema):

```powershell
winget install Python.Python.3.12
```

## 2. Crear el entorno virtual con 3.12

Desde la carpeta del proyecto (`xone-k3-bridge/`):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si `Activate.ps1` da error de permisos:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## 3. loopMIDI (solo por el driver teVirtualMIDI)

En Windows, `python-rtmidi` no puede crear puertos virtuales por sí solo. Pero **no** creamos
un puerto en loopMIDI: el puente crea el suyo (`PIONEER DDJ-SX2`) por código, usando
**teVirtualMIDI** — el driver que está por debajo de loopMIDI.

¿Por qué teVirtualMIDI y no un puerto loopMIDI común? Un puerto loopMIDI es un *loopback*:
reflejaría el feedback de LEDs de Rekordbox de vuelta hacia Rekordbox, causando plays / cues
fantasma. Con teVirtualMIDI, el puente **es** el dispositivo, así que ese feedback nos llega a
nosotros — sin loop.

Lo único que necesitás de loopMIDI es que **instale el driver**:

1. Descargá e instalá loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html
2. Listo. **No** hace falta abrir loopMIDI ni crear ningún puerto. El instalador deja el
   driver `teVirtualMIDI64.sys` y el DLL `C:\Windows\System32\teVirtualMIDI64.dll`, que es lo
   que usa `src/te_virtualmidi.py`.

> Para solo escuchar el K3 (`monitor.py`) no hace falta ni loopMIDI. El puerto virtual solo se
> usa para el forward real hacia Rekordbox (`main.py`).

## 4. Validación mínima (paso 3): escuchar el K3

Enchufá el K3 por USB y corré:

```powershell
python src\monitor.py --list     # ver los puertos; deberías ver algo con "XONE" o "K3"
python src\monitor.py            # escuchar y mover controles
```

Al mover un control vas a ver el mensaje MIDI decodificado y etiquetado, p. ej.:

```
ch  tipo            num val  control
----------------------------------------------------
15  control_change   16 100  Fader (Volumen)  [Col 1]
```

- El K3 manda en **canal 15** (en mido, 0-based, es el canal 14). Si ves otro canal,
  ajustá `device.midi_channel` en `config/xone_k3_input.yaml`.
- Si algún control no coincide con la etiqueta esperada, corregí el mapa en ese YAML.

## 5. Correr el puente completo

Con el K3 enchufado y **Rekordbox cerrado**:

```powershell
python src\main.py     # crea "PIONEER DDJ-SX2" y agarra el K3
```

Después abrí Rekordbox (detecta el DDJ-SX2). El orden importa: el puente primero. Ver el
README para el flujo completo, flags y solución de problemas.
