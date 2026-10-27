"""Shared pieces for the Dye House utilities and new components (Tannin, Warp & Weft,
Dye Lot, Selvedge and others).

The family bus: Max's global send, receive and value reach every device in a Live set (no
scripts, so it runs on Push 3 too). The names:

    dyehouse_key      Tannin's key, as the list 'root scale' (root 0-11, scale: lib/scales.py's
                      index). Sent on every change and kept in 'value dyehouse_key', so a device
                      that starts following later still gets it.

    dyehouse_tannin   'here N' / 'also N' / 'gone N': Tannins in the set find each other (N: a random
                      id), so a second one can say so. Tannin sends 'gone' on dyehouse_key as it
                      leaves the set, so devices on Tannin key stop using its last key; a Tannin
                      still in the set then sends its own key again.

The Key choice (follow) picks a device's key: its own, Live's (live_key: the scale of the clip
playing on its track, or Live's current scale, when its Scale Mode is on) or Tannin's. Nothing
here writes to Live, and the choice never changes a device's own parameters.
    dyehouse_set      'root scale' asks Tannin to change key (Dye Lot's SET).
    dyehouse_rinse    'rinse' (stop the sound, release holds) or 'wipe' (also empty what's recorded).
    dyehouse_cable_X  Warp & Weft's cable X (A-D): 'note p v ch', 'bend v ch', 'press v ch', 'cc n v ch'.
"""

from m4l import (AMBER, BG, BLUE, BORDER, BTN, CARD, CORAL, DIAL, FONT, GREEN, INK, LOGO_W,  # noqa: F401
                 MUTED, TEXT, YELLOW, CLEAR as TRANSPARENT)
from scales import LIVE, SCALES

KEY, SET, RINSE, TANNIN = "dyehouse_key", "dyehouse_set", "dyehouse_rinse", "dyehouse_tannin"
WEAVE_KEY, WEAVE_HELD = "dyehouse_weave_key", "dyehouse_weave_held"   # a probe's key, held chord
CABLES = ["A", "B", "C", "D"]
ROOTS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
SCALE_NAMES = [n for n, _, _ in SCALES]
SHIFT = LOGO_W + 4


def reset_bytes():
    """The sustain pedal up (CC 64: notes it holds would outlast an all-notes-off), all notes off (CC 123),
    bend centred, pressure 0 and timbre (CC 74) centred, on all 16 channels: the reset, and what every
    family MIDI device sends when the reset is pressed."""
    out = []
    for c in range(16):
        out += [0xB0 + c, 64, 0, 0xB0 + c, 123, 0, 0xE0 + c, 0, 64, 0xD0 + c, 0, 0xB0 + c, 74, 64]
    return out


def answer_rinse(p, dest, x=40, y=1200, wipe=None):
    """A family MIDI device answering the reset (dyehouse_rinse): 'rinse' or 'wipe' sends the reset
    bytes out of `dest` (an 'iter' into midiout, see passthrough). wipe: an object to bang on
    'wipe' as well (a device that empties what it recorded)."""
    p.obj("rinse-r", f"r {RINSE}", 0, 1, x, y)
    p.obj("rinse-rt", "route rinse wipe", 1, 3, x, y + 30)
    p.line("rinse-r", "rinse-rt")
    p.msg("rinse-bytes", " ".join(str(b) for b in reset_bytes()), x, y + 90)
    p.line("rinse-rt", "rinse-bytes", 0, 0)
    if wipe:
        p.obj("rinse-wt", "t b b", 1, 2, x + 120, y + 60)
        p.line("rinse-rt", "rinse-wt", 1, 0)
        p.line("rinse-wt", "rinse-bytes", 1, 0)
        p.line("rinse-wt", wipe, 0, 0)
    else:
        p.line("rinse-rt", "rinse-bytes", 1, 0)
    p.line("rinse-bytes", dest)


def cable(kind, letter):
    return f"dyehouse_{kind}_{letter}"


# ---------------------------------------------------------------- panel pieces
def card(p, oid, rect, color, title):
    x, y, w, h = rect
    p.panel(oid, rect, CARD, rounded=7, border=BORDER)
    p.panel(f"{oid}-stripe", [x, y, w, 3], color)
    p.comment(f"{oid}-title", title, [x + 8, y + 6, w - 16, 14], color)


def label(p, oid, text, rect):
    p.comment(oid, text, rect, MUTED, size=7.5)


