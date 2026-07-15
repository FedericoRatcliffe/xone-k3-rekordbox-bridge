"""
monitor.py — Paso 3 del bridge: escuchar el Xone K3 e imprimir sus mensajes MIDI.

Objetivo: validar que leemos bien el K3 y APRENDER qué CC/Note manda cada control.
Cruza cada mensaje contra config/xone_k3_input.yaml para etiquetarlo en humano
("moví el fader de la Col 1" -> CC 16).

Uso:
    python src/monitor.py --list           # lista puertos MIDI de entrada y sale
    python src/monitor.py                   # auto-detecta el K3 y escucha
    python src/monitor.py --port "XONE"     # elige puerto por substring del nombre
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import mido
except ImportError:
    sys.exit("Falta 'mido'. Instalá dependencias: pip install -r requirements.txt")

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "xone_k3_input.yaml"


def load_lookup(config_path: Path) -> dict:
    """dict {(tipo, numero): (label, columna)} a partir del YAML de entrada."""
    if yaml is None or not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    lookup: dict = {}
    for ctrl in (data.get("controls") or {}).values():
        label = ctrl.get("label", "?")
        for col, num in enumerate(ctrl.get("cc", []), start=1):
            lookup[("cc", num)] = (label, col)
        for col, num in enumerate(ctrl.get("note", []), start=1):
            lookup[("note", num)] = (label, col)
    return lookup


def annotate(msg, lookup: dict) -> str:
    if msg.type == "control_change":
        key = ("cc", msg.control)
    elif msg.type in ("note_on", "note_off"):
        key = ("note", msg.note)
    else:
        return ""
    label, col = lookup.get(key, ("", None))
    return f"{label}  [Col {col}]" if col else ""


def pick_port(preferred: str | None) -> str:
    ports = mido.get_input_names()
    if not ports:
        sys.exit("No hay puertos MIDI de entrada. ¿Enchufaste el K3 / abriste loopMIDI?")
    if preferred:
        for p in ports:
            if preferred.lower() in p.lower():
                return p
        sys.exit(f"No hay puerto con '{preferred}'. Disponibles:\n  " + "\n  ".join(ports))
    for needle in ("xone", "k3"):
        for p in ports:
            if needle in p.lower():
                return p
    if len(ports) == 1:
        return ports[0]
    sys.exit("No pude auto-detectar el K3. Usá --port <substring>. Puertos:\n  " + "\n  ".join(ports))


def main() -> None:
    ap = argparse.ArgumentParser(description="Monitor MIDI del Xone K3")
    ap.add_argument("--list", action="store_true", help="Lista puertos de entrada y sale")
    ap.add_argument("--port", help="Substring del nombre del puerto a abrir")
    args = ap.parse_args()

    if args.list:
        print("Puertos MIDI de entrada:")
        for p in mido.get_input_names():
            print(f"  - {p}")
        return

    lookup = load_lookup(CONFIG_PATH)
    if not lookup:
        print("(aviso) No cargué el YAML de mapeo; muestro mensajes crudos sin etiqueta.\n")

    port_name = pick_port(args.port)
    print(f"Escuchando: {port_name}")
    print("Mové controles del K3. Ctrl+C para salir.\n")
    print(f"{'ch':>2}  {'tipo':<14} {'num':>3} {'val':>3}  control")
    print("-" * 52)

    with mido.open_input(port_name) as inport:
        try:
            for msg in inport:
                ch = getattr(msg, "channel", None)
                ch_s = str(ch + 1) if ch is not None else "-"   # 1-based para lectura humana
                if msg.type == "control_change":
                    num, val = msg.control, msg.value
                elif msg.type in ("note_on", "note_off"):
                    num, val = msg.note, msg.velocity
                else:
                    num, val = "", ""
                print(f"{ch_s:>2}  {msg.type:<14} {str(num):>3} {str(val):>3}  {annotate(msg, lookup)}")
        except KeyboardInterrupt:
            print("\nChau.")


if __name__ == "__main__":
    main()
