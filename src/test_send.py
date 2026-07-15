"""
test_send.py — Diagnóstico de RECEPCIÓN. Manda mensajes DDJ-SX2 conocidos al puerto
virtual, SIN depender del K3, para aislar si Rekordbox recibe/reacciona a nuestro MIDI.

Con Rekordbox abierto (vista MIXER activada) y este script corriendo, mirá el Deck 1:

    python src/test_send.py            # barre el fader de volumen del Deck 1 (CC 0x13) en loop
    python src/test_send.py --play     # toggle Play/Pause del Deck 1 cada 2s (cargá un track)
    python src/test_send.py --deck 2   # probar otro deck
    python src/test_send.py --out DDJ-SX2

Lectura del resultado:
  - El fader/play en pantalla SE MUEVE  -> RB SÍ recibe. El problema está antes (K3/traducción).
  - No se mueve NADA                    -> RB NO recibe. Problema de loopMIDI / puerto / RB.
"""
from __future__ import annotations

import argparse
import sys
import time

import mido


def pick_out(preferred: str | None) -> str:
    ports = mido.get_output_names()
    if not ports:
        sys.exit("No hay puertos de salida. ¿Abriste loopMIDI?")
    needles = (preferred.lower(),) if preferred else ("pioneer ddj-sx2", "ddj-sx2", "loopmidi")
    for needle in needles:
        for p in ports:
            if needle in p.lower():
                return p
    sys.exit("No encontré el puerto de salida. Puertos:\n  " + "\n  ".join(ports))


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnóstico: manda MIDI DDJ-SX2 al puerto virtual")
    ap.add_argument("--out", help="Substring del puerto de salida")
    ap.add_argument("--play", action="store_true", help="Toggle Play/Pause en vez de barrer el fader")
    ap.add_argument("--deck", type=int, default=1, help="Deck 1-4")
    args = ap.parse_args()

    ch = args.deck - 1  # deck 1..4 -> canal 0..3
    name = pick_out(args.out)
    print(f"Salida: {name}   (Deck {args.deck} -> canal MIDI {ch})")
    print("Mirá Rekordbox. Ctrl+C para salir.\n")

    with mido.open_output(name) as out:
        try:
            if args.play:
                while True:
                    out.send(mido.Message("note_on", channel=ch, note=11, velocity=127))
                    out.send(mido.Message("note_off", channel=ch, note=11, velocity=0))
                    print("Play/Pause -> toggle (note 0x0B)")
                    time.sleep(2)
            else:
                # HiRes 14-bit: MSB en CC 19 (0x13) + LSB en CC 51 (0x33).
                sweep = list(range(0, 128, 2)) + list(range(126, -1, -2))
                while True:
                    for v in sweep:
                        v14 = round(v / 127 * 16383)
                        out.send(mido.Message("control_change", channel=ch, control=19, value=(v14 >> 7) & 0x7F))
                        out.send(mido.Message("control_change", channel=ch, control=51, value=v14 & 0x7F))
                        print(f"fader Deck {args.deck} -> {v:>3}  (HiRes CC 0x13+0x33)", end="\r")
                        time.sleep(0.03)
        except KeyboardInterrupt:
            print("\nChau.")


if __name__ == "__main__":
    main()
