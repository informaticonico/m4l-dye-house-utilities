#!/usr/bin/env python3
"""Selvedge's panel in lib/maxsim.py: the readout, the meter, the scale's steps, the columns and the key's colours.

    python3 test/test_ui.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "lib"))
sys.path.insert(0, str(HERE.parent))
import jsrun  # noqa: E402
from kit import BLUE, KEY, YELLOW, color_msg  # noqa: E402
from kittest import Expect, say  # noqa: E402
from m4l import read_amxd, read_embedded  # noqa: E402
from maxsim import Bus, MaxSim  # noqa: E402
from scales import SCALES  # noqa: E402
import build  # noqa: E402

expect = Expect()
PATCH = read_amxd(build.OUT)
FILES = read_embedded(build.OUT)


def drawn(sim, oid):
    js = sim.objs[f"{oid}-js"]
    return jsrun.run(FILES[js.box["filename"]].decode(), js.received, js.box["presentation_rect"][2:])["values"]


def heard(sim, pitch, idx, cents, hz):
    """gen~'s readouts as they change: the step's pitch, its index, the cents from it; fzero~'s Hz."""
    sim.objs["chg-t"].receive(0, pitch)
    sim.objs["chg-i"].receive(0, idx)
    sim.objs["chg-c"].receive(0, cents)
    sim.objs["hz-t"].receive(0, hz)


s = MaxSim(PATCH)
s.load()

print("the meter, flat: the cents from the nearest step; at rest when nothing is heard")
s.objs["chg-c"].receive(0, 12.0)
needle = s.objs["needle-js"]
expect(needle.received[-1] == ["value", 12.0], f"+12 cents reaches it: {needle.received[-1:]}")
expect(drawn(s, "needle") == [12, 1], f"drawn at +12, reading: {drawn(s, 'needle')}")
s.objs["chg-i"].receive(0, -1)
expect(needle.received[-1] == ["idle"] and drawn(s, "needle")[1] == 0, "nothing heard: it rests")
expect(s.comment_text("step") == "listening" and s.comment_text("name") == "" and s.comment_text("hz") == "",
       f"listening: {s.comment_text('step')!r} {s.comment_text('name')!r}")

print("a note on A 19-EDO (the README's example, as it is): step 4 of 19, B3 -11 cents")
s.set_param("Scale", 10)
steps = SCALES[10][1]
pitch = 60 + 9 + steps[3]
heard(s, pitch, 3, 6.0, 492.6)
expect(s.comment_text("step") == "step 4 of 19", s.comment_text("step"))
expect(s.comment_text("name") == "B3 -11 cents", f"the step is 11 cents under B3: {s.comment_text('name')}")
expect(s.comment_text("hz") == "492.6 Hz" and s.comment_text("sub") == "the nearest step of A 19-EDO",
       f"{s.comment_text('hz')} / {s.comment_text('sub')}")
got = drawn(s, "strip")
expect(got[0] == 19 and got[1] == 3 and got[2] == ["A", "Bb", "B", "C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab"],
       f"the strip: 19 steps, the 4th lit, the twelve names from A: {got}")
s.set_param("Scale", 9)
got = drawn(s, "strip")
expect(got[0] == 13 and len(got[2]) == 10, f"Bohlen-Pierce: 13 steps over a tritave, every other name: {got}")
s.set_param("Scale", 2)

print("ROOT, SCALE and KEY as columns, Live's own menus laid over them; ROOT and SCALE pale unless Key is Own")
boxes = {b["box"]["id"]: b["box"] for b in PATCH["boxes"]}
for var, name in (("root", "Root"), ("scale", "Scale"), ("keysrc", "Key")):
    box, col = boxes[var], boxes[f"{var}-col-js"]
    expect(box["maxclass"] == "live.menu" and box["textcolor"] == [0, 0, 0, 0]
           and box["presentation_rect"] == col["presentation_rect"]
           and box["saved_attribute_attributes"]["valueof"]["parameter_longname"] == name,
           f"{name}: transparent over its column")
bus = Bus()
say(bus, KEY, [9, 10])
bus.values[KEY] = [9, 10]
t = MaxSim(PATCH, bus=bus)
t.load()
expect(drawn(t, "root-col") == [["root", "A", 0]] and drawn(t, "keysrc-col") == [["keysrc", "Own key", 0]],
       f"Own key: ROOT A, not pale: {drawn(t, 'root-col')}")
expect(t.comment_text("fk-readout") == "its own key" and t.comment_text("own") == "own: A Minor",
       f"PLAYS: {t.comment_text('fk-readout')} / {t.comment_text('own')}")
t.set_param("Key", 2)
expect(drawn(t, "root-col") == [["root", "A", 1]] and drawn(t, "scale-col") == [["scale", "Minor", 1]],
       f"Tannin key: ROOT and SCALE pale: {drawn(t, 'scale-col')}")
kc = [m for m in t.objs["keysrc-col-js"].received if m[0] == "kc"]
expect(kc and color_msg([float(v) for v in kc[-1][1:]]) == color_msg(BLUE), f"KEY in Tannin's blue: {kc[-1:]}")
expect(t.comment_text("fk-readout") == "A 19-EDO" and t.comment_text("sub") == "the nearest step of A 19-EDO",
       f"PLAYS Tannin's A 19-EDO: {t.comment_text('fk-readout')}; {t.comment_text('sub')}")
expect(drawn(t, "strip")[0] == 19, "the strip shows Tannin's scale")
say(bus, KEY, "gone")
expect(t.comment_text("fk-readout") == "no Tannin" and t.comment_text("sub") == "the nearest step of A Minor",
       f"Tannin gone: its own key ({t.comment_text('sub')})")
t.set_param("Key", 0)
kc = [m for m in t.objs["keysrc-col-js"].received if m[0] == "kc"]
expect(color_msg([float(v) for v in kc[-1][1:]]) == color_msg(YELLOW), "Own key: KEY in the card's yellow")

print("a set reopening: the columns, the strip and the readout as saved")
r = MaxSim(PATCH, bus=Bus())
r.set_param("Root", 2)
r.set_param("Scale", 3)
r.load(order="shuffle")
expect(drawn(r, "root-col") == [["root", "D", 0]] and drawn(r, "scale-col") == [["scale", "Dorian", 0]]
       and r.comment_text("own") == "own: D Dorian" and r.comment_text("sub") == "the nearest step of D Dorian"
       and drawn(r, "strip")[2][0] == "D", f"D Dorian: {r.comment_text('own')}, {r.comment_text('sub')}")
expect.done()
