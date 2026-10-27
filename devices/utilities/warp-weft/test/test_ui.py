#!/usr/bin/env python3
"""Tests for Warp and Weft on a shared bus, in lib/maxsim.py.

    python3 test/test_ui.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "lib"))
sys.path.insert(0, str(HERE.parent))
from kit import RINSE, cable, reset_bytes  # noqa: E402
from kittest import Expect, check_rinse, midi_messages, say  # noqa: E402
import jsrun  # noqa: E402
from m4l import read_amxd, read_embedded  # noqa: E402
from maxsim import Bus, MaxSim  # noqa: E402
import build  # noqa: E402

WARP, WEFT = read_amxd(build.OUT_WARP), read_amxd(build.OUT_WEFT)
expect = Expect()


def device(patch, bus):
    sim = MaxSim(patch, bus=bus)
    sim.load()
    return sim


def play(warp, ch=3):
    """An MPE note on the Warp's track, as notein, xbendin, touchin and ctlin send it (channel first)."""
    o = warp.objs
    o["bend-in"].out(1, ch), o["bend-in"].out(0, 9000)
    o["press-in"].out(1, ch), o["press-in"].out(0, 90)
    o["cc-in"].out(2, ch), o["cc-in"].out(1, 74), o["cc-in"].out(0, 30)
    o["n-in"].out(2, ch), o["n-in"].out(1, 100), o["n-in"].out(0, 60)
    o["n-in"].out(2, ch), o["n-in"].out(1, 0), o["n-in"].out(0, 60)


WANT = [("bend", 3, 9000), ("press", 3, 90), ("cc", 3, 74, 30), ("note", 3, 60, 100), ("off", 3, 60)]

print("a note with its bend, pressure and timbre goes down cable A into every Weft on A")
bus = Bus()
warp, weft1, weft2 = device(WARP, bus), device(WEFT, bus), device(WEFT, bus)
play(warp)
expect(midi_messages(weft1) == WANT, f"Weft 1: {midi_messages(weft1)}")
expect(midi_messages(weft2) == WANT, "Weft 2 too: one cable, several synths")
print("another cable doesn't hear it; switching the Warp to B reaches it")
weft2.set_param("Cable", 1)
play(warp)
expect(len(midi_messages(weft2)) == 5, "a Weft on B: nothing new")
warp.set_param("Cable", 1)
n1 = len(midi_messages(weft1))
play(warp)
expect(midi_messages(weft2)[5:] == WANT and len(midi_messages(weft1)) == n1, "Warp on B: the B Weft plays, the A one doesn't")
print("THRU: the Warp's own track keeps its MIDI, unless THRU is off; the Weft's own MIDI plays too")
for b in (0x90, 64, 90):
    warp.objs["midiin"].out(0, b)
expect(warp.midi_bytes == [0x90, 64, 90], f"THRU on: {warp.midi_bytes}")
warp.set_param("Thru", 0)
for b in (0x90, 65, 90):
    warp.objs["midiin"].out(0, b)
expect(warp.midi_bytes == [0x90, 64, 90] + reset_bytes(),
       "THRU off: what it let through is stopped (the reset into its own track), and nothing more")
n = len(weft1.midi_bytes)
for b in (0x91, 50, 70):
    weft1.objs["midiin"].out(0, b)
expect(weft1.midi_bytes[n:] == [0x91, 50, 70], "the Weft's own track passes through")
check_rinse(WEFT, expect, "Weft")
check_rinse(WARP, expect, "Warp")

print("nothing hangs (v0.2): a note held when the Warp goes, or either Cable changes, is let go")


def hold(warp, p=60, ch=2):
    o = warp.objs
    o["n-in"].out(2, ch), o["n-in"].out(1, 100), o["n-in"].out(0, p)


def offs(sim, since):
    return [m for m in midi_messages(sim)[since:] if m[0] == "off"]


bus = Bus()
warp, weft = device(WARP, bus), device(WEFT, bus)
hold(warp, 60), hold(warp, 64, 3)
n = len(midi_messages(weft))
warp.objs["free"].out(0, "bang")                       # the Warp deleted
expect(sorted(offs(weft, n)) == [("off", 2, 60), ("off", 3, 64)], f"the Warp deleted: both let go ({offs(weft, n)})")
n = len(midi_messages(weft))
warp.objs["free"].out(0, "bang")
expect(offs(weft, n) == [], "a second release: nothing left to let go")

bus = Bus()
warp, weft = device(WARP, bus), device(WEFT, bus)
hold(warp, 62)
n = len(midi_messages(weft))
warp.set_param("Cable", 1)
expect(offs(weft, n) == [("off", 2, 62)], f"the Warp to cable B: the A Weft lets go ({offs(weft, n)})")

bus = Bus()
warp, weft = device(WARP, bus), device(WEFT, bus)
hold(warp, 67, 5)
n = len(midi_messages(weft))
weft.set_param("Cable", 3)
expect(offs(weft, n) == [("off", 5, 67)], f"the Weft to cable D: it lets go of what A played ({offs(weft, n)})")
hold(warp, 69)
expect(offs(weft, len(midi_messages(weft))) == [] and all(m[2] != 69 for m in midi_messages(weft) if m[0] == "note"),
       "and A's notes no longer reach it")

