#!/usr/bin/env python3
"""Build Warp.amxd and Weft.amxd: MIDI and MPE cables between tracks.

    python3 build.py

Warp (the sender) goes on the track that plays: Push's pads, a sequencer. Everything it
hears (notes, per-note pitch bend, pressure and controllers, each on its own channel) goes
down cable A, B, C or D. THRU (on) also lets it through on its own track.

Weft (the receiver) goes on another track, before the instrument. It plays what arrives on
its cable, mixed with that track's own MIDI. Any number of Wefts can listen to one cable:
one Push performance, several synths; or one sequencer playing two synths at once.

The cable is the family bus (lib/kit.py): 'note p v ch', 'bend v ch', 'press v ch' and
'cc v n ch', whole messages, so notes and their expression never interleave; 'release' lets go of
every note that came down it (a Warp sends it before it leaves a cable, and when it's deleted).

Nothing hangs (v0.2): each Weft keeps the notes it played from its cable and lets them go on
'release', when its own Cable changes, and on the reset; THRU going off silences the Warp's own track,
and the Warp answers the reset too. Both are MPE devices (Live sends them each note on its channel).

The panel (v1.0b1, the owner, Oct 15: plans/ideas/utilities-panels.md): the probes' panel G, 300 px. The family
cable selector (A · B · C · D: one live.tab, Cable, its items and index as the menu's were: lib/panelg.py's
cable_tab); the keyboard (three octaves) with the held notes lit; a slot a held note with its bend, pressure and timbre
(screens.py). Warp: THRU and SENDING. Weft: THE SENDER, "Warp A: playing" or "quiet", "no Warp on A", "2 Warps on A".
Each Warp keeps how many Warps are on each cable in 'value dyehouse_warps_X' (one more as it loads or moves onto X, one
fewer as it leaves X or the set) and sends 'warps n' down the cable as it changes; a Weft reads the value as it loads
or changes cable. Every other listener on a cable routes what it takes ('note', 'press', 'hit', 'release') and drops
'warps'.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lib"))
from kit import (answer_rinse, BLUE, CABLES, CORAL, background, cable, open_gates,  # noqa: E402
                 passthrough, reset_bytes, RINSE, toggle)
from m4l import everywhere, INK, LOGO_W, MIDI_EFFECT, MUTED, Patch, check, pack_amxd  # noqa: E402
from visual import embed_script, keyboard_script, tap  # noqa: E402
import panelg  # noqa: E402
import screens  # noqa: E402

OUT_WARP = HERE / "Warp.amxd"
OUT_WEFT = HERE / "Weft.amxd"
VERSION = "v1.0.1"
WIDTH = 300
X0 = LOGO_W + 8                          # 34: the panel starts after the logo column
WARPS = "dyehouse_warps"                 # 'value dyehouse_warps_X': how many Warps are on cable X
# the keyboard stays on C2-B4 while every note held is in it (the C under the lowest note otherwise): this function,
# after lib/visual.py's keyboard_script, is the one the script uses
KB_BASE = """
function base() {
	var s = sounding(), lo = null, hi = null;
	for (var k = 0; k < s.length; k++) {
		if (lo === null || s[k][0] < lo) lo = s[k][0];
		if (hi === null || s[k][0] > hi) hi = s[k][0];
	}
	return lo === null || (lo >= 48 && hi < 48 + 12 * OCTAVES) ? 48 : 12 * Math.floor(lo / 12);
}
"""


def box_of(p, oid):
    return next(b["box"] for b in p.boxes if b["box"].get("id") == oid)


def frame(p, name, verb, color, note):
    """The logo column (the name, its verb, the version at 7 px), the card with the cable it's on at its right."""
    background(p, WIDTH, name, verb, VERSION, sub_color=color)
    box_of(p, "version")["fontsize"] = 7.0                      # no word under 7 px
    panelg.card(p, "c", [X0, 4, WIDTH - 4 - X0, 161], color, name.upper())
    panelg.text(p, "c-note", f"{note} CABLE A", WIDTH - 8, 17, 7, MUTED, anchor="end", w=100)


