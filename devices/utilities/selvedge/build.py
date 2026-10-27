#!/usr/bin/env python3
"""Build Selvedge.amxd: a tuner for the Dye House's scales, microtonal ones included.

    python3 build.py

Put it on any audio (a hardware synth, a resonator, a voice). fzero~ tracks the
pitch; the display shows how far it is from the nearest step of the Scale (Root and Scale,
or Tannin's or Live's, with Key), which step that is, and the step's nearest 12-note name with its
offset: so on A 19-EDO a note near the fourth step reads 'step 4 of 19' and 'B3 -11 cents' (that step is 11 cents
under B3). Audio passes through untouched.

The panel (v1.0b1, the owner, Oct 15: plans/ideas/utilities-panels.md): the probes' panel G, 380 px. TUNER: the step
large, its nearest twelve-note name with cents and the Hz; the cents meter, flat (screens.py); the scale's steps as a
strip, the nearest lit, the root outlined, the twelve names above where they fall. SCALE: ROOT, SCALE and KEY as value
columns (Live's live.menus laid transparent over them: lib/panelg.py), KEY in its source's colour (lib/kit.py's
KIND_COLOR: blue Tannin, purple Live, amber a Live scale the family lacks), ROOT and SCALE pale while another key is
played; PLAYS: the key played, and its own.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lib"))
from kit import (GREEN, KEY_SOURCES, MUTED, ROOTS, SCALE_NAMES, TEXT, YELLOW, background, follow,  # noqa: E402
                 menu, open_gates)
from m4l import everywhere, LOGO_W, Patch, check, pack_amxd  # noqa: E402
from visual import embed_script  # noqa: E402
from scales import SCALES  # noqa: E402
import dsp  # noqa: E402
import panelg  # noqa: E402
import screens  # noqa: E402

OUT = HERE / "Selvedge.amxd"
VERSION = "v1.0.1"
WIDTH = 380
X0 = LOGO_W + 8                          # 34: the panel starts after the logo column
BIG = [X0 + 4, 21, 232, 72]              # the readout and the meter
STRIP = [X0 + 4, 97, 232, 64]            # the scale's steps
SX = X0 + 244                            # the SCALE card
SW = WIDTH - 4 - SX
COLS = {"root": [SX + 3, 21, SW - 6, 32], "scale": [SX + 3, 56, SW - 6, 32], "keysrc": [SX + 3, 91, SW - 6, 32]}
PLAYS = [SX + 3, 126, SW - 6, 35]
OWN_KEY = [["keysrc", [0], 0]]           # Root and Scale do something only with the Key choice Own


def box_of(p, oid):
    return next(b["box"] for b in p.boxes if b["box"].get("id") == oid)


def grow(p, oid):
    """A trigger given one more outlet, on its right (it fires first); returns that outlet's index."""
    box = box_of(p, oid)
    assert box["text"].startswith("t "), box["text"]
    box["text"] += " i"
    box["numoutlets"] += 1
    box["outlettype"] = [""] * box["numoutlets"]
    return box["numoutlets"] - 1


def column(p, var, label, color, items, initial, x, when=None, extra=""):
    """A value column over Live's own menu `var` (laid transparent over it)."""
    item = dict(v=var, l=label, f="menu", lo=0, hi=len(items) - 1, d=initial, items=[str(i) for i in items])
    if when:
        item["when"] = when
    js = embed_script(p, f"{var}-col", COLS[var], panelg.columns_script(
        f"Selvedge's {label}", color, [item], source="devices/ideas/selvedge/build.py", value_size=11) + extra, x, 1300)
    panelg.lay(box_of(p, var), COLS[var])
    return js


