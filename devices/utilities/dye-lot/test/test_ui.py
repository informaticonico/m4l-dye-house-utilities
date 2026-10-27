#!/usr/bin/env python3
"""Tests for Dye Lot, in lib/maxsim.py: key detection, the runners-up and how sure, SET and AUTO to Tannin, TANNIN NOW.

    python3 test/test_ui.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(HERE.parent))
from kit import KEY, SET  # noqa: E402
from kittest import Expect, Tap, say  # noqa: E402
import jsrun  # noqa: E402
from m4l import read_amxd, read_embedded  # noqa: E402
from maxsim import Bus, MaxSim  # noqa: E402
import build  # noqa: E402

PATCH = read_amxd(build.OUT)
FILES = read_embedded(build.OUT)
expect = Expect()


def dye_lot(bus=None):
    sim = MaxSim(PATCH, bus=bus)
    sim.load()
    return sim


def play(sim, notes, vel=100):
    n = sim.objs["notein"]
    for pitch in notes:
        for v in (vel, 0):
            n.out(2, 1), n.out(1, v), n.out(0, pitch)


def bar(sim):
    sim.objs["tick"].receive(0, "bang")


def drawn(sim, oid):
    js = sim.objs[f"{oid}-js"]
    return jsrun.run(FILES[js.box["filename"]].decode(), js.received, js.box["presentation_rect"][2:])["values"]


def heard(sim):
    """The key named, and the runners-up: [[name, how sure %] x3], or ['listening']."""
    return drawn(sim, "guess")


def best(sim):
    return heard(sim)[0] if heard(sim) == ["listening"] else heard(sim)[0][0]


A_MINOR = [57, 60, 64, 57, 62, 65, 57, 64, 67, 69, 72, 57]     # leaning on A
C_MAJOR = [60, 64, 67, 60, 62, 65, 71, 72, 60, 67, 64, 60]     # the same notes nearly, leaning on C

print("nothing heard: listening")
sim = dye_lot()
bar(sim)
expect(heard(sim) == ["listening"], f"{heard(sim)}")
print("an A minor phrase leaning on A: A Minor; a C major one leaning on C: C Major")
play(sim, A_MINOR)
bar(sim)
expect(best(sim) == "A Minor", f"{heard(sim)}")
sim = dye_lot()
play(sim, C_MAJOR)
bar(sim)
expect(best(sim) == "C Major", f"{heard(sim)}")
print("keys that change: the tally fades, so after a few bars the new key wins")
play(sim, [n + 7 for n in C_MAJOR])        # G major
for _ in range(3):
    bar(sim)
    play(sim, [n + 7 for n in C_MAJOR])
bar(sim)
expect(best(sim) == "G Major", f"after four bars of G: {heard(sim)}")
print("a single quiet note isn't enough")
sim = dye_lot()
play(sim, [61], vel=40)
bar(sim)
expect(heard(sim) == ["listening"], f"one quiet note: {heard(sim)}")


def ranked(tally):
    """The ranking as the device should make it, from the tally: each of the 24 keys' score (its scale's notes
    once, its root twice), the best three; how sure: a score over the tally's sum and its loudest."""
    out = []
    for k, m in enumerate(build.masks()):
        out.append((sum(t * w for t, w in zip(tally, m)), -k, k))
    out.sort(reverse=True)
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    den = sum(tally) + max(tally)
    return [[f"{names[k % 12]} {'Minor' if k >= 12 else 'Major'}", round(s / den * 100)] for s, _, k in out[:3]]


def tally(sim):
    return [sim.colls["---hist"][k][0] for k in range(12)]


print("the runners-up (v1.0b1): the best three of the 24 keys, best first, each with how sure")
sim = dye_lot()
play(sim, A_MINOR * 2)
t = tally(sim)
bar(sim)
want = ranked(t)
got = heard(sim)
expect(got == want and got[0][0] == "A Minor" and got[1][0] == "C Major",
       f"A minor leaned on: A Minor, then C Major (the same notes): {got} (want {want})")
