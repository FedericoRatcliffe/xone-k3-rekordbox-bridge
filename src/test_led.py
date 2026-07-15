"""
test_led.py — Descubrir el protocolo de LEDs del Xone K3.

El K3 prende LEDs recibiendo note_on en su puerto de ENTRADA (para nosotros, el OUTPUT
"XONE:K3"). En el K3 (como en el K2) el COLOR lo define QUÉ NOTA mandás: cada botón responde
a ~3 notas = 3 colores (offset +36), configurado en el Xone Controller Editor. velocity>0
prende, velocity 0 apaga.

Uso:
    python src/test_led.py --note 24            # prende SOLO la nota 24 y la mantiene
    python src/test_led.py --note 60            # 24+36 -> ¿mismo botón, otro color?
    python src/test_led.py                      # barre notas 0-127, una por vez (descubrir todo)
    python src/test_led.py --from 20 --to 60
    python src/test_led.py --channel 15         # canal 1-based (K3 manda/recibe en 15)
"""
from __future__ import annotations

import argparse
import sys
import time

import mido


def pick_out(preferred: str | None) -> str:
    ports = mido.get_output_names()
    needles = (preferred.lower(),) if preferred else ("xone", "k3")
    for n in needles:
        for p in ports:
            if n in p.lower():
                return p
    sys.exit("No encontré el K3 en salidas MIDI:\n  " + "\n  ".join(ports))


def all_off(out, ch: int) -> None:
    for n in range(128):
        out.send(mido.Message("note_on", channel=ch, note=n, velocity=0))


def main() -> None:
    ap = argparse.ArgumentParser(description="Descubridor de LEDs del Xone K3")
    ap.add_argument("--out", help="Substring del puerto de salida del K3")
    ap.add_argument("--channel", type=int, default=15, help="Canal MIDI 1-based (K3 = 15)")
    ap.add_argument("--note", type=int, help="Prende SOLO esta nota y la mantiene")
    ap.add_argument("--vel", type=int, default=127, help="Velocity a mandar (default 127)")
    ap.add_argument("--from", dest="lo", type=int, default=0, help="Nota inicial del barrido")
    ap.add_argument("--to", dest="hi", type=int, default=127, help="Nota final del barrido")
    ap.add_argument("--delay", type=float, default=0.35, help="Segundos por nota en el barrido")
    args = ap.parse_args()

    ch = args.channel - 1
    name = pick_out(args.out)
    print(f"Salida: {name}   canal {args.channel} (0-based {ch})\n")

    with mido.open_output(name) as out:
        try:
            if args.note is not None:
                out.send(mido.Message("note_on", channel=ch, note=args.note, velocity=args.vel))
                print(f"Nota {args.note} (vel {args.vel}) ENCENDIDA. ¿Qué LED prendió y de qué color?")
                print("Ctrl+C para apagar y salir.")
                while True:
                    time.sleep(1)
            else:
                print("Barriendo notas. Anotá qué LED prende en cada número.\n")
                for n in range(args.lo, args.hi + 1):
                    out.send(mido.Message("note_on", channel=ch, note=n, velocity=args.vel))
                    print(f"  nota {n:>3} ON")
                    time.sleep(args.delay)
                    out.send(mido.Message("note_on", channel=ch, note=n, velocity=0))
        except KeyboardInterrupt:
            pass
        finally:
            all_off(out, ch)
            print("\nApagado todo. Chau.")


if __name__ == "__main__":
    main()