def toggle(p, oid, name, rect, color, x, mode=1, initial=0.0, text=None, gated=True):
    """A live.text switch (mode 1) or button (mode 0). gated: its output passes only once the
    device has loaded (a gate '{oid}-load', opened by open_gates), so a set reopening with it on
    doesn't act by itself. Wire from '{oid}-out'."""
    t = text or name.upper()
    p.param(oid, name, name,
            dict(parameter_type=2, parameter_initial=[float(initial)], parameter_mmax=1, parameter_enum=["off", "on"]),
            maxclass="live.text", patching_rect=[x, 20, 60, 20], presentation=1, presentation_rect=rect,
            varname=oid, numinlets=1, numoutlets=2, outlettype=["", ""], mode=mode, text=t, texton=t,
            rounded=9.0, fontname=FONT, fontsize=9.0, bgcolor=BTN, activebgcolor=BTN, bgoncolor=color,
            activebgoncolor=color, textcolor=color, activetextcolor=color,
            activetextoncolor=INK, bordercolor=color)
    if gated:
        p.obj(f"{oid}-load", "gate 1", 2, 1, x, 50)
        p.line(oid, f"{oid}-load", 0, 1)
        p.obj(f"{oid}-out", "t l", 1, 1, x, 80)
        p.line(f"{oid}-load", f"{oid}-out")
    else:
        p.obj(f"{oid}-out", "t l", 1, 1, x, 80)
        p.line(oid, f"{oid}-out")


def press(p, oid, x):
    """A mode-0 button's real presses as one bang out of '{oid}-press' (a bang, or 1 on press)."""
    p.obj(f"{oid}-route", "route bang", 2, 2, x, 110)
    p.line(f"{oid}-out", f"{oid}-route")
    p.obj(f"{oid}-one", "sel 1", 2, 2, x + 40, 140)
    p.line(f"{oid}-route", f"{oid}-one", 1, 0)
    p.obj(f"{oid}-press", "t b", 1, 1, x, 170)
    p.line(f"{oid}-route", f"{oid}-press", 0, 0)
    p.line(f"{oid}-one", f"{oid}-press", 0, 0)


def menu(p, oid, name, rect, items, initial, x, short=None):
    p.param(oid, name, short or name,
            dict(parameter_type=2, parameter_initial=[float(initial)], parameter_mmax=len(items) - 1,
                 parameter_enum=list(items)),
            maxclass="live.menu", patching_rect=[x, 20, 60, 16], presentation=1, presentation_rect=rect,
            varname=oid, numinlets=1, numoutlets=3, outlettype=["", "", "float"], fontsize=9.0)


def numbox(p, oid, name, rect, lo, hi, initial, x, unitstyle=0, kind=1, units=None):
    v = dict(parameter_type=kind, parameter_initial=[float(initial)], parameter_mmin=lo, parameter_mmax=hi,
             parameter_unitstyle=unitstyle)
    if units:
        v["parameter_units"] = units
    p.param(oid, name, name, v, maxclass="live.numbox", patching_rect=[x, 20, 44, 16], presentation=1,
            presentation_rect=rect, varname=oid, numinlets=1, numoutlets=2, outlettype=["", "float"], fontsize=9.0)


def dial(p, oid, name, rect, color, lo, hi, initial, x, unitstyle=1, units=None, exponent=None):
    v = dict(parameter_type=0, parameter_initial=[float(initial)], parameter_mmin=lo, parameter_mmax=hi,
             parameter_unitstyle=unitstyle)
    if units:
        v["parameter_units"] = units
    if exponent:                          # a knob curve (its start stored as is: m4l.stored_initial)
        v["parameter_exponent"] = exponent
    p.param(oid, name, name, v, maxclass="live.dial", patching_rect=[x, 20, 44, 44], presentation=1,
            presentation_rect=rect, varname=oid, numinlets=1, numoutlets=2, outlettype=["", "float"],
            showname=1, shownumber=1, dialcolor=DIAL, activedialcolor=color, needlecolor=TEXT,
            activeneedlecolor=TEXT, textcolor=TEXT, panelcolor=TRANSPARENT)


def background(p, width, name, subtitle, version, sub_color=AMBER):
    p.panel("bg", [0, 0, width, 169], BG)
    p.logo(subtitle, sub_color, version, name=name)


def open_gates(p, oids, x=40, y=20, extra=0):
    """live.thisdevice -> 'init' (t b ... b): opens each gated control's gate; returns the number of
    the first free outlet of 'init' (outlets 0..extra-1 are left for the caller, fired last)."""
    p.obj("thisdevice", "live.thisdevice", 1, 3, x, y)
    n = extra + 1
    p.obj("init", "t " + " ".join(["b"] * n), 1, n, x, y + 30)
    p.line("thisdevice", "init")
    if oids:
        p.msg("open", "1", x + 80, y + 60)
        p.line("init", "open", n - 1, 0)
        p.obj("open-t", "t " + " ".join(["1"] * len(oids)), 1, len(oids), x + 80, y + 90)
        p.line("open", "open-t")
        for i, oid in enumerate(oids):
            p.line("open-t", f"{oid}-load", i, 0)


