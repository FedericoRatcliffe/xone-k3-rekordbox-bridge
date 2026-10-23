# Ejecutable para Windows (.exe)

El puente se puede empaquetar como un `.exe` con **PyInstaller**, para usarlo sin instalar
Python ni crear el entorno virtual.

## Generar el ejecutable

Requisito: el entorno `.venv` con Python 3.12 (ver [SETUP_WINDOWS.md](SETUP_WINDOWS.md)).

```powershell
.\build_exe.ps1
```

Si PowerShell bloquea el script:
`powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`

El script instala PyInstaller en el `.venv`, compila y deja:

```
dist\
├── XoneK3Bridge\
│   ├── XoneK3Bridge.exe     <- ejecutable (un solo archivo, ~10 MB)
│   └── config\              <- mapeos YAML, editables sin recompilar
└── XoneK3Bridge.zip         <- la carpeta anterior comprimida, lista para compartir
```

`build/` y `dist/` están en `.gitignore`: el ejecutable no se versiona, se regenera.

## Usar el ejecutable

1. En la PC donde se use, instalá **loopMIDI** (por el driver teVirtualMIDI; no hace falta
   crear ningún puerto). El driver **no** va dentro del `.exe`.
2. Copiá la carpeta `XoneK3Bridge\` completa (o descomprimí el `.zip`). El `.exe` necesita la
   carpeta `config\` a su lado.
3. Enchufá el K3, abrí `XoneK3Bridge.exe` (doble click) y **después** abrí Rekordbox.
4. Para cerrarlo: **Ctrl+C** en la consola (así guarda las posiciones de faders/EQ en
   `state\positions.json`, al lado del `.exe`).

Los mismos flags que la versión Python funcionan desde una terminal:

```powershell
.\XoneK3Bridge.exe --list
.\XoneK3Bridge.exe --dry-run
.\XoneK3Bridge.exe --no-leds
.\XoneK3Bridge.exe --verbose
```

Si algo falla al arrancar (por ejemplo el K3 no está enchufado), la consola queda abierta
mostrando el error hasta que presiones Enter.

## Cómo funciona por dentro

- `src/midi_router.py` detecta si corre empaquetado (`sys.frozen`) y en ese caso toma como raíz
  la carpeta del `.exe`, no la del código fuente. Por eso `config\` y `state\` viven al lado del
  ejecutable.
- `mido` elige su backend MIDI en tiempo de ejecución, así que el build declara a mano
  `--hidden-import mido.backends.rtmidi` y `--collect-submodules rtmidi`.
- Es `--onefile`: al abrirlo, el `.exe` se descomprime en una carpeta temporal y lanza un
  proceso hijo. Si lo cerrás desde el Administrador de tareas, cerrá **los dos**
  procesos `XoneK3Bridge.exe`; si no, el puerto virtual `PIONEER DDJ-SX2` queda abierto.
- Algunos antivirus marcan los `.exe` de PyInstaller como sospechosos (falso positivo). Si
  pasa, agregá una excepción o usá la versión Python.
