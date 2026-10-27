#!/usr/bin/env python3
"""Tests for Tannin on the family bus, in lib/maxsim.py.

    python3 test/test_ui.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "lib"))
sys.path.insert(0, str(HERE.parent))
from kit import AMBER, BLUE, KEY, LIVE_C, SET, color_msg  # noqa: E402
from kittest import Expect, Tap, say  # noqa: E402
import jsrun  # noqa: E402
from m4l import read_amxd, read_embedded  # noqa: E402
from maxsim import Bus, MaxSim  # noqa: E402
import build  # noqa: E402

PATCH = read_amxd(build.OUT)
FILES = read_embedded(build.OUT)
expect = Expect()


def drawn(sim, oid):
    js = sim.objs[f"{oid}-js"]
    return jsrun.run(FILES[js.box["filename"]].decode(), js.received, js.box["presentation_rect"][2:])["values"]


def colour(sim, oid):
    told = getattr(sim.objs[oid], "attrs", {}).get("textcolor")
    return color_msg([float(v) for v in told.split()]) if told else None


print("Tannin publishes its key on load, on every change, and keeps it for late followers")
bus = Bus()
tap = Tap(bus, KEY)
sim = MaxSim(PATCH, bus=bus)
sim.load()
expect(tap.got[-1] == [9, 2] and bus.values[KEY] == [9, 2], f"loaded: A Minor (9 2): {tap.got[-1:]}")
expect(sim.comment_text("key-line") == "devices play A Minor", sim.comment_text("key-line"))
sim.set_param("Root", 2)
sim.set_param("Scale", 10)
expect(tap.got[-1] == [2, 10] and bus.values[KEY] == [2, 10], f"D, 19-EDO: {tap.got[-1]}")
expect(sim.comment_text("steps") == "19 notes an octave", sim.comment_text("steps"))
expect(sim.comment_text("key-line") == "devices play D 19-EDO", sim.comment_text("key-line"))
sim.set_param("Scale", 9)
expect("13 steps a tritave" == sim.comment_text("steps"), sim.comment_text("steps"))

print("the panel (v1.0b1): ROOT and SCALE as columns, Live's own menus laid over them")
for var, name in (("root", "Root"), ("scale", "Scale")):
    box = next(b["box"] for b in PATCH["boxes"] if b["box"].get("id") == var)
    col = next(b["box"] for b in PATCH["boxes"] if b["box"].get("id") == f"{var}-col-js")
    expect(box["maxclass"] == "live.menu" and box["textcolor"] == [0, 0, 0, 0]
           and box["presentation_rect"] == col["presentation_rect"]
           and box["saved_attribute_attributes"]["valueof"]["parameter_longname"] == name,
           f"{name}: a live.menu, transparent over its column")
got = drawn(sim, "root-col"), drawn(sim, "scale-col")
expect(got == ([["root", "D", 0]], [["scale", "Bohlen-P", 0]]), f"the columns show D, Bohlen-P: {got}")
rebuilt = MaxSim(PATCH, bus=Bus())
rebuilt.set_param("Root", 4)
rebuilt.set_param("Scale", 3)
rebuilt.load(order="shuffle")
got = drawn(rebuilt, "root-col"), drawn(rebuilt, "scale-col"), rebuilt.comment_text("key-line")
expect(got == ([["root", "E", 0]], [["scale", "Dorian", 0]], "devices play E Dorian"),
       f"a set reopening with E Dorian: drawn and named so ({got})")

print("a 'root scale' on dyehouse_set (Dye Lot's SET) changes Tannin, which sends it on")
say(bus, SET, [7, 1])
expect(sim.param("Root") == 7 and sim.param("Scale") == 1 and tap.got[-1] == [7, 1],
       f"G Major: menus {sim.param('Root')} {sim.param('Scale')}, sent {tap.got[-1]}")

print("Tannin shows Live's current scale, in Live's purple, and never writes itself or Live")
fresh = MaxSim(PATCH, bus=Bus())
fresh.load()
expect(fresh.comment_text("live") == "C Major", f"on load: {fresh.comment_text('live')}")
sim.live_set(root_note=5, scale_intervals=[0, 2, 4, 6, 7, 9, 11], scale_name="Lydian")
expect(sim.comment_text("live") == "F Lydian", sim.comment_text("live"))
expect(sim.comment_text("live-mode") == "SCALE MODE OFF" and sim.comment_text("live-plays") == "Key Live plays its own",
       f"{sim.comment_text('live-mode')} / {sim.comment_text('live-plays')}")
sim.live_set(scale_mode=1)
expect(sim.comment_text("live-mode") == "SCALE MODE ON" and sim.comment_text("live-plays") == "Key Live plays this"
       and colour(sim, "live") == color_msg(LIVE_C), f"{sim.comment_text('live-mode')}, {colour(sim, 'live')}")
expect(sim.param("Root") == 7 and sim.param("Scale") == 1 and tap.got[-1] == [7, 1],
       f"Tannin's own key untouched: {sim.param('Root')} {sim.param('Scale')}, last sent {tap.got[-1]}")
sim.live_set(scale_intervals=[0, 2, 3, 6, 7, 8, 11], scale_name="Hungarian Minor")
expect(sim.comment_text("live") == "F Hungarian Minor" and sim.comment_text("live-mode") == "NOT ONE OF OURS"
       and sim.comment_text("live-plays") == "Key Live plays Chromatic" and colour(sim, "live") == color_msg(AMBER),
       f"{sim.comment_text('live')} / {sim.comment_text('live-mode')}: amber, a scale the family lacks")
expect(not any(c for c in sim.live.calls), f"no Live API calls: {sim.live.calls}")

print("FROM LIVE copies Live's current scale into Tannin, only when pressed")
sim.live_set(scale_intervals=[0, 2, 4, 5, 7, 9, 10], scale_name="Mixolydian")
expect(sim.param("Scale") == 1, "not before the press")
sim.press("From Live")
expect(sim.param("Root") == 5 and sim.param("Scale") == 11 and tap.got[-1] == [5, 11],
       f"F Mixolydian: {sim.param('Root')} {sim.param('Scale')}, sent {tap.got[-1]}")

print("Live 12.1's tuning system, shown")
expect(sim.comment_text("tuning") == "none loaded (Live 12.1's tuning systems show here)", sim.comment_text("tuning"))
sim.live.tuning = "Pelog"
sim.live_set(tuning_system="id 3")
expect(sim.comment_text("tuning") == "Pelog", sim.comment_text("tuning"))


def delete(device):
    """Delete a Tannin from the set: its freebang fires, then its receives are gone from the bus."""
    device.objs["tn-free"].out(0, "bang")
    for rs in device.bus.receivers.values():
        rs[:] = [r for r in rs if getattr(r, "sim", None) is not device]


print("a second Tannin says so, on both, in the ON TANNIN KEY line; when one leaves, its key is back")
bus = Bus()
tap = Tap(bus, KEY)
one = MaxSim(PATCH, bus=bus, seed=1)
one.load()
one.set_param("Root", 2)
one.set_param("Scale", 3)
expect(one.comment_text("key-cap") == "ON TANNIN KEY" and one.comment_text("key-line") == "devices play D Dorian",
       "alone: no warning, the key")
two = MaxSim(PATCH, bus=bus, seed=2)
two.load()
w = build.WARNING
expect(one.comment_text("key-line") == w and two.comment_text("key-line") == w
       and one.comment_text("key-cap") == "TWO TANNINS" and colour(one, "key-line") == color_msg(AMBER),
       f"{one.comment_text('key-line')!r} / {two.comment_text('key-line')!r}")
one.set_param("Root", 4)
expect(one.comment_text("key-line") == w, "a key change while warned: the warning stays")
expect(tap.got[-1] == [4, 3], f"(and the key still goes out: {tap.got[-1]})")
n = len(tap.got)
delete(two)
expect(one.comment_text("key-line") == "devices play E Dorian" and colour(one, "key-line") == color_msg(BLUE)
       and one.comment_text("key-cap") == "ON TANNIN KEY", f"the other left: {one.comment_text('key-line')!r}")
expect(tap.got[n:] == ["gone", [4, 3]] and bus.values[KEY] == [4, 3],
       f"its 'gone', then the one left sends its key (E Dorian), kept for late followers: "
       f"sent {tap.got[n:]}, kept {bus.values[KEY]}")
print("the last Tannin leaving sends 'gone', and keeps it")
delete(one)
expect(tap.got[-1] == "gone" and bus.values[KEY] == "gone", f"'gone' sent and kept: {tap.got[-1]}")

print("MIDI passes through")
for b in (0x92, 60, 100):
    sim.objs["midiin"].out(0, b)
expect(sim.midi_bytes == [0x92, 60, 100], f"{sim.midi_bytes}")

print("the circle: the key's notes round the twelve, or a microtonal scale's steps round a turn")
sim.set_param("Root", 2)
sim.set_param("Scale", 3)
got = drawn(sim, "circle")
expect(got == [1, [0, 2, 4, 5, 7, 9, 11]], f"D Dorian: C major's notes ringed, D the root: {got}")
sim.set_param("Scale", 9)
got = drawn(sim, "circle")
expect(got[0] == 0 and len(got[1]) == 13, f"Bohlen-Pierce: 13 steps round a turn (a tritave): {len(got[1])}")
expect.done()
