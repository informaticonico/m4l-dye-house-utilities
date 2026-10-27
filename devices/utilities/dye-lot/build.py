#!/usr/bin/env python3
"""Build Dye Lot.amxd: which key are you playing in?

    python3 build.py

Dye Lot listens to the notes on its track (MIDI passes through untouched) and keeps a
tally of the twelve pitch classes, each note counting by its velocity; every bar the tally
fades by Memory (1-8 bars to halve). At each bar it scores all 24 major and minor keys:
the notes of the scale count once, the root twice (so A minor and C major, the same seven
notes, are told apart by which root you lean on). The best is shown, with two runners-up (v1.0b1): the scoring runs
three times, each leaving out the keys already found. How sure each is: its score over the best a tally could score
(every note in the key's scale, its root the loudest), 0-100 %. SET sends the best to Tannin (dyehouse_set), which
sets the whole house; AUTO does that every bar. TANNIN NOW shows Tannin's key as followers read it ('value
dyehouse_key' as it loads, then dyehouse_key; 'gone': no Tannin).

It knows the 12-note major and minor keys only; microtonal scales are set on Tannin.

The panel (v1.0b1, the owner, Oct 15: plans/ideas/utilities-panels.md): the probes' panel G, 330 px.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lib"))
from kit import (BLUE, GREEN, KEY, MUTED, ROOTS, SCALE_NAMES, SET, TEXT, YELLOW, background, color_msg,  # noqa: E402
                 menu, open_gates, passthrough, press, toggle)
from m4l import everywhere, INK, LOGO_W, MIDI_EFFECT, Patch, check, pack_amxd  # noqa: E402
from scales import SCALES  # noqa: E402
from visual import embed_script, tap  # noqa: E402
import panelg  # noqa: E402
import screens  # noqa: E402

OUT = HERE / "Dye Lot.amxd"
VERSION = "v1.0.1"
WIDTH = 330
X0 = LOGO_W + 8                                 # 34: the panel starts after the logo column
MEMORY = [("1 bar", 1), ("2 bars", 2), ("4 bars", 4), ("8 bars", 8)]
KINDS = [(1, "Major"), (2, "Minor")]          # lib/scales.py indices
THRESHOLD = 2.0                                 # below this best score: not enough heard
GUESS = [X0 + 4, 21, 150, 86]
HEARD = [X0 + 158, 21, 130, 86]
MEM_COL = [X0 + 80, 112, 64, 49]
NOW = [X0 + 148, 112, 140, 49]


def box_of(p, oid):
    return next(b["box"] for b in p.boxes if b["box"].get("id") == oid)


def masks():
    out = []
    for scale, _ in KINDS:
        steps = SCALES[scale][1]
        for root in range(12):
            m = [0] * 12
            for s in steps:
                m[(root + s) % 12] = 1
            m[root] = 2
            out.append(m)
    return out


def ranking(p, x=1500, y=200):
    """After the 24 keys are scored (a pass: 'run-pass'), the best kept for rank n by 'p<n>' (n 1-3); the next pass
    leaves the keys found out (their score less 1000: 'excl'). 'top-pk' gathers 'best possible, k1 s1 k2 s2 k3 s3'."""
    p.obj("run-pass", "t b b", 1, 2, x, y)
    p.line("run-pass", "reset-t", 1, 0)
    p.line("run-pass", "k-uzi", 0, 0)
    p.obj("pe", "t b b", 1, 2, x, y + 400)
    p.line("k-uzi", "pe", 1, 0)
    p.obj("pe-f", "gate 3", 2, 3, x + 100, y + 460)
    p.obj("pe-i", "gate 3", 2, 3, x, y + 460)
    p.line("pe", "best-f", 1, 0)
    p.line("best-f", "pe-f", 0, 1)
    p.line("pe", "best-i", 0, 0)
    p.line("best-i", "pe-i", 0, 1)
    for n in (1, 2, 3):
        p.obj(f"p{n}", f"t b {n}", 1, 2, x + 200 + 60 * n, y - 60)
        p.obj(f"p{n}-g", "t i i", 1, 2, x + 200 + 60 * n, y - 30)
        p.line(f"p{n}", f"p{n}-g", 1, 0)
        p.line(f"p{n}-g", "pe-f", 1, 0)
        p.line(f"p{n}-g", "pe-i", 0, 0)
        p.line(f"p{n}", "run-pass", 0, 0)
    p.obj("top-pk", "pack 0. 0 0. 0 0. 0 0.", 7, 1, x, y + 560)
    p.obj("r1i", "i", 2, 1, x, y + 520)
    p.obj("r1i-t", "t i i i", 1, 3, x, y + 490)
    p.line("pe-i", "r1i-t", 0, 0)
    p.line("r1i-t", "excl", 2, 2)
    p.line("r1i-t", "top-pk", 1, 1)
    p.line("r1i-t", "r1i", 0, 1)
    p.obj("r2i-t", "t i i", 1, 2, x + 60, y + 490)
    p.line("pe-i", "r2i-t", 1, 0)
    p.line("r2i-t", "excl", 1, 3)
    p.line("r2i-t", "top-pk", 0, 3)
    p.line("pe-i", "top-pk", 2, 5)
    p.obj("r1f", "f", 2, 1, x + 160, y + 520)
    p.obj("r1f-t", "t f f", 1, 2, x + 160, y + 490)
    p.line("pe-f", "r1f-t", 0, 0)
    p.line("r1f-t", "top-pk", 1, 2)
    p.line("r1f-t", "r1f", 0, 1)
    p.line("pe-f", "top-pk", 1, 4)
    p.line("pe-f", "top-pk", 2, 6)
    # before pass 1: no key left out
    p.msg("ex-none", "-1", x + 400, y - 60)
    p.obj("ex-t", "t i i", 1, 2, x + 400, y - 30)
    p.line("ex-none", "ex-t")
    p.line("ex-t", "excl", 1, 3)
    p.line("ex-t", "excl", 0, 2)


def heard_stats(p, x=1900, y=200):
    """The best a tally could score: its sum (every note in the key's scale) and its loudest (the root): 'den'."""
    p.obj("sum", "zl sum", 2, 2, x, y + 60)
    p.line("h-group", "sum")
    p.obj("sum-f", "f", 2, 1, x, y + 90)
    p.line("sum", "sum-f", 0, 1)
    p.obj("den", "expr $f1+$f2", 2, 1, x, y + 120)
    p.line("sum-f", "den")
    p.obj("mx", "expr ($f1>$f2)*$f1+($f1<=$f2)*$f2", 2, 1, x + 100, y + 60)
    p.obj("mx-t", "t f f", 1, 2, x + 100, y + 90)
    p.line("mx", "mx-t")
    p.line("mx-t", "mx", 1, 1)
    p.line("mx-t", "den", 0, 1)
    p.msg("mx-zero", "0.", x + 200, y + 30)
    p.line("mx-zero", "mx-t")


def tannin_now(p, x=2200, y=1300):
    """TANNIN NOW: Tannin's key as followers read it (the value as it loads, then the bus), in Tannin's blue; 'gone'
    (or nothing there): no Tannin."""
    nx, ny, nw, nh = NOW
    panelg.screen(p, "now-scr", NOW)
    panelg.text(p, "now-cap", "TANNIN NOW", nx + 5, ny + 11, 7, MUTED)
    panelg.text(p, "now", "no Tannin", nx + 5, ny + 29, 12, MUTED, w=nw - 10)
    panelg.text(p, "now-note", "SET sends it the key heard", nx + 5, ny + 42, 7, MUTED, w=nw - 10)
    p.obj("tk-r", f"r {KEY}", 0, 1, x, y)
    p.obj("tk-v", f"v {KEY}", 1, 1, x + 100, y)
    p.obj("tk-rt", "route gone", 2, 2, x, y + 30)
    p.line("tk-r", "tk-rt")
    p.line("tk-v", "tk-rt")
    p.msg("tk-gone", f"set no Tannin, textcolor {color_msg(MUTED)}", x, y + 60)
    p.line("tk-rt", "tk-gone", 0, 0)
    p.line("tk-gone", "now")
    p.obj("tk-t", "t b l", 1, 2, x + 100, y + 60)
    p.line("tk-rt", "tk-t", 1, 0)
    p.msg("tk-blue", f"textcolor {color_msg(BLUE)}", x + 200, y + 90)
    p.line("tk-t", "tk-blue", 0, 0)
    p.line("tk-blue", "now")
    p.obj("tk-un", "unpack 0 0", 1, 2, x + 100, y + 90)
    p.line("tk-t", "tk-un", 1, 0)
    p.obj("tk-sn", "expr $i1+1", 1, 1, x + 160, y + 120)
    p.line("tk-un", "tk-sn", 1, 0)
    p.obj("tk-sg", f"gate {len(SCALES)}", 2, len(SCALES), x + 100, y + 180)
    p.line("tk-sn", "tk-sg", 0, 0)
    p.obj("tk-rsel", "sel " + " ".join(str(i) for i in range(12)), 2, 13, x + 100, y + 120)
    p.line("tk-un", "tk-rsel", 0, 0)
    for i, name in enumerate(ROOTS):
        p.msg(f"tk-r{i}", name, x + 100 + 30 * i, y + 150)
        p.line("tk-rsel", f"tk-r{i}", i, 0)
        p.line(f"tk-r{i}", "tk-sg", 0, 1)
    for i, name in enumerate(SCALE_NAMES):
        p.msg(f"tk-n{i}", f"set $1 {name}", x + 100 + 40 * i, y + 210)
        p.line("tk-sg", f"tk-n{i}", i, 0)
        p.line(f"tk-n{i}", "now")
    # AUTO, in words under it
    tap(p, "auto", x + 400, y - 30)
    p.obj("an-sel", "sel 0 1", 2, 3, x + 400, y)
    p.line("auto", "an-sel")
    for k, words in enumerate(("SET sends it the key heard", "AUTO sets it at every bar")):
        p.msg(f"an-{k}", f"set {words}", x + 400 + 120 * k, y + 30)
        p.line("an-sel", f"an-{k}", k, 0)
        p.line(f"an-{k}", "now-note")


def build_patcher():
    p = Patch(WIDTH)
    background(p, WIDTH, "Dye Lot", "listens", VERSION, sub_color=GREEN)
    box_of(p, "version")["fontsize"] = 7.0                      # no word under 7 px
    panelg.card(p, "c", [X0, 4, WIDTH - 4 - X0, 161], GREEN, "KEY HEARD", note="EVERY BAR")
    # the guess and two runners-up; what it hears as twelve bars (the help text is in Live's Info View)
    guess = embed_script(p, "guess", GUESS, screens.guess_script(GREEN), 1600, 300)
    heard = embed_script(p, "hist", HEARD, screens.heard_script(GREEN, masks()), 1700, 300)
    toggle(p, "set", "Set", [X0 + 4, 112, 72, 22], YELLOW, 40, mode=0)
    toggle(p, "auto", "Auto", [X0 + 4, 139, 72, 22], GREEN, 160)
    for oid in ("set", "auto"):
        box_of(p, oid).update(bgcolor=list(INK), activebgcolor=list(INK), rounded=8.0)
    menu(p, "memory", "Memory", MEM_COL, [n for n, _ in MEMORY], 1, 280)
    v = box_of(p, "memory")["saved_attribute_attributes"]["valueof"]
    item = dict(v="memory", l="MEMORY", f="step", lo=0, hi=len(MEMORY) - 1, d=1, items=v["parameter_enum"])
    mem = embed_script(p, "mem-col", MEM_COL, panelg.columns_script(
        "Dye Lot's MEMORY", GREEN, [item], source="devices/ideas/dye-lot/build.py", steps=True, value_size=12,
        formats='if (it.f == "step") { var s = it.items[clampf(Math.round(x), 0, it.items.length - 1)].split(" "); '
                'return [s[0], s[1]]; }'), 2800, 1300)
    panelg.lay(box_of(p, "memory"))
    panelg.feed(p, "memory", "memory", mem, 2800)
    press(p, "set", 40)
    passthrough(p)
    # load: the tally at zero, the key masks
    p.obj("hist-w", "coll ---hist", 1, 4, 600, 300)
    p.obj("zero-uzi", "uzi 12", 2, 3, 600, 200)
    p.obj("zero-i", "- 1", 2, 1, 600, 230)
    p.line("zero-uzi", "zero-i", 2, 0)
    p.obj("zero-pk", "pack 0 0.", 2, 1, 600, 260)
    p.line("zero-i", "zero-pk")
    p.line("zero-pk", "hist-w")
    p.obj("masks", "coll ---masks", 1, 4, 800, 500)
    body = ", ".join(f"{c} " + " ".join(map(str, m)) for c, m in enumerate(masks()))
    p.msg("mask-data", body, 800, 470)
    p.line("mask-data", "masks")
    # every note-on counts, by its velocity
    p.obj("notein", "notein", 1, 3, 40, 300)
    p.obj("n-pk", "pack 0 0", 2, 1, 40, 330)
    p.line("notein", "n-pk", 1, 1)
    p.line("notein", "n-pk", 0, 0)
    p.obj("n-t", "t l l", 1, 2, 40, 360)
    p.line("n-pk", "n-t")
    p.obj("n-on", "expr $i2>0", 2, 1, 120, 390)
    p.line("n-t", "n-on", 1, 0)
    p.obj("n-gate", "gate 1", 2, 1, 40, 420)
    p.line("n-on", "n-gate", 0, 0)
    p.line("n-t", "n-gate", 0, 1)
    p.obj("n-un", "unpack 0 0", 1, 2, 40, 450)
    p.line("n-gate", "n-un")
    p.obj("n-w", "/ 127.", 2, 1, 120, 480)
    p.line("n-un", "n-w", 1, 0)
    p.obj("n-add", "expr $f1+$f2", 2, 1, 120, 540)
    p.line("n-w", "n-add", 0, 1)
    p.obj("n-pc", "% 12", 2, 1, 40, 480)
    p.line("n-un", "n-pc", 0, 0)
    p.obj("n-pct", "t i i", 1, 2, 40, 510)
    p.line("n-pc", "n-pct")
    p.obj("hist-r1", "coll ---hist", 1, 4, 120, 510)
    p.line("n-pct", "hist-r1", 1, 0)
    p.line("hist-r1", "n-add", 0, 0)
    p.obj("n-upd", "pack 0 0.", 2, 1, 40, 570)
    p.line("n-add", "n-upd", 0, 1)
    p.line("n-pct", "n-upd", 0, 0)
    p.obj("hist-w1", "coll ---hist", 1, 4, 40, 600)
    p.line("n-upd", "hist-w1")
    # every bar: score, then fade
    p.obj("metro", "metro 1n @quantize 1n @active 1", 2, 1, 300, 200)
    p.obj("tick", "t b b", 1, 2, 300, 230)
    p.line("metro", "tick")
    p.obj("fade-uzi", "uzi 12", 2, 3, 400, 260)
    p.line("tick", "fade-uzi", 0, 0)
    p.obj("fade-i", "- 1", 2, 1, 400, 290)
    p.line("fade-uzi", "fade-i", 2, 0)
    p.obj("fade-t", "t i i", 1, 2, 400, 320)
    p.line("fade-i", "fade-t")
    p.obj("hist-r2", "coll ---hist", 1, 4, 480, 350)
    p.line("fade-t", "hist-r2", 1, 0)
    p.obj("fade-mul", "* 0.707", 2, 1, 480, 380)
    p.line("hist-r2", "fade-mul")
    p.obj("fade-pk", "pack 0 0.", 2, 1, 400, 410)
    p.line("fade-mul", "fade-pk", 0, 1)
    p.line("fade-t", "fade-pk", 0, 0)
    p.obj("hist-w2", "coll ---hist", 1, 4, 400, 440)
    p.line("fade-pk", "hist-w2")
    p.obj("mem-sel", "sel 0 1 2 3", 2, 5, 280, 100)
    p.line("memory", "mem-sel")
    for i, (_, bars) in enumerate(MEMORY):
        p.msg(f"mem-{i}", f"{0.5 ** (1 / bars):.4f}", 280 + 50 * i, 130)
        p.line("mem-sel", f"mem-{i}", i, 0)
        p.line(f"mem-{i}", "fade-mul", 0, 1)
    # each bar: the tally as a list (and the best it could score), then three passes of the 24 keys, then the verdict
    p.obj("an-t", "t b b b b b b b", 1, 7, 1000, 200)
    p.line("tick", "an-t", 1, 0)
    p.obj("h-uzi", "uzi 12", 2, 3, 1100, 230)
    p.line("an-t", "mx-zero", 6, 0)
    p.line("an-t", "h-uzi", 5, 0)
    p.obj("h-i", "- 1", 2, 1, 1100, 260)
    p.line("h-uzi", "h-i", 2, 0)
    p.obj("hist-r3", "coll ---hist", 1, 4, 1100, 290)
    p.line("h-i", "hist-r3")
    p.obj("h-val", "t f f", 1, 2, 1100, 305)
    p.line("hist-r3", "h-val")
    p.line("h-val", "mx", 1, 0)
    p.obj("h-group", "zl group 12", 2, 2, 1100, 320)
    p.line("h-val", "h-group", 0, 0)
    p.msg("h-list", "", 1100, 350)
    p.line("h-group", "h-list", 0, 1)
    p.obj("reset-t", "t -1. 0", 1, 2, 1250, 230)
    p.line("an-t", "ex-none", 4, 0)
    p.line("an-t", "p1", 3, 0)
    p.line("an-t", "p2", 2, 0)
    p.line("an-t", "p3", 1, 0)
    p.line("an-t", "verdict", 0, 0)
    p.obj("k-uzi", "uzi 24", 2, 3, 1000, 380)
    p.obj("k-i", "- 1", 2, 1, 1000, 410)
    p.line("k-uzi", "k-i", 2, 0)
    p.obj("k-t", "t b i i i", 1, 4, 1000, 440)
    p.line("k-i", "k-t")
    p.obj("cur", "i 0", 2, 1, 1200, 470)
    p.line("k-t", "cur", 2, 1)
    p.obj("masks-r", "coll ---masks", 1, 4, 1100, 470)
    p.line("k-t", "masks-r", 1, 0)
    p.obj("prod", "vexpr $f1*$f2", 2, 1, 1000, 500)
    p.line("masks-r", "prod", 0, 1)
    p.line("k-t", "h-list", 0, 0)
    p.line("h-list", "prod", 0, 0)
    p.obj("score", "zl sum", 2, 2, 1000, 530)
    p.line("prod", "score")
    p.obj("excl", "expr $f1-1000.*(($i2==$i3)+($i2==$i4))", 4, 1, 1000, 545)   # a key already found: left out
    p.line("k-t", "excl", 3, 1)
    p.line("score", "excl")
    p.obj("sc-t", "t f f", 1, 2, 1000, 560)
    p.line("excl", "sc-t")
    p.obj("sc-store", "f 0", 2, 1, 1100, 590)
    p.line("sc-t", "sc-store", 1, 1)
    p.obj("cmp", "expr $f1>$f2", 2, 1, 1000, 590)
    p.line("sc-t", "cmp", 0, 0)
    p.obj("cmp-sel", "sel 1", 2, 2, 1000, 620)
    p.line("cmp", "cmp-sel")
    p.obj("upd", "t b b", 1, 2, 1000, 650)
    p.line("cmp-sel", "upd", 0, 0)
    p.line("upd", "sc-store", 1, 0)
    p.obj("sc-out", "t f f", 1, 2, 1100, 680)
    p.line("sc-store", "sc-out")
    p.obj("best-f", "f -1", 2, 1, 1250, 710)
    p.line("sc-out", "cmp", 1, 1)
    p.line("sc-out", "best-f", 0, 1)
    p.obj("best-i", "i 0", 2, 1, 1200, 710)
    p.line("upd", "cur", 0, 0)
    p.line("cur", "best-i", 0, 1)
    # before a pass: best score -1, best key 0
    p.obj("rst-f", "t f f", 1, 2, 1250, 260)
    p.line("reset-t", "rst-f", 0, 0)
    p.line("rst-f", "cmp", 1, 1)
    p.line("rst-f", "best-f", 0, 1)
    p.line("reset-t", "best-i", 1, 1)
    ranking(p)
    heard_stats(p)
    # the verdict: enough heard? then the key (kept for SET, sent if AUTO) and the top three shown; else listening
    p.obj("verdict", "t b", 1, 1, 1000, 740)
    p.line("verdict", "r1f")
    p.obj("enough", f"expr $f1>={THRESHOLD}", 1, 1, 1000, 770)
    p.line("r1f", "enough")
    p.obj("enough-sel", "sel 1 0", 2, 3, 1000, 800)
    p.line("enough", "enough-sel")
    p.obj("win", "t b b", 1, 2, 1000, 815)
    p.line("enough-sel", "win", 0, 0)
    p.line("win", "sum-f", 1, 0)
    p.line("den", "top-pk", 0, 0)
    p.obj("top-p", "prepend top", 1, 1, 1600, 600)
    p.line("top-pk", "top-p")
    p.obj("top-fan", "t l l", 1, 2, 1600, 630)
    p.line("top-p", "top-fan")
    p.line("top-fan", guess, 1, 0)
    p.line("top-fan", heard, 0, 0)
    p.line("win", "r1i", 0, 0)
    p.msg("idle", "idle", 1100, 830)
    p.line("enough-sel", "idle", 1, 0)
    p.obj("idle-fan", "t l l", 1, 2, 1100, 850)
    p.line("idle", "idle-fan")
    p.line("idle-fan", guess, 1, 0)
    p.line("idle-fan", heard, 0, 0)
    p.obj("dec-t", "t i i", 1, 2, 1000, 860)
    p.line("r1i", "dec-t")
    p.obj("dec-root", "% 12", 2, 1, 1000, 890)
    p.obj("dec-scale", "expr 1+($i1>=12)", 1, 1, 1100, 890)
    p.line("dec-t", "dec-scale", 1, 0)
    p.line("dec-t", "dec-root", 0, 0)
    p.obj("found", "pack 0 0", 2, 1, 1000, 920)
    p.line("dec-scale", "found", 0, 1)
    p.line("dec-root", "found", 0, 0)
    p.obj("found-t", "t l l", 1, 2, 1000, 950)
    p.line("found", "found-t")
    p.msg("result", "", 1000, 1010)
    p.line("found-t", "result", 1, 1)
    p.obj("auto-gate", "gate 1", 2, 1, 1060, 980)
    p.line("auto-out", "auto-gate", 0, 0)
    p.line("found-t", "auto-gate", 0, 1)
    p.obj("to-tannin", f"s {SET}", 1, 0, 1000, 1040)
    p.line("auto-gate", "to-tannin")
    p.line("set-press", "result")
    p.line("result", "to-tannin")
    # the tally each bar, to the bars
    tap(p, "h-group", 1600, 200)
    p.obj("hist-in", "prepend hist", 1, 1, 1600, 230)
    p.line("h-group", "hist-in")
    p.line("hist-in", heard)
    tannin_now(p)
    open_gates(p, ["set", "auto"], x=1600, extra=3)
    p.line("init", "tk-v", 2, 0)
    p.line("init", "mask-data", 1, 0)
    p.line("init", "zero-uzi", 0, 0)
    return everywhere(p.patcher([("Dye Lot", ["Set", "Auto", "Memory"])]), "Dye Lot")       # every shown part its Info View text (1.0.1)


def main():
    OUT.write_bytes(pack_amxd(build_patcher(), MIDI_EFFECT))
    nboxes, nlines = check(OUT, WIDTH, gen=False)
    print(f"wrote {OUT.name}: {OUT.stat().st_size} bytes, {nboxes} boxes, {nlines} lines, checks OK")


if __name__ == "__main__":
    sys.exit(main())