def song_start(p, x, y, dest="gen", guard=False):
    """Where the song is when Live starts, for a gen~ clock that counts its own steps: a bang into
    'song-start' sends 'startbeat B' to dest, B the song position in quarter notes (Live's transport:
    bars, beats in the signature's unit, ticks at 480 a quarter note). Bang it before the device's
    restart (its 'rst'), so the clock places step 1 on Live's bar line, wherever play started
    (plans/r1/device-review.md, the bar line). guard: a denominator of 0 (as Live can report while a set reopens:
    two "expr: divide by zero" lines in the Max window, Oct 21) taken as 4; Weld Kit 1.0.1 first, the others when
    they're next built on purpose (it changes their patch)."""
    p.obj("song-start", "t b", 1, 1, x, y)
    p.obj("song-tp", "transport", 2, 9, x, y + 30)
    p.line("song-start", "song-tp")
    p.obj("song-pk", "pack 0 0 0 4 4", 5, 1, x, y + 90)       # bars beats ticks numerator denominator
    # the time signature is a list on outlet 5 (Max's reference; until Oct 20 read as two outlets, 5 and 6, the
    # second being Live's play state: plans/process/transport-outlets.md)
    p.obj("song-sig", "unpack 4 4", 1, 2, x + 60, y + 60)
    p.line("song-tp", "song-sig", 5, 0)
    p.line("song-sig", "song-pk", 1, 4)
    p.line("song-sig", "song-pk", 0, 3)
    p.line("song-tp", "song-pk", 2, 2)
    p.line("song-tp", "song-pk", 1, 1)
    p.line("song-tp", "song-pk", 0, 0)
    den = "($i5 + 4 * ($i5 < 1))" if guard else "$i5"
    p.obj("song-beat", f"expr (($i1 - 1) * $i4 + ($i2 - 1)) * 4. / {den} + $i3 / 480.", 5, 1, x, y + 120)
    p.line("song-pk", "song-beat")
    p.obj("song-p", "prepend startbeat", 1, 1, x, y + 150)
    p.line("song-beat", "song-p")
    p.line("song-p", dest)


def passthrough(p, x=40, y=900):
    """What comes in goes out: midiin -> 'midiout' (also fed by the device's own 'iter')."""
    p.obj("midiin", "midiin", 1, 1, x, y)
    p.obj("midiout", "midiout", 1, 0, x, y + 60)
    p.line("midiin", "midiout")
    p.obj("iter", "iter", 2, 1, x + 100, y + 30)
    p.line("iter", "midiout")


# ---------------------------------------------------------------- following Live, or Tannin
# The Key choice (follow): Own, Live or Tannin. Its readout shows the key being played, in the
# colour of its source: Live 12's purple; amber when Live's scale isn't one of the family's
# (played Chromatic from Live's root); blue for Tannin.
KEY_SOURCES = ["Own key", "Live key", "Tannin key"]
LIVE_C = [0.63, 0.55, 0.95, 1.0]
KIND_COLOR = {0: MUTED, 1: BLUE, 2: LIVE_C, 3: AMBER}   # none, Tannin, Live, Live (not ours)


def color_msg(c):
    return " ".join(f"{v:.3f}" for v in c)


def scale_source(p, pre, x, y):
    """One Live scale (a clip's or the song's): observers '{pre}-mode', '{pre}-int' and '{pre}-root',
    to be given an 'id N' in their right inlet (root first, then scale, then mode, so the key is
    whole when the mode arrives). '{pre}-pk' holds 'root scale kind' (kind 2: one of the family's
    scales; 3: a Live scale the family lacks, played as Chromatic) and outputs it on every change,
    and on a bang."""
    for k, (oid, prop) in enumerate(((f"{pre}-mode", "scale_mode"), (f"{pre}-int", "scale_intervals"),
                                     (f"{pre}-root", "root_note"))):
        p.obj(oid, f"live.observer {prop}", 2, 2, x + 80 * k, y)
    # Live's scale_intervals -> one number (bit k for k semitones) -> the family's scale
    p.obj(f"{pre}-pow", "vexpr 1<<$i1", 2, 1, x + 80, y + 30)
    p.line(f"{pre}-int", f"{pre}-pow")
    p.obj(f"{pre}-sum", "zl sum", 2, 2, x + 80, y + 60)
    p.line(f"{pre}-pow", f"{pre}-sum")
    p.obj(f"{pre}-i", "t i", 1, 1, x + 80, y + 90)
    p.line(f"{pre}-sum", f"{pre}-i")
    masks = list(LIVE)
    p.obj(f"{pre}-sel", "sel " + " ".join(str(m) for m in masks), 2, len(masks) + 1, x + 80, y + 120)
    p.line(f"{pre}-i", f"{pre}-sel")
    p.obj(f"{pre}-pk", "pack 0 0 2", 3, 1, x, y + 240)
    p.obj(f"{pre}-st", "t b l", 1, 2, x + 80, y + 180)
    p.obj(f"{pre}-su", "unpack 0 0", 1, 2, x + 120, y + 210)
    p.line(f"{pre}-st", f"{pre}-su", 1, 0)
    p.line(f"{pre}-su", f"{pre}-pk", 1, 2)
    p.line(f"{pre}-su", f"{pre}-pk", 0, 1)
    p.line(f"{pre}-st", f"{pre}-pk", 0, 0)
    for k, m in enumerate(masks + [None]):
        p.msg(f"{pre}-s{k}", f"{LIVE[m]} 2" if m is not None else "0 3", x + 80 + 30 * k, y + 150)
        p.line(f"{pre}-sel", f"{pre}-s{k}", k, 0)
        p.line(f"{pre}-s{k}", f"{pre}-st")
    p.line(f"{pre}-root", f"{pre}-pk", 0, 0)