bus = Bus()
warp, weft = device(WARP, bus), device(WEFT, bus)
hold(warp, 60)
warp.objs["n-in"].out(2, 2), warp.objs["n-in"].out(1, 0), warp.objs["n-in"].out(0, 60)   # played and let go
n = len(midi_messages(weft))
weft.set_param("Cable", 1)
expect(offs(weft, n) == [], "a note already let go isn't let go again")
bus = Bus()
warp, weft = device(WARP, bus), device(WEFT, bus)
hold(warp, 60)
bus.deliver(RINSE, "rinse")
n = len(midi_messages(weft))
weft.set_param("Cable", 1)
expect(offs(weft, n) == [], "after a reset, nothing is held")
expect(WARP.get("is_mpe") == 1 and WEFT.get("is_mpe") == 1, "both are MPE devices: Live sends them each note on its channel")


def shown(sim, path, oid):
    js = sim.objs[f"{oid}-js"]
    return jsrun.run(read_embedded(path)[js.box["filename"]].decode(), js.received,
                     js.box["presentation_rect"][2:])["values"]


print("the cable selector (v1.0b1): one live.tab, Cable, A-D as the menu was, laid over its drawing")
for path, patch in ((build.OUT_WARP, WARP), (build.OUT_WEFT, WEFT)):
    tab = next(b["box"] for b in patch["boxes"] if b["box"].get("id") == "cable")
    v = tab["saved_attribute_attributes"]["valueof"]
    expect(tab["maxclass"] == "live.tab" and v["parameter_longname"] == "Cable" and v["parameter_enum"] == list("ABCD")
           and v["parameter_initial"] == [0.0] and v.get("parameter_invisible", 0) == 0,
           f"{path.stem}: Cable a live.tab, A-D from A, automatable")
    seg = next(b["box"] for b in patch["boxes"] if b["box"].get("id") == "cable-seg-js")
    sx, sy, sw, sh = seg["presentation_rect"]
    tx, ty, tw, th = tab["presentation_rect"]
    expect(tab["textcolor"] == [0, 0, 0, 0] and sx == tx and sw == tw and ty > sy and ty + th == sy + sh,
           f"{path.stem}: transparent over the drawn segments, under the label pill")
bus = Bus()
weft = device(WEFT, bus)
expect(shown(weft, build.OUT_WEFT, "cable-seg") == [0, "A"], "the drawing shows A")
weft.set_param("Cable", 3)
expect(shown(weft, build.OUT_WEFT, "cable-seg") == [3, "D"] and weft.comment_text("c-note") == "PLAYS CABLE D",
       f"D chosen: drawn, and named on the card ({weft.comment_text('c-note')})")

print("the screens: the notes held in words, a keyboard of them, each note's bend, pressure and timbre")
bus = Bus()
warp, weft = device(WARP, bus), device(WEFT, bus)
expect(shown(warp, build.OUT_WARP, "status") == [0, "nothing held", "", "play on this track"],
       f"Warp, nothing held: {shown(warp, build.OUT_WARP, 'status')}")
expect(shown(weft, build.OUT_WEFT, "status")[:3] == [0, "Warp A: quiet", "nothing held"],
       f"Weft, a Warp on A, quiet: {shown(weft, build.OUT_WEFT, 'status')}")
for ch, (p, bend, press, timbre) in enumerate([(60, 8192, 90, 64), (64, 11000, 70, 80), (67, 6000, 110, 50)], start=2):
    o = warp.objs
    o["bend-in"].out(1, ch), o["bend-in"].out(0, bend)
    o["press-in"].out(1, ch), o["press-in"].out(0, press)
    o["cc-in"].out(2, ch), o["cc-in"].out(1, 74), o["cc-in"].out(0, timbre)
    o["n-in"].out(2, ch), o["n-in"].out(1, 100), o["n-in"].out(0, p)
expect(shown(warp, build.OUT_WARP, "status") == [3, "3 notes held", "", "C3 E3 G3"],
       f"Warp: {shown(warp, build.OUT_WARP, 'status')}")
expect(shown(weft, build.OUT_WEFT, "status") == [3, "Warp A: playing", "3 notes held", "C3 E3 G3"],
       f"Weft: {shown(weft, build.OUT_WEFT, 'status')}")
keys = shown(weft, build.OUT_WEFT, "keys")
expect(keys[0] == 48 and sorted(n for n, _ in keys[2]) == [60, 64, 67], f"the keyboard: C3 E3 G3 on C2-B4: {keys}")
for sim, path in ((warp, build.OUT_WARP), (weft, build.OUT_WEFT)):
    slots = shown(sim, path, "expr")
    want = [["C3", 0.0, 90 / 127, 64 / 127], ["E3", (11000 - 8192) / 8192, 70 / 127, 80 / 127],
            ["G3", (6000 - 8192) / 8192, 110 / 127, 50 / 127], ["\u2014"]]
    expect(all(len(a) == len(b) and a[0] == b[0] and all(abs(x - y) < 1e-6 for x, y in zip(a[1:], b[1:]))
               for a, b in zip(slots, want)),
           f"{path.stem}: a slot each, its own bend (from the middle), pressure and timbre: {slots}")
