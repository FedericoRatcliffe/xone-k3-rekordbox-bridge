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

        # --- SHIFT: estado interno (el K3 no cambia de código con SHIFT, lo llevamos acá) ---
        self.shift_note = int(input_cfg.get("device", {}).get("shift_note", 15))
        self.shift_pressed = False
        # Con SHIFT apretado, estos controles hacen otra cosa (funcion -> target alternativo).
        self.shift_map = target_cfg.get("shift_map") or {}

        # --- Estados a forzar ON al arrancar (Master Tempo, Quantize) ---
        self.startup_enable = target_cfg.get("startup_enable") or {}
        # (tipo, numero) -> (funcion, scope)
        self.startup_reverse = {
            ("note", s["number"]): (func, s.get("scope", "per_deck"))
            for func, s in self.startup_enable.items()
            if s.get("type") == "note"
        }

        # --- Posiciones de controles absolutos (faders/EQ) para restaurar al reiniciar ---
        # Sembramos defaults seguros; main.py después superpone lo guardado en disco.
        self.positions: dict = {}
        for func, ctrl in self.input_controls.items():
            if ctrl.get("type") == "cc" and ctrl.get("kind") == "absolute" and "default" in ctrl:
                for deck in range(len(ctrl.get("cc") or [])):
                    self.positions[(func, deck)] = ctrl["default"]

    @staticmethod
    def _key(msg):
        if msg.type == "control_change":
            return ("cc", msg.control), msg.value
        if msg.type in ("note_on", "note_off"):
            return ("note", msg.note), msg.velocity
        return None, None

    def translate(self, msg) -> list:
        """Devuelve la lista de mensajes mido a mandar al DDJ-SX2 (puede ser 0, 1 o 2)."""
        # SHIFT: estado interno. Interceptamos su nota y NO la reenviamos a RB.
        if msg.type in ("note_on", "note_off") and msg.note == self.shift_note:
            self.shift_pressed = msg.type == "note_on" and msg.velocity > 0
            return []

        key, value = self._key(msg)
        if key is None or key not in self.lookup:
            return []
        func, deck_idx, kind = self.lookup[key]

        # Con SHIFT apretado, algunos controles usan un target alternativo (shift_map).
        if self.shift_pressed and func in self.shift_map:
            target = self.shift_map[func]
            kind = target.get("kind", kind)
        else:
            target = self.target_map.get(func)
        if not target:
            return []

        channel = self._channel(target, deck_idx)

        # 1) Encoder relativo -> pulso (loop half/double) o CC con valor (browse), por dirección.
        if target.get("relative"):
            direction = relative_direction(value)
            if direction == 0:
                return []
            side = target["cw"] if direction > 0 else target["ccw"]
            return self._side_messages(side, channel)

        # 2) CC absoluto (EQ, fader). Guardamos la posición para restaurarla al reiniciar.
        if target["type"] == "cc":
            self.positions[(func, deck_idx)] = value
            return self._cc_messages(target, channel, value)

        # 3) Note (play/cue/sync/loop-on/headphone-cue/load). `notes` = una nota por deck.
        if target["type"] == "note":
            number = target["notes"][deck_idx] if "notes" in target else target["number"]
            is_press = msg.type == "note_on" and msg.velocity > 0
            if kind == "gate":
                # "Gate" (Cue): press-and-hold -> on al apretar, off al soltar.
                if is_press:
                    return [mido.Message("note_on", channel=channel, note=number, velocity=127)]
                return [mido.Message("note_off", channel=channel, note=number, velocity=0)]
            # "Trigger": un toque limpio (on+off) en el press; ignora el release.
            if is_press:
                return self._pulse(number, channel)
            return []

        return []

    def _channel(self, target: dict, deck: int) -> int:
        """Canal del target: explícito si lo trae (browse/load son globales), si no el del deck."""
        if "channel" in target:
            return target["channel"]
        return self.deck_to_channel[deck] if deck < len(self.deck_to_channel) else 0

    @staticmethod
    def _side_messages(side: dict, channel: int) -> list:
        """Un lado de un encoder relativo -> pulso de nota (loop) o CC con valor (browse)."""
        if side["type"] == "note":
            return MidiRouter._pulse(side["number"], channel)
        return [mido.Message("control_change", channel=channel,
                             control=side["number"], value=side.get("value", 0))]

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

    def feedback_enforce(self, msg, done: set) -> list:
        """Al arrancar, fuerza Master Tempo / Quantize a ON (plug-and-play en cualquier PC).

        Usa el feedback de RB para saber el estado real: si RB reporta que están en OFF,
        devuelve el toggle a mandarle a RB para prenderlos. Actúa UNA sola vez por objetivo
        (marca en `done`), así no pelea si después los apagás a mano.
        Devuelve (mensajes_para_RB, texto_log) — o ([], "") si no hay nada que hacer.
        """
        if msg.type not in ("note_on", "note_off"):
            return [], ""
        spec = self.startup_reverse.get(("note", msg.note))
        if spec is None:
            return [], ""
        func, scope = spec
        deck = self.channel_to_deck.get(msg.channel)
        if deck is None:
            return [], ""
        marker = (func,) if scope == "once" else (func, deck)
        if marker in done:
            return [], ""
        done.add(marker)                       # visto: no lo tocamos más

        state_on = msg.type == "note_on" and msg.velocity > 0
        if state_on:
            return [], ""                       # ya está ON, no hacemos nada

        ch = self.deck_to_channel[deck]
        toggle = [
            mido.Message("note_on", channel=ch, note=msg.note, velocity=127),
            mido.Message("note_off", channel=ch, note=msg.note, velocity=0),
        ]
        where = "global" if scope == "once" else f"deck {deck + 1}"
        return toggle, f"[startup] {func} estaba OFF ({where}) -> lo prendo"

    def replay_positions(self) -> list:
        """Mensajes para restaurar en RB las últimas posiciones de faders/EQ (al reiniciar)."""
        out: list = []
        for (func, deck), value in self.positions.items():
            target = self.target_map.get(func)
            if not target or target.get("type") != "cc":
                continue
            channel = self.deck_to_channel[deck] if deck < len(self.deck_to_channel) else 0
            out += self._cc_messages(target, channel, value)
        return out

    @staticmethod
    def _cc_messages(target: dict, channel: int, value: int) -> list:
        """CC absoluto -> mensaje(s). HiRes manda MSB (CC N) + LSB (CC N+32) escalando a 14-bit."""
        if target.get("hires"):
            v14 = round(value / 127 * 16383)
            return [
                mido.Message("control_change", channel=channel, control=target["number"], value=(v14 >> 7) & 0x7F),
                mido.Message("control_change", channel=channel, control=target["number"] + 32, value=v14 & 0x7F),
            ]
        return [mido.Message("control_change", channel=channel, control=target["number"], value=value)]

    @staticmethod
    def _pulse(note: int, channel: int) -> list:
        """Un 'toque' de botón: note_on 127 + note_off 0 (para triggers tipo half/double)."""
        return [
            mido.Message("note_on", channel=channel, note=note, velocity=127),
            mido.Message("note_off", channel=channel, note=note, velocity=0),
        ]