def names(p, pre, src, x, y, fmt, dest):
    """'root scale' (src, a pak) -> 'set <fmt with the key's name>' into dest: the root's name, the family scale's."""
    p.obj(f"{pre}-un", "unpack 0 0", 1, 2, x, y)
    p.line(src, f"{pre}-un")
    p.obj(f"{pre}-sn", "expr $i1+1", 1, 1, x + 60, y + 30)
    p.line(f"{pre}-un", f"{pre}-sn", 1, 0)
    p.obj(f"{pre}-sg", f"gate {len(SCALES)}", 2, len(SCALES), x, y + 90)
    p.line(f"{pre}-sn", f"{pre}-sg", 0, 0)
    p.obj(f"{pre}-rsel", "sel " + " ".join(str(i) for i in range(12)), 2, 13, x, y + 30)
    p.line(f"{pre}-un", f"{pre}-rsel", 0, 0)
    for i, name in enumerate(ROOTS):
        p.msg(f"{pre}-r{i}", name, x + 30 * i, y + 60)
        p.line(f"{pre}-rsel", f"{pre}-r{i}", i, 0)
        p.line(f"{pre}-r{i}", f"{pre}-sg", 0, 1)
    for i, name in enumerate(SCALE_NAMES):
        p.msg(f"{pre}-n{i}", "set " + fmt.format(f"$1 {name}"), x + 40 * i, y + 120)
        p.line(f"{pre}-sg", f"{pre}-n{i}", i, 0)
        p.line(f"{pre}-n{i}", dest)


