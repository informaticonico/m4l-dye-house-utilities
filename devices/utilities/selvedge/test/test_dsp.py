#!/usr/bin/env python3
"""Tests for Selvedge: the codebox (lib/genexpr.py) and the readouts (lib/maxsim.py).

    python3 test/test_dsp.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "lib"))
sys.path.insert(0, str(HERE.parent))
from genexpr import Engine  # noqa: E402
from kit import KEY  # noqa: E402
from kittest import Expect, check_follow, say  # noqa: E402
from m4l import read_amxd  # noqa: E402
from maxsim import Bus, MaxSim  # noqa: E402
from scales import degree  # noqa: E402
import build  # noqa: E402
import dsp  # noqa: E402

expect = Expect()


def hz(note):
    return 440 * 2 ** ((note - 69) / 12)


def tune(freq, root=9, scale=2):
    e = Engine(dsp.generate(), 48000)
    e.set("root", root), e.set("scale", scale), e.set("hz", freq)
    out = e.tick_all(0.25, -0.5)
    return out


print("A minor: A is the root, dead on; 452 Hz is A, 47 cents sharp; E is step 5")
o = tune(440)
expect(o[:2] == (0.25, -0.5) and abs(o[2]) < 0.01 and o[3] == 0, f"440 Hz: {o}")
o = tune(452)
expect(abs(o[2] - 46.58) < 0.1 and o[3] == 0 and o[4] == 69, f"452 Hz: {o[2]:+.1f} cents from step {o[3]:.0f}")
o = tune(hz(64 + 0.1))
expect(abs(o[2] - 10) < 0.01 and o[3] == 4, f"E +10 cents: {o[2]:+.1f}, step {o[3]:.0f}")
print("19-EDO from C: its steps read as steps, not as 12-note notes")
t = 60 + degree(10, 4)
o = tune(hz(t), root=0, scale=10)
expect(abs(o[2]) < 0.01 and o[3] == 4 and abs(o[4] - t) < 1e-6, f"step 4 of 19: {o}")
o = tune(hz(t + 0.2), root=0, scale=10)
expect(abs(o[2] - 20) < 0.01 and o[3] == 4, f"20 cents above it: {o[2]:+.1f}")
print("Bohlen-Pierce: steps above the tritave (19.02 semitones) count again from the root")
t = 62 + degree(9, 15)
o = tune(hz(t), root=2, scale=9)
expect(abs(o[2]) < 0.01 and o[3] == 2 and abs(o[4] - t) < 1e-6, f"D, step 15 = step 2 a tritave up: {o}")
print("nothing heard: step -1")
o = tune(0)
expect(o[3] == -1 and o[2] == 0, f"{o}")

print("the readouts")
sim = MaxSim(read_amxd(build.OUT))
sim.load()
sim.objs["snap-c"].out(0, -12.4)
sim.objs["snap-i"].out(0, 4)
sim.objs["snap-t"].out(0, 64 - 0.37)
sim.objs["fzero"].out(0, 322.7)
expect(sim.objs["needle-js"].received[-1] == ["value", -12.4], f"the meter: {sim.objs['needle-js'].received[-1:]}")
expect(sim.comment_text("step") == "step 5 of 7", sim.comment_text("step"))
expect(sim.comment_text("name") == "E3 -37 cents", sim.comment_text("name"))
expect(sim.comment_text("hz") == "322.7 Hz", sim.comment_text("hz"))
sent = [m for m in sim.objs["gen"].received if isinstance(m, list)]
expect(["hz", 322.7] in sent, "the pitch goes to the codebox")
sim.set_param("Scale", 10)
sim.objs["snap-i"].out(0, 3)
expect(sim.comment_text("step") == "step 4 of 19", sim.comment_text("step"))
sim.objs["snap-i"].out(0, -1)
expect(sim.comment_text("step") == "listening", sim.comment_text("step"))
print("Key: Tannin")
bus = Bus()
sim = MaxSim(read_amxd(build.OUT), bus=bus)
sim.load()
sim.set_param("Key", 2)
say(bus, KEY, [2, 9])
sent = [m for m in sim.objs["gen"].received if isinstance(m, list)]
expect(["root", 2] in sent and (["scale", 9] in sent or ["scale_p", 9] in sent), "Tannin's key reaches the codebox")
check_follow(read_amxd(build.OUT), expect, idle="its own key")
expect.done()