expect(got[0][1] > got[1][1] > got[2][1] > 0, f"how sure falls down the list: {[g[1] for g in got]}")
sim = dye_lot()
play(sim, C_MAJOR * 2)
t = tally(sim)
bar(sim)
got = heard(sim)
expect(got == ranked(t) and got[0][0] == "C Major" and "A Minor" not in [g[0] for g in got[:1]],
       f"C major leaned on: C Major first (C Minor next: the same root, leaned on): {got}")
sim = dye_lot()
play(sim, [57, 61, 64, 69, 57, 69, 73, 76] * 2)                  # A major's triad, leaning on A
t = tally(sim)
bar(sim)
got = heard(sim)
expect(got == ranked(t) and got[0] == ["A Major", 100], f"every note in A major, A the loudest: 100 %: {got}")
print("a change of key: the runners-up move with it")
sim = dye_lot()
play(sim, A_MINOR * 2)
bar(sim)
for _ in range(6):
    play(sim, [n + 7 for n in C_MAJOR])                         # G major, bar after bar
    t = tally(sim)
    bar(sim)
got = heard(sim)
expect(got == ranked(t) and got[0][0] == "G Major", f"after six bars of G: {got}")
print("the bars: what it heard, the best key's notes lit, its root outlined")
sim = dye_lot()
play(sim, [57])
bar(sim)
got = drawn(sim, "hist")
expect(got[0] == -1 and got[1][9] == 1, f"one A: not enough to name a key, A's bar full: {got[0]}")
play(sim, A_MINOR * 2)
bar(sim)
got = drawn(sim, "hist")
expect(got[0] == 12 + 9 and max(got[1]) == 1 and got[1][1] == 0, f"A minor named (key 21), C# never played: {got}")

print("SET sends the key to Tannin; AUTO does it every bar")
bus = Bus()
tap = Tap(bus, SET)
sim = dye_lot(bus)
play(sim, A_MINOR)
bar(sim)
expect(tap.got == [], "nothing sent by itself")
sim.press("Set")
expect(tap.got == [[9, 2]], f"SET: {tap.got}")
sim.set_param("Auto", 1)
expect(sim.comment_text("now-note") == "AUTO sets it at every bar", sim.comment_text("now-note"))
play(sim, C_MAJOR * 3)
bar(sim)
expect(tap.got[-1] == [0, 1], f"AUTO: {tap.got[-1]}")

print("TANNIN NOW: Tannin's key as followers read it; no Tannin, or Tannin gone")
expect(sim.comment_text("now") == "no Tannin", f"no Tannin in the set: {sim.comment_text('now')}")
sys.path.insert(0, str(ROOT / "devices" / "utilities" / "tannin"))
dl_build = sys.modules.pop("build")
import build as tannin_build  # noqa: E402
sys.modules["build"] = dl_build
tannin = MaxSim(read_amxd(tannin_build.OUT), bus=bus)
tannin.load()
expect(sim.comment_text("now") == "A Minor", f"Tannin loaded (A Minor): {sim.comment_text('now')}")
keys = Tap(bus, KEY)
sim.set_param("Auto", 0)
sim2 = dye_lot(bus)
expect(sim2.comment_text("now") == "A Minor", f"a Dye Lot loaded later reads the value: {sim2.comment_text('now')}")
play(sim2, [n + 2 for n in A_MINOR] * 2)          # B minor
bar(sim2)
sim2.press("Set")
expect(tannin.param("Root") == 11 and tannin.param("Scale") == 2 and keys.got[-1] == [11, 2],
       f"Tannin: B Minor ({tannin.param('Root')} {tannin.param('Scale')})")
expect(sim2.comment_text("now") == "B Minor" and sim.comment_text("now") == "B Minor",
       f"SET: TANNIN NOW reads B Minor on both: {sim2.comment_text('now')}")
tannin.set_param("Scale", 10)
expect(sim2.comment_text("now") == "B 19-EDO", f"any of Tannin's scales: {sim2.comment_text('now')}")
say(bus, KEY, "gone")
expect(sim2.comment_text("now") == "no Tannin", f"Tannin gone: {sim2.comment_text('now')}")
expect.done()
