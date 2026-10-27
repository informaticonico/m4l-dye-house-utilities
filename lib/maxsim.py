"""Simulate a message-domain Max patch (a built .amxd) in Python.

Covers the vanilla objects the Tincture family's MIDI devices use, with Max's
depth-first, right-to-left message order. It encodes our understanding of each
object's behaviour; it checks the patch's wiring and message order, which is
where hand-built patches usually break. It is not a substitute for Live.

    sim = MaxSim(patcher)            # patcher dict from m4l.read_amxd()
    sim.load()                       # parameters output their values, then live.thisdevice bangs
    sim.set_param("Mode", 1)
    sim.play(bars=2, tempo=120)      # run the transport; returns note events
"""

import heapq
import json
import math
import random
import re

from m4l import initial, read_amxd  # noqa: F401  (read_amxd re-exported for callers)

BANG = "bang"


def _words(msg):
    """A message as words: a list such as ['id', 5] reads as 'id 5', as in Max."""
    return " ".join(map(str, msg)).split() if isinstance(msg, list) else str(msg).split()


def _parse(tok):
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return tok


_NUMS = {}            # a word's number, once parsed (words repeat: every box's text, every message's)


def _num(tok):
    if tok.__class__ is str:
        v = _NUMS.get(tok, _NUMS)
        if v is _NUMS:
            v = _parse(tok)
            if len(_NUMS) < 200000:
                _NUMS[tok] = v
        return v
    return _parse(tok)


def _split(text):
    """An object's text as words, a "quoted symbol" one word (as Max reads it)."""
    if '"' not in text:
        return text.split()
    import shlex
    return shlex.split(text)


class Obj:
    def __init__(self, sim, box):
        self.sim, self.box, self.id = sim, box, box["id"]
        self.args = [_num(t) for t in _split(box.get("text", ""))[1:]]
        self.sent = {}           # outlet -> the last message out of it (for tests)

    def out(self, outlet, msg):
        self.sent[outlet] = msg
        self.sim.send(self.id, outlet, msg)

    def receive(self, inlet, msg):
        raise NotImplementedError(f"{self.box.get('text', self.box['maxclass'])} inlet {inlet} got {msg!r}")