for p in (69, 71, 72):
    warp.objs["n-in"].out(2, 9), warp.objs["n-in"].out(1, 90), warp.objs["n-in"].out(0, p)
slots = shown(weft, build.OUT_WEFT, "expr")
expect([s[0] for s in slots] == ["C3", "E3", "G3", "+3"], f"six held: three slots and '+3': {[s[0] for s in slots]}")
for p in (69, 71, 72, 64):
    warp.objs["n-in"].out(2, 9 if p != 64 else 3), warp.objs["n-in"].out(1, 0), warp.objs["n-in"].out(0, p)
expect(shown(weft, build.OUT_WEFT, "status")[:3] == [2, "Warp A: playing", "2 notes held"], "one let go: two held")
weft.set_param("Cable", 2)
expect(shown(weft, build.OUT_WEFT, "keys")[2] == [] and shown(weft, build.OUT_WEFT, "expr")[0] == ["\u2014"],
       "Weft to cable C: nothing held")

print("THE SENDER (v1.0b1): a Warp on the cable or not, playing or quiet, how many; read as a Weft loads")
WARPS = "dyehouse_warps_"


def delete(sim):
    sim.objs["free"].out(0, "bang")
    for rs in sim.bus.receivers.values():
        rs[:] = [r for r in rs if getattr(r, "sim", None) is not sim]


def sender(weft):
    return shown(weft, build.OUT_WEFT, "status")[1:]


bus = Bus()
weft = device(WEFT, bus)
expect(sender(weft) == ["no Warp on A", "nothing arrives", "put a Warp on A"], f"alone: {sender(weft)}")
warp = device(WARP, bus)
expect(bus.values.get(WARPS + "A") == 1 and sender(weft)[0] == "Warp A: quiet",
       f"a Warp loads on A: counted ({bus.values.get(WARPS + 'A')}), {sender(weft)[0]}")
late = device(WEFT, bus)
expect(sender(late)[0] == "Warp A: quiet", f"a Weft loaded later reads the count: {sender(late)[0]}")
warp.set_param("Cable", 1)
expect(bus.values.get(WARPS + "A") == 0 and bus.values.get(WARPS + "B") == 1 and sender(weft)[0] == "no Warp on A",
       f"the Warp moves to B: A {bus.values.get(WARPS + 'A')}, B {bus.values.get(WARPS + 'B')}; {sender(weft)[0]}")
warp.set_param("Cable", 1)
expect(bus.values.get(WARPS + "B") == 1, "chosen again: counted once")
weft.set_param("Cable", 1)
expect(sender(weft)[0] == "Warp B: quiet", f"the Weft moves to B too: {sender(weft)[0]}")
two = device(WARP, bus)
two.set_param("Cable", 1)
expect(bus.values.get(WARPS + "B") == 2 and sender(weft)[:2] == ["2 Warps on B", "quiet"],
       f"a second Warp on B: {sender(weft)}")
two.objs["n-in"].out(2, 1), two.objs["n-in"].out(1, 100), two.objs["n-in"].out(0, 62)
expect(sender(weft)[:3] == ["2 Warps on B", "1 note held", "D3"], f"one of them playing: {sender(weft)}")
delete(two)
expect(bus.values.get(WARPS + "B") == 1 and sender(weft)[:2] == ["Warp B: quiet", "nothing held"],
       f"the playing one deleted: its note let go, the count back to 1: {sender(weft)}")
delete(warp)
expect(bus.values.get(WARPS + "B") == 0 and sender(weft)[0] == "no Warp on B",
       f"the last Warp deleted: the value back to 0, {sender(weft)[0]}")
say(bus, cable("cable", "B"), ["note", 65, 100, 1])
expect(sender(weft)[:3] == ["cable B: playing", "1 note held", "F3"],
       f"notes from another sender (another device's Notes Out): {sender(weft)}")
reopened = MaxSim(WARP, bus=bus)
reopened.set_param("Cable", 2)
reopened.load()
expect(bus.values.get(WARPS + "C") == 1 and bus.values.get(WARPS + "A") == 0
       and shown(reopened, build.OUT_WARP, "cable-seg") == [2, "C"] and reopened.comment_text("c-note") == "SENDS CABLE C",
       f"a set reopening with a Warp on C: counted on C only (A {bus.values.get(WARPS + 'A')}, "
       f"C {bus.values.get(WARPS + 'C')})")

for rel, oid in ():       # (the other listeners on a cable, in devices not here)
    path = HERE.parents[2] / rel
    if not path.exists():
        continue
    p = read_amxd(path)
    from m4l import flat
    boxes, lines = flat(p)
    route = next(b["box"] for b in boxes if b["box"]["id"] == oid)
    words = route["text"].split()[1:]
    last = len(words)
    used = {ln["patchline"]["source"][1] for ln in lines if ln["patchline"]["source"][0] == oid}
    expect("warps" not in words and last not in used, f"{path.stem}: '{route['text']}', its unmatched outlet unused")
expect.done()
