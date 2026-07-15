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

## 3. loopMIDI (puerto MIDI virtual)

En Windows, `python-rtmidi` no puede crear puertos virtuales por sí solo, por eso usamos
**loopMIDI** (gratis, de Tobias Erichsen) para crear el puerto a nivel de sistema.

1. Descargar e instalar loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html
2. Abrir loopMIDI y crear un puerto nuevo. El **nombre importa** (ver más abajo).
3. Dejarlo abierto: el puerto existe mientras loopMIDI corre.

### Nombre del puerto virtual (IMPORTANTE)

Rekordbox reconoce el dispositivo por **name-matching**: si el puerto se llama igual que
un controlador Pioneer soportado, RB carga su perfil nativo. Emulamos el **DDJ-SX2**, así
que el puerto de loopMIDI tiene que llamarse **exactamente**:

```
PIONEER DDJ-SX2
```

(en loopMIDI, escribí ese nombre en "New port-name" y dale "+"). Puede que Windows le
agregue un sufijo tipo `PIONEER DDJ-SX2 1` — no pasa nada, el puente lo detecta por
substring, y para el name-matching de RB probamos ambas variantes.

> Para el paso de solo escuchar el K3 (monitor.py) NO hace falta loopMIDI. Sí hace falta
> para el forward real hacia Rekordbox.

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
16  control_change   16 100  Fader (Volumen)  [Col 1]
```

- Si la columna `ch` muestra **16** en vez de 15, es por el tema del nibble hex F — lo
  confirmamos acá y ajustamos `config/xone_k3_input.yaml`.
- Si algún control no coincide con la etiqueta esperada, lo anotamos y corregimos el mapa.