class Trigger(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.right_to_left = list(enumerate(self.args))[::-1]

    def receive(self, inlet, msg):
        for k, kind in self.right_to_left:
            if kind == "b":
                self.out(k, BANG)
            elif kind == "i":
                self.out(k, int(_first(msg)))
            elif kind == "f":
                self.out(k, float(_first(msg)))
            elif kind == "l":
                self.out(k, msg)
            else:  # constant
                self.out(k, kind)


def _first(msg):
    return msg[0] if isinstance(msg, list) else msg


class Store(Obj):  # i / f
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.cast = int if box["text"].split()[0] == "i" else float
        self.v = self.cast(self.args[0]) if self.args else self.cast(0)

    def receive(self, inlet, msg):
        if inlet == 1:
            self.v = self.cast(_first(msg))
        else:
            if msg != BANG:
                self.v = self.cast(_first(msg))
            self.out(0, self.v)


class Arith(Obj):  # + - * / %
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.op = box["text"].split()[0]
        self.right = self.args[0] if self.args else 0
        self.left = 0
        self.isint = isinstance(self.right, int)

    def receive(self, inlet, msg):
        if inlet == 1:
            self.right = _first(msg)
            return
        if msg != BANG:
            self.left = _first(msg)
        a, b = self.left, self.right
        if self.isint:
            a, b = int(a), int(b)
        if self.op == "+":
            r = a + b
        elif self.op == "-":
            r = a - b
        elif self.op == "*":
            r = a * b
        elif self.op == "/":
            r = (int(a / b) if self.isint else a / b) if b else 0
        elif self.op == "%":
            r = (a % b) if b else 0
        self.out(0, r)


class Expr(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        src = box["text"].split(None, 1)[1].replace("\\,", ",")     # Max escapes a box's commas
        n = max(int(m) for m in re.findall(r"\$[if](\d+)", src))
        # Max's expr has at most nine inputs and refuses the box past that ("expr: inlet out of range", Weld Kit's
        # mask of sixteen, the beta's console, Oct 18)
        assert n <= 9, f"{self.id}: expr with {n} inputs; Max's takes at most 9"
        self.vals = [0] * n
        self.kinds = ["i"] * n
        for kind, idx in re.findall(r"\$([if])(\d+)", src):
            self.kinds[int(idx) - 1] = kind
        py = re.sub(r"\$([if])(\d+)", lambda m: f"v[{int(m.group(2)) - 1}]", src)
        py = py.replace("&&", " and ").replace("||", " or ")
        self.code = compile(py, "<expr>", "eval")

    def receive(self, inlet, msg):
        if inlet == 0 and isinstance(msg, list):
            for k, v in enumerate(msg[:len(self.vals)]):
                self.vals[k] = int(v) if self.kinds[k] == "i" else float(v)
        elif isinstance(msg, list) and len(msg) > 1:
            # as Max: a list into a right inlet is refused, the value kept as it was (until Oct 20 this took its first
            # item, and Mordant's swing read transport's time signature so: plans/process/transport-outlets.md)
            self.sim.console.append("expr: inlet: list: wrong message or type")
            return
        elif msg != BANG:
            v = _first(msg)
            self.vals[inlet] = int(v) if self.kinds[inlet] == "i" else float(v)
        if inlet == 0:
            try:
                r = eval(self.code, _EXPR_NAMES, {"v": self.vals})
            except ZeroDivisionError:            # as Max: said in the Max window, and 0 out (Weld Kit 1.0.1)
                self.sim.console.append("expr: divide by zero")
                r = 0
            r = int(r) if isinstance(r, bool) else r
            self.out(0, r)


_EXPR_NAMES = {"int": int, "abs": abs, "min": min, "max": max, "fmod": math.fmod, "sin": math.sin, "cos": math.cos,
               "pow": math.pow, "float": float, "log": math.log, "exp": math.exp, "tanh": math.tanh, "sqrt": math.sqrt,
               "log10": math.log10}      # what an expr's code can call (one dict, made once)


class Sel(Obj):
    def receive(self, inlet, msg):
        v = msg if isinstance(msg, str) and msg in self.args else _first(msg)
        for k, a in enumerate(self.args):
            if v == a:
                self.out(k, BANG)
                return
        self.out(len(self.args), msg)


class Gate(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.open = self.args[1] if len(self.args) > 1 else 0

    def receive(self, inlet, msg):
        if inlet == 0:
            self.open = int(_first(msg))
        elif 1 <= self.open <= self.args[0]:
            self.out(self.open - 1, msg)


class Uzi(Obj):
    def receive(self, inlet, msg):
        if inlet == 1:
            self.args[0] = int(_first(msg))
            return
        if msg != BANG:
            self.args[0] = int(_first(msg))  # an int in the left inlet sets the count and starts
        for k in range(1, self.args[0] + 1):
            self.out(2, k)
            self.out(0, BANG)
        self.out(1, BANG)


class Random(Obj):
    def receive(self, inlet, msg):
        if inlet == 1:
            self.args[0] = int(_first(msg))
        else:
            self.out(0, self.sim.rng.randrange(self.args[0]))


class Pak(Obj):  # pak: any inlet outputs; pack: left inlet outputs
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.vals = list(self.args)
        self.hot_all = box["text"].split()[0] == "pak"

    def receive(self, inlet, msg):
        if isinstance(msg, list) and inlet == 0:
            for k, v in enumerate(msg):
                self.vals[k] = v
        elif msg != BANG:
            self.vals[inlet] = type(self.vals[inlet])(_first(msg))
        if inlet == 0 or self.hot_all:
            self.out(0, list(self.vals))


class Zl(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.mode = box["text"].split()[1]
        self.stored = []

    def receive(self, inlet, msg):
        if isinstance(msg, str) and msg != BANG:
            msg = [_num(t) for t in msg.split()]
        lst = msg if isinstance(msg, list) else [msg]
        if self.mode == "lookup":
            if inlet == 1:
                self.stored = lst
            else:
                i = int(lst[0])
                if 0 <= i < len(self.stored):  # zl lookup indexes from 0
                    self.out(0, self.stored[i])
        elif self.mode == "reg":                   # zl reg: the right inlet stores, a bang outputs it
            if inlet == 1:
                self.stored = lst
            elif msg == BANG:
                self.out(0, list(self.stored))
            else:
                self.stored = lst
                self.out(0, list(lst))
        elif self.mode == "change":                # zl change: the input only when it differs from the last
            if inlet == 0 and lst != self.stored:
                self.stored = lst
                self.out(0, msg if not isinstance(msg, list) else list(lst))
        elif self.mode == "len":
            self.out(0, len(lst))
        elif self.mode == "lace":                  # zl lace: a1 b1 a2 b2 ..., the right inlet cold
            if inlet == 1:
                self.stored = lst
            else:
                self.out(0, [v for pair in zip(lst, self.stored) for v in pair])
        elif self.mode == "join":                  # zl join: the left's list, then the right's (stored, cold)
            if inlet == 1:
                self.stored = lst
            else:
                self.out(0, list(lst) + list(self.stored))
        elif self.mode == "slice":                 # zl slice N: the first N from the left outlet, the rest the right
            if inlet == 1:                          # (the right inlet sets N)
                self.n = int(lst[0])
                return
            n = getattr(self, "n", None)
            n = int(self.box["text"].split()[2]) if n is None else n
            if len(lst) > n:
                self.out(1, lst[n:])
            self.out(0, lst[:n])
        elif self.mode == "rev":
            self.out(0, list(reversed(lst)))
        elif self.mode == "sum":
            self.out(0, sum(float(x) for x in lst))
        elif self.mode == "iter":                  # zl iter N: the list N items at a time
            n = int(self.box["text"].split()[2])
            for k in range(0, len(lst), n):
                self.out(0, lst[k:k + n] if n > 1 else lst[k])
        elif self.mode == "group":                 # zl group N: collect N items, then output them
            n = int(self.box["text"].split()[2])
            self.stored += lst
            if len(self.stored) >= n:
                out, self.stored = self.stored[:n], self.stored[n:]
                self.out(0, out)


class Route(Obj):
    def receive(self, inlet, msg):
        for k, a in enumerate(self.args):
            if isinstance(msg, list) and msg and msg[0] == a:     # a message such as ['id', 5]
                rest = msg[1:]
                self.out(k, BANG if not rest else rest[0] if len(rest) == 1 else rest)
                return
            if msg == a or (isinstance(msg, str) and msg.split()[0] == a):
                rest = [_num(t) for t in str(msg).split()[1:]]
                self.out(k, BANG if not rest else rest[0] if len(rest) == 1 else rest)
                return
        self.out(len(self.args), msg)


class Pipe(Obj):
    """pipe v1 .. vN delay: a list in the left inlet comes out delay ms later."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.vals = list(self.args[:-1])
        self.delay = float(self.args[-1])

    def receive(self, inlet, msg):
        n = len(self.vals)
        if inlet == n:
            self.delay = float(_first(msg))
            return
        if isinstance(msg, list) and inlet == 0:
            self.vals[:len(msg)] = msg
        elif msg != BANG:
            self.vals[inlet] = _first(msg)
        if inlet == 0:
            vals = list(self.vals)

            def fire():
                for k in range(n - 1, -1, -1):
                    self.out(k, vals[k])
            self.sim.schedule(self.delay, fire)


class Sprintf(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.fmt = box["text"].split(None, 1)[1]
        if "%%" in self.fmt:                 # Oct 26: in Live, another device's 'sprintf set %ld %%' never reached its comment
            raise ValueError(f"sprintf with '%%' ({box['text']}): Max sends nothing; use 'append %' then 'prepend set'")
        self.specs = re.findall(r"%[-+ .0-9]*l?[sdf]", self.fmt)
        self.vals = ["" if s.endswith("s") else 0 for s in self.specs]

    def receive(self, inlet, msg):
        if isinstance(msg, list) and inlet == 0:   # a list fills the inlets from the left
            self.vals[:len(msg)] = msg[:len(self.vals)]
        elif msg != BANG:
            self.vals[inlet] = _first(msg)
        if inlet == 0:
            vals = [float(v) if spec.endswith("f") else (int(v) if spec.endswith("d") else v)
                    for spec, v in zip(self.specs, self.vals)]
            self.out(0, self.fmt.replace("%ld", "%d") % tuple(vals))


class Comment(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.text = box.get("text", "")

    def receive(self, inlet, msg):
        if isinstance(msg, list):            # 'prepend set' makes a list: set Filter Freq
            msg = " ".join(map(str, msg))
        parts = str(msg).split(None, 1)
        if parts[0] != "set":                # an attribute: 'textcolor r g b a'
            self.attrs = getattr(self, "attrs", {})
            self.attrs[parts[0]] = parts[1] if len(parts) > 1 else ""
            return
        self.text = parts[1] if len(parts) > 1 else ""


class Deferlow(Obj):
    def receive(self, inlet, msg):
        self.out(0, msg)


class LivePath(Obj):
    """live.path: 'path ...' -> 'id N' (0 when the path doesn't resolve). Its left outlet follows
    the object: 'id 0' when it is deleted (MaxSim.delete_target), the same id when it moves."""
    following = 0

    def receive(self, inlet, msg):
        words = _words(msg)
        assert words[0] == "path", msg
        self.following = self.sim.live.resolve(' '.join(words[1:]))
        self.out(0, f"id {self.following}")


class LiveObject(Obj):
    """live.object: right inlet 'id N', left inlet 'get prop' / 'call fn args'."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.target = 0

    def receive(self, inlet, msg):
        words = _words(msg)
        if inlet == 1:
            assert words[0] == "id", msg
            self.target = int(words[1])
            return
        result = self.sim.live.handle(self.target, words)
        if result is not None:
            self.out(0, result)


class LiveRemote(Obj):
    """live.remote~: right inlet 'id N' (0 lets go), left inlet a value set on that parameter,
    without undo. The value lands in FakeLive's object and in its remote_log as (ms, id, value)."""
    target = 0

    def receive(self, inlet, msg):
        self.received = getattr(self, "received", []) + [msg]     # as a Sink records (another device's tests read it)
        words = _words(msg)
        if inlet == 1:
            if words and words[0] == "id":
                self.target = int(words[1])
            return
        if self.target and self.target in self.sim.live.objects:
            v = float(_first(msg))
            self.sim.live.objects[self.target]["value"] = v
            self.sim.live.remote_log.append((self.sim.now_ms, self.target, v))


class FakeLive:
    """Just enough of a Live Set for Mordant: the clip slots of its own track.
    slots[i] is None (empty) or a clip dict {"length", "notes"}; ids: live_set 1,
    slot i -> 100 + i, the clip in slot i -> 200 + i."""
    TRACK = "this_device canonical_parent"

    def __init__(self, slots=None):
        self.slots = [None] * 8 if slots is None else slots
        self.paths, self.objects, self.remote_log = {}, {}, []   # a generic Live object model (add)
        self.targets = {}
        self.calls = []

    @property
    def clip(self):
        """The most recently created clip (convenience for tests)."""
        return self.last_clip

    last_clip = None

    arm = 0
    # the song's current scale (Live 12: the selected clip's, shown above the tracks): Live's
    # default, C Major, with Scale Mode off
    root_note = 0
    scale_intervals = [0, 2, 4, 5, 7, 9, 11]
    scale_name = "Major"
    scale_mode = 0
    # the Session clip playing on this device's track (-1: none); a clip's own scale is in its
    # dict ('scale_mode', 'root_note', 'scale_intervals'), Scale Mode off when missing
    playing_slot_index = -1
    # Live 12.1's tuning system: None, or its name (live_set tuning_system, id 3)
    tuning = None
    session_record = 0
    record_mode = 0
    tempo = 120.0
    signature_numerator = 4
    signature_denominator = 4
    is_playing = 0
    # parameters elsewhere in the set a modulator can map: id -> name, min, max, value
    # (ids from 700); the selected one is what the user last clicked in Live
    targets = {}
    selected_parameter = 0

    def value(self, target, prop):
        if target == 50 and prop == "arm":
            return self.arm
        if target == 1 and prop in ("session_record", "record_mode", "tempo", "is_playing", "root_note",
                                    "scale_intervals", "scale_mode", "scale_name",
                                    "signature_numerator", "signature_denominator"):
            return getattr(self, prop)
        if target in (50, 60) and prop == "playing_slot_index":
            return self.playing_slot_index
        if 200 <= target < 300 and prop in ("scale_mode", "root_note", "scale_intervals", "scale_name"):
            c = self.slots[target - 200] or {}
            return c.get(prop, {"scale_mode": 0, "root_note": 0, "scale_intervals": [0, 2, 4, 5, 7, 9, 11],
                                "scale_name": "Major"}[prop])
        if target == 3 and prop == "name":
            return self.tuning
        if target == 1 and prop == "tuning_system":
            return f"id {3 if self.tuning else 0}"
        if target == 2 and prop == "selected_parameter":
            return f"id {self.selected_parameter}"
        return None

    def add(self, path, **props):
        """An object at `path` with its properties (a list of ids is 'id a id b ...'): its id, from 2000."""
        oid = 2000 + len(self.objects)
        self.paths[path] = oid
        self.objects[oid] = dict(props)
        return oid

    def target_path(self, target):
        """Where a mappable parameter lives: its 'path', else a device on track 1."""
        return self.targets[target].get("path", f"live_set tracks 1 devices 0 parameters {target - 700}")

    def resolve(self, path):
        if path in self.paths:
            return self.paths[path]
        for t in self.targets:
            if path == self.target_path(t):
                return t
        words = path.split()
        if path == "live_set":
            return 1
        if path == "live_set view":
            return 2
        if path == "live_set tuning_system":
            return 3 if self.tuning else 0
        if path == self.TRACK:
            return 50 if self.slots else 60   # 60: a return track or chain, no arm
        head = self.TRACK.split()
        if words[:2] == head and len(words) >= 4 and words[2] == "clip_slots":
            i = int(words[3])
            if not 0 <= i < len(self.slots):
                return 0
            if len(words) == 4:
                return 100 + i
            if words[4:] == ["clip"]:
                return 200 + i if self.slots[i] is not None else 0
        return 0

    def js_view(self):
        """The set as a js object's LiveAPI sees it (lib/jsrun.py): the playing slot, and each clip's
        notes as get_notes_extended gives them (note_id: its place in the clip, from 1)."""
        keys = ("pitch", "start_time", "duration", "velocity", "mute")
        clips = {i: {"length": c["length"], "notes": [dict(zip(("note_id",) + keys, (k + 1,) + tuple(n)))
                                                      for k, n in enumerate(c["notes"])]}
                 for i, c in enumerate(self.slots) if c}
        # the track's devices: this one (40), then each target's device ('device', "Synth" if none) in the order
        # first met (ids 600 + n), its parameters as Live lists them: Device On first (650 + n), then its targets
        # ('items': a menu's or a switch's)
        devs = {}
        for t, d in sorted(self.targets.items()):
            devs.setdefault(d.get("device", "Synth"), []).append(dict(id=t, name=d.get("name", ""), items=d.get("items")))
        track = {"self": 40, "devices": [dict(id=40, name="This device", params=[])]
                 + [dict(id=600 + n, name=name, params=[dict(id=650 + n, name="Device On", items=["Off", "On"])] + ps)
                    for n, (name, ps) in enumerate(devs.items())]}
        return {"playing": getattr(self, "playing_slot_index", -1), "clips": clips,
                "slots": [bool(c) for c in self.slots], "track": track}

    def handle(self, target, words):
        self.calls.append((target, " ".join(str(w) for w in words)))
        assert target, f"live.object has no target for {words}"
        if target in self.objects and words[0] == "get":
            v = self.objects[target].get(words[1])
            if isinstance(v, list):
                v = " ".join(f"id {i}" for i in v)
            return f"{words[1]} {v}"
        if target in self.objects and words[0] == "set":
            self.objects[target][words[1]] = _num(words[2])
            return None
        if target == 1:
            assert words == ["call", "create_scene", "-1"], words
            self.slots.append(None)
            return None
        if target in self.targets and words[0] == "get":
            if words[1] == "is_quantized":                # a menu or a switch: its items
                return f"is_quantized {int(bool(self.targets[target].get('items')))}"
            return f"{words[1]} {self.targets[target][words[1]]}"
        if target in self.targets and words[0] == "getpath":
            return f"path {self.target_path(target)}"
        if 100 <= target < 200:
            i = target - 100
            if words[:2] == ["get", "has_clip"]:
                return f"has_clip {int(self.slots[i] is not None)}"
            if words[:2] == ["call", "create_clip"]:
                assert self.slots[i] is None, f"create_clip on occupied slot {i}"
                self.slots[i] = {"length": float(words[2]), "notes": [], "expect": None, "open": False,
                                 "slot": i}
                self.last_clip = self.slots[i]
                return None
        if 200 <= target < 300:
            c = self.slots[target - 200]
            if words[:2] == ["call", "add_new_notes"]:
                # the LOM's Clip.add_new_notes (Live 11+): a dictionary {"notes": [{pitch, start_time,
                # duration, velocity, mute}...]}; the pitch must be a whole MIDI note
                spec = words[2]
                assert isinstance(spec, dict) and isinstance(spec.get("notes"), list), spec
                for n in spec["notes"]:
                    assert set(n) <= {"pitch", "start_time", "duration", "velocity", "mute", "probability",
                                      "velocity_deviation", "release_velocity"}, n
                    assert n["pitch"] == int(n["pitch"]) and 0 <= n["pitch"] <= 127, n
                    c["notes"].append((int(n["pitch"]), float(n["start_time"]), float(n["duration"]),
                                       int(n.get("velocity", 100)), int(n.get("mute", 0))))
                    c.setdefault("probability", []).append(float(n.get("probability", 1)))   # each note's chance
                return None
            if words[:2] == ["call", "apply_note_modifications"]:
                # notes as get_notes_extended gave them, changed; matched by note_id
                for n in words[2]["notes"]:
                    k = int(n["note_id"]) - 1
                    assert 0 <= k < len(c["notes"]), n
                    c["notes"][k] = (int(n["pitch"]), float(n["start_time"]), float(n["duration"]),
                                     int(round(n["velocity"])), int(n["mute"]))
                return None
            if words[:2] == ["call", "get_notes_extended"]:
                return None
            if words[:2] == ["call", "create_automation_envelope"]:
                # as Live: Max for Live's Clip has no create_automation_envelope (the bridge's check in Live, Oct 20;
                # the Python API's only), and says so in Max's window
                self.sim.console.append("jsliveapi: 'Clip' object has no attribute 'create_automation_envelope'")
                return None
            raise AssertionError(f"unexpected clip call {words}")
        if 5200 <= target < 5300 and words[:2] == ["call", "insert_step"]:
            # an envelope's AutomationEnvelope.insert_step(time, duration, value)
            self.slots[target - 5200].setdefault("envelope", []).append(tuple(float(w) for w in words[2:5]))
            return None
        raise AssertionError(f"unexpected Live API call {words} on id {target}")


class Coll(Obj):
    """coll: 'k a b c' stores [a b c] at k; an int k outputs what's stored; 'clear'; 'remove k'
    forgets k; 'dump' outputs every entry, in the order stored, then a bang from its last outlet.
    Colls with the same name share their data, as in Max."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.data = sim.colls.setdefault(str(self.args[0]), {}) if self.args else {}

    def receive(self, inlet, msg):
        if isinstance(msg, str) and " " in msg:     # 'k a b' as one message: a list, as in Max
            msg = [_num(t) for t in msg.split()]
        if isinstance(msg, list) and msg and msg[0] == "remove":
            self.data.pop(int(msg[1]), None)
        elif msg == "dump":
            for v in list(self.data.values()):     # a copy: what it sets off may change the coll
                self.out(0, v if len(v) > 1 else v[0])
            if self.box.get("numoutlets", 1) > 1:   # done: a bang from the last outlet
                self.out(self.box["numoutlets"] - 1, BANG)
        elif msg == "clear":
            self.data.clear()
        elif isinstance(msg, list):
            self.data[int(msg[0])] = msg[1:]
        else:
            k = int(_first(msg))
            if k in self.data:
                v = self.data[k]
                self.out(0, v if len(v) > 1 else v[0])


class Dict(Obj):
    """dict name: keys holding lists. 'clear'; 'set k v...' and 'replace k v...' store; 'append k v...' adds to the
    end; 'remove k'; 'get k' outputs 'k v...' from outlet 1 (nothing for a missing key). Dicts with the same name share
    their data (MaxSim.dicts: a test hands a reopened device its saved contents there before load())."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        name = str(self.args[0]) if self.args and not str(self.args[0]).startswith("@") else box["id"]
        self.data = sim.dicts.setdefault(name, {})

    def receive(self, inlet, msg):
        words = _words(msg)
        if not words:
            return
        cmd, rest = words[0], [_num(w) for w in words[1:]]
        if cmd == "clear":
            self.data.clear()
        elif cmd in ("set", "replace"):
            self.data[str(rest[0])] = rest[1:]
        elif cmd == "append":
            self.data.setdefault(str(rest[0]), []).extend(rest[1:])
        elif cmd == "remove":
            self.data.pop(str(rest[0]), None)
        elif cmd == "get":
            k = str(rest[0])
            if k in self.data:
                self.out(1, [k] + list(self.data[k]))
            else:                                # as Max: "dict: could not retrieve key", kept for the tests
                self.sim.console.append(f"dict: could not retrieve key {k}")
        elif cmd == "contains":                  # as Max: 1 or 0 from the third outlet (dict.maxref.xml)
            self.out(2, int(str(rest[0]) in self.data))
        else:
            raise NotImplementedError(f"dict: {msg!r}")


class Poly(Obj):
    """poly N 1: voice allocation. Right inlet velocity (cold), left inlet note (hot). A note-on
    takes the first free voice (or, all busy, steals the voice whose note is oldest); a
    note-off (velocity 0) finds the voice holding that note. Outputs voice (1-based), note,
    velocity, right to left."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.n = int(self.args[0]) if self.args else 1
        self.steal = int(self.args[1]) if len(self.args) > 1 else 0
        self.vel = 0
        self.voices = [None] * self.n        # note held by each voice
        self.order = []                      # voices, oldest note first

    def receive(self, inlet, msg):
        assert _first(msg) != "clear", f"{self.id}: poly doesn't understand 'clear' (its own is 'stop')"
        if _first(msg) == "stop":                # as Max: a note-off for each held note, oldest first
            for k in list(self.order):
                note, self.voices[k] = self.voices[k], None
                self.out(2, 0)
                self.out(1, note)
                self.out(0, k + 1)
            self.order = []
            return
        v = int(_first(msg))
        if inlet == 1:
            self.vel = v
            return
        if self.vel > 0:
            if None in self.voices:
                k = self.voices.index(None)
            elif self.steal:
                k = self.order[0]
            else:
                return
            self.voices[k] = v
            if k in self.order:
                self.order.remove(k)
            self.order.append(k)
        else:
            if v not in self.voices:
                return
            k = self.voices.index(v)
            self.voices[k] = None
            self.order.remove(k)
        self.out(2, self.vel)
        self.out(1, v)
        self.out(0, k + 1)


class Change(Obj):
    """change: a number out only when it differs from the last; 'set v' sets the last without output."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.last = self.args[0] if self.args else 0   # Max: the argument is the initial value

    def receive(self, inlet, msg):
        words = msg.split() if isinstance(msg, str) else msg if isinstance(msg, list) else [msg]
        if words and words[0] == "set":
            self.last = _num(words[1]) if isinstance(words[1], str) else words[1]
            return
        v = _first(msg)
        if v != self.last:
            self.last = v
            self.out(0, v)


class Sink(Obj):
    """Audio objects (plugin~, gen~, plugout~): messages to them are accepted and dropped."""
    def receive(self, inlet, msg):
        if (isinstance(msg, str) and len(msg.split()) > 1        # a message box's 'kg0 0' reaches gen~
                and self.box.get("text", "").startswith("gen~")):  # as a list, as in Max
            msg = [_num(t) for t in msg.split()]
        self.received = getattr(self, "received", []) + [msg]


def _set_words(msg):
    """A message's words after 'set' when it is a 'set ...' message (what prepend and append take as their own command,
    as in Max), else None."""
    words = msg if isinstance(msg, list) else str(msg).split() if isinstance(msg, str) else [msg]
    return list(words[1:]) if words[:1] == ["set"] else None


class Prepend(Obj):
    """prepend: its words before each message. 'set <words>' changes them and sends nothing, as in Max: a 'set ...'
    message can't pass through a prepend (another device: a slot's name, 'set <name>', never reached its screen; the
    probes' windows lost every 'set' carried in under a 'prepend <tag>')."""
    def receive(self, inlet, msg):
        words = _set_words(msg)
        if words is not None:
            self.args = [_num(w) if isinstance(w, str) else w for w in words]
            return
        self.out(0, list(self.args) + (msg if isinstance(msg, list) else [msg]))


class Append(Obj):
    """append: its words after each message; 'set <words>' changes them and sends nothing (as prepend)."""
    def receive(self, inlet, msg):
        words = _set_words(msg)
        if words is not None:
            self.args = [_num(w) if isinstance(w, str) else w for w in words]
            return
        self.out(0, (msg if isinstance(msg, list) else [msg]) + list(self.args))


class LivePush(Sink):
    """live.push: every message kept (.received, as a Sink); an attribute set ('play_pad_map serial') is kept, and
    'get<attribute>' answers '<attribute> <value>' from its outlet, as a Max attribute does (a probe asks
    'getplay_pad_map' to see that the object exists; before any is set, play_pad_map reads 'scale', an assumption).
    The real one answered nothing (the probe's first run, Oct 12); v0.2 asks nothing and reads .attrs back through
    Maxobj.getattr instead (Js's view 'attrs')."""
    def receive(self, inlet, msg):
        super().receive(inlet, msg)
        words = msg if isinstance(msg, list) else str(msg).split()
        self.attrs = getattr(self, "attrs", {"play_pad_map": ["scale"]})
        if not words or not isinstance(words[0], str):
            return
        if words[0].startswith("get") and len(words) == 1:
            name = words[0][3:]
            self.out(0, " ".join(map(str, [name] + list(self.attrs.get(name, [])))))
        else:
            self.attrs[words[0]] = list(words[1:])


class Lcd(Obj):
    """lcd: keeps what it was told to draw. ops: every message; poly: the last paintpoly's
    coordinates (lib/visual.py's drawn() reads them back as values)."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.ops, self.poly = [], []

    def receive(self, inlet, msg):
        words = msg if isinstance(msg, list) else str(msg).split()
        words = [_num(str(w)) for w in words]
        self.ops.append(words)
        if words and words[0] == "paintpoly":
            self.poly = [float(v) for v in words[1:]]


class Snapshot(Obj):
    """snapshot~: here a value the test sets (.value); a bang outputs it (with an interval argument
    it would also output on its own, which the tests do by hand)."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.value = 0.0

    def receive(self, inlet, msg):
        if msg == BANG:
            self.out(0, self.value)


class Jsui(Obj):
    """jsui: keeps every message sent to it; lib/visual.py's drawn() runs its script on them."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.received = []

    def receive(self, inlet, msg):
        self.received.append(msg if isinstance(msg, list) else str(msg).split())


_SCRIPTS = {}


def script(name, files=None):
    """A packed script's text: from files, lib/m4l's EMBEDDED, or the first built device holding it."""
    from m4l import EMBEDDED, read_embedded
    body = (files or {}).get(name) or EMBEDDED.get(name) or _SCRIPTS.get(name)
    if body is None:
        from pathlib import Path
        devices = Path(__file__).resolve().parents[1] / "devices"
        # (then the old builds a product keeps in base/, R1 from the probes: Mordant v1.0b5's scripts, for instance)
        for amxd in sorted(devices.glob("*/*/*.amxd")) + sorted(devices.glob("*/*/base/*.amxd")):
            found = read_embedded(amxd)
            if name in found:
                body = _SCRIPTS[name] = found[name]
                break
    assert body is not None, f"js {name}: no script packed in any built device"
    return body.decode("utf-8") if isinstance(body, bytes) else body


class Js(Obj):
    """js <file>: a plain script (no drawing), run in Node by lib/jsrun.py with a stand-in LiveAPI.
    Each message is kept; on 'write' (or bang) the script is replayed from the start and whatever new it
    asked the Live API is handed to the fake Live (sim.live), and what it sent out goes out.
    The script comes from MaxSim(files=...), lib/m4l's EMBEDDED (this process built it), or the
    built device that packs it."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.name = str(self.args[0]) if self.args else ""
        self.script = None
        self.acts_on = {"write", "bang", "groove"}   # the messages after which it reaches Live or its outlet
        if self.name.endswith("-pushcheck.js"):      # a probe's Push check (v0.23; the another device's): news on any of these
            self.acts_on = {"from", "base", "check", "note", "type", "pad_layout", "grabbed", "why"}   # (v0.24, v0.25)
        if self.name == "probe-lights.js":     # a probe's LIGHTS (v0.24): news on any
            self.acts_on = {"lights", "nogrid", "grid", "surface", "matrix", "track", "selected", "press", "paint",
                            "bye", "show", "unshow", "touched", "refresh"}
        if self.name == "dyehouse-clip.js":         # lib/clips.py's recorder: news on any of these
            self.acts_on = {"start", "stop", "now"}
        if self.name == "dyehouse-history.js":      # lib/history.py's undo: news after these
            self.acts_on = {"store", "begin", "undo", "redo"}
        if self.name.endswith("-dice.js"):           # lib/dice.py's scripts: news after a roll
            self.acts_on = {"roll"}
        if self.name.endswith("-four.js"):           # another device's KEEP 1-4: news on an engine switch
            self.acts_on = {"loaded", "engine"}
        if self.name.endswith("-clipin.js"):         # CLIP IN: news after a read
            self.acts_on = {"read"}
        if self.name.endswith("-patterns.js"):       # PATTERN A-D: news on a switch, a bar, the load
            self.acts_on = {"loaded", "bar", "pattern", "playing", "chain"}
        if self.name.endswith("-learn.js"):          # a probe's scale from the keys you play: news on any
            self.acts_on = {"learn", "note", "scale", "root", "mask", "write"}
        if self.name.endswith("-held.js"):           # a probe's HELD: news on any
            self.acts_on = {"note", "active", "steps", "period", "root", "ext", "chord"}
        if self.name.endswith("-pitch.js"):          # a probe's Pitch as notes (v0.13): news on any
            self.acts_on = {"note", "write", "pos", "armed", "mode", "pads", "pad", "range", "root", "octave",
                            "period", "steps", "writes", "mutate"}   # (v0.17: a pattern switched to; v0.19 MUTATE)
        if self.name.endswith(("-takeover.js", "-surface.js")):   # lib/surface.py's layer and its client (the Mordant
            self.acts_on = None                                    # a probe's TAKEOVER, the another device's): news on any
        if self.name == "weld-kit-sounds.js":       # a probe's sounds: a load, the window's DICE, and
            self.acts_on = {"write", "roll", "step", "type", "sound", "shown"}   # v0.5's browser (types, arrows)
        if self.name.endswith("-temp.js"):           # lib/temp.py's TEMP by name: news only when it sends back
            self.acts_on = {"back"}
        if self.name.endswith("-fold.js"):           # a probe's EXPRESSION fold: news on either message
            self.acts_on = {"d", "a"}
        if self.name.endswith("-matrix-fold.js"):    # a probe's MATRIX fold: an amount, a target
            self.acts_on = {"a", "t"}
        if self.name.endswith("-bendkey.js"):        # and BEND IN KEY's table: the key's steps
            self.acts_on = {"steps"}
        if self.name.endswith("-matrix-learn.js"):   # and v0.62's LEARN: a row armed, a control touched
            self.acts_on = {"arm", "name"}
        if self.name.endswith("-pads.js"):           # a probe's pad colours: news on any but 'layout'
            self.acts_on = {"map", "base", "state", "pal"}   # (v0.25: COLOURS)
        if self.name.endswith("-picker.js"):         # a probe's MAP picker: news on a scan or a pick
            self.acts_on = {"scan", "pick", "last", "macros"}   # (v0.19: the last touched; MACROS)
        if self.name.endswith("-arp.js"):            # a probe's ARP order: news on any, once a note is held
            self.acts_on = {"add", "drop", "clear", "style", "octaves", "walk", "scale", "base", "layout"}
        if self.name == "push-probe-report.js":    # a probe's report: news on any
            self.acts_on = {"loaded", "get_major_version", "get_minor_version", "get_bugfix_version",
                            "get_version_string", "slot", "sid", "get_control_names", "pushreply", "me", "mytrack",
                            "seldev", "seltrk", "path", "layout", "note", "pressure", "grab", "grabnone",
                            "grabnomatrix", "grabbed", "gpress", "released",
                            # v0.2: TEST SEQUENTIAL and TEST COLOURS, the pads' expression, what live.push says
                            "sequential", "colourkey", "cc", "poly", "pushsaid",
                            # v0.3: the light tests and GRAB PAD
                            "needgrab", "later", "lit", "swept", "rowslit", "grabpad", "padnoctl", "padgrabbed",
                            "padlit", "padpress", "midisent",
                            # v0.4: CHART, FREE MIDI, TEST GRAB again, what RELEASE sent
                            "charted", "freesent", "freerefused", "freenone", "grabagain", "relraw",
                            # v0.5: RELEASE CLEAR and REPAINT
                            "cleared", "clearraw", "rpaway", "rpback", "rpnone",
                            # v0.6: each surface's type, VALUE and FOLLOW
                            "type", "valued", "follow"}
        self.received, self.ncalls, self.nouts = [], 0, 0
        self.globals = []        # Max's Globals as each message found them (a script that uses one: lib/surface.py)
        # the worker keeps the script's state after the last replay (lib/jsrun.py's keep): while the Live set it sees
        # is as it was, the next replay goes on from there, sent only the messages since, and plays as a replay from
        # the first message would. A script with Math.random or Date goes on from its state too: closer to Max than a
        # replay, which rolls its dice again (what it sent then no longer what it holds) and may send more or less
        self.kept, self.kept_view, self.kept_n = None, None, 0

    def receive(self, inlet, msg):
        import copy
        import jsrun
        if self.script is None:
            self.script = script(self.name, self.sim.files)
        words = str(msg).split()          # (a message's numbers reach the script as numbers, as in Max)
        self.received.append(msg if isinstance(msg, list) else words[:1] + [_num(t) for t in words[1:]])
        shared = "new Global(" in self.script
        if shared:
            self.globals.append(copy.deepcopy(self.sim.bus.globals))
        if self.acts_on is not None and self.received[-1][0] not in self.acts_on:
            return
        if self.name.endswith("-arp.js") and not any(m[0] == "add" for m in self.received):
            return                                  # (nothing held yet: its order is empty, as the patch starts)
        if self.name == "dyehouse-clip.js" and self.received[-1][0] == "now":
            beat = int(float(self.received[-1][1]) + 1e-6)   # its takes start and end on beats:
            if beat == getattr(self, "beat", None):           # between them, nothing new to say
                return
            self.beat = beat
        view = self.sim.live.js_view()
        # what this.patcher.getnamed(name).maxclass finds (a newobj's class is its text's first word), and max.version
        view["boxes"] = {n: (_split(b.get("text", ""))[:1] or ["newobj"])[0] if b["maxclass"] == "newobj" else b["maxclass"]
                         for n, b in self.sim.named.items()}
        view["maxversion"] = getattr(self.sim.live, "maxversion", None)
        # and what a named live.push holds (Maxobj.getattr reads it: a probe's line 3)
        view["attrs"] = {n: dict(self.sim.objs[b["id"]].attrs) for n, b in self.sim.named.items()
                         if isinstance(self.sim.objs.get(b["id"]), LivePush) and hasattr(self.sim.objs[b["id"]], "attrs")}
        g = self.globals if shared else None
        res = None
        seen = json.dumps(view, sort_keys=True)
        if self.kept and seen == self.kept_view:
            try:
                res = jsrun.run_logic(self.script, self.received[self.kept_n:], None,
                                      g[self.kept_n:] if shared else None, (self.ncalls, self.nouts), keep=True,
                                      after=self.kept)
            except jsrun.Gone:
                res = None
            except RuntimeError:
                self.kept = None
                raise
        if res is None:
            self.kept = None
            res = jsrun.run_logic(self.script, self.received, view, g, (self.ncalls, self.nouts), keep=True)
            self.kept_view = seen
        self.kept, self.kept_n = res.get("kept"), len(self.received)
        if shared:
            self.sim.bus.globals.update(res["globals"])
        # what's new is marked sent before it goes: what it sends may come back into this script (a deferlow, run at
        # once here), whose replay then sends only what that message adds
        calls, self.ncalls = res["calls"], res["ncalls"]
        outs, self.nouts = res["outlets"], res["nouts"]
        for target, fn, *args in calls:
            self.sim.live.handle(int(target), ["call", fn] + args)
        for n, *args in outs:      # [outlet, args...]
            self.out(int(n), [_num(v) if isinstance(v, str) else v for v in args] if len(args) > 1 else args[0])


class Line(Obj):
    """line initial grain: 'target time' ramps there, a value every grain ms, ending
    exactly on target (ints in, ints out); a single number jumps; 'stop' ends a ramp where it is;
    'set v' sets the value without output (ending a ramp)."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.value = self.args[0] if self.args else 0
        self.grain = float(self.args[1]) if len(self.args) > 1 else 20.0
        self.token = 0

    def receive(self, inlet, msg):
        vals = msg.split() if isinstance(msg, str) and " " in msg else msg if isinstance(msg, list) else [msg]
        self.token += 1
        if vals[0] == "stop":
            return
        if vals[0] == "set":
            self.value = _num(vals[1]) if isinstance(vals[1], str) else vals[1]
            return
        target = vals[0]
        if len(vals) < 2 or float(vals[1]) <= 0:
            self.value = target
            self.out(0, target)
            return
        start, time, token = self.value, float(vals[1]), self.token
        n = max(1, int(time // self.grain))
        for k in range(1, n + 1):
            def fire(k=k):
                if self.token != token:
                    return
                v = start + (target - start) * k / n
                self.value = target if k == n else (int(v) if isinstance(target, int) else v)
                self.out(0, self.value)
            self.sim.schedule(time * k / n, fire)


class Unpack(Obj):
    def receive(self, inlet, msg):
        vals = msg if isinstance(msg, list) else [msg]
        for k in range(min(len(vals), len(self.args)) - 1, -1, -1):
            self.out(k, vals[k])


class Spray(Obj):
    """spray N [offset]: 'index value ...' -> each value out of outlet index - offset, the next outlets in turn."""
    def receive(self, inlet, msg):
        vals = msg if isinstance(msg, list) else [msg]
        k = int(vals[0]) - (int(self.args[1]) if len(self.args) > 1 else 0)
        for j, v in enumerate(vals[1:]):
            if 0 <= k + j < int(self.args[0]):
                self.out(k + j, v)


class LiveObserver(Obj):
    """live.observer <property>: right inlet 'id N'; outputs the value now and on every change."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.prop = box["text"].split()[1]
        self.target = 0
        sim.observers.append(self)

    def receive(self, inlet, msg):
        words = _words(msg)
        if inlet == 1:
            assert words[0] == "id", msg
            self.target = int(words[1])
            self.notify()

    def notify(self):
        v = self.sim.live.value(self.target, self.prop)
        if v is not None:
            self.out(0, v)


class LiveMap(Obj):
    """live.map: a bang listens for the next control clicked in Live (MaxSim.click_control); it then gives the control's
    path, id ('id N') and name, right to left, and stops listening. 'cancel' stops it; 1 or 0 starts or stops it."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.listening = False

    def receive(self, inlet, msg):
        words = _words(msg)
        if words[0] == "bang":
            self.listening = True
        elif words[0] == "cancel":
            self.listening = False
        elif words[0] in ("int", "float") or isinstance(msg, (int, float)):
            self.listening = bool(_first(msg))
        self.out(3, int(self.listening))

    def clicked(self, target):
        if not self.listening:
            return
        self.listening = False
        t = self.sim.live.targets.get(target, {})
        self.out(3, 0)
        self.out(2, t.get("name", ""))
        self.out(1, f"id {target}")
        self.out(0, self.sim.live.target_path(target) if target in self.sim.live.targets else "")


class Clip(Obj):
    def receive(self, inlet, msg):
        if inlet == 0:
            v = _first(msg)
            self.out(0, min(max(v, self.args[0]), self.args[1]))
        else:
            self.args[inlet - 1] = _first(msg)


class Makenote(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.vel, self.dur = self.args[0], self.args[1]

        self.held = []      # [pitch, still pending] for each note-off to come

    def receive(self, inlet, msg):
        if inlet == 1:
            self.vel = int(_first(msg))
        elif inlet == 2:
            self.dur = float(_first(msg))
        elif msg == "stop":     # note-offs for every held note, now
            held, self.held = self.held, []
            for note in held:
                if note[1]:
                    note[1] = False
                    self.out(1, 0)
                    self.out(0, note[0])
        else:
            p = int(_first(msg))
            self.out(1, self.vel)
            self.out(0, p)
            if self.vel > 0:
                self.sim.pending.append((self.sim.now_ms + self.dur, p))
                note = [p, True]
                self.held.append(note)

                def off():
                    if note[1]:
                        note[1] = False
                        self.held.remove(note)
                        self.out(1, 0)
                        self.out(0, p)
                self.sim.schedule(self.dur, off)


class Midiformat(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.channel = 1

    def receive(self, inlet, msg):
        if inlet == 6:
            self.channel = int(_first(msg))
            return
        ch = self.channel - 1
        if inlet == 4:                                  # channel pressure: two bytes
            for byte in (0xD0 + ch, int(_first(msg))):
                self.out(0, byte)
            return
        assert inlet in (0, 1, 2) and isinstance(msg, list) and len(msg) == 2, msg
        a, b = msg
        # note [pitch vel], poly pressure [pitch value], control change [value controller]
        for byte in {0: (0x90 + ch, a, b), 1: (0xA0 + ch, a, b), 2: (0xB0 + ch, b, a)}[inlet]:
            self.out(0, int(byte))


def midi_starts(b):
    """Where each message starts in a stream of MIDI bytes: three bytes each, but program change and channel pressure
    (0xC0, 0xD0) two."""
    k, out = 0, []
    while k < len(b):
        out.append(k)
        k += 2 if b[k] & 0xF0 in (0xC0, 0xD0) else 3
    return out


class Midiout(Obj):
    def receive(self, inlet, msg):
        self.sim.midi_bytes.append(int(msg))
        self.sim.midi_times.append(self.sim.now_ms)


class Metro(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        m = re.search(r"(\d+)n", box["text"])
        self.ticks = {"16": 120, "8": 240, "4": 480, "32": 60, "2": 960, "1": 1920}[m.group(1)] if m else 120
        sim.metro = self

    def receive(self, inlet, msg):
        parts = msg.split() if isinstance(msg, str) else (list(msg) if isinstance(msg, list) else [msg])
        if parts[0] in (0, 1):             # a free-running metro switched on or off: tests bang its tick
            self.active = parts[0]
            return
        if parts[0] == "interval":
            assert parts[2] == "ticks", msg
            self.ticks = int(parts[1])
        elif parts[0] == "quantize":
            assert parts[2] == "ticks", msg
        else:
            raise ValueError(msg)


class Transport(Obj):
    """transport, banged: where Live is now, as Max answers between metro ticks too (a note-off a
    pipe delays reads its own time, not its step's)."""
    def receive(self, inlet, msg):
        sim = self.sim
        was = sim.abs_ticks
        ticks = sim.abs_ticks = max(was, int(round(sim.now_ms * 480 * sim.tempo / 60000.0)))
        bars, beats, units = sim.position()
        sim.abs_ticks = was
        # its outlets as Max's reference numbers them (transport.maxref.xml; until Oct 20 this answered numerator,
        # denominator and state on 5, 6, 7: plans/process/transport-outlets.md), right to left
        self.out(7, ticks)                 # raw ticks
        self.out(6, sim.running)           # its state: 1 while Live plays (the first play() on, until stop())
        sig = getattr(sim, "reported_signature", None) or sim.signature   # (what Live says, if not its signature: a
        self.out(5, [sig[0], sig[1]])      # the time signature, a list            # denominator of 0 as a set reopens)
        self.out(4, float(sim.tempo))
        self.out(3, 480)                   # resolution (PPQ)
        self.out(2, units)
        self.out(1, beats)
        self.out(0, bars)


class Translate(Obj):
    def receive(self, inlet, msg):
        assert self.args[:2] == ["ticks", "ms"]
        self.out(0, float(_first(msg)) * 60000.0 / (480.0 * self.sim.tempo))


class Message(Obj):
    def receive(self, inlet, msg):
        if inlet == 1:
            self.box["text"] = " ".join(map(str, msg if isinstance(msg, list) else [msg]))
            return
        dollar = msg if isinstance(msg, list) else [msg]
        for part in self.box["text"].split(","):
            toks = []
            for t in part.split():
                m = re.fullmatch(r"\$(\d)", t)
                toks.append(dollar[int(m.group(1)) - 1] if m else _num(t))
            if not toks:
                continue
            if len(toks) == 1 and not isinstance(toks[0], str):
                self.out(0, toks[0])
            elif all(not isinstance(t, str) for t in toks):
                self.out(0, toks)
            else:
                self.out(0, " ".join(map(str, toks)))


class UMenu(Obj):
    """umenu: a plain Max menu, no Live parameter (a probe's window shows the device's menus with it): a number
    chooses that item and sends its index; 'set <n>' chooses it silently; 'clear', 'append <words>' and 'enableitem <i>
    <0|1>' change its items (a probe's MAP picker), silently."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.items, word = [], []
        for t in box.get("items", []) + [","]:          # Max saves the items as words, a comma between items
            if t == ",":
                self.items.append(" ".join(str(x) for x in word))
                word = []
            else:
                word.append(t)
        self.value = 0
        self.disabled = set()

    def receive(self, inlet, msg):
        words = msg if isinstance(msg, list) else ([msg] if isinstance(msg, (int, float)) else str(msg).split())
        if words[:1] == ["clear"]:
            self.items, self.disabled, self.value = [], set(), 0
            return
        if words[:1] == ["append"]:
            self.items.append(" ".join(str(w) for w in words[1:]))
            return
        if words[:1] == ["setitem"]:                    # (a probe's picker, v0.19: its last-touched item)
            i = int(float(words[1]))
            if 0 <= i < len(self.items):
                self.items[i] = " ".join(str(w) for w in words[2:])
            return
        if words[:1] == ["enableitem"]:
            (self.disabled.discard if int(float(words[2])) else self.disabled.add)(int(float(words[1])))
            return
        silent = words[:1] == ["set"]
        words = words[1:] if silent else words
        if not words:
            return
        self.value = max(0, min(len(self.items) - 1, int(float(words[0]))))
        if not silent:
            self.out(0, self.value)


class LiveParam(Obj):
    def __init__(self, sim, box):
        super().__init__(sim, box)
        v = box.get("saved_attribute_attributes", {}).get("valueof", {})
        self.meta = v
        self.value = initial(v) if v else 0     # where Live starts it (m4l.initial)
        self.enabled = box.get("parameter_enable", 0)
        self.attrs = {}          # attributes set by message ('active 0', 'texton ...', 'bgoncolor ...')

    def clamp(self, x):
        lo = self.meta.get("parameter_mmin", 0)
        hi = self.meta.get("parameter_mmax", 127 if self.box["maxclass"] != "live.menu" else 0)
        x = min(max(x, lo), hi)
        if self.meta.get("parameter_type") in (1, 2):  # int, enum
            x = int(round(x))
        return x

    def receive(self, inlet, msg):
        words = msg.split() if isinstance(msg, str) else (msg if isinstance(msg, list) else [msg])
        if words and words[0] == "set":       # 'set v': change what it shows, output nothing
            self.value = self.clamp(float(words[1]))
            return
        if words and words[0] == "outputvalue":   # every live.* control: its value out, unchanged
            self.out(0, self.value)
            return
        if msg == BANG and self.box["maxclass"] == "live.text" and self.box.get("mode", 1) == 1:
            # a toggle: a bang flips it (Cycling '74's live.text reference: "A bang message will toggle the
            # state of the object"); dials, menus, tabs and number boxes send their value again
            self.value = 0 if self.value else 1
            self.out(0, self.value)
            return
        if words and isinstance(words[0], str) and words[0] != BANG and not isinstance(_num(words[0]), (int, float)):
            # an attribute message: changes how it looks, never its value (no undo step in Live)
            self.attrs[words[0]] = " ".join(map(str, words[1:]))
            return
        if msg != BANG:
            self.value = self.clamp(_first(msg))
        if self.box["maxclass"] == "live.text" and self.box.get("mode", 1) == 0:
            # button mode: we don't know for sure whether Max sends a bang (once, on press)
            # or the value (1 on press, 0 on release), so tests run both
            if self.sim.button_output == "bang":
                if self.value:
                    self.out(0, BANG)
            else:
                self.out(0, self.value)
        else:
            self.out(0, self.value)


class Tosymbol(Obj):
    """tosymbol: a message or list as one symbol, its words joined by spaces."""
    def receive(self, inlet, msg):
        self.out(0, " ".join(map(str, msg if isinstance(msg, list) else [msg])))


class Iter(Obj):
    """iter: a list comes out one element at a time, in order."""
    def receive(self, inlet, msg):
        for v in (msg if isinstance(msg, list) else [msg]):
            self.out(0, v)


class Delay(Obj):
    """delay ms: a bang comes out ms later; another bang restarts it, 'stop' cancels it."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.ms = float(self.args[0]) if self.args else 0.0
        self.token = 0

    def receive(self, inlet, msg):
        if inlet == 1:
            self.ms = float(_first(msg))
            return
        self.token += 1
        if msg == "stop":
            return
        token = self.token

        def fire():
            if self.token == token:
                self.out(0, BANG)
        self.sim.schedule(self.ms, fire)


class Midiparse(Obj):
    """midiparse: MIDI bytes in; out, channel first (rightmost): 0 note [pitch vel], 1 poly
    pressure [pitch value], 2 control change [cc value], 4 channel pressure, 5 bend (MSB; with @hires 1 the 14-bit
    value from -1 to 1), 6 channel."""
    SIZES = {0x80: 3, 0x90: 3, 0xA0: 3, 0xB0: 3, 0xC0: 2, 0xD0: 2, 0xE0: 3}

    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.buf = []

    def receive(self, inlet, msg):
        b = int(_first(msg))
        if b >= 0x80:
            self.buf = [b]
            return
        if not self.buf:
            return
        self.buf.append(b)
        st = self.buf[0]
        if len(self.buf) < self.SIZES.get(st & 0xF0, 99):
            return
        kind, data = st & 0xF0, self.buf[1:]
        self.buf = [st]                     # running status
        self.out(6, (st & 0x0F) + 1)
        if kind == 0x90:
            self.out(0, [data[0], data[1]])
        elif kind == 0x80:
            self.out(0, [data[0], 0])
        elif kind == 0xA0:
            self.out(1, [data[0], data[1]])
        elif kind == 0xB0:
            self.out(2, [data[1], data[0]])
        elif kind == 0xD0:
            self.out(4, data[0])
        elif kind == 0xE0:                  # @hires 1: the 14-bit bend from -1 to 1; else its MSB
            hires = "@hires 1" in self.box.get("text", "")
            self.out(5, ((data[1] * 128 + data[0]) - 8192) / 8192 if hires else data[1])


class Multislider(Obj):
    """multislider (display only here): 'set v1 v2 ...' shows a list without output."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.values = []

    def receive(self, inlet, msg):
        words = msg if isinstance(msg, list) else str(msg).split()
        if words and words[0] == "set":
            words = words[1:]
        self.values = [_num(str(w)) for w in words]


class Bus:
    """What Max's global send, receive and value share: every device in a Live set. Give two
    MaxSims the same Bus to have their devices talk."""
    def __init__(self):
        self.receivers = {}      # name -> [Receive]
        self.values = {}         # name -> stored message
        self.globals = {}        # name -> a js Global's properties (every js in Max shares one by its name)

    def deliver(self, name, msg):
        for r in list(self.receivers.get(name, [])):
            r.out(0, msg)


def _local(sim, name):
    """A '---name' is Max for Live's device-local name: unique to each device, as here to each sim."""
    return f"{id(sim)}{name}" if name.startswith("---") else name


class Send(Obj):
    """send name (s name): every message goes to every receive name on the bus, 'set other' too: Max's send has no
    set and can't be renamed (Warp in Live, Oct 20: 'set dyehouse_cable_D' arrived on cable A). forward renames."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.name = _local(sim, str(self.args[0])) if self.args else ""

    def receive(self, inlet, msg):
        self.sim.bus.deliver(self.name, msg)


class Forward(Send):
    """forward name: as send, but 'send other' sends to other from now on (Max's forward; 'set' it passes on)."""
    def receive(self, inlet, msg):
        words = msg if isinstance(msg, list) else str(msg).split()
        if words and words[0] == "send" and len(words) == 2:
            self.name = _local(self.sim, str(words[1]))
            return
        self.sim.bus.deliver(self.name, msg)


class Receive(Obj):
    """receive name (r name): outputs what any send name sends; 'set other' renames."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.name = _local(sim, str(self.args[0])) if self.args else ""
        sim.bus.receivers.setdefault(self.name, []).append(self)

    def receive(self, inlet, msg):
        # as Max: a receive given a name has no inlet ("patchcord inlet out of range"); a nameless one takes 'set'
        assert not self.args, f"{self.id}: 'receive {self.args[0]}' has no inlet (only a nameless receive takes set)"
        words = str(msg).split()
        if words and words[0] == "set":
            self.sim.bus.receivers[self.name].remove(self)
            self.name = words[1]
            self.sim.bus.receivers.setdefault(self.name, []).append(self)


class Value(Obj):
    """value name (v name): a message shared by name; a bang outputs it, anything else stores it."""
    def receive(self, inlet, msg):
        name = str(self.args[0])
        if msg == BANG:
            if name in self.sim.bus.values:
                self.out(0, self.sim.bus.values[name])
        else:
            self.sim.bus.values[name] = msg


class Vexpr(Obj):
    """vexpr: element by element over lists in any inlet ($f1, $f2, ...); the left inlet is hot. As
    Max: the output is as long as the shortest input, so a single number makes a one-element list,
    unless @scalarmode 1, which applies it to every element. Max's functions the displays use
    (lib/visual.py) included."""
    FUNCS = {"min": min, "max": max, "abs": abs, "pow": pow, "tanh": math.tanh, "sqrt": math.sqrt,
             "log10": math.log10, "exp": math.exp, "sin": math.sin, "cos": math.cos, "int": int,
             "floor": math.floor}

    def __init__(self, sim, box):
        super().__init__(sim, box)
        src = box["text"].split(None, 1)[1].replace("\\,", ",")
        self.scalar = bool(re.search(r"@scalarmode\s+1", src))
        src = re.sub(r"@scalarmode\s+\d", "", src).strip()
        src = re.sub(r"\$i(\d)", lambda m: f"int(v{m.group(1)})", src)      # $i: whole numbers, as Max
        self.code = compile(re.sub(r"\$f(\d)", lambda m: f"v{m.group(1)}", src), "<vexpr>", "eval")
        n = max([int(k) for k in re.findall(r"v(\d)", re.sub(r"\$f(\d)", lambda m: f"v{m.group(1)}", src))] or [1])
        self.nvars = n                                   # the inlets the expression uses
        self.ins = [[0.0] for _ in range(max(n, 2))]

    def receive(self, inlet, msg):
        lst = msg if isinstance(msg, list) else [msg]
        if inlet > 0:
            self.ins[inlet] = lst
            return
        self.ins[0] = lst
        used = self.ins[:self.nvars]
        longest = max(len(v) for v in used)
        if self.scalar and all(len(v) in (1, longest) for v in used):
            n = longest
        else:
            n = min(len(v) for v in used)
        out = []
        for k in range(n):
            env = {f"v{j + 1}": float(v[k % len(v)]) for j, v in enumerate(self.ins)}
            out.append(eval(self.code, dict(self.FUNCS), env))
        self.out(0, out)


class ThisDevice(Obj):
    """live.thisdevice: bangs once loaded (MaxSim.load); what it's told is kept in .got ('setwidth N': the device's
    width, a probe's fold)."""
    def receive(self, inlet, msg):
        self.got = getattr(self, "got", []) + [msg]


class LiveBanks(Obj):
    """live.banks (Max 8.6+): changes the device's Push pages while it runs. A stand-in: each message it gets is kept
    in .got as words, a "quoted symbol" one word (a probe's Hit Pad page)."""
    def receive(self, inlet, msg):
        text = " ".join(map(str, msg)) if isinstance(msg, list) else str(msg)
        self.got = getattr(self, "got", []) + [_split(text)]


class Drop(Obj):
    """live.drop: a file dropped on it (sim.drop(path)) leaves as its path, from the left outlet; 'set <path>' keeps a
    path without sending it (.path: the file it keeps, as Live saves it with the set)."""
    def receive(self, inlet, msg):
        words = _words(msg)
        if words and words[0] == "set":
            self.path = " ".join(map(str, words[1:]))
        elif msg == BANG and getattr(self, "path", None):
            self.out(0, self.path)


class BufferObj(Obj):
    """buffer~ <name>: 'replace <file>' reads a file (sim.files gives its sample rate) and bangs its right outlet
    when done; every message it gets is kept in .got, for tests."""
    def receive(self, inlet, msg):
        words = _words(msg)
        self.got = getattr(self, "got", []) + [" ".join(map(str, words))]
        if words and words[0] in ("replace", "read"):
            self.sim.buffers[self.box["text"].split()[1]] = self.sim.files.get(" ".join(words[1:]), 44100.0)
            self.out(1, BANG)


class Peek(Obj):
    """peek~ <name>: a list 'index value' (left inlet) writes value at index of the named buffer~; the writes are kept
    in sim.buffer_data[name] ({index: value}), for tests."""
    def receive(self, inlet, msg):
        words = _words(msg)
        if inlet == 0 and len(words) >= 2:
            self.sim.buffer_data.setdefault(self.box["text"].split()[1], {})[int(words[0])] = float(words[1])


class Info(Obj):
    """info~ <name>: a bang reports the buffer's sample rate from the left outlet."""
    def receive(self, inlet, msg):
        if msg == BANG:
            self.out(0, float(self.sim.buffers.get(self.box["text"].split()[1], 44100.0)))


class Matrixctrl(Obj):
    """matrixctrl: a grid of cells. 'set col row val' sets a cell quietly, 'clear' clears them all,
    a list 'col row val' sets one and outputs it; click(col, row) flips a cell, as a mouse does."""
    def __init__(self, sim, box):
        super().__init__(sim, box)
        self.cells = {}

    def receive(self, inlet, msg):
        words = msg.split() if isinstance(msg, str) else (msg if isinstance(msg, list) else [msg])
        if words[0] == "clear":
            self.cells = {}
        elif words[0] == "set":
            self.cells[(int(words[1]), int(words[2]))] = int(words[3])
        else:
            c, r, v = (int(w) for w in words[:3])
            self.cells[(c, r)] = v
            self.out(0, [c, r, v])

    def click(self, col, row):
        self.receive(0, [col, row, 1 - self.cells.get((col, row), 0)])

    def row(self, r, n=16):
        return [self.cells.get((c, r), 0) for c in range(n)]


class Source(Obj):  # midiin: produces nothing in these tests
    def receive(self, inlet, msg):
        pass


class ThisPatcher(Obj):
    """thispatcher: 'script show name' and 'script hide name' set that box's hidden flag (by varname),
    as Live does to the panel (lib/panel.py's MOD tabs); 'script sendbox name presentation_rect x y w h' moves it
    (a probe's cards, in the order you hear them); other messages are kept and dropped."""
    def receive(self, inlet, msg):
        words = msg if isinstance(msg, list) else str(msg).split()
        if not hasattr(self, "received"):
            self.received = []
        self.received.append(words)          # (appended: a new list each message made a long session quadratic)
        if len(words) == 3 and words[0] == "script" and words[1] in ("show", "hide"):
            box = self.sim.by_varname(words[2])
            if box is None:
                raise KeyError(f"thispatcher: no box named {words[2]!r}")
            box["hidden"] = 1 if words[1] == "hide" else 0
        if len(words) == 8 and words[:2] == ["script", "sendbox"] and words[3] == "presentation_rect":
            box = self.sim.by_varname(str(words[2]))
            if box is None:
                raise KeyError(f"thispatcher: no box named {words[2]!r}")
            box["presentation_rect"] = [float(v) for v in words[4:8]]


class Sub(Obj):
    """p name: a subpatcher (a device's own window). MaxSim runs its boxes as the device's (flatten()): what comes
    into its inlet k leaves its k-th inlet box, left to right as Max numbers them."""
    def receive(self, inlet, msg):
        self.sim.objs[self.sim.subs[self.id][0][inlet]].out(0, msg)


class Inlet(Obj):
    """A subpatcher's inlet box: it passes on what its subpatcher's inlet gets (Sub sends it out)."""


class Outlet(Obj):
    """A subpatcher's outlet box: what it gets leaves the subpatcher's own outlet."""
    def receive(self, inlet, msg):
        parent = next(pid for pid, (_, outs) in self.sim.subs.items() if self.id in outs)
        self.sim.objs[parent].out(self.sim.subs[parent][1].index(self.id), msg)


def flatten(patcher, prefix=""):
    """A patcher's boxes and lines, each subpatcher's ('p name') among them, their ids prefixed '<p box's id>::' (as
    Max lists a subpatcher's parameters); and for each subpatcher its inlet and outlet boxes, left to right."""
    boxes, lines, subs = [], [], {}
    for b in patcher["boxes"]:
        box = dict(b["box"], id=prefix + b["box"]["id"])
        boxes.append(box)
        if "patcher" in box and (box["maxclass"] == "bpatcher"            # (an embedded bpatcher: a probe)
                                 or box["maxclass"] == "newobj" and _split(box.get("text", ""))[:1] == ["p"]):
            inner = box["id"] + "::"
            ib, il, isubs = flatten(box["patcher"], inner)
            boxes += ib
            lines += il
            subs.update(isubs)
            mine = [x for x in ib if x["id"].count("::") == inner.count("::")]
            subs[box["id"]] = tuple([x["id"] for x in sorted((x for x in mine if x["maxclass"] == kind),
                                                            key=lambda x: x.get("patching_rect", [0])[0])]
                                    for kind in ("inlet", "outlet"))
    for ln in patcher["lines"]:
        s, d = ln["patchline"]["source"], ln["patchline"]["destination"]
        lines.append(((prefix + s[0], s[1]), (prefix + d[0], d[1])))
    return boxes, lines, subs


CLASSES = {
    "p": Sub, "bpatcher": Sub, "inlet": Inlet, "outlet": Outlet, "pcontrol": Sink,
    "t": Trigger, "trigger": Trigger, "i": Store, "f": Store, "js": Js,
    "+": Arith, "-": Arith, "*": Arith, "/": Arith, "%": Arith,
    "expr": Expr, "sel": Sel, "select": Sel, "gate": Gate, "uzi": Uzi, "random": Random,
    "coll": Coll, "dict": Dict, "change": Change, "line": Line, "plugin~": Sink, "plugout~": Sink, "gen~": Sink, "prepend": Prepend, "append": Append, "unpack": Unpack, "spray": Spray, "live.observer": LiveObserver, "live.map": LiveMap,
    "pipe": Pipe, "deferlow": Deferlow, "live.path": LivePath, "live.object": LiveObject, "sprintf": Sprintf, "route": Route, "pak": Pak, "pack": Pak, "zl": Zl, "clip": Clip, "makenote": Makenote,
    "midiformat": Midiformat, "midiout": Midiout, "midiin": Source, "thispatcher": ThisPatcher, "metro": Metro,
    "transport": Transport, "translate": Translate, "live.thisdevice": ThisDevice, "buffer~": BufferObj, "peek~": Peek, "info~": Info, "record~": Sink,
    "live.drop": Drop, "live.banks": LiveBanks,
    "live.remote~": LiveRemote, "notein": Source, "polyin": Source, "pgmin": Source, "xbendin": Source, "snapshot~": Snapshot, "touchin": Source, "ctlin": Source, "poly": Poly,
    "iter": Iter, "delay": Delay, "midiparse": Midiparse, "live.push": LivePush, "freebang": Source, "tosymbol": Tosymbol,
    "multislider": Multislider, "number": Multislider, "print": Sink, "flonum": Multislider, "matrixctrl": Matrixctrl, "send~": Sink, "receive~": Sink, "fzero~": Sink,
    "poke~": Sink, "*~": Sink, "clip~": Sink, "mstosamps~": Sink, "peakamp~": Sink,
    "send": Send, "s": Send, "forward": Forward, "receive": Receive, "r": Receive, "value": Value, "v": Value, "vexpr": Vexpr,
    "umenu": UMenu,
}


class MaxSim:
    def __init__(self, patcher, seed=1, button_output="bang", bus=None, files=None):
        self.files = dict(files or {})     # the device's embedded files, for js objects
        self.bus = bus if bus is not None else Bus()
        self.rng = random.Random(seed)
        self.button_output = button_output
        self.objs, self.wires = {}, {}
        self.colls = {}          # named colls' shared data
        self.dicts = {}          # named dicts' shared data
        self.console = []        # what Max would print in its console (a dict asked for a key it lacks...)
        self.metro = None
        self.tempo, self.now_ms, self.abs_ticks = 120.0, 0.0, 0
        self.running = 0         # Live's transport: stopped until play(), which leaves it running; stop() stops it
        self.signature = (4, 4)  # Live's time signature: numerator, denominator
        self.midi_bytes, self.midi_times, self.pending = [], [], []
        self.queue, self.seq = [], 0
        self.live = FakeLive()
        self.bend = 8192   # the instrument's pitch bend, as last set by Mordant
        self.observers = []
        self.named = {}          # varname -> box, panels included (thispatcher's script show/hide)
        boxes, lines, self.subs = flatten(patcher)      # a subpatcher's boxes run as the device's own
        for box in boxes:
            mc = box["maxclass"]
            if box.get("varname"):
                self.named[box["varname"]] = box
            if mc == "panel":
                continue
            if mc == "jsui":
                self.objs[box["id"]] = Jsui(self, box)
                continue
            if mc == "lcd":
                self.objs[box["id"]] = Lcd(self, box)
                continue
            if mc == "comment":
                self.objs[box["id"]] = Comment(self, box)
            elif mc == "message":
                self.objs[box["id"]] = Message(self, box)
            elif mc.startswith("live.") and mc not in ("live.thisdevice", "live.path", "live.object",
                                                         "live.observer", "live.drop"):
                self.objs[box["id"]] = LiveParam(self, box)
            else:
                name = box.get("text", mc).split()[0]
                self.objs[box["id"]] = CLASSES[name](self, box)
        for s, d in lines:
            self.wires.setdefault((s[0], s[1]), []).append((d[0], d[1]))
        # each outlet's cords in the order Max fans out (right to left by patching x), sorted once: boxes don't move,
        # and send() sorted them again for every message (8 % of a patch test, Oct 20)
        for key, dests in self.wires.items():
            dests.sort(key=lambda d: -self.objs[d[0]].box.get("patching_rect", [0])[0])
        self.by_name = {o.meta["parameter_longname"]: o for o in self.objs.values()
                        if isinstance(o, LiveParam) and o.enabled}
        self.depth = 0
        self.files, self.buffers = {}, {}     # dropped files' sample rates; buffer~ name -> its file's rate
        self.buffer_data = {}                 # buffer~ name -> {index: value}, as peek~ writes it

    # -- message passing (depth-first; fan-outs right-to-left by patching x)
    def send(self, oid, outlet, msg):
        self.depth += 1
        if self.depth >= 200:
            raise AssertionError("message loop")
        targets = self.wires.get((oid, outlet))
        if targets:
            objs = self.objs
            for did, inlet in targets:
                objs[did].receive(inlet, msg)
        self.depth -= 1

    # -- Live side
    def load(self, order=None):
        params = [o for o in self.objs.values() if isinstance(o, LiveParam) and o.enabled]
        if order == "shuffle":
            self.rng.shuffle(params)
        for o in params:
            o.receive(0, o.value)
        for o in self.objs.values():
            if isinstance(o, ThisDevice):
                o.out(0, BANG)

    def set_param(self, name, value):
        self.by_name[name].receive(0, value)

    def drop(self, oid, path, samplerate=44100.0):
        """A file dropped on live.drop `oid` (its sample rate, for buffer~ and info~)."""
        self.files[path] = samplerate
        self.objs[oid].path = path                 # (kept, as Live keeps a live.drop's file with the set)
        self.objs[oid].out(0, path)

    def by_varname(self, name):
        return self.named.get(name)

    def shown(self, name):
        """Whether the box named so is on the panel: in presentation and not hidden."""
        box = self.named[name]
        return bool(box.get("presentation")) and not box.get("hidden")

    def press(self, name):
        self.by_name[name].receive(0, 1)
        self.by_name[name].receive(0, 0)  # release

    def param(self, name):
        return self.by_name[name].value

    def bar_ticks(self):
        num, den = self.signature
        return num * 1920 // den

    def position(self):
        """bars, beats, units as Max's transport reports them, in Live's time signature: a
        beat is the signature's note value, units are ticks (480 a quarter) into the beat."""
        num, den = self.signature
        bars, rest = divmod(self.abs_ticks, self.bar_ticks())
        beats, units = divmod(rest, 1920 // den)
        return bars + 1, beats + 1, units

    def schedule(self, delay_ms, fn):
        self.seq += 1
        heapq.heappush(self.queue, (self.now_ms + max(delay_ms, 0.0), self.seq, fn))

    def run_until(self, ms):
        while self.queue and self.queue[0][0] <= ms + 1e-9:
            when, _, fn = heapq.heappop(self.queue)
            self.now_ms = when
            fn()

    def live_set(self, **props):
        """Change arm / session_record / record_mode / the song's key, as the user would in Live."""
        for k, v in props.items():
            setattr(self.live, k, v)
            for o in self.observers:
                if o.prop == k:
                    o.notify()

    def click_control(self, target):
        """The user clicks the control `target` in Live: a live.map listening takes it (Max for Live's own
        click-to-select, as Live's LFO maps), and Live's selected parameter becomes it (a Rack's macro or a Live
        device's control; a click on a Max for Live device's control doesn't set it in Live: the owner, Oct 7)."""
        for o in list(self.objs.values()):
            if isinstance(o, LiveMap):
                o.clicked(target)
        self.live_set(selected_parameter=target)

    def delete_target(self, target):
        """The mappable parameter `target` is deleted in Live (its device removed)."""
        del self.live.targets[target]
        for o in list(self.objs.values()):
            if isinstance(o, LivePath) and o.following == target:
                o.following = 0
                o.out(0, "id 0")

    def move_target(self, target, path):
        """`target` moves (its device dragged elsewhere): same object, same id, a new path."""
        self.live.targets[target]["path"] = path
        for o in list(self.objs.values()):
            if isinstance(o, LivePath) and o.following == target:
                o.out(0, f"id {target}")

    def set_clip(self, slot, **props):
        """Change the scale of the clip in `slot` (on this device's track), as the user would."""
        clip = self.live.slots[slot]
        for k, v in props.items():
            clip[k] = v
            for o in self.observers:
                if o.prop == k and o.target == 200 + slot:
                    o.notify()

    def comment_text(self, oid):
        return self.objs[oid].text

    def stop(self):
        """Live's transport stops (a transport banged says so); the next play() starts it again."""
        self.running = 0

    def play(self, bars=2, tempo=120.0, start_ticks=0):
        """Run the transport from start_ticks; returns [(step_index, pitch, velocity)]
        for every note-on, step_index counted in metro ticks from the start. The
        note-on times in ms (from the start) are left in self.note_ms."""
        self.tempo = tempo
        self.running = 1
        ms_per_tick = 60000.0 / (480 * tempo)
        t0 = start_ticks * ms_per_tick
        self.midi_bytes, self.midi_times = [], []
        t = start_ticks
        end = start_ticks + bars * self.bar_ticks()
        while t < end:
            if t % self.metro.ticks == 0:
                self.run_until(t * ms_per_tick)
                self.abs_ticks = t
                self.now_ms = t * ms_per_tick
                self.metro.out(0, BANG)
                self.run_until(self.now_ms)
            t += 1
        self.run_until(end * ms_per_tick - 1e-6)
        step_ms = self.metro.ticks * ms_per_tick
        events, self.note_ms, self.note_bends = [], [], []
        b, times = self.midi_bytes, self.midi_times
        for k in midi_starts(b):
            if b[k] & 0xF0 == 0xE0:
                self.bend = b[k + 1] + 128 * b[k + 2]
            if b[k] & 0xF0 == 0x90 and b[k + 2] > 0:
                self.note_bends.append(self.bend)
                rel = times[k] - t0
                events.append((int((rel + 1e-6) // step_ms), b[k + 1], b[k + 2]))
                self.note_ms.append(rel)
        return events


class PushView(FakeLive):
    """One device's view of a FakePush set: 'this_device' is its id, its track 'this_device canonical_parent', that
    track's view 'this_device canonical_parent view' (id 10000 + the track); the rest as FakeLive (clip slots and so
    on, for a device's other Live API work)."""
    def __init__(self, push, dev, track):
        super().__init__()
        self.push, self.dev, self.track = push, dev, track
        self.calls = push.calls_of(dev)

    def resolve(self, path):
        if path == "this_device":
            return self.dev
        if path == self.TRACK:
            return self.track
        if path == self.TRACK + " view":
            return 10000 + self.track
        if path in FakePush.SURFACES:
            return FakePush.SURFACES[path][0]
        return super().resolve(path)

    def value(self, target, prop):
        if target == 2 and prop == "selected_track":
            return f"id {self.push.selected}"
        if target == 10000 + self.track and prop == "selected_device":
            return f"id {self.push.seldev.get(self.track, 0)}"
        return super().value(target, prop)

    def handle(self, target, words):
        if target in FakePush.TYPES:
            return self.push.handle(self.dev, target, [str(w) for w in words])
        return super().handle(target, words)


class FakePush:
    """A Live set with Push 3, for the family's Surface layer (lib/surface.py): a Komplete Kontrol on control surface 0 and Push 3 on surface 3, their ids negative as Live's
    (-4, -2), Push's Button_Matrix -3. Tracks are ids (50, 51 ...); the selected track, and each track's selected device.
    Several devices, each a MaxSim with its own id on a track, sharing one Bus (Max's global send and receive, and the
    js Globals: every device in Live runs in one Max).

    It keeps every call to Push's surface and grid, by device (.log: (device, words)); who holds the grid (.holder);
    the pads as Push shows them (.lit: (column, row from the top) -> colour); and what Live would not take quietly
    (.problems): a grab while another device holds the grid, a light or a release from a device that doesn't hold it,
    a device deleted still holding it. What Live does then is to verify; the family's devices must never do it.

        push = FakePush(selected=50)
        loom = push.add(LOOM, track=50)                # a MaxSim, loaded (sim.dev its id)
        mor = push.add(MORDANT, track=51, saved={"Takeover": 1})
        push.select(51); push.run(); push.holder == mor.dev
        push.delete(mor)                               # its freebang; then gone
    """
    SURFACE, GRID = -2, -3
    SURFACES = {"control_surfaces 0": (-4, "Komplete_Kontrol_A"), "control_surfaces 3": (-2, "Push3")}
    TYPES = {-4: "Komplete_Kontrol_A", -2: "Push3", -3: "Button_Matrix"}

    def __init__(self, selected=50):
        self.bus = Bus()
        self.selected = selected
        self.seldev = {}               # track -> the id of its selected device (Live's device view)
        self.holder = None
        self.log, self.problems, self.lit = [], [], {}
        self.devices, self.tracks = {}, {}
        self.next_id = 7001
        self._calls = {}

    def calls_of(self, dev):
        return self._calls.setdefault(dev, [])

    def add(self, patch, track, saved=None, files=None, load=True):
        """A device on `track`: a MaxSim of `patch`, its saved values (by long name) set, loaded."""
        dev = self.next_id
        self.next_id += 1
        sim = MaxSim(patch, bus=self.bus, files=files)
        sim.live = PushView(self, dev, track)
        sim.dev = dev
        self.devices[dev], self.tracks[dev] = sim, track
        for k, v in (saved or {}).items():
            sim.by_name[k].value = v
        if load:
            sim.load()
        return sim

    def handle(self, dev, target, words):
        self.calls_of(dev).append((target, " ".join(words)))
        if words == ["gettype"]:
            return f"type {self.TYPES[target]}"
        self.log.append((dev, " ".join(words)))
        if target == self.SURFACE and words[:2] == ["call", "get_control"]:
            return f"get_control id {self.GRID}" if words[2:] == ["Button_Matrix"] else "get_control id 0"
        if target == self.SURFACE and words[:2] == ["call", "grab_control"]:
            if self.holder not in (None, dev):
                self.problems.append(f"{dev} grabbed the grid {self.holder} holds")
            self.holder = dev
            return None
        if target == self.SURFACE and words[:2] == ["call", "release_control"]:
            if self.holder != dev:
                self.problems.append(f"{dev} released the grid {self.holder} holds")
            else:
                self.holder = None
            return None
        if target == self.GRID and words[:2] == ["call", "send_value"]:
            c, r, v = (int(float(w)) for w in words[2:5])
            if self.holder != dev:
                self.problems.append(f"{dev} lit a pad of the grid {self.holder} holds")
            else:
                self.lit[(c, r)] = v
            return None
        raise AssertionError(f"unexpected call on Push ({target}): {words}")

    def sims(self):
        return list(self.devices.values())

    def _notify(self, prop, sims=None):
        for sim in self.sims() if sims is None else sims:
            for o in list(sim.observers):
                if o.prop == prop:
                    o.notify()

    def select(self, track):
        """Another track selected in Live."""
        self.selected = track
        self._notify("selected_track")

    def select_device(self, sim):
        """sim's device clicked in its track's device view (it becomes that track's selected device)."""
        track = self.tracks[sim.dev]
        self.seldev[track] = sim.dev
        self._notify("selected_device", [s for d, s in self.devices.items() if self.tracks[d] == track])

    def switch(self, sim, on):
        """The device's own on/off switch (live.thisdevice's middle outlet)."""
        for o in list(sim.objs.values()):
            if isinstance(o, ThisDevice):
                o.out(1, 1 if on else 0)

    def delete(self, sim):
        """The device deleted (or replaced by a preset): its freebang, then it is gone (its receives with it); Live gives
        back what it still held."""
        for o in list(sim.objs.values()):
            if o.box.get("text", "").split()[:1] == ["freebang"]:
                o.out(0, BANG)
        for rs in self.bus.receivers.values():
            rs[:] = [r for r in rs if r.sim is not sim]
        del self.devices[sim.dev]
        if self.holder == sim.dev:
            self.holder = None
            self.problems.append(f"{sim.dev} deleted still holding the grid (Live let it go)")

    def run(self, ms=300):
        """Time passes for every device."""
        for sim in self.sims():
            sim.run_until(sim.now_ms + ms)

    def grabs(self, dev=None):
        """Each grab and release, in order: (device, 'grab' | 'release')."""
        return [(d, w.split()[1].split("_")[0]) for d, w in self.log
                if w.split()[1:2] in (["grab_control"], ["release_control"]) and dev in (None, d)]