def cable_menu(p, target, color, x, release, joins=False):
    """The family cable selector (Cable: A-D, one live.tab) -> 'set dyehouse_cable_X' into target (a receive), or
    'send dyehouse_cable_X' (joins: Warp's forward), after a bang to release (what lets go of the notes held on the old cable). joins (Warp): only a cable
    other than the one it's on moves it: it leaves the old one (the count down, 'warps n' down the old cable), then
    the send is set, then it joins the new one (the count up, 'warps n' down it)."""
    panelg.cable_tab(p, "cable", "Cable", [X0 + 4, 21, 92, 30], color, x, 1600)
    p.obj("cable-sel", "sel 0 1 2 3", 2, 5, x, 60)
    for i, c in enumerate(CABLES):              # a receive takes 'set <name>'; Warp's forward 'send <name>' (a send can't)
        p.msg(f"cable-{c}", f"{'send' if joins else 'set'} {cable('cable', c)}", x + 60 * i, 90)
        p.line("cable-sel", f"cable-{c}", i, 0)
        p.line(f"cable-{c}", target)
    if not joins:
        p.obj("cable-t", "t i b", 1, 2, x, 40)
        p.line("cable", "cable-t")
        p.line("cable-t", release, 1, 0)                # first: the old cable's notes go
        p.line("cable-t", "cable-sel", 0, 0)
        return
    p.obj("wc-t", "t i i", 1, 2, x, 20)
    p.line("cable", "wc-t")
    p.obj("wc-new", "i", 2, 1, x + 200, 40)
    p.line("wc-t", "wc-new", 1, 1)
    p.obj("wc-diff", "expr $i1+1!=$i2", 2, 1, x, 40)             # $i2: the cable it is on, plus one (0: none yet)
    p.line("wc-t", "wc-diff", 0, 0)
    p.obj("wc-chg", "sel 1", 2, 2, x, 50)
    p.line("wc-diff", "wc-chg")
    p.obj("wc-go", "t b b b", 1, 3, x, 55)
    p.line("wc-chg", "wc-go", 0, 0)
    p.line("wc-go", release, 2, 0)                     # first: the old cable's notes go
    p.obj("wc-cur", "i -1", 2, 1, x + 100, 70)         # the cable it's on (-1: none yet)
    p.line("wc-go", "wc-cur", 1, 0)                    # then it leaves the old cable
    p.obj("wc-cs", "sel -1", 2, 2, x + 100, 80)
    p.line("wc-cur", "wc-cs")
    p.line("wc-cs", "wl-k", 1, 0)
    p.line("wc-go", "wc-new", 0, 0)                    # then the new one: the send set, joined
    p.obj("wc-nt", "t i i i i", 1, 4, x + 200, 70)
    p.line("wc-new", "wc-nt")
    p.line("wc-nt", "cable-sel", 3, 0)
    p.line("wc-nt", "wc-cur", 2, 1)
    p.obj("wc-cur1", "+ 1", 2, 1, x + 260, 90)
    p.line("wc-nt", "wc-cur1", 1, 0)
    p.line("wc-cur1", "wc-diff", 0, 1)
    p.line("wc-nt", "wj-k", 0, 0)


def count(p, pre, x, y, change=None):
    """How many Warps are on cable k ('value dyehouse_warps_X'), read: an index k into '{pre}-k', the count out of
    '{pre}-n' (0 when none has been kept yet). change: an expr applied to it, the result kept in the cable's value
    again and sent down the cable ('warps n', into 'out')."""
    p.obj(f"{pre}-k", "t b i 0 i", 1, 4, x, y)
    p.obj(f"{pre}-n", "i", 2, 1, x, y + 120)
    p.line(f"{pre}-k", f"{pre}-n", 2, 1)               # none kept yet: 0
    p.obj(f"{pre}-sel", "sel 0 1 2 3", 2, 5, x + 60, y + 30)
    p.line(f"{pre}-k", f"{pre}-sel", 1, 0)
    if change:
        p.obj(f"{pre}-g1", "+ 1", 2, 1, x + 300, y + 30)
        p.line(f"{pre}-k", f"{pre}-g1", 3, 0)
        p.obj(f"{pre}-st", "gate 4", 2, 4, x + 300, y + 180)
        p.line(f"{pre}-g1", f"{pre}-st", 0, 0)
    for i, c in enumerate(CABLES):
        p.obj(f"{pre}-v{c}", f"v {WARPS}_{c}", 1, 1, x + 60 + 60 * i, y + 60)
        p.line(f"{pre}-sel", f"{pre}-v{c}", i, 0)
        p.line(f"{pre}-v{c}", f"{pre}-n", 0, 1)
        if change:
            p.line(f"{pre}-st", f"{pre}-v{c}", i, 0)
    p.line(f"{pre}-k", f"{pre}-n", 0, 0)
    if change:
        p.obj(f"{pre}-ch", f"expr {change}", 1, 1, x, y + 150)
        p.line(f"{pre}-n", f"{pre}-ch")
        p.obj(f"{pre}-t", "t i i", 1, 2, x, y + 180)
        p.line(f"{pre}-ch", f"{pre}-t")
        p.line(f"{pre}-t", f"{pre}-st", 1, 1)
        p.obj(f"{pre}-p", "prepend warps", 1, 1, x, y + 210)
        p.line(f"{pre}-t", f"{pre}-p", 0, 0)
        p.line(f"{pre}-p", "out")