def song_scale(p, src, outlet, x, y):
    """Live's current scale (the one above the tracks: the selected clip's), from a bang on
    src's outlet: 'ls-pk' (scale_source) and 'ls-mode'; also 'ls-name', Live's own name for it."""
    p.msg("ls-path", "path live_set", x, y)
    p.line(src, "ls-path", outlet, 0)
    p.obj("ls-lp", "live.path", 2, 3, x, y + 30)
    p.line("ls-path", "ls-lp")
    p.obj("ls-ids", "t l l l l", 1, 4, x, y + 60)
    p.line("ls-lp", "ls-ids")
    scale_source(p, "ls", x, y + 90)
    for k, oid in enumerate(("ls-mode", "ls-int", "ls-root")):
        p.line("ls-ids", oid, k, 1)
    p.obj("ls-name", "live.observer scale_name", 2, 2, x + 240, y + 90)
    p.line("ls-ids", "ls-name", 3, 1)


def live_key(p, x, y):
    """Live's scale for this device, as Live's own scale-aware devices take it: the scale of the
    Session clip playing on its track, if that clip's Scale Mode is on; else Live's current scale
    (the one above the tracks: the selected clip's), if its Scale Mode is on. 'lk-out' gives
    'root scale kind' whenever it changes or comes into force; 'lk-on' gives 1 or 0 as Live's
    scale comes into or out of force, before the key. Bang 'lk-ask' for the key now (nothing while
    no Live scale is in force). Never writes to Live."""
    p.obj("lk-td", "live.thisdevice", 1, 3, x, y)
    p.obj("lk-init", "t b b", 1, 2, x, y + 30)
    p.line("lk-td", "lk-init")
    # the song's current scale
    song_scale(p, "lk-init", 1, x, y + 60)
    # the clip playing on this device's track (its slot, as it changes)
    p.msg("lt-path", "path this_device canonical_parent", x + 700, y + 60)
    p.line("lk-init", "lt-path", 0, 0)
    p.obj("lt-lp", "live.path", 2, 3, x + 700, y + 90)
    p.line("lt-path", "lt-lp")
    p.obj("lt-slot", "live.observer playing_slot_index", 2, 2, x + 700, y + 120)
    p.line("lt-lp", "lt-slot", 0, 1)
    p.msg("lc-path", "path this_device canonical_parent clip_slots $1 clip", x + 700, y + 150)
    p.line("lt-slot", "lc-path")
    p.obj("lc-lp", "live.path", 2, 3, x + 700, y + 180)
    p.line("lc-path", "lc-lp")
    p.obj("lc-idt", "t l l", 1, 2, x + 700, y + 210)
    p.line("lc-lp", "lc-idt")
    # no clip playing (id 0): its Scale Mode counts as off
    p.obj("lc-id", "route id", 2, 2, x + 900, y + 240)
    p.line("lc-idt", "lc-id", 1, 0)
    p.obj("lc-none", "sel 0", 2, 2, x + 900, y + 270)
    p.line("lc-id", "lc-none")
    p.msg("lc-off", "0", x + 900, y + 300)
    p.line("lc-none", "lc-off")
    p.obj("lc-ids", "t l l l", 1, 3, x + 700, y + 240)
    p.line("lc-idt", "lc-ids", 0, 0)
    scale_source(p, "lc", x + 700, y + 330)
    for k, oid in enumerate(("lc-mode", "lc-int", "lc-root")):
        p.line("lc-ids", oid, k, 1)
    # which is in force: the clip's, else the song's
    p.obj("lk-modes", "pak 0 0", 2, 1, x + 400, y + 60)
    p.line("lc-mode", "lk-modes", 0, 0)
    p.line("lc-off", "lk-modes", 0, 0)
    p.line("ls-mode", "lk-modes", 0, 1)
    p.obj("lk-mt", "t b l l l", 1, 4, x + 400, y + 90)
    p.line("lk-modes", "lk-mt")
    p.obj("lc-on", "expr $i1!=0", 1, 1, x + 520, y + 120)
    p.line("lk-mt", "lc-on", 3, 0)
    p.obj("ls-on", "expr ($i2!=0)*($i1==0)", 1, 1, x + 460, y + 120)
    p.line("lk-mt", "ls-on", 2, 0)
    p.obj("lk-any", "expr ($i1!=0)+($i2!=0)>0", 1, 1, x + 400, y + 120)
    p.line("lk-mt", "lk-any", 1, 0)
    p.obj("lk-on", "change", 1, 1, x + 400, y + 150)
    p.line("lk-any", "lk-on")
    p.obj("lk-ask", "t b b", 1, 2, x + 340, y + 150)
    p.line("lk-mt", "lk-ask", 0, 0)
    p.line("lk-ask", "lc-pk", 1, 0)
    p.line("lk-ask", "ls-pk", 0, 0)
    p.obj("lc-g", "gate 1", 2, 1, x + 520, y + 420)
    p.line("lc-on", "lc-g", 0, 0)
    p.line("lc-pk", "lc-g", 0, 1)
    p.obj("ls-g", "gate 1", 2, 1, x + 460, y + 420)
    p.line("ls-on", "ls-g", 0, 0)
    p.line("ls-pk", "ls-g", 0, 1)
    p.obj("lk-out", "t l", 1, 1, x + 460, y + 450)
    p.line("lc-g", "lk-out")
    p.line("ls-g", "lk-out")


