"""
main.py — Entry point del puente:  K3  <->  puerto virtual "PIONEER DDJ-SX2"  <->  Rekordbox

Flujo completo (bidireccional):
  - CONTROLES: K3 (in) -> traducimos -> puerto virtual -> Rekordbox.
  - LEDs:      Rekordbox -> puerto virtual -> traducimos al revés -> K3 (out) -> se prenden.

El puerto virtual lo CREAMOS con teVirtualMIDI (no loopMIDI), así el puente ES el dispositivo
y no hay loop de feedback.

IMPORTANTE: no tiene que haber un puerto loopMIDI con el mismo nombre abierto (chocarían).
Cerrá loopMIDI. Y arrancá el puente ANTES de abrir Rekordbox (así agarra el K3 primero).

Uso:
    python src/main.py --dry-run     # traduce e imprime, sin crear el puerto virtual ni LEDs
    python src/main.py               # forward completo + LEDs
    python src/main.py --in XONE
    python src/main.py --no-leds     # sin feedback de LEDs
    python src/main.py --list        # lista puertos y sale
"""
from __future__ import annotations

import argparse
import sys
import threading

import mido

from midi_router import MidiRouter, load_yaml, INPUT_CFG, TARGET_CFG
from te_virtualmidi import VirtualMidiPort


def pick(ports: list[str], preferred: str | None, needles: tuple[str, ...]) -> str | None:
    if preferred:
        for p in ports:
            if preferred.lower() in p.lower():
                return p
        return None
    for needle in needles:
        for p in ports:
            if needle in p.lower():
                return p
    return None


def clear_leds(k3_out, channel: int) -> None:
    """Apaga todos los LEDs del K3 (note_on velocity 0 en todas las notas)."""
    for n in range(128):
        k3_out.send(mido.Message("note_on", channel=channel, note=n, velocity=0))


def feedback_loop(vport: VirtualMidiPort, router: MidiRouter, k3_out) -> None:
    """Hilo: recibe feedback de RB, lo traduce a LEDs y lo manda al K3.
    Como el puente ES el device (no loopback), esto NO vuelve a RB -> sin loop."""
    parser = mido.Parser()
    while True:
        data = vport.get()
        if data is None:      # el puerto se cerró
            return
        parser.feed(data)
        for rb_msg in parser:
            for led in router.translate_feedback(rb_msg):
                if k3_out is not None:
                    k3_out.send(led)


def main() -> None:
    ap = argparse.ArgumentParser(description="Puente MIDI Xone K3 <-> DDJ-SX2 <-> Rekordbox")
    ap.add_argument("--dry-run", action="store_true", help="Traduce e imprime, sin puerto virtual ni LEDs")
    ap.add_argument("--in", dest="in_port", help="Substring del puerto de entrada (K3)")
    ap.add_argument("--no-leds", action="store_true", help="No mandar feedback de LEDs al K3")
    ap.add_argument("--list", action="store_true", help="Lista puertos y sale")
    args = ap.parse_args()

    if args.list:
        print("Entradas:", *(f"\n  - {p}" for p in mido.get_input_names()))
        print("Salidas :", *(f"\n  - {p}" for p in mido.get_output_names()))
        return

    router = MidiRouter(load_yaml(INPUT_CFG), load_yaml(TARGET_CFG))
    target_name = load_yaml(TARGET_CFG).get("target", {}).get("device_name", "PIONEER DDJ-SX2")

    in_name = pick(mido.get_input_names(), args.in_port, ("xone", "k3"))
    if not in_name:
        sys.exit("No encontré el K3 en las entradas. ¿Está enchufado? (probá --list)")
    print(f"Entrada (K3):       {in_name}")

    vport = None
    k3_out = None
    if args.dry_run:
        print("Salida:             --dry-run (sin puerto virtual ni LEDs)")
    else:
        vport = VirtualMidiPort(target_name)
        print(f"Salida (virtual):   {target_name}  (teVirtualMIDI, sin loop)")
        if not args.no_leds:
            out_name = pick(mido.get_output_names(), None, ("xone", "k3"))
            if out_name:
                k3_out = mido.open_output(out_name)
                clear_leds(k3_out, router.k3_channel)
                print(f"LEDs (K3 out):      {out_name}")
            else:
                print("LEDs:               (no encontré la salida del K3; sin LEDs)")
        threading.Thread(target=feedback_loop, args=(vport, router, k3_out), daemon=True).start()

    print("\nMové controles del K3. Ctrl+C para salir.\n")

    with mido.open_input(in_name) as inport:
        try:
            for msg in inport:
                outs = router.translate(msg)
                for o in outs:
                    if vport:
                        vport.send(bytes(o.bytes()))
                    print(f"  K3 {msg.type:<13} -> {o}")
                if not outs and msg.type in ("control_change", "note_on", "note_off"):
                    print(f"  K3 {msg.type:<13} (sin mapeo) {msg}")
        except KeyboardInterrupt:
            print("\nChau.")
        finally:
            if k3_out is not None:
                clear_leds(k3_out, router.k3_channel)
                k3_out.close()
            if vport:
                vport.close()


if __name__ == "__main__":
    main()