def displays(p, name, color, verb, notes, status_rect, expr_src):
    """The keyboard (three octaves) of the notes going through, the status in words (status_rect), a slot a held note
    with its bend, pressure and timbre. notes: the object whose outlet 0 sends 'p v ch' for each note; expr_src:
    [(kind, object, outlet)], each sending 'v ch' (bend, press) or 'v n ch' (cc) from a trigger's own outlet."""
    status = embed_script(p, "status", status_rect, screens.status_script(f"{name} status", color, name), 2150, 100,
                          name=name)
    panelg.screen(p, "kb-scr", [134, 21, 158, 44])
    kb = embed_script(p, "keys", [138, 25, 150, 36], keyboard_script(f"{name} keys", color, octaves=3) + KB_BASE,
                      2300, 100, name=name)
    ex = embed_script(p, "expr", [134, 69, 158, 92], screens.expression_script(f"{name} expression", color), 2450,
                      100, name=name)
    tap(p, notes, 2000, 20)
    p.obj("shw-note", "prepend note", 1, 1, 2000, 50)
    p.line(notes, "shw-note")
    p.obj("shw-nt", "t l l l", 1, 3, 2000, 80)
    p.line("shw-note", "shw-nt")
    for k, dest in enumerate((kb, status, ex)):
        p.line("shw-nt", dest, k, 0)
    for k, (kind, src, outlet) in enumerate(expr_src):
        p.obj(f"shw-{kind}", f"prepend {kind}", 1, 1, 2500 + 60 * k, 50)
        p.line(src, f"shw-{kind}", outlet, 0)
        p.line(f"shw-{kind}", ex)
    # a new cable: nothing held; its letter in the words and on the card
    tap(p, "cable", 2200, 20)
    p.obj("shw-cable", "prepend cable", 1, 1, 2200, 50)
    p.line("cable", "shw-cable")
    p.obj("shw-ct", "t b l l", 1, 3, 2200, 80)
    p.line("shw-cable", "shw-ct")
    p.line("shw-ct", ex, 2, 0)
    p.line("shw-ct", status, 1, 0)
    p.msg("shw-flush", "flush", 2300, 60)
    p.line("shw-ct", "shw-flush", 0, 0)
    p.line("shw-flush", kb)
    p.obj("shw-csel", "sel 0 1 2 3", 2, 5, 2600, 80)
    p.line("cable", "shw-csel")
    for i, c in enumerate(CABLES):
        p.msg(f"shw-c{c}", f"set {verb.upper()} CABLE {c}", 2600 + 60 * i, 110)
        p.line("shw-csel", f"shw-c{c}", i, 0)
        p.line(f"shw-c{c}", "c-note")


