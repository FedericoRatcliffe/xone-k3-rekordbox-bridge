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
    python src/main.py --verbose     # además loguea cada mensaje (SOLO debug: agrega latencia)
    python src/main.py --in XONE
    python src/main.py --no-leds     # sin feedback de LEDs
    python src/main.py --list        # lista puertos y sale
"""
from __future__ import annotations

import argparse
import sys
import threading
import time

import mido

from midi_router import MidiRouter, load_yaml, INPUT_CFG, TARGET_CFG, ROOT
from te_virtualmidi import VirtualMidiPort
from positions import load_positions, save_positions

STATE_FILE = ROOT / "state" / "positions.json"

# Lock para escribir en la salida del K3 desde 2 lados sin pisarse: el hilo de feedback
# (LEDs de RB) y el hilo principal (LEDs de EQ kill).
_led_lock = threading.Lock()


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


def replay_scheduler(vport: VirtualMidiPort, router: MidiRouter) -> None:
    """Reasienta las posiciones de faders/EQ varias veces tras conectar RB.
    RB tarda en abrir su entrada MIDI e inicializar el mixer, así que un solo envío se pierde.
    Es seguro repetir: `replay_positions` manda la posición ACTUAL (si movés algo, manda ese
    valor nuevo), así que no pelea con lo que toques."""
    for delay in (0.3, 0.7, 1.5, 3.0, 5.0):
        time.sleep(delay)
        for m in router.replay_positions():
            vport.send(bytes(m.bytes()))


def feedback_loop(vport: VirtualMidiPort, router: MidiRouter, k3_out) -> None:
    """Hilo: recibe feedback de RB. Lo usa para (1) LEDs del K3 y (2) forzar Master Tempo /
    Quantize a ON al arrancar. Como el puente ES el device (no loopback), no hay loop."""
    parser = mido.Parser()
    enforced: set = set()
    replayed = False
    while True:
        data = vport.get()
        if data is None:      # el puerto se cerró
            return
        if not replayed:      # RB acaba de conectar -> restauramos posiciones (varias veces)
            replayed = True
            threading.Thread(target=replay_scheduler, args=(vport, router), daemon=True).start()
            print(f"[startup] restaurando posiciones de faders/EQ ({len(router.positions)} controles)...")
        parser.feed(data)
        for rb_msg in parser:
            # (1) LEDs: RB -> K3
            for led in router.translate_feedback(rb_msg):
                if k3_out is not None:
                    with _led_lock:
                        k3_out.send(led)
            # (2) Startup enable: forzar Master Tempo / Quantize a ON (una vez, si están OFF)
            toggle, log = router.feedback_enforce(rb_msg, enforced)
            for m in toggle:
                vport.send(bytes(m.bytes()))
            if log:
                print(log)


def main() -> None:
    ap = argparse.ArgumentParser(description="Puente MIDI Xone K3 <-> DDJ-SX2 <-> Rekordbox")
    ap.add_argument("--dry-run", action="store_true", help="Traduce e imprime, sin puerto virtual ni LEDs")
    ap.add_argument("--in", dest="in_port", help="Substring del puerto de entrada (K3)")
    ap.add_argument("--no-leds", action="store_true", help="No mandar feedback de LEDs al K3")
    ap.add_argument("--list", action="store_true", help="Lista puertos y sale")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Loguea cada mensaje traducido (imprimir en consola agrega latencia; solo debug)")
    args = ap.parse_args()
    # En dry-run el log ES el output, así que ahí siempre imprimimos.
    verbose = args.verbose or args.dry_run

    if args.list:
        print("Entradas:", *(f"\n  - {p}" for p in mido.get_input_names()))
        print("Salidas :", *(f"\n  - {p}" for p in mido.get_output_names()))
        return

    router = MidiRouter(load_yaml(INPUT_CFG), load_yaml(TARGET_CFG))
    router.positions.update(load_positions(STATE_FILE))   # superpone lo guardado sobre los defaults
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

                # LED sender para EQ kill (prende/apaga el botón; thread-safe con el lock).
                def _led_sender(note, on, _out=k3_out, _ch=router.k3_channel):
                    with _led_lock:
                        _out.send(mido.Message("note_on", channel=_ch, note=note, velocity=127 if on else 0))
                router.led_sender = _led_sender
            else:
                print("LEDs:               (no encontré la salida del K3; sin LEDs)")
        threading.Thread(target=feedback_loop, args=(vport, router, k3_out), daemon=True).start()

    hint = "" if verbose else "  (--verbose para ver cada mensaje)"
    print(f"\nPuente andando. Mové controles del K3. Ctrl+C para salir.{hint}\n")

    with mido.open_input(in_name) as inport:
        try:
            # Sondeo no bloqueante + micro-pausa: así Ctrl+C se atrapa al instante
            # (el bucle bloqueante clásico se queda trabado en código nativo y lo ignora).
            # OJO: acá NO se imprime por mensaje salvo --verbose. Imprimir en la consola de
            # Windows tarda varios ms y encola los mensajes siguientes -> knobs con lag.
            while True:
                for msg in inport.iter_pending():
                    outs = router.translate(msg)
                    for o in outs:
                        if vport:
                            vport.send(bytes(o.bytes()))
                        if verbose:
                            print(f"  K3 {msg.type:<13} -> {o}")
                    if verbose and not outs and msg.type in ("control_change", "note_on", "note_off"):
                        print(f"  K3 {msg.type:<13} (sin mapeo) {msg}")
                time.sleep(0.002)
        except KeyboardInterrupt:
            print("\nChau.")
        finally:
            if not args.dry_run:
                save_positions(STATE_FILE, router.positions)   # recordar posiciones para la próxima
                print("Posiciones guardadas.")
            if k3_out is not None:
                clear_leds(k3_out, router.k3_channel)
                k3_out.close()
            if vport:
                vport.close()


if __name__ == "__main__":
    main()
