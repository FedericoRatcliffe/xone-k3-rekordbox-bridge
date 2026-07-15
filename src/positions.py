"""
positions.py — Persistencia de las posiciones de faders/knobs (controles absolutos).

El K3 no puede reportar sus posiciones al iniciar (limitación de firmware), así que el
puente RECUERDA el último valor que vio de cada control y lo restaura en Rekordbox al
arrancar. Se guarda en un JSON simple. Clave = "funcion|deck", valor = 0-127.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_positions(path) -> dict:
    """Lee el archivo y devuelve {(funcion, deck): valor}. {} si no existe o está roto."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    out: dict = {}
    for key, value in data.items():
        try:
            func, deck = key.rsplit("|", 1)
            out[(func, int(deck))] = int(value)
        except (ValueError, TypeError):
            continue
    return out


def save_positions(path, positions: dict) -> None:
    """Guarda {(funcion, deck): valor} como JSON {"funcion|deck": valor}."""
    data = {f"{func}|{deck}": int(value) for (func, deck), value in positions.items()}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
