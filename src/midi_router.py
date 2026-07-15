"""
midi_router.py — Núcleo del puente. Traduce mensajes del K3 a mensajes "Pioneer DDJ-SX2".

Lee dos mapas:
  - config/xone_k3_input.yaml    : qué manda cada control del K3 (por columna/deck)
  - config/rekordbox_target.yaml : qué código DDJ-SX2 emular por función (deck = canal MIDI)

El K3 manda TODO en canal 15 (mido 0-based = 14). No filtramos por canal: cada control se
identifica por su número de CC/Note. El deck (columna) sale del ÍNDICE dentro de la lista
del mapa de entrada, y ese deck define el CANAL de salida (Pioneer: deck1=ch0 ... deck4=ch3).
"""
from __future__ import annotations

from pathlib import Path

import mido
import yaml

ROOT = Path(__file__).resolve().parent.parent
INPUT_CFG = ROOT / "config" / "xone_k3_input.yaml"
TARGET_CFG = ROOT / "config" / "rekordbox_target.yaml"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def relative_direction(value: int) -> int:
    """Interpreta un CC relativo (two's complement) -> +1 (CW), -1 (CCW) o 0.

    Convención por defecto: 1..63 = +1, 65..127 = -1, 0 y 64 = 0.
    OJO: falta VALIDAR el modo real del encoder del K3. Corré monitor.py, girá el encoder
    y fijate qué valores manda; si no es two's complement, ajustamos esta función.
    """
    if value in (0, 64):
        return 0
    return 1 if value < 64 else -1


class MidiRouter:
    def __init__(self, input_cfg: dict, target_cfg: dict):
        self.target_map = target_cfg.get("map", {})
        self.deck_to_channel = target_cfg.get("target", {}).get("deck_to_channel", [0, 1, 2, 3])
        # lookup: (tipo, numero) -> (funcion, deck_idx)
        self.lookup: dict = {}
        for func, ctrl in (input_cfg.get("controls") or {}).items():
            ttype = ctrl.get("type")
            kind = ctrl.get("kind")
            numbers = ctrl.get("cc") if ttype == "cc" else ctrl.get("note")
            for deck_idx, num in enumerate(numbers or []):
                self.lookup[(ttype, num)] = (func, deck_idx, kind)

        # --- Feedback inverso: RB (DDJ-SX2) -> LED del K3 ---
        self.input_controls = input_cfg.get("controls") or {}
        # canal del K3 (0-based). En el YAML está 1-based (15) -> mido 14.
        self.k3_channel = int(input_cfg.get("device", {}).get("midi_channel", 15)) - 1
        # (tipo, numero) del target -> funcion, para reconocer qué manda RB.
        self.target_reverse = {
            (t["type"], t["number"]): func
            for func, t in self.target_map.items()
            if "type" in t and "number" in t
        }
        # canal MIDI -> índice de deck (para saber qué columna del K3 prender).
        self.channel_to_deck = {ch: i for i, ch in enumerate(self.deck_to_channel)}

    @staticmethod
    def _key(msg):
        if msg.type == "control_change":
            return ("cc", msg.control), msg.value
        if msg.type in ("note_on", "note_off"):
            return ("note", msg.note), msg.velocity
        return None, None

    def translate(self, msg) -> list:
        """Devuelve la lista de mensajes mido a mandar al DDJ-SX2 (puede ser 0, 1 o 2)."""
        key, value = self._key(msg)
        if key is None or key not in self.lookup:
            return []
        func, deck_idx, kind = self.lookup[key]
        target = self.target_map.get(func)
        if not target:
            return []
        channel = self.deck_to_channel[deck_idx] if deck_idx < len(self.deck_to_channel) else 0

        # 1) Encoder relativo -> un "toque" de half/double según la dirección del giro.
        if target.get("relative"):
            direction = relative_direction(value)
            if direction == 0:
                return []
            side = target["cw"] if direction > 0 else target["ccw"]
            return self._pulse(side["number"], channel)

        # 2) CC absoluto (EQ, fader).
        if target["type"] == "cc":
            if target.get("hires"):
                # HiRes 14-bit: RB reconstruye el valor con MSB (CC N) + LSB (CC N+32).
                # Escalamos el 7-bit del K3 (0-127) a 14-bit (0-16383) para usar todo el rango.
                v14 = round(value / 127 * 16383)
                msb, lsb = (v14 >> 7) & 0x7F, v14 & 0x7F
                return [
                    mido.Message("control_change", channel=channel, control=target["number"], value=msb),
                    mido.Message("control_change", channel=channel, control=target["number"] + 32, value=lsb),
                ]
            return [mido.Message("control_change", channel=channel,
                                 control=target["number"], value=value)]

        # 3) Note (play / cue / sync / loop-on).
        if target["type"] == "note":
            is_press = msg.type == "note_on" and msg.velocity > 0
            if kind == "gate":
                # "Gate" (Cue): press-and-hold -> on al apretar, off al soltar.
                if is_press:
                    return [mido.Message("note_on", channel=channel, note=target["number"], velocity=127)]
                return [mido.Message("note_off", channel=channel, note=target["number"], velocity=0)]
            # "Trigger" (Play/Sync/Loop-on): un toque limpio (on+off) en el press.
            # El K3 manda solo el press; emulamos el click completo de un botón real.
            if is_press:
                return self._pulse(target["number"], channel)
            return []

        return []

    def translate_feedback(self, msg) -> list:
        """Feedback de RB (DDJ-SX2) -> mensajes de LED para el K3.

        RB manda, p. ej., note_on 900B (play deck1 ON) / velocity 0 (OFF). Lo mapeamos a la
        nota del K3 de esa función+deck y lo mandamos a la salida del K3 (prende/apaga el LED).
        El color ya está fijado en el editor por botón/layer.
        """
        if msg.type == "control_change":
            key, on, ch = ("cc", msg.control), msg.value, msg.channel
        elif msg.type in ("note_on", "note_off"):
            on = msg.velocity if msg.type == "note_on" else 0
            key, ch = ("note", msg.note), msg.channel
        else:
            return []

        func = self.target_reverse.get(key)
        deck = self.channel_to_deck.get(ch)
        if func is None or deck is None:
            return []
        notes = (self.input_controls.get(func) or {}).get("note")
        if not notes or deck >= len(notes):
            return []   # esa función no tiene LED en el K3 (p. ej. EQ/fader son CC)

        velocity = 127 if on > 0 else 0
        return [mido.Message("note_on", channel=self.k3_channel, note=notes[deck], velocity=velocity)]

    @staticmethod
    def _pulse(note: int, channel: int) -> list:
        """Un 'toque' de botón: note_on 127 + note_off 0 (para triggers tipo half/double)."""
        return [
            mido.Message("note_on", channel=channel, note=note, velocity=127),
            mido.Message("note_off", channel=channel, note=note, velocity=0),
        ]