def follow(p, rect, x, y, root_menu, scale_menu, show=None, idle="", idle_color=MUTED, justify=0, menu_fn=None):
    """The Key choice: which key the device plays. Own: its own Root and Scale. Live: Live's scale,
    as Live's own devices take it (live_key: the clip playing on its track, else Live's current
    scale, when Scale Mode is on). Tannin: Tannin's key (the bus, or the stored key, which is also
    how a set reopens). With Live or Tannin chosen and nothing there, it plays its own key.

    It never changes the device's own Root and Scale: they grey out (a look, not a value) and keep
    their values and automation. Whatever the menus fed now leaves from 'fk-root-eff' and
    'fk-scale-eff' (Patch.reroute). The readout comment ('fk-readout', at `show`, else under the
    menu) reads the key being played, coloured by source (KIND_COLOR), 'no Live scale' or
    'no Tannin' when there is none, and `idle` with Own. root_menu None: a device with a Scale and
    no Root takes only the scale. menu_fn(p, rect, x) draws the menu another way; it must be a
    live.menu with id 'keysrc' and items KEY_SOURCES."""
    rx, ry, rw, rh = rect
    if menu_fn:
        menu_fn(p, rect, x)
    else:
        menu(p, "keysrc", "Key", rect, KEY_SOURCES, 0, x)
    if show is None:
        show = [rx, ry + rh + 1, rw, 11]
    p.comment("fk-readout", idle, show, idle_color, size=7.5, justify=justify)
    parts = [("scale", scale_menu)] + ([("root", root_menu)] if root_menu else [])
    # the device's own key: kept, and passed on while it's the one chosen
    for j, (k, m) in enumerate(parts):
        px = x + 700 + 160 * j
        p.obj(f"fk-{k}-t", "t i i", 1, 2, px, y)
        p.line(m, f"fk-{k}-t")
        p.obj(f"fk-{k}-own", "i", 2, 1, px + 60, y + 30)
        p.line(f"fk-{k}-t", f"fk-{k}-own", 1, 1)
        p.obj(f"fk-{k}-og", "gate 1 1", 2, 1, px, y + 60)
        p.line(f"fk-{k}-t", f"fk-{k}-og", 0, 1)
        p.obj(f"fk-{k}-ag", "gate 1", 2, 1, px + 100, y + 60)
        p.obj(f"fk-{k}-eff", "t i", 1, 1, px, y + 90)
        p.line(f"fk-{k}-og", f"fk-{k}-eff")
        p.line(f"fk-{k}-own", f"fk-{k}-eff")
        p.line(f"fk-{k}-ag", f"fk-{k}-eff")
        p.reroute[m] = f"fk-{k}-eff"
    # the choice: 0 Own, 1 Live, 2 Tannin
    p.obj("fk-src", "t i i i i i", 1, 5, x, y)
    p.line("keysrc", "fk-src")
    p.obj("fk-srcv", "i", 2, 1, x + 400, y + 240)          # kept, for the readout's 'no ...'
    p.line("fk-src", "fk-srcv", 4, 1)
    p.obj("fk-on", "expr $i1>0", 1, 1, x, y + 30)
    p.line("fk-src", "fk-on", 3, 0)
    p.obj("fk-fg", "gate 1", 2, 1, x, y + 150)
    p.line("fk-on", "fk-fg", 0, 0)
    p.obj("fk-live", "expr $i1==1", 1, 1, x + 60, y + 30)
    p.line("fk-src", "fk-live", 2, 0)
    p.obj("fk-lg", "gate 1", 2, 1, x + 460, y + 120)
    p.obj("fk-tan", "expr $i1==2", 1, 1, x + 120, y + 30)
    p.line("fk-src", "fk-tan", 1, 0)
    p.obj("fk-tk", "gate 1", 2, 1, x + 240, y + 90)
    p.line("fk-tan", "fk-tk", 0, 0)
    # the own menus grey out unless Own is chosen, and pass on only then
    p.obj("fk-not", "expr $i1==0", 1, 1, x + 180, y + 30)
    p.line("fk-src", "fk-not", 0, 0)
    p.obj("fk-nt", "t b i " + " ".join("i" for _ in parts), 1, len(parts) + 2, x + 180, y + 60)
    p.line("fk-not", "fk-nt")
    for j, (k, _) in enumerate(parts):
        p.line("fk-nt", f"fk-{k}-og", j + 2, 0)
    p.msg("fk-active", "active $1", x + 180, y + 90)
    p.line("fk-nt", "fk-active", 1, 0)
    p.obj("fk-act", "t " + " ".join("l" for _ in parts), 1, len(parts), x + 180, y + 120)
    p.line("fk-active", "fk-act")
    for j, (_, m) in enumerate(parts):
        p.line("fk-act", m, j, 0)
    # then: nothing yet (own key, 'no ...'), then ask the chosen source for its key now
    p.obj("fk-ask", "t b b b", 1, 3, x + 180, y + 150)
    p.line("fk-nt", "fk-ask", 0, 0)
    p.msg("fk-none", "-1 -1 0", x + 240, y + 180)
    p.line("fk-ask", "fk-none", 2, 0)
    p.obj("fk-v", f"v {KEY}", 1, 1, x + 240, y + 60)
    p.line("fk-ask", "fk-v", 1, 0)
    # Tannin ('gone' as it leaves the set)
    p.obj("fk-r", f"r {KEY}", 0, 1, x + 300, y + 30)
    p.line("fk-r", "fk-tk", 0, 1)
    p.line("fk-v", "fk-tk", 0, 1)
    p.obj("fk-tr", "route gone", 2, 2, x + 240, y + 120)
    p.line("fk-tk", "fk-tr")
    p.line("fk-tr", "fk-none", 0, 0)
    p.msg("fk-tannin", "$1 $2 1", x + 300, y + 150)
    p.line("fk-tr", "fk-tannin", 1, 0)
    p.line("fk-tannin", "fk-fg", 0, 1)
    # Live: its key while chosen; out of force (Scale Mode off, no clip scale): nothing
    live_key(p, x + 1200, y)
    p.line("fk-ask", "lk-ask", 0, 0)
    p.line("lk-out", "fk-lg", 0, 1)
    p.line("fk-lg", "fk-fg", 0, 1)
    p.obj("fk-lsel", "sel 0", 2, 2, x + 420, y + 60)
    p.line("lk-on", "fk-lsel")
    p.obj("fk-loff", "gate 1", 2, 1, x + 420, y + 90)
    p.obj("fk-live2", "t i i", 1, 2, x + 60, y + 60)
    p.line("fk-live", "fk-live2")
    p.line("fk-live2", "fk-lg", 1, 0)
    p.line("fk-live2", "fk-loff", 0, 0)
    p.line("fk-lsel", "fk-loff", 0, 1)
    p.line("fk-loff", "fk-none", 0, 0)
    # the key: 'root scale kind' (kind 0: none, the device's own)
    p.obj("fk-key", "t l l", 1, 2, x, y + 180)
    p.line("fk-fg", "fk-key")
    p.line("fk-none", "fk-key")       # 'none' always passes: the device's own key, and why
    p.obj("fk-un", "unpack 0 0 0", 1, 3, x, y + 210)
    p.line("fk-key", "fk-un", 0, 0)
    p.obj("fk-kind", "t i i", 1, 2, x + 60, y + 240)
    p.line("fk-un", "fk-kind", 2, 0)
    p.obj("fk-some", "expr $i1>0", 1, 1, x + 60, y + 270)
    p.line("fk-kind", "fk-some", 1, 0)
    p.obj("fk-st", "t " + " ".join("i" for _ in parts), 1, len(parts), x + 60, y + 300)
    p.line("fk-some", "fk-st")
    for j, (k, _) in enumerate(parts):
        p.line("fk-st", f"fk-{k}-ag", j, 0)
    p.obj("fk-k0", "sel 0", 2, 2, x + 120, y + 270)
    p.line("fk-kind", "fk-k0", 0, 0)
    # with no key there (kind 0) the device plays its own: its Root and Scale pass on as they
    # change, whatever the choice, so a set reopening in any order, or a Root turned while
    # Live's Scale Mode is off, is heard
    p.obj("fk-ownok", "expr $i1==0", 1, 1, x + 180, y + 240)
    p.line("fk-kind", "fk-ownok", 1, 0)
    p.obj("fk-ot", "t " + " ".join("i" for _ in parts), 1, len(parts), x + 180, y + 270)
    p.line("fk-ownok", "fk-ot")
    for j, (k, _) in enumerate(parts):
        p.line("fk-ot", f"fk-{k}-og", j, 0)
    p.obj("fk-restore", "t b " + " ".join("b" for _ in parts), 1, len(parts) + 1, x + 120, y + 300)
    p.line("fk-k0", "fk-restore", 0, 0)
    for j, (k, _) in enumerate(parts):
        p.line("fk-restore", f"fk-{k}-own", j + 1, 0)
    p.line("fk-un", "fk-scale-ag", 1, 1)
    if root_menu:
        p.line("fk-un", "fk-root-ag", 0, 1)
    # the readout
    p.line("fk-restore", "fk-srcv", 0, 0)
    p.obj("fk-why", "sel 0 1 2", 2, 4, x + 400, y + 270)
    p.line("fk-srcv", "fk-why")
    for k, text in enumerate((f"set {idle}".rstrip(), "set no Live scale", "set no Tannin")):
        c = idle_color if k == 0 else MUTED
        p.msg(f"fk-w{k}", f"{text}, textcolor {color_msg(c)}", x + 400 + 100 * k, y + 300)
        p.line("fk-why", f"fk-w{k}", k, 0)
        p.line(f"fk-w{k}", "fk-readout")
    p.obj("fk-show", "unpack 0 0 0", 1, 3, x + 700, y + 180)
    p.line("fk-key", "fk-show", 1, 0)
    p.obj("fk-col", "sel 1 2 3", 2, 4, x + 820, y + 210)
    p.line("fk-show", "fk-col", 2, 0)
    for k in (1, 2, 3):
        p.msg(f"fk-c{k}", f"textcolor {color_msg(KIND_COLOR[k])}", x + 820 + 60 * k, y + 240)
        p.line("fk-col", f"fk-c{k}", k - 1, 0)
        p.line(f"fk-c{k}", "fk-readout")
    p.obj("fk-text", "prepend set", 1, 1, x + 700, y + 330)
    p.line("fk-text", "fk-readout")
    names = [n for n, _, _ in SCALES]
    if root_menu:
        # the scale picks the message, the root's name fills it in
        p.obj("fk-sn", "expr $i1+1", 1, 1, x + 760, y + 210)
        p.line("fk-show", "fk-sn", 1, 0)
        p.obj("fk-sg", f"gate {len(names)}", 2, len(names), x + 700, y + 270)
        p.line("fk-sn", "fk-sg", 0, 0)
        p.obj("fk-rn", "zl lookup", 2, 2, x + 700, y + 240)
        p.line("fk-show", "fk-rn", 0, 0)
        p.line("fk-rn", "fk-sg", 0, 1)
        p.obj("fk-td", "live.thisdevice", 1, 3, x + 600, y + 210)
        p.msg("fk-roots", " ".join(ROOTS), x + 600, y + 240)
        p.line("fk-td", "fk-roots")
        p.line("fk-roots", "fk-rn", 0, 1)
        for i, n in enumerate(names):
            p.msg(f"fk-n{i}", f"$1 {n}", x + 700 + 40 * i, y + 300)
            p.line("fk-sg", f"fk-n{i}", i, 0)
            p.line(f"fk-n{i}", "fk-text")
    else:
        p.obj("fk-sn", "sel " + " ".join(str(i) for i in range(len(names))), 2, len(names) + 1, x + 760, y + 240)
        p.line("fk-show", "fk-sn", 1, 0)
        for i, n in enumerate(names):
            p.msg(f"fk-n{i}", n, x + 700 + 40 * i, y + 300)
            p.line("fk-sn", f"fk-n{i}", i, 0)
            p.line(f"fk-n{i}", "fk-text")