def warp():
    p = Patch(WIDTH)
    frame(p, "Warp", "sends", CORAL, "SENDS")
    p.obj("out", f"forward {cable('cable', 'A')}", 1, 0, 400, 400)   # forward: 'send <name>' moves it (Max's send has no set)
    # 'release' down the cable: every Weft on it lets go of what it played from it (before a new
    # cable, and when the Warp is deleted)
    p.msg("release", "release", 300, 370)
    p.line("release", "out")
    # deleted: its notes let go on its cable, then it leaves the cable's count
    p.obj("free", "freebang", 0, 1, 300, 340)
    p.obj("free-t", "t b b", 1, 2, 300, 355)
    p.line("free", "free-t")
    p.line("free-t", "release", 1, 0)
    p.line("free-t", "wc-cur", 0, 0)
    cable_menu(p, "out", CORAL, 400, "release", joins=True)
    count(p, "wl", 3000, 300, change="($i1>0)*($i1-1)")
    count(p, "wj", 3400, 300, change="$i1+1")
    toggle(p, "thru", "Thru", [X0 + 4, 56, 92, 18], CORAL, 600, initial=1)
    box_of(p, "thru").update(bgcolor=list(INK), activebgcolor=list(INK), fontsize=8.0, rounded=9.0)
    panelg.text(p, "thru-note", "its own track plays too", X0 + 50, 83, 7, MUTED, anchor="middle", w=96)
    # this track's MIDI: through, if THRU
    p.obj("midiin", "midiin", 1, 1, 40, 900)
    p.obj("thru-gate", "gate 1 1", 2, 1, 40, 930)
    p.line("midiin", "thru-gate", 0, 1)
    p.line("thru-out", "thru-gate", 0, 0)
    p.obj("midiout", "midiout", 1, 0, 40, 960)
    p.line("thru-gate", "midiout")
    # the Warp's own reset bytes (THRU off, the reset) into its track
    p.obj("own", "iter", 2, 1, 140, 930)
    p.line("own", "midiout")
    p.obj("thru-off", "sel 0", 2, 2, 140, 870)
    p.line("thru-out", "thru-off")
    p.msg("thru-reset", " ".join(str(b) for b in reset_bytes()), 140, 900)
    p.line("thru-off", "thru-reset", 0, 0)        # THRU off: what it let through stops
    p.line("thru-reset", "own")
    # THRU, in words under it
    tap(p, "thru", 700, 20)
    p.obj("thru-w", "sel 0 1", 2, 3, 700, 50)
    p.line("thru", "thru-w")
    for k, words in enumerate(("only the cable plays it", "its own track plays too")):
        p.msg(f"thru-w{k}", f"set {words}", 700 + 100 * k, 80)
        p.line("thru-w", f"thru-w{k}", k, 0)
        p.line(f"thru-w{k}", "thru-note")
    answer_rinse(p, "own")
    # down the cable: whole messages
    p.obj("n-in", "notein", 1, 3, 200, 200)
    p.obj("n-pk", "pack 0 0 0", 3, 1, 200, 230)
    for k in (2, 1, 0):
        p.line("n-in", "n-pk", k, k)
    p.obj("n-pre", "prepend note", 1, 1, 200, 260)
    p.line("n-pk", "n-pre")
    p.line("n-pre", "out")
    for name, obj, x in (("bend", "xbendin", 300), ("press", "touchin", 400)):
        p.obj(f"{name}-in", obj, 1, 2, x, 200)
        p.obj(f"{name}-pk", "pack 0 0", 2, 1, x, 230)
        p.line(f"{name}-in", f"{name}-pk", 1, 1)
        p.line(f"{name}-in", f"{name}-pk", 0, 0)
        p.obj(f"{name}-pt", "t l l", 1, 2, x, 245)
        p.line(f"{name}-pk", f"{name}-pt")
        p.obj(f"{name}-pre", f"prepend {name}", 1, 1, x, 260)
        p.line(f"{name}-pt", f"{name}-pre", 0, 0)
        p.line(f"{name}-pre", "out")
    p.obj("cc-in", "ctlin", 1, 3, 500, 200)
    p.obj("cc-pk", "pack 0 0 0", 3, 1, 500, 230)
    for k in (2, 1, 0):
        p.line("cc-in", "cc-pk", k, k)
    p.obj("cc-pt", "t l l", 1, 2, 500, 245)
    p.line("cc-pk", "cc-pt")
    p.obj("cc-pre", "prepend cc", 1, 1, 500, 260)
    p.line("cc-pt", "cc-pre", 0, 0)
    p.line("cc-pre", "out")
    displays(p, "warp", CORAL, "sends", "n-pk", [X0 + 4, 87, 92, 74],
             [("bend", "bend-pt", 1), ("press", "press-pt", 1), ("cc", "cc-pt", 1)])
    open_gates(p, ["thru"], x=800, extra=1)
    # loaded: the cable selector says where it is (it joins its cable then, if it hasn't yet: never twice)
    p.line("init", p.again("cable", 800, 120), 0, 0)
    return everywhere(p.patcher([("Warp", ["Cable", "Thru"])], mpe=True), "Warp")       # every shown part its Info View text (1.0.1)