def build_patcher():
    dsp.write()
    p = Patch(WIDTH)
    background(p, WIDTH, "Selvedge", "tunes", VERSION, sub_color=GREEN)
    box_of(p, "version")["fontsize"] = 7.0                      # no word under 7 px
    panelg.card(p, "tune", [X0, 4, 240, 161], GREEN, "TUNER")
    panelg.card(p, "key", [SX, 4, SW, 161], YELLOW, "SCALE")
    # the readout: the step, its nearest twelve-note name with cents, the Hz; the meter under it
    bx, by, bw, bh = BIG
    panelg.screen(p, "big-scr", BIG)
    panelg.text(p, "step", "listening", bx + 8, by + 21, 15, TEXT, w=130)
    panelg.text(p, "name", "", bx + bw - 8, by + 21, 10, TEXT, anchor="end", w=92)
    panelg.text(p, "hz", "", bx + bw - 8, by + 33, 7, MUTED, anchor="end", w=60)
    panelg.text(p, "sub", "the nearest step of A Minor", bx + 8, by + 33, 7, MUTED, w=160)
    embed_script(p, "needle", [bx + 4, by + 39, bw - 8, 31], screens.meter_script(GREEN), 1200, 600)
    embed_script(p, "strip", STRIP, screens.steps_script(GREEN, YELLOW, SCALES, ROOTS), 1300, 600)
    # SCALE: ROOT, SCALE, KEY; PLAYS
    menu(p, "root", "Root", COLS["root"], ROOTS, 9, 400)
    menu(p, "scale", "Scale", COLS["scale"], SCALE_NAMES, 2, 460)
    px, py, pw, ph = PLAYS
    panelg.screen(p, "plays-scr", PLAYS)
    panelg.text(p, "plays-cap", "PLAYS", px + 5, py + 11, 7, MUTED)
    follow(p, COLS["keysrc"], 1400, 100, "root", "scale", show=[px + 5, py + 15, pw - 8, 11], idle="its own key",
           idle_color=YELLOW)
    box_of(p, "fk-readout")["fontsize"] = 8.0
    panelg.text(p, "own", "own: A Minor", px + 5, py + 30, 7, MUTED, w=pw - 8)
    p.audio(dsp.OUT.read_text(), outs=5)
    for name in ("root", "scale"):
        p.obj(f"{name}-t", "t i i i", 1, 3, 400 if name == "root" else 460, 60)
        p.line(name, f"{name}-t")
        p.obj(f"{name}-p", f"prepend {name}", 1, 1, 400 if name == "root" else 460, 90)
        p.line(f"{name}-t", f"{name}-p", 2, 0)
        p.line(f"{name}-p", "gen")
    # the key played (as gen~ gets it): its name under the step; the strip
    p.obj("kp-pak", "pak 0 0", 2, 1, 600, 120)
    p.line("root-t", "kp-pak", 1, 0)
    p.line("scale-t", "kp-pak", 1, 1)
    names(p, "kp", "kp-pak", 3600, 100, "the nearest step of {}", "sub")
    for name, x in (("root", 400), ("scale", 460)):
        p.obj(f"{name}-sp", f"prepend {name}", 1, 1, x, 150)
        p.line(f"{name}-sp", "strip-js")
    p.line("root-t", "root-sp", 0, 0)                 # (the scale: after its step count, sc-fan)
    # pitch tracking
    p.obj("fzero", "fzero~", 1, 3, 200, 300)
    p.line("plugin", "fzero", 0, 0)
    p.obj("hz-t", "t f f", 1, 2, 200, 330)
    p.line("fzero", "hz-t")
    p.obj("hz-p", "prepend hz", 1, 1, 200, 360)
    p.line("hz-t", "hz-p", 1, 0)
    p.line("hz-p", "gen")
    p.obj("hz-fmt", "sprintf set %.1f Hz", 1, 1, 260, 360)
    p.line("hz-t", "hz-fmt", 0, 0)
    p.line("hz-fmt", "hz")
    # the readouts
    for k, name in ((2, "c"), (3, "i"), (4, "t")):
        p.obj(f"snap-{name}", "snapshot~ 50", 2, 1, 500 + 100 * k, 400)
        p.line("gen", f"snap-{name}", k, 0)
        p.obj(f"chg-{name}", "change", 1, 1, 500 + 100 * k, 430)
        p.line(f"snap-{name}", f"chg-{name}")
    p.obj("c-needle", "prepend value", 1, 1, 760, 490)
    p.line("chg-c", "c-needle")
    p.line("c-needle", "needle-js")
    # the step: 'step k of N', or listening (no name, no Hz)
    p.obj("i-t", "t i i", 1, 2, 800, 445)
    p.line("chg-i", "i-t")
    p.obj("i-strip", "prepend step", 1, 1, 900, 460)
    p.line("i-t", "i-strip", 1, 0)
    p.line("i-strip", "strip-js")
    p.obj("i-sel", "sel -1", 2, 2, 800, 460)
    p.line("i-t", "i-sel", 0, 0)
    p.obj("i-none-t", "t b b b b", 1, 4, 800, 490)
    p.line("i-sel", "i-none-t", 0, 0)
    p.msg("i-none", "set listening", 800, 520)
    p.line("i-none-t", "i-none", 3, 0)
    p.line("i-none", "step")
    p.msg("i-noname", "set", 840, 520)
    p.line("i-none-t", "i-noname", 2, 0)
    p.line("i-noname", "name")
    p.msg("i-nohz", "set", 880, 520)
    p.line("i-none-t", "i-nohz", 1, 0)
    p.line("i-nohz", "hz")
    p.msg("i-idle", "idle", 760, 520)
    p.line("i-none-t", "i-idle", 0, 0)
    p.line("i-idle", "needle-js")
    p.obj("i-plus", "+ 1", 2, 1, 860, 490)
    p.line("i-sel", "i-plus", 1, 0)
    p.obj("i-fmt", "sprintf set step %ld of %ld", 2, 1, 860, 520)
    p.line("i-plus", "i-fmt")
    p.line("i-fmt", "step")
    p.obj("n-sel", "sel " + " ".join(str(i) for i in range(len(SCALES))), 2, len(SCALES) + 1, 460, 180)
    for i, (_, st, _) in enumerate(SCALES):
        p.msg(f"n-{i}", str(len(st)), 460 + 30 * i, 210)
        p.line("n-sel", f"n-{i}", i, 0)
        p.line(f"n-{i}", "i-fmt", 0, 1)
    p.obj("sc-fan", "t i i", 1, 2, 520, 150)
    p.line("scale-t", "sc-fan", 0, 0)
    p.line("sc-fan", "n-sel", 1, 0)
    p.line("sc-fan", "scale-sp", 0, 0)
    # the step's nearest 12-note name, and how far the step is from it
    p.obj("t-t", "t f f f", 1, 3, 900, 460)
    p.line("chg-t", "t-t")
    p.obj("t-off", "expr ($f1-int($f1+0.5))*100.", 1, 1, 1000, 490)
    p.line("t-t", "t-off", 2, 0)
    p.obj("t-oct", "expr int($f1+0.5)/12-2", 1, 1, 960, 490)
    p.line("t-t", "t-oct", 1, 0)
    p.obj("t-pc", "expr int($f1+0.5)%12", 1, 1, 900, 490)
    p.line("t-t", "t-pc", 0, 0)
    p.obj("nm-look", "zl lookup", 2, 2, 900, 520)
    p.line("t-pc", "nm-look")
    p.msg("names", " ".join(ROOTS), 1000, 400)
    p.line("names", "nm-look", 0, 1)
    p.obj("nm-fmt", "sprintf set %s%ld %+.0f cents", 3, 1, 900, 550)
    p.line("t-off", "nm-fmt", 0, 2)
    p.line("t-oct", "nm-fmt", 0, 1)
    p.line("nm-look", "nm-fmt", 0, 0)
    p.line("nm-fmt", "name")
    columns_and_colours(p)
    open_gates(p, [], x=1600, extra=1)
    p.line("init", "names", 0, 0)
    return everywhere(p.patcher([("Selvedge", ["Root", "Scale", "Key"])]), "Selvedge")       # every shown part its Info View text (1.0.1)