def scale_steps_msgs(p, prefix, coll_name, x, y, src, src_outlet=0):
    """Scale index (from src) -> fills 'coll <coll_name>' with 'k step' for each step, then
    '{prefix}-np' (unpack) outputs the scale's period (outlet 1) and size (outlet 0): wire them."""
    p.obj(f"{prefix}-sel", "sel " + " ".join(str(i) for i in range(len(SCALES))), 2, len(SCALES) + 1, x, y)
    p.line(src, f"{prefix}-sel", src_outlet, 0)
    p.obj(f"{prefix}-coll", f"coll {coll_name}", 1, 4, x, y + 90)
    for i, (_, steps, per) in enumerate(SCALES):
        p.obj(f"{prefix}-go{i}", "t b b", 1, 2, x + 40 * i, y + 30)
        p.line(f"{prefix}-sel", f"{prefix}-go{i}", i, 0)
        body = ", ".join(f"{k} {v:g}" for k, v in enumerate(steps))
        p.msg(f"{prefix}-data{i}", f"clear, {body}", x + 40 * i, y + 60)
        p.line(f"{prefix}-go{i}", f"{prefix}-data{i}", 1, 0)
        p.line(f"{prefix}-data{i}", f"{prefix}-coll")
        p.msg(f"{prefix}-np{i}", f"{len(steps)} {per:g}", x + 40 * i + 20, y + 60)
        p.line(f"{prefix}-go{i}", f"{prefix}-np{i}", 0, 0)
        p.line(f"{prefix}-np{i}", f"{prefix}-np")
    p.obj(f"{prefix}-np", "unpack 0 0.", 1, 2, x, y + 120)