def weft():
    p = Patch(WIDTH)
    frame(p, "Weft", "receives", BLUE, "PLAYS")
    p.obj("in", "receive", 1, 1, 400, 400)   # nameless: a named receive has no inlet for set (the cable chosen sets it at load)
    passthrough(p)
    p.obj("route", "route note bend press cc release warps", 1, 7, 400, 430)
    p.line("in", "route")
    held(p)
    cable_menu(p, "in", BLUE, 400, "h-rel")
    answer_rinse(p, "iter")
    # note [p v ch] -> status p v ('notes': the cable's, and the note-offs of a release)
    p.obj("n-t", "t l l", 1, 2, 200, 460)
    p.line("notes", "n-t", 0, 0)
    p.obj("n-un", "unpack 0 0 0", 1, 3, 260, 490)
    p.line("n-t", "n-un", 1, 0)
    p.obj("n-pk", "pack 0 0 0", 3, 1, 200, 550)
    p.line("n-un", "n-pk", 1, 2)
    p.line("n-un", "n-pk", 0, 1)
    p.obj("n-st", "expr $i3+143", 3, 1, 200, 520)
    p.line("n-t", "n-st", 0, 0)
    p.line("n-st", "n-pk", 0, 0)
    p.line("n-pk", "iter")
    # bend [v ch] -> status LSB MSB
    p.obj("b-t", "t l l l l", 1, 4, 400, 460)
    p.line("route", "b-t", 1, 0)
    p.obj("b-msb", "expr $i1>>7", 1, 1, 480, 490)
    p.obj("b-lsb", "expr $i1&127", 1, 1, 440, 490)
    p.line("b-t", "b-msb", 2, 0)
    p.line("b-t", "b-lsb", 1, 0)
    p.obj("b-pk", "pack 0 0 0", 3, 1, 400, 550)
    p.line("b-msb", "b-pk", 0, 2)
    p.line("b-lsb", "b-pk", 0, 1)
    p.obj("b-st", "expr $i2+223", 2, 1, 400, 520)
    p.line("b-t", "b-st", 0, 0)
    p.line("b-st", "b-pk", 0, 0)
    p.line("b-pk", "iter")
    # pressure [v ch] -> status v
    p.obj("p-t", "t l l l", 1, 3, 600, 460)
    p.line("route", "p-t", 2, 0)
    p.obj("p-v", "expr $i1", 1, 1, 640, 490)
    p.line("p-t", "p-v", 1, 0)
    p.obj("p-pk", "pack 0 0", 2, 1, 600, 550)
    p.line("p-v", "p-pk", 0, 1)
    p.obj("p-st", "expr $i2+207", 2, 1, 600, 520)
    p.line("p-t", "p-st", 0, 0)
    p.line("p-st", "p-pk", 0, 0)
    p.line("p-pk", "iter")
    # cc [v n ch] -> status n v
    p.obj("c-t", "t l l l", 1, 3, 800, 460)
    p.line("route", "c-t", 3, 0)
    p.obj("c-un", "unpack 0 0 0", 1, 3, 860, 490)
    p.line("c-t", "c-un", 1, 0)
    p.obj("c-pk", "pack 0 0 0", 3, 1, 800, 550)
    p.line("c-un", "c-pk", 1, 1)
    p.line("c-un", "c-pk", 0, 2)
    p.obj("c-st", "expr $i3+175", 3, 1, 800, 520)
    p.line("c-t", "c-st", 0, 0)
    p.line("c-st", "c-pk", 0, 0)
    p.line("c-pk", "iter")
    displays(p, "weft", BLUE, "plays", "notes", [X0 + 4, 56, 92, 105],
             [("bend", "b-t", 3), ("press", "p-t", 2), ("cc", "c-t", 2)])
    # THE SENDER: how many Warps are on its cable, read as it loads or changes cable, and as Warps come and go
    count(p, "wr", 3000, 300)
    p.obj("wr-p", "prepend warps", 1, 1, 3000, 460)
    p.line("wr-n", "wr-p")
    p.line("route", "wr-p", 5, 0)
    p.line("wr-p", "status-js")
    p.obj("wr-ct", "t b i", 1, 2, 3100, 230)
    p.line("cable", "wr-ct")
    p.obj("wr-cab", "i", 2, 1, 3100, 260)
    p.line("wr-ct", "wr-cab", 1, 1)
    p.line("wr-ct", "wr-cab", 0, 0)
    p.obj("wr-load", "live.thisdevice", 1, 3, 3200, 200)
    p.line("wr-load", "wr-cab")
    p.line("wr-cab", "wr-k")
    return everywhere(p.patcher([("Weft", ["Cable"])], mpe=True), "Weft")       # every shown part its Info View text (1.0.1)