def columns_and_colours(p):
    """ROOT, SCALE (pale unless Key is Own) and KEY as columns; KEY, the strip's root and the readout in the colour
    of the key's source (kit.follow's readout colours: 'kc r g b a'); 'own: A Minor', the device's own key."""
    kc = ('\nfunction kc(r, g, b, a) { C = [r, g, b, a === undefined ? 1 : a]; mgraphics.redraw(); }\n')
    roots = column(p, "root", "ROOT", YELLOW, ROOTS, 9, 4000, when=OWN_KEY)
    scales = column(p, "scale", "SCALE", YELLOW, SCALE_NAMES, 2, 4100, when=OWN_KEY)
    keys = column(p, "keysrc", "KEY", YELLOW, KEY_SOURCES, 0, 4200, extra=kc)
    # the own Scale and Root, as chosen (kit.follow's triggers, one more outlet each), to their columns and 'own'
    p.obj("own-pak", "pak 0 0", 2, 1, 4300, 1500)
    for k, (var, js) in enumerate((("scale", scales), ("root", roots))):
        p.obj(f"own-{var}", "t i i", 1, 2, 4000 + 80 * k, 1500)
        p.line(f"fk-{var}-t", f"own-{var}", grow(p, f"fk-{var}-t"), 0)
        p.obj(f"own-{var}-v", f"prepend v {var}", 1, 1, 4000 + 80 * k, 1540)
        p.line(f"own-{var}", f"own-{var}-v", 1, 0)
        p.line(f"own-{var}-v", js)
        p.line(f"own-{var}", "own-pak", 0, 1 if var == "scale" else 0)
    names(p, "on", "own-pak", 4400, 1600, "own: {}", "own")
    # the Key choice, to the three columns (pale or not; KEY's own value)
    p.obj("ks-v", "prepend v keysrc", 1, 1, 4600, 1540)
    p.line("fk-src", "ks-v", grow(p, "fk-src"), 0)
    p.obj("ks-fan", "t l l l", 1, 3, 4600, 1580)
    p.line("ks-v", "ks-fan")
    for k, d in enumerate((roots, scales, keys)):
        p.line("ks-fan", d, k, 0)
    # the source's colour (follow's readout messages), to KEY and the strip's root
    p.obj("kc-route", "route textcolor", 2, 2, 4800, 1540)
    for b in list(p.boxes):
        oid = b["box"].get("id", "")
        if b["box"].get("maxclass") == "message" and (oid.startswith("fk-w") or oid.startswith("fk-c")):
            p.line(oid, "kc-route")
    p.obj("kc-p", "prepend kc", 1, 1, 4800, 1570)
    p.line("kc-route", "kc-p", 0, 0)
    p.obj("kc-fan", "t l l", 1, 2, 4800, 1600)
    p.line("kc-p", "kc-fan")
    p.line("kc-fan", keys, 1, 0)
    p.line("kc-fan", "strip-js", 0, 0)


def main():
    OUT.write_bytes(pack_amxd(build_patcher(), name=OUT.name))
    nboxes, nlines = check(OUT, WIDTH, internal=["hz"], ui_only=["keysrc"])
    print(f"wrote {OUT.name}: {OUT.stat().st_size} bytes, {nboxes} boxes, {nlines} lines, checks OK")


if __name__ == "__main__":
    sys.exit(main())