# ---------------------------------------------------------------- MIDI out, whole messages
def emitter(p, kind, prefix, x, y):
    """'{prefix}' takes a list and sends its MIDI bytes to 'iter' (see passthrough):
    note [p v ch] (v 0 is a note-off), bend [v ch] (14 bits), press [v ch], cc [v n ch]."""
    if kind == "note":
        p.obj(prefix, "t l l", 1, 2, x, y)
        p.obj(f"{prefix}-un", "unpack 0 0 0", 1, 3, x + 60, y + 30)
        p.line(prefix, f"{prefix}-un", 1, 0)
        p.obj(f"{prefix}-pk", "pack 0 0 0", 3, 1, x, y + 90)
        p.line(f"{prefix}-un", f"{prefix}-pk", 1, 2)
        p.line(f"{prefix}-un", f"{prefix}-pk", 0, 1)
        p.obj(f"{prefix}-st", "expr $i3+143", 3, 1, x, y + 60)
    elif kind == "bend":
        p.obj(prefix, "t l l l", 1, 3, x, y)
        p.obj(f"{prefix}-msb", "expr $i1>>7", 1, 1, x + 80, y + 30)
        p.obj(f"{prefix}-lsb", "expr $i1&127", 1, 1, x + 40, y + 30)
        p.line(prefix, f"{prefix}-msb", 2, 0)
        p.line(prefix, f"{prefix}-lsb", 1, 0)
        p.obj(f"{prefix}-pk", "pack 0 0 0", 3, 1, x, y + 90)
        p.line(f"{prefix}-msb", f"{prefix}-pk", 0, 2)
        p.line(f"{prefix}-lsb", f"{prefix}-pk", 0, 1)
        p.obj(f"{prefix}-st", "expr $i2+223", 2, 1, x, y + 60)
    elif kind == "press":
        p.obj(prefix, "t l l", 1, 2, x, y)
        p.obj(f"{prefix}-v", "expr $i1", 1, 1, x + 40, y + 30)
        p.line(prefix, f"{prefix}-v", 1, 0)
        p.obj(f"{prefix}-pk", "pack 0 0", 2, 1, x, y + 90)
        p.line(f"{prefix}-v", f"{prefix}-pk", 0, 1)
        p.obj(f"{prefix}-st", "expr $i2+207", 2, 1, x, y + 60)
    elif kind == "cc":
        p.obj(prefix, "t l l", 1, 2, x, y)
        p.obj(f"{prefix}-un", "unpack 0 0 0", 1, 3, x + 60, y + 30)
        p.line(prefix, f"{prefix}-un", 1, 0)
        p.obj(f"{prefix}-pk", "pack 0 0 0", 3, 1, x, y + 90)
        p.line(f"{prefix}-un", f"{prefix}-pk", 1, 1)
        p.line(f"{prefix}-un", f"{prefix}-pk", 0, 2)
        p.obj(f"{prefix}-st", "expr $i3+175", 3, 1, x, y + 60)
    p.line(prefix, f"{prefix}-st", 0, 0)
    p.line(f"{prefix}-st", f"{prefix}-pk", 0, 0)
    p.line(f"{prefix}-pk", "iter")