def held(p, x=1000, y=430):
    """The notes this Weft played from its cable, kept in a coll (key ch*128+p, data 'p ch'):
    stored at a note-on, forgotten at its note-off. 'h-rel' (a 'release' down the cable, or a new
    Cable) plays a note-off for each and forgets them all; 'h-clear' forgets them (the reset)."""
    p.obj("notes", "t l", 1, 1, 200, 440)             # the notes played, from the cable or a release
    p.obj("h-t", "t l l l", 1, 3, x, y)                # its key and data, keep or forget, then play
    p.line("route", "h-t", 0, 0)
    p.line("h-t", "notes", 0, 0)
    p.obj("h-t2", "t l l", 1, 2, x + 100, y + 30)
    p.line("h-t", "h-t2", 2, 0)
    p.obj("h-key", "expr $i3*128+$i1", 3, 1, x + 200, y + 60)
    p.line("h-t2", "h-key", 1, 0)
    p.obj("h-kt", "t i i", 1, 2, x + 200, y + 75)
    p.line("h-key", "h-kt")
    p.obj("h-un", "unpack 0 0 0", 1, 3, x + 100, y + 60)
    p.line("h-t2", "h-un", 0, 0)
    p.obj("h-pk", "pack 0 0 0", 3, 1, x + 100, y + 120)
    p.line("h-un", "h-pk", 0, 1)
    p.line("h-un", "h-pk", 2, 2)
    p.obj("h-ks", "i", 2, 1, x + 200, y + 90)
    p.obj("h-kr", "i", 2, 1, x + 260, y + 90)
    p.line("h-kt", "h-ks", 1, 1)
    p.line("h-kt", "h-kr", 0, 1)
    p.obj("h-v", "expr $i2 > 0", 3, 1, x, y + 60)
    p.line("h-t", "h-v", 1, 0)
    p.obj("h-sel", "sel 0 1", 2, 3, x, y + 90)
    p.line("h-v", "h-sel")
    p.line("h-sel", "h-kr", 0, 0)                     # a note-off: forget it
    p.line("h-sel", "h-ks", 1, 0)                     # a note-on: keep it
    p.line("h-ks", "h-pk", 0, 0)
    p.obj("held", "coll ---weft-held", 1, 4, x + 100, y + 180, outlettype=["", "", "", "bang"])
    p.line("h-pk", "held")
    p.obj("h-rm", "prepend remove", 1, 1, x + 260, y + 120)
    p.line("h-kr", "h-rm")
    p.line("h-rm", "held")
    # release: a note-off for each note held, then forget them
    p.obj("h-rel", "t b b", 1, 2, x + 300, y + 150)
    p.line("route", "h-rel", 4, 0)
    p.msg("h-dump", "dump", x + 300, y + 180)
    p.line("h-rel", "h-dump", 1, 0)
    p.line("h-dump", "held")
    p.msg("h-clear", "clear", x + 400, y + 180)
    p.line("h-rel", "h-clear", 0, 0)
    p.line("h-clear", "held")
    p.obj("h-rinse", f"r {RINSE}", 0, 1, x + 400, y + 120)   # after a reset nothing is held
    p.obj("h-rinse-rt", "route rinse wipe", 1, 3, x + 400, y + 150)
    p.line("h-rinse", "h-rinse-rt")
    p.line("h-rinse-rt", "h-clear", 0, 0)
    p.line("h-rinse-rt", "h-clear", 1, 0)
    p.obj("h-off", "unpack 0 0", 1, 2, x + 100, y + 210)
    p.line("held", "h-off", 0, 0)
    p.obj("h-offpk", "pack 0 0 0", 3, 1, x + 100, y + 240)
    p.line("h-off", "h-offpk", 1, 2)
    p.line("h-off", "h-offpk", 0, 0)
    p.line("h-offpk", "notes")


def main():
    for path, build in ((OUT_WARP, warp), (OUT_WEFT, weft)):
        path.write_bytes(pack_amxd(build(), MIDI_EFFECT))
        nboxes, nlines = check(path, WIDTH, gen=False)
        print(f"wrote {path.name}: {path.stat().st_size} bytes, {nboxes} boxes, {nlines} lines, checks OK")


if __name__ == "__main__":
    sys.exit(main())
