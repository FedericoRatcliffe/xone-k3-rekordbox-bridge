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

        # --- SHIFT: estado interno (el K3 no cambia los códigos de los DEMÁS controles con
        # SHIFT, lo llevamos acá). OJO: el botón SHIFT en sí manda OTRA nota según la layer
        # activa (Latching Layers): 15 en Layer 1, 19 en Layer 2. Todas cuentan como SHIFT.
        shift_cfg = input_cfg.get("device", {}).get("shift_note", 15)
        self.shift_notes = {int(n) for n in shift_cfg} if isinstance(shift_cfg, list) else {int(shift_cfg)}
        self.shift_pressed = False
        # Con SHIFT apretado, estos controles hacen otra cosa (funcion -> target alternativo).
        self.shift_map = target_cfg.get("shift_map") or {}

        # --- FX channel-assign (SHIFT + encoder en Layer 2): ciclo de asignación por unidad ---
        # Config: un target del shift_map con `cycle` = una lista de notas de assign por unidad
        # (FX1, FX2). El índice arranca como los defaults de RB (FX1->CH1, FX2->CH2) y se
        # corrige solo con el feedback real de RB (si cambiás el assign con el mouse, se re-sincroniza).
        self.fx_assign_cycle = []
        self.fx_assign_channel = None
        for t in self.shift_map.values():
            if isinstance(t, dict) and "cycle" in t:
                self.fx_assign_cycle = t["cycle"]
                self.fx_assign_channel = t.get("channel", 6)
        self.fx_assign_idx = {u: min(u, len(notes) - 1)
                              for u, notes in enumerate(self.fx_assign_cycle)}

        # --- Estados a forzar ON al arrancar (Master Tempo, Quantize) ---
        self.startup_enable = target_cfg.get("startup_enable") or {}
        # (tipo, numero) -> (funcion, scope)
        self.startup_reverse = {
            ("note", s["number"]): (func, s.get("scope", "per_deck"))
            for func, s in self.startup_enable.items()
            if s.get("type") == "note"
        }

        # --- EQ kill: estado de cada banda "matada" por deck: {(eq_func, deck): True} ---
        self.killed: dict = {}
        self.led_sender = None    # main.py lo setea: prende/apaga LEDs del K3 (thread-safe)
        # (eq_func, deck) -> nota del botón de kill en el K3, para apagar su LED al destapar.
        self.kill_led_note: dict = {}
        for kfunc, ktarget in self.target_map.items():
            if isinstance(ktarget, dict) and "kill" in ktarget:
                notes = (self.input_controls.get(kfunc) or {}).get("note") or []
                for deck, note in enumerate(notes):
                    self.kill_led_note[(ktarget["kill"], deck)] = note

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
        # SHIFT: estado interno. Interceptamos su nota (una por layer) y NO la reenviamos a RB.
        if msg.type in ("note_on", "note_off") and msg.note in self.shift_notes:
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

        # EQ kill: toggle de la banda -> a 0 (matar) / restaurar a la posición del knob.
        # Reusa `positions` (lo que recordamos del knob físico). Solo en el press.
        if "kill" in target:
            if msg.type == "note_on" and msg.velocity > 0:
                eq_func = target["kill"]
                eq_target = self.target_map.get(eq_func)
                if not eq_target:
                    return []
                k = (eq_func, deck_idx)
                self.killed[k] = not self.killed.get(k, False)
                if self.led_sender:   # LED del botón: prendido = banda matada
                    self.led_sender(msg.note, self.killed[k])
                value = 0 if self.killed[k] else self.positions.get(k, 64)
                return self._cc_messages(eq_target, self._channel(eq_target, deck_idx), value, deck_idx)
            return []

        channel = self._channel(target, deck_idx)

        # 0) SHIFT + encoder (L2): ciclar el canal asignado del Beat FX (CH1->2->3->4->CH1).
        # `cycle` trae las notas de assign de esa unidad; el índice actual vive en fx_assign_idx
        # (seedeado con los defaults de RB y sincronizado por feedback en translate_feedback).
        if "cycle" in target:
            direction = relative_direction(value)
            if direction == 0:
                return []
            notes = target["cycle"][deck_idx] if deck_idx < len(target["cycle"]) else []
            if not notes:
                return []
            prev = self.fx_assign_idx.get(deck_idx, 0)
            idx = (prev + direction) % len(notes)
            self.fx_assign_idx[deck_idx] = idx
            # El assign del SX2 es TOGGLE (cada nota prende/apaga ese canal), NO "radio". Para
            # que se comporte como "mover" el canal, apagamos el anterior y prendemos el nuevo;
            # si solo prendiéramos el nuevo, se irían acumulando todos los canales prendidos.
            out = []
            if idx != prev:
                out += self._pulse(notes[prev], channel)   # apaga el canal anterior
            out += self._pulse(notes[idx], channel)          # prende el nuevo
            return out

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
            if self.killed.pop((func, deck_idx), None):   # estaba killed -> destapo + apago LED
                note = self.kill_led_note.get((func, deck_idx))
                if note is not None and self.led_sender:
                    self.led_sender(note, False)
            return self._cc_messages(target, channel, value, deck_idx)

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
        """Canal del target: por-deck si trae `channels` (p. ej. FX1=ch4, FX2=ch5), explícito
        si trae `channel` (browse/load/CFX son globales), si no el del deck (Pioneer: deck=canal)."""
        if "channels" in target:
            chans = target["channels"]
            return chans[deck] if deck < len(chans) else chans[0]
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

        # Tracking del FX channel-assign: RB reporta qué canal tiene cada unidad (velocity>0).
        # Mantiene el ciclo de SHIFT+encoder sincronizado aunque cambies el assign con el mouse.
        if key[0] == "note" and ch == self.fx_assign_channel and on > 0:
            for unit, notes in enumerate(self.fx_assign_cycle):
                if key[1] in notes:
                    self.fx_assign_idx[unit] = notes.index(key[1])

        func = self.target_reverse.get(key)
        if func is None:
            return []
        notes = (self.input_controls.get(func) or {}).get("note")
        if not notes:
            return []   # esa función no tiene LED en el K3 (p. ej. EQ/fader/depth son CC)
        target = self.target_map.get(func) or {}
        if "channels" in target:
            # Target por-canal (p. ej. FX1=ch4, FX2=ch5): el índice de columna es la posición
            # del canal en `channels` -> FX1 (ch4) prende la col 1, FX2 (ch5) la col 2.
            chans = target["channels"]
            deck = chans.index(ch) if ch in chans else None
        else:
            deck = self.channel_to_deck.get(ch)
            if deck is None:
                # Canal que no es un deck: si el control es global (una sola nota), usamos la 0.
                deck = 0 if len(notes) == 1 else None
        if deck is None or deck >= len(notes):
            return []

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
            channel = self._channel(target, deck)
            out += self._cc_messages(target, channel, value, deck)
        return out

    @staticmethod
    def _cc_messages(target: dict, channel: int, value: int, deck: int = 0) -> list:
        """CC absoluto -> mensaje(s). HiRes manda MSB (CC N) + LSB (CC N+32) escalando a 14-bit.
        El número de CC puede ser por-deck (`numbers: [...]`, p. ej. Sound Color FX: un CC por canal)."""
        number = target.get("number")
        if "numbers" in target:
            nums = target["numbers"]
            number = nums[deck] if deck < len(nums) else nums[0]
        if target.get("hires"):
            v14 = round(value / 127 * 16383)
            return [
                mido.Message("control_change", channel=channel, control=number, value=(v14 >> 7) & 0x7F),
                mido.Message("control_change", channel=channel, control=number + 32, value=v14 & 0x7F),
            ]
        return [mido.Message("control_change", channel=channel, control=number, value=value)]

    @staticmethod
    def _pulse(note: int, channel: int) -> list:
        """Un 'toque' de botón: note_on 127 + note_off 0 (para triggers tipo half/double)."""
        return [
            mido.Message("note_on", channel=channel, note=note, velocity=127),
            mido.Message("note_off", channel=channel, note=note, velocity=0),
        ]
