r"""
te_virtualmidi.py — Wrapper mínimo (ctypes) del SDK teVirtualMIDI de Tobias Erichsen.

teVirtualMIDI es el driver que está POR DEBAJO de loopMIDI (ya instalado en tu sistema).
Diferencia clave con un puerto loopMIDI:
  - loopMIDI = loopback: refleja todo lo que se escribe -> Rekordbox escucha su propio
    feedback de LEDs -> se auto-reproduce / agrega cues (el bug que teníamos).
  - teVirtualMIDI = NUESTRO programa ES el dispositivo: el feedback de RB nos llega a
    nosotros (como a un controlador real), no se refleja a sí mismo. SIN loop.

DLL: C:\Windows\System32\teVirtualMIDI64.dll  (viene con loopMIDI, está en el PATH del sistema).
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

# Flags del SDK (teVirtualMIDI.h)
TE_VM_FLAGS_PARSE_RX = 1
TE_VM_FLAGS_PARSE_TX = 2
TE_VM_FLAGS_INSTANTIATE_RX_ONLY = 4
TE_VM_FLAGS_INSTANTIATE_TX_ONLY = 8
TE_VM_FLAGS_INSTANTIATE_BOTH = 12

MAX_SYSEX = 65535

_dll = ctypes.WinDLL("teVirtualMIDI64.dll", use_last_error=True)

# LPVM_MIDI_PORT virtualMIDICreatePortEx2(LPCWSTR name, cb, DWORD_PTR inst, DWORD maxSysex, DWORD flags)
_dll.virtualMIDICreatePortEx2.argtypes = [
    wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
]
_dll.virtualMIDICreatePortEx2.restype = ctypes.c_void_p

# BOOL virtualMIDISendData(LPVM_MIDI_PORT, LPBYTE, DWORD)
_dll.virtualMIDISendData.argtypes = [ctypes.c_void_p, ctypes.c_char_p, wintypes.DWORD]
_dll.virtualMIDISendData.restype = wintypes.BOOL

# BOOL virtualMIDIGetData(LPVM_MIDI_PORT, LPBYTE, LPDWORD)  -- BLOQUEANTE
_dll.virtualMIDIGetData.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(wintypes.DWORD)]
_dll.virtualMIDIGetData.restype = wintypes.BOOL

# void virtualMIDIClosePort(LPVM_MIDI_PORT)
_dll.virtualMIDIClosePort.argtypes = [ctypes.c_void_p]
_dll.virtualMIDIClosePort.restype = None


class VirtualMidiPort:
    """Puerto MIDI virtual propio. Aparece en Windows/Rekordbox con el nombre `name`."""

    def __init__(self, name: str, flags: int = TE_VM_FLAGS_INSTANTIATE_BOTH | TE_VM_FLAGS_PARSE_RX):
        self.name = name
        self._port = _dll.virtualMIDICreatePortEx2(name, None, None, MAX_SYSEX, flags)
        if not self._port:
            err = ctypes.get_last_error()
            raise OSError(
                f"No pude crear el puerto virtual '{name}' (teVirtualMIDI err={err}). "
                f"¿Hay un puerto loopMIDI con el MISMO nombre abierto? Borralo/cerrá loopMIDI."
            )

    def send(self, data) -> None:
        """Manda bytes MIDI crudos (p. ej. bytes(msg.bytes()) de mido) a Rekordbox."""
        buf = bytes(data)
        if not _dll.virtualMIDISendData(self._port, buf, len(buf)):
            raise OSError(f"virtualMIDISendData falló (err={ctypes.get_last_error()})")

    def get(self):
        """Bloquea hasta recibir datos de RB (feedback de LEDs). Devuelve bytes, o None si cerró."""
        buf = ctypes.create_string_buffer(MAX_SYSEX)
        length = wintypes.DWORD(MAX_SYSEX)
        if not _dll.virtualMIDIGetData(self._port, buf, ctypes.byref(length)):
            return None
        return buf.raw[: length.value]

    def close(self) -> None:
        if self._port:
            _dll.virtualMIDIClosePort(self._port)
            self._port = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
