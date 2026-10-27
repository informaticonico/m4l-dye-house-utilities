"""Shared helpers for building Tincture-family Max for Live devices.

A device is described in Python with Patch, which collects boxes, patch
lines and Live parameters, then written as an .amxd with pack_amxd() and
verified with check(). Every UI control is a Live parameter whose output is
prefixed with its gen~ Param name and sent to the gen~ codebox's first inlet.
"""

import json
import re
import struct

import frozen

HEIGHT = 169  # Live's fixed device height

# Tincture palette: a mid-dark surface (lifted from near-black for readability;
# every label is at least 5:1 against its card), the four module colours, and INK
# for text on a coloured fill
BG = [0.168627, 0.168627, 0.156863, 1.0]  # #2B2B28
CARD = [0.227451, 0.227451, 0.211765, 1.0]  # #3A3A36
BORDER = [0.360784, 0.356863, 0.337255, 1.0]  # #5C5B56
BTN = [0.192157, 0.192157, 0.180392, 1.0]  # #31312E
DIAL = [0.431373, 0.427451, 0.4, 1.0]  # #6E6D66
CORAL = [0.9411764705882353, 0.6, 0.4823529411764706, 1.0]
YELLOW = [0.9803921568627451, 0.7803921568627451, 0.4588235294117647, 1.0]
BLUE = [0.5215686274509804, 0.7176470588235294, 0.9215686274509803, 1.0]
GREEN = [0.592156862745098, 0.7686274509803922, 0.34901960784313724, 1.0]
AMBER = [0.9372549019607843, 0.6235294117647059, 0.15294117647058825, 1.0]
TEXT = [0.964706, 0.956863, 0.933333, 1.0]  # #F6F4EE
MUTED = [0.788235, 0.780392, 0.745098, 1.0]  # #C9C7BE
INK = [0.109804, 0.109804, 0.101961, 1.0]  # #1C1C1A
CLEAR = [0, 0, 0, 0]
FONT = "Ableton Sans Bold"

# logo mark: four translucent circles, one per Tincture module colour
LOGO_W = 26
LOGO_ALPHA = 0.88
LOGO_CIRCLES = (
    (0, 0, [0.9411764705882353, 0.6, 0.4823529411764706]),       # coral, top-left
    (1, 0, [0.9725490196078431, 0.7803921568627451, 0.4784313725490196]),  # amber, top-right
    (0, 1, [0.5333333333333333, 0.7137254901960784, 0.9098039215686274]),  # blue, bottom-left
    (1, 1, [0.6, 0.7647058823529411, 0.3568627450980392]),        # green, bottom-right
)

APPVERSION = {"major": 8, "minor": 6, "revision": 0, "architecture": "x64", "modernui": 1}



def _curve(v):
    """(lo, hi, exponent) of a float control with a knob curve, or None."""
    e = v.get("parameter_exponent", 1) or 1
    if v.get("parameter_type", 0) != 0 or e == 1:
        return None
    return float(v.get("parameter_mmin", 0)), float(v.get("parameter_mmax", 127)), float(e)


LEVEL_CURVE = 2.0     # a Level knob's travel, as a fader's: the value is the square of the knob's position


def level_knob(longname, v, attrs):
    """A Level knob (a plain gain, 0 to at most 1.6, 0.8 unity): it gets LEVEL_CURVE, so its travel
    runs in decibels as Live's own volume controls do (0.8 at 71 % of a 0-1.6 knob, 89 % of a 0-1;
    -6 dB half a knob's travel lower, -12 dB lower again) instead of crowding the quiet end into the
    first few degrees. The value is still the gain, but Live keeps a curved knob by its position, not its value: a set
    saved before a knob got its curve reopens with the value lower (Tincture 1.0's Level 0.62 came back at 0.38 in 2.0,
    Oct 21; the owner kept the curve, and 2.0's manual and update email say so). A device on sale keeps its curves."""
    return (attrs.get("maxclass") == "live.dial" and longname.endswith("Level")
            and v.get("parameter_type", 0) == 0 and v.get("parameter_mmin", 0) == 0
            and 0 < v.get("parameter_mmax", 1) <= 2 and v.get("parameter_unitstyle", 1) == 1
            and "parameter_exponent" not in v)


# Live's Int parameters hold 256 values, 0-255 (Cycling '74, Device Parameters: "If you need an integer type that
# exceeds this range then instead set the type to Float, and change the unit style to Int")
INT_VALUES = 256
# a Live object's id, stored (a mapping): exact even if Live keeps a Float at 32-bit precision; ids stay far below
LIVE_ID_MAX = 2 ** 24 - 1


def stored_initial(v, value):
    """What to store as parameter_initial so that a control starts at `value` in Live: the value itself.

    Live starts a control at its stored initial value as is, knob curve (parameter_exponent) or not. From Sep 29 to
    Oct 8 the family stored the inverse of the curve here, on the belief that Live applied the curve once more (read
    from Tincture presets saved from Live 12.4); every curved knob then started below its design: the owner, Oct 8,
    on a probe, "cutoff is ... at 32.9Hz" (the 32.94 stored for 260 Hz) and Decay "22ms" (the 21.9 stored
    for 400 ms). A probe's template, saved from Live, had held its pads' starts exactly. Kept as a
    function so every build says where a start is stored."""
    return float(value)


def initial(v):
    """The value a control starts at in Live, from its saved attributes (valueof): the stored initial value."""
    return float((v.get("parameter_initial") or [0])[0])

class Patch:
    def __init__(self, width):
        self.width = width
        self.boxes = []
        self.lines = []
        self.parameters = {}
        # object id -> another: every patchline out of the first's outlet 0 leaves from the
        # second instead, except those into 'fk-' objects (lib/kit.py's follow puts itself
        # between a device's Root and Scale menus and wherever they go)
        self.reroute = {}
        self.files = {}         # name -> text: files packed inside the device (embed())

    def embed(self, name, text):
        """A file the device needs (a drawing script): packed inside the .amxd, which is then
        a frozen device (lib/frozen.py), so it travels with the device and needs no install."""
        assert self.files.get(name, text) == text, f"two different {name}"
        self.files[name] = text
        EMBEDDED[name] = text.encode("utf-8")

    def box(self, **attrs):
        if attrs.get("maxclass") == "live.text" and "textoncolor" in attrs:
            # live.text documents activetextoncolor, not textoncolor (live.tab has both)
            attrs.setdefault("activetextoncolor", attrs["textoncolor"])
            del attrs["textoncolor"]
        self.boxes.append({"box": attrs})
        return attrs["id"]

    def line(self, src, dst, outlet=0, inlet=0):
        self.lines.append({"patchline": {"source": [src, outlet], "destination": [dst, inlet]}})

    def panel(self, oid, rect, color, rounded=0, border=None, background=True):
        attrs = dict(
            id=oid, maxclass="panel", numinlets=1, numoutlets=0, bgcolor=color, bgfillcolor=color,
            rounded=rounded, patching_rect=[900, 700 + 12 * len(self.boxes), 10, 10],
            presentation=1, presentation_rect=rect,
        )
        if background:
            attrs.update(background=1)
        else:  # drawn in the foreground layer, above every background panel
            attrs.update(ignoreclick=1)
        if border:
            attrs.update(border=1, bordercolor=border)
        self.box(**attrs)

    def comment(self, oid, text, rect, color, size=8.5, bold=True, justify=0):
        attrs = dict(
            id=oid, maxclass="comment", text=text, numinlets=1, numoutlets=0,
            patching_rect=[700, 700 + 12 * len(self.boxes), rect[2], rect[3]],
            presentation=1, presentation_rect=rect, fontsize=size,
            textcolor=color, textjustification=justify,
        )
        if bold:
            attrs.update(fontface=1, fontname=FONT)
        self.box(**attrs)

    def param(self, oid, longname, shortname, valueof, **attrs):
        self.parameters[oid] = [longname, shortname, 0]
        valueof = dict(valueof)
        if level_knob(longname, valueof, attrs):
            valueof["parameter_exponent"] = LEVEL_CURVE
        if attrs.get("maxclass") == "live.numbox":
            # a number box shows its value as is in Live (Tincture Mini's Capture Length, Oct 1): no curve
            valueof.pop("parameter_exponent", None)
        if "parameter_initial" in valueof:
            valueof["parameter_initial"] = [stored_initial(valueof, valueof["parameter_initial"][0])]
        if attrs.get("maxclass") == "live.text" and len(valueof.get("parameter_enum", [])) == 2:
            # what Live and Push 3 call its two states: a live.text's own 'automation' and 'automationon'
            # labels (Cycling '74's reference), which default to "val1" and "val2" whatever the enum says
            attrs.setdefault("automation", valueof["parameter_enum"][0])
            attrs.setdefault("automationon", valueof["parameter_enum"][1])
        self.box(id=oid, parameter_enable=1,
                 saved_attribute_attributes={"valueof": dict(
                     parameter_longname=longname, parameter_shortname=shortname,
                     parameter_initial_enable=1, **valueof)},
                 **attrs)

    def stored(self, oid, longname, lo, hi, x, y=700, kind=0, varname=None, shortname=None, w=60, initial=0.0):
        """A value saved with the set that the user never sees: a hidden live.numbox
        (parameter_invisible 1: stored, not automatable, not on Push). Live gives it
        back when the set reopens, like any control, before the device's loadbang;
        a device that must not act on it until then gates it (kit.py's load gates).
        kind: 0 float, 1 int. initial: its value in a new set. Live's Int holds 256 values: a wider
        int is stored as a Float shown as an Int, as Cycling '74 advises (check() refuses a wide Int)."""
        style = {}
        if kind == 1 and hi - lo + 1 > INT_VALUES:
            kind, style = 0, dict(parameter_unitstyle=0)
        self.param(oid, longname, shortname or longname,
                   dict(parameter_type=kind, parameter_initial=[float(initial)], parameter_mmin=lo, parameter_mmax=hi,
                        parameter_invisible=1, **style),
                   maxclass="live.numbox", patching_rect=[x, y, w, 15],
                   varname=varname or oid.replace("-", "_"), numinlets=1, numoutlets=2, outlettype=["", "float"])

    def on_button(self, oid, longname, shortname, varname, rect, color, x, gen=True, initial=0.0):
        """Module ON switch. Tincture convention: the parameter is a Bypass, so
        the button reads ON (lit) when the parameter is off, OFF when on."""
        self.param(oid, longname, shortname,
                   dict(parameter_type=2, parameter_initial=[float(initial)], parameter_mmax=1,
                        parameter_enum=["off", "on"]),
                   maxclass="live.text", patching_rect=[x, 120, 28, 14],
                   presentation=1, presentation_rect=rect,
                   varname=varname, numinlets=1, numoutlets=2, outlettype=["", ""],
                   mode=1, text="ON", texton="OFF", rounded=7.0, fontname=FONT, fontsize=8.5,
                   bgcolor=color, activebgcolor=color, bgoncolor=BTN, activebgoncolor=BTN,
                   textcolor=INK, activetextcolor=INK,
                   activetextoncolor=MUTED, bordercolor=BORDER)
        if gen:
            self.to_gen(oid, varname, x)

    def capture(self, button_rect, len_rect, sec_rect, x, bars=False):
        """CAPTURE toggle, its length box (0.1-30 s) and the 'sec' label. bars=True: the label is a
        sec / bars switch instead ('Capture Unit'); in bars, the length is counted in bars of Live's
        tempo and time signature and sent to gen~ as seconds (at most 30, the buffer)."""
        self.param("cap", "Capture", "Capture",
                   dict(parameter_type=2, parameter_initial=[0.0], parameter_mmax=1,
                        parameter_enum=["off", "on"]),
                   maxclass="live.text", patching_rect=[x, 120, 90, 24],
                   presentation=1, presentation_rect=button_rect,
                   varname="cap_on", numinlets=1, numoutlets=2, outlettype=["", ""],
                   mode=1, text="CAPTURE", texton="CAPTURE", rounded=11.0,
                   fontname=FONT, fontsize=8.5, bgcolor=BTN, activebgcolor=BTN,
                   bgoncolor=AMBER, activebgoncolor=AMBER, textcolor=MUTED,
                   activetextcolor=MUTED, activetextoncolor=INK,
                   bordercolor=BORDER)
        self.to_gen("cap", "cap_on", x)
        self.param("caplen", "Capture Length", "Cap Len",
                   dict(parameter_type=0, parameter_initial=[2.0], parameter_mmin=0.1,
                        parameter_mmax=30, parameter_unitstyle=1, parameter_exponent=2.5),   # fine at the short end
                   maxclass="live.numbox", patching_rect=[x + 140, 120, 40, 15],
                   presentation=1, presentation_rect=len_rect,
                   varname="cap_len", numinlets=1, numoutlets=2, outlettype=["", "float"])
        if not bars:
            self.to_gen("caplen", "cap_len", x + 140)
            self.comment("sec", "sec", sec_rect, MUTED, size=7.5, bold=False, justify=1)
            return
        self.param("capunit", "Capture Unit", "Cap Unit",
                   dict(parameter_type=2, parameter_initial=[0.0], parameter_mmax=1,
                        parameter_enum=["sec", "bars"]),
                   maxclass="live.text", patching_rect=[x + 200, 120, 40, 15],
                   presentation=1, presentation_rect=sec_rect, varname="capunit",
                   numinlets=1, numoutlets=2, outlettype=["", ""], mode=1, text="sec", texton="bars",
                   rounded=6.0, fontname=FONT, fontsize=7.5, bgcolor=BTN, activebgcolor=BTN,
                   bgoncolor=BTN, activebgoncolor=BTN, textcolor=MUTED, activetextcolor=MUTED,
                   activetextoncolor=AMBER, bordercolor=BORDER)
        # length, unit, tempo, beats a bar, beat value -> seconds: bars of 4/4 at 120 BPM are 2 s each
        self.obj("cl-pak", "pak 0. 0 120. 4 4", 5, 1, x + 140, 200)
        self.line("caplen", "cl-pak", 0, 0)
        self.line("capunit", "cl-pak", 0, 1)
        self.obj("cl-sec", "expr $f1*(1-$i2)+min($f1*$i4*240./($i5*$f3),30.)*$i2", 1, 1, x + 140, 230)
        self.line("cl-pak", "cl-sec")
        self.obj("cl-p", "prepend cap_len", 1, 1, x + 140, 260)
        self.line("cl-sec", "cl-p")
        self.line("cl-p", "gen")
        self.obj("cl-td", "live.thisdevice", 1, 3, x + 300, 100)
        self.msg("cl-path", "path live_set", x + 300, 130)
        self.line("cl-td", "cl-path")
        self.obj("cl-lp", "live.path", 2, 3, x + 300, 160)
        self.line("cl-path", "cl-lp")
        self.obj("cl-ids", "t l l l", 1, 3, x + 300, 190)
        self.line("cl-lp", "cl-ids")
        for k, prop in enumerate(("tempo", "signature_numerator", "signature_denominator")):
            self.obj(f"cl-{k}", f"live.observer {prop}", 2, 2, x + 300 + 120 * k, 220)
            self.line("cl-ids", f"cl-{k}", k, 1)
            self.line(f"cl-{k}", "cl-pak", 0, 2 + k)

    def dial(self, oid, longname, shortname, varname, rect, color, x, valueof, extra=None,
             **attrs):
        self.param(oid, longname, shortname, {"parameter_type": 0, **valueof},
                   maxclass="live.dial", patching_rect=[x, 120, rect[2], rect[3]],
                   presentation=1, presentation_rect=rect,
                   varname=varname, numinlets=1, numoutlets=2, outlettype=["", "float"],
                   **attrs, dialcolor=DIAL, activedialcolor=color,
                   needlecolor=TEXT, activeneedlecolor=TEXT, textcolor=TEXT,
                   panelcolor=CLEAR)
        self.to_gen(oid, varname, x, extra)

    def obj(self, oid, text, ins, outs, x, y, outlettype=None):
        """A plain Max object box in the patching view."""
        return self.box(id=oid, maxclass="newobj", text=text, numinlets=ins, numoutlets=outs,
                        outlettype=outlettype if outlettype is not None else [""] * outs,
                        patching_rect=[x, y, max(40, 7 * len(text)), 22])

    def msg(self, oid, text, x, y):
        """A message box."""
        return self.box(id=oid, maxclass="message", text=text, numinlets=2, numoutlets=1,
                        outlettype=[""], patching_rect=[x, y, max(30, 7 * len(text)), 22])

    def again(self, oid, x, y):
        """What to bang to send control `oid`'s value again, unchanged: the control itself, but for a
        live.text switch a message 'outputvalue' into it. A bang flips a live.text (Cycling '74's
        reference: "A bang message will toggle the state of the object"); dials, menus, tabs and
        number boxes send their value again."""
        box = next(b["box"] for b in self.boxes if b["box"]["id"] == oid)
        if box.get("maxclass") != "live.text" or box.get("mode", 1) != 1:
            return oid
        mid = f"{oid}-again"
        if not any(b["box"]["id"] == mid for b in self.boxes):
            self.msg(mid, "outputvalue", x, y)
            self.line(mid, oid)
        return mid

    def to_gen(self, oid, name, x, extra=None):
        """Route a control into gen~ via 'prepend <name>' (optionally scaled first)."""
        src = oid
        if extra:
            sid = self.box(id=oid + "-s", maxclass="newobj", text=extra, numinlets=2,
                           numoutlets=1, outlettype=[""], patching_rect=[x, 170, 60, 22])
            self.line(src, sid)
            src = sid
        name = getattr(self, "gen_alias", {}).get(name, name)   # a Param named as a gen~ operator is renamed there
        pid = self.box(id=oid + "-p", maxclass="newobj", text="prepend " + name,
                       numinlets=1, numoutlets=1, outlettype=[""],
                       patching_rect=[x, 200, 110, 22])
        self.line(src, pid)
        self.line(pid, "gen")

    def audio(self, code, outs=2, plugin=True, ins=2):
        """plugin~ -> gen~ (holding the codebox) -> plugout~, stereo. outs > 2 adds gen~
        outlets 3.. for the caller to wire, ins > 2 inlets 3.. (in3 ..); plugin=False for an
        instrument (no audio in)."""
        if plugin:
            self.box(id="plugin", maxclass="newobj", text="plugin~", numinlets=2,
                     numoutlets=2, outlettype=["signal", "signal"], patching_rect=[40, 260, 60, 22])
        self.box(id="gen", maxclass="newobj", text="gen~", numinlets=ins, numoutlets=outs,
                 outlettype=["signal"] * outs, patching_rect=[40, 320, 400, 22],
                 patcher=gen_patcher(code, outs, ins))
        self.box(id="plugout", maxclass="newobj", text="plugout~", numinlets=2,
                 numoutlets=0, outlettype=[], patching_rect=[40, 380, 60, 22])
        if plugin:
            self.line("plugin", "gen", 0, 0)
            self.line("plugin", "gen", 1, 1)
        self.line("gen", "plugout", 0, 0)
        self.line("gen", "plugout", 1, 1)

    def logo(self, subtitle, sub_color, version, name="Tincture"):
        """The Tincture mark (four overlapping circles, which Live draws as rounded squares)
        at the top of a LOGO_W-wide strip at the left edge, the name under it one letter
        per line (the subtitle after it, in its colour), the version at the foot. Live's
        title bar already names the device, so the strip stays narrow. The mark is in the
        foreground layer so no background panel can cover it."""
        self.device_names = [f"{name} {subtitle.title()}", name] if subtitle else [name]
        d, step = 12, 7  # circle diameter, offset between circle centres
        x0 = 4 + (LOGO_W - (d + step)) / 2
        y0 = 8
        for i, (cx, cy, rgb) in enumerate(LOGO_CIRCLES):
            self.panel(f"logo-c{i}", [x0 + cx * step, y0 + cy * step, d, d],
                       rgb + [LOGO_ALPHA], rounded=d / 2, background=False)
        words = [(name.upper(), TEXT, "logo-name")] + ([(subtitle.upper(), sub_color, "logo-sub")] if subtitle else [])
        letters = sum(len(w.replace(" ", "")) + w.count(" ") * 0.5 for w, _, _ in words) + 0.5 * (len(words) - 1)
        lh = min(10.0, 112 / max(letters, 1))                # letter pitch: all of it fits above the version
        y = 34.0
        for w, color, oid in words:
            for j, ch in enumerate(w):
                if ch == " ":
                    y += lh / 2
                    continue
                self.comment(f"{oid}-{j}", ch, [4, round(y, 1), LOGO_W, 11], color, size=7.5, justify=1)
                y += lh
            y += lh / 2
        self.comment("version", version, [2, 152, LOGO_W + 4, 11], MUTED, size=6.5, bold=False, justify=1)

    def _sanitize_gen(self):
        """gen~'s own names out of the codebox (lib/genlint.py): a Param named like an operator
        becomes '<name>_p' there, and the 'prepend <name>' boxes feeding gen~ follow."""
        from genlint import sanitize
        gen = next((b["box"] for b in self.boxes if b["box"].get("id") == "gen" and "patcher" in b["box"]), None)
        if gen is None:
            return
        cb = gen["patcher"]["boxes"][2]["box"]
        cb["code"], renamed = sanitize(cb["code"])
        if not renamed:
            return
        into_gen = {ln["patchline"]["source"][0] for ln in self.lines if ln["patchline"]["destination"][0] == "gen"}
        for b in self.boxes:
            box = b["box"]
            words = box.get("text", "").split()
            if box.get("id") in into_gen and len(words) == 2 and words[0] == "prepend" and words[1] in renamed:
                box["text"] = f"prepend {renamed[words[1]]}"

    def annotate(self):
        """Info View text (lib/annotations.py), shown in Live when a control is hovered, on each control of the patch
        (patcher() does it; a probe moving its controls into a panel does it first, a probe)."""
        from annotations import ANNOTATIONS
        texts = next((ANNOTATIONS[n] for n in getattr(self, "device_names", []) if n in ANNOTATIONS), {})
        for b in self.boxes:
            box = b["box"]
            if box.get("parameter_enable"):
                long = box["saved_attribute_attributes"]["valueof"]["parameter_longname"]
                if long in texts:
                    box["annotation_name"] = long
                    box["annotation"] = texts[long]

    def patcher(self, banks, mpe=False):
        """mpe=True declares the device MPE-capable (Live then sends each note on its own channel)."""
        params = dict(self.parameters)
        params["parameterbanks"] = {
            str(i): {"index": i, "name": name, "parameters": names + ["-"] * (8 - len(names))}
            for i, (name, names) in enumerate(banks)
        }
        params["inherited_shortname"] = 1
        self.annotate()
        from annotations import DEVICE_INFO
        # by the full name only: another device isn't Mordant, nor Tincture Drive Tincture
        info = DEVICE_INFO.get((getattr(self, "device_names", None) or [None])[0])
        for ln in self.lines:
            src, dst = ln["patchline"]["source"], ln["patchline"]["destination"]
            if (src[0] in self.reroute and src[1] == 0 and not dst[0].startswith("fk-")
                    and dst[0] != self.reroute[src[0]]):
                ln["patchline"]["source"] = [self.reroute[src[0]], 0]
        # Live draws the box listed first on top, in each layer (the logo, checked in Live; the
        # a probe's background square, Sep 29). Panels are made back to front (the full-size
        # background first, then each card, then its stripe), so the background layer is listed
        # in reverse: the full-size panel last, at the back, where it can't cover the cards.
        back = [b for b in self.boxes if b["box"].get("background")]
        self.boxes[:] = list(reversed(back)) + [b for b in self.boxes if not b["box"].get("background")]
        # and Live shows its controls larger than a file may ask (lib/livesizes.py, measured in Live 12): of two
        # controls that then overlap, the lower is listed first, on top where it's drawn
        if getattr(self, "live_order", True):           # (a device may keep its order: a probe, Oct 20)
            from livesizes import live_order
            self.boxes[:] = live_order(self.boxes)
        if any(BLANK_PICTURE in (b["box"].get("pictures") or []) for b in self.boxes):
            self.embed(BLANK_PICTURE, BLANK_SVG)           # the tabs' blank pictures travel with the device
        self._sanitize_gen()
        out = {"patcher": {
            "fileversion": 1,
            "appversion": APPVERSION,
            "classnamespace": "box",
            "rect": [60, 80, 1000, 600],
            "openinpresentation": 1,
            "devicewidth": float(self.width),
            "default_fontsize": 10.0,
            "default_fontface": 0,
            "default_fontname": "Arial",
            "gridonopen": 1,
            "gridsize": [15.0, 15.0],
            "boxes": self.boxes,
            "lines": self.lines,
            "dependency_cache": [{"name": n, "bootpath": "~/devices/lib", "type": "TEXT", "implicit": 1}
                                 for n in sorted(self.files)],
            "latency": 0,
            "is_mpe": 1 if mpe else 0,
            # Live 12.1 retunes an MPE instrument to a loaded tuning system (per-note bend) when this
            # is on: the pitched synths ask for it (lib/panel.py's build(live_tuning=True))
            "external_mpe_tuning_enabled": 1 if getattr(self, "live_tuning", False) else 0,
            "minimum_live_version": "",
            "minimum_max_version": "",
            "platform_compatibility": 0,
            "autosave": 0,
            "parameters": params,
        }}
        if info:                    # the device's own Info text (lib/annotations.py's DEVICE_INFO)
            out["patcher"]["description"] = out["patcher"]["digest"] = info
        return out


def tempo(p, src, outlet, x, readout=None):
    """Live's tempo -> gen~ 'bpm' (and 'set N BPM' to the readout comment), started by a
    bang from src's outlet (the device's load trigger)."""
    p.msg("tp-path", "path live_set", x, 100)
    p.line(src, "tp-path", outlet, 0)
    p.obj("tp-lp", "live.path", 2, 3, x, 130)
    p.line("tp-path", "tp-lp")
    p.obj("tp-obs", "live.observer tempo", 2, 2, x, 160)
    p.line("tp-lp", "tp-obs", 0, 1)
    p.obj("tp-change", "change", 1, 1, x, 190)
    p.line("tp-obs", "tp-change")
    p.obj("tp-t", "t f f", 1, 2, x, 220)
    p.line("tp-change", "tp-t")
    p.obj("bpm-p", "prepend bpm", 1, 1, x, 250)
    p.line("tp-t", "bpm-p", 0, 0)
    p.line("bpm-p", "gen")
    if readout:
        p.obj("tp-int", "i", 2, 1, x + 100, 250)
        p.line("tp-t", "tp-int", 1, 0)
        p.msg("tp-show", "set $1 BPM", x + 100, 280)
        p.line("tp-int", "tp-show")
        p.line("tp-show", readout)


def gen_name(ids, oid):
    """The name a control reaches gen~ by: its 'prepend <name>' (Patch.to_gen, where a device's
    gen_alias renames a Param that shares a gen~ operator's name), else its varname. A control moved into the
    device's window ('<p box>::<id>') still has its 'prepend' on the device, under its own id."""
    b = ids.get(oid + "-p") or ids.get(oid.split("::")[-1] + "-p")
    if b and b.get("text", "").startswith("prepend "):
        return b["text"].split()[1]
    return ids[oid].get("varname")


def gen_patcher(code, outs=2, ins=2):
    """A gen~ patcher: in 1 .. in <ins> -> the codebox -> out 1 .. out <outs>. A cord only where the codebox has that
    inlet or outlet: as many as the in<n> and out<n> its code uses (Max deletes any other on load, saying "codebox:
    patchcord inlet out of range": a synth reads no audio in, the beta's console, Oct 18)."""
    used = re.sub(r"//[^\n]*", "", code)
    n_in = max([int(n) for n in re.findall(r"\bin(\d+)\b", used)] + [0])
    n_out = max([int(n) for n in re.findall(r"\bout(\d+)\b", used)] + [0])
    boxes = [
        {"box": {"id": "g-in1", "maxclass": "newobj", "text": "in 1",
                 "numinlets": 0, "numoutlets": 1, "outlettype": [""],
                 "patching_rect": [20, 20, 30, 22]}},
        {"box": {"id": "g-in2", "maxclass": "newobj", "text": "in 2",
                 "numinlets": 0, "numoutlets": 1, "outlettype": [""],
                 "patching_rect": [400, 20, 30, 22]}},
        {"box": {"id": "g-code", "maxclass": "codebox", "code": code,
                 "fontface": 0, "fontname": "<Monospaced>", "fontsize": 12.0,
                 "numinlets": 2, "numoutlets": outs, "outlettype": [""] * outs,
                 "patching_rect": [20, 60, 600, 440]}},
    ]
    lines = [{"patchline": {"source": [f"g-in{k}", 0], "destination": ["g-code", k - 1]}} for k in (1, 2) if k <= n_in]
    for k in range(3, ins + 1):
        boxes.append({"box": {"id": f"g-in{k}", "maxclass": "newobj", "text": f"in {k}", "numinlets": 0,
                              "numoutlets": 1, "outlettype": [""], "patching_rect": [400 + 120 * (k - 2), 20, 30, 22]}})
        if k <= n_in:
            lines.append({"patchline": {"source": [f"g-in{k}", 0], "destination": ["g-code", k - 1]}})
    boxes[2]["box"]["numinlets"] = max(2, ins)
    for k in range(outs):
        boxes.append({"box": {"id": f"g-out{k + 1}", "maxclass": "newobj", "text": f"out {k + 1}",
                              "numinlets": 1, "numoutlets": 0,
                              "patching_rect": [[20, 400][k] if k < 2 else 400 + 120 * (k - 1), 520, 36, 22]}})
        if k < n_out:
            lines.append({"patchline": {"source": ["g-code", k], "destination": [f"g-out{k + 1}", 0]}})
    return {
        "fileversion": 1,
        "appversion": APPVERSION,
        "classnamespace": "dsp.gen",
        "rect": [100, 100, 700, 600],
        "boxes": boxes,
        "lines": lines,
    }


AUDIO_EFFECT, MIDI_EFFECT, INSTRUMENT = b"aaaa", b"mmmm", b"iiii"
# a picture of nothing, for a live.tab laid over its drawing (lib/panelg.py's BLANK_TABS): Live 12 Beta draws a switched-off
# device's live.tab text itself, whatever its colours (another device, Oct 25; a probe: only the tab did)
BLANK_PICTURE = "dyehouse-blank.svg"
BLANK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="none"/></svg>\n'


# the files Patch.embed() was given, by name (a build packs the ones its patcher lists)
EMBEDDED = {}
# the packed files' date (a Mac time): fixed, so a rebuild with nothing changed gives the same bytes
MDAT = frozen.MAC_EPOCH + 1790640000         # Sep 29, 2026


def pack_amxd(patch, kind=AUDIO_EFFECT, name="device.amxd"):
    """Wrap patcher JSON in the Max for Live device container; frozen (lib/frozen.py), with
    the files it lists in dependency_cache inside it, when it has any."""
    body = json.dumps(patch, indent="\t").encode("utf-8") + b"\x00"
    deps = patch["patcher"].get("dependency_cache", [])
    if deps:
        files = [frozen.File(name, body, "JSON", frozen.MAIN_FLAG, mdat=MDAT)]
        files += [frozen.File(d["name"], EMBEDDED[d["name"]], d["type"], mdat=MDAT) for d in deps]
        return frozen.pack(kind, files)
    return (b"ampf" + struct.pack("<I", 4) + kind
            + b"meta" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
            + b"ptch" + struct.pack("<I", len(body)) + body)


def read_embedded(path):
    """The files packed inside a frozen device, by name (its own patcher left out)."""
    data = path.read_bytes()
    if not frozen.is_frozen(data):
        return {}
    return {f.name: f.data for f in frozen.parse(data)[2] if f.flag != frozen.MAIN_FLAG}


def read_amxd(path):
    data = path.read_bytes()
    assert data[:4] == b"ampf" and data[8:12] in (AUDIO_EFFECT, MIDI_EFFECT, INSTRUMENT), "bad header"
    if frozen.is_frozen(data):
        main = next(f for f in frozen.parse(data)[2] if f.flag == frozen.MAIN_FLAG)
        assert main.data[-1:] == b"\x00", "missing NUL terminator"
        return json.loads(main.data[:-1])["patcher"]
    assert data[24:28] == b"ptch", "missing ptch chunk"
    (size,) = struct.unpack("<I", data[28:32])
    assert size == len(data) - 32, "ptch length mismatch"
    assert data[-1:] == b"\x00", "missing NUL terminator"
    return json.loads(data[32:-1])["patcher"]


def gen_code(patcher):
    ids = {b["box"]["id"]: b["box"] for b in patcher["boxes"]}
    return ids["gen"]["patcher"]["boxes"][2]["box"]["code"]


def sends_bang(box, outlet):
    """Whether this outlet sends a bang: a trigger's b, a button, live.thisdevice's left outlet,
    loadbang, uzi's left outlet, delay, metro, a select's matching outlets."""
    if box.get("maxclass") in ("button", "live.button"):
        return True
    words = box.get("text", "").split() if box.get("maxclass") == "newobj" else []
    if not words:
        return False
    head, args = words[0], words[1:]
    if head in ("t", "trigger"):
        return outlet < len(args) and args[outlet] in ("b", "bang")
    if head in ("sel", "select"):
        return outlet < max(1, len(args))
    return (head in ("live.thisdevice", "uzi") and outlet == 0) or head in ("loadbang", "delay", "del", "metro")


def flat(patcher, prefix=""):
    """A patcher's boxes and lines with each subpatcher's ('p name': a device's own window; an embedded bpatcher)
    among them, their ids prefixed '<p box's id>::', as Max lists a subpatcher's parameters."""
    boxes, lines = [], []
    for b in patcher["boxes"]:
        box = dict(b["box"], id=prefix + b["box"]["id"])
        boxes.append({"box": box})
        if "patcher" in box and (box.get("maxclass") == "bpatcher"
                                 or box.get("maxclass") == "newobj" and box.get("text", "").split()[:1] == ["p"]):
            ib, il = flat(box["patcher"], box["id"] + "::")
            boxes += ib
            lines += il
    for ln in patcher["lines"]:
        s, d = ln["patchline"]["source"], ln["patchline"]["destination"]
        lines.append({"patchline": {"source": [prefix + s[0], s[1]], "destination": [prefix + d[0], d[1]]}})
    return boxes, lines


def check(path, width, gen=True, internal=(), strict=None, ui_only=(), scripted=(), fixed=()):
    """Structural checks on a built device; returns (boxes, lines).
    gen=False for devices without a gen~ codebox (message-domain devices).
    With gen, every UI parameter must be a gen Param and vice versa, except the
    `internal` Params the patch sets itself (another device's tempo), and except the `ui_only`
    parameters (by box id) that stay in the patch (another device's MAP buttons and mapping ids). `scripted`: internal
    Params a script in the patch sets by name, without a 'prepend' (a probe's EXPRESSION fold).
    `fixed`: Params nothing sets, so they play at their defaults (a probe: the pressure's feel, another device's since
    v0.51, in the DVNA code it keeps).
    strict (the default without gen): no fan-out, so every outlet feeds at most one
    inlet unless it belongs to a trigger and message order never depends on patch
    layout; and no $n glued to other text in message boxes. A subpatcher's boxes (the device's own window) are
    checked with the device's, but placed in its own window, not on the panel."""
    strict = (not gen) if strict is None else strict
    p = read_amxd(path)
    top = {b["box"]["id"] for b in p["boxes"]}
    boxes, lines = flat(p)
    p = dict(p, boxes=boxes, lines=lines)
    ids = {b["box"]["id"]: b["box"] for b in p["boxes"]}
    assert len(ids) == len(p["boxes"]), "duplicate box ids"
    entries = {k for k, e in p.get("parameters", {}).items() if isinstance(e, list)}
    enabled = {oid for oid, b in ids.items() if b.get("parameter_enable")}
    assert entries == enabled, ("the parameter table and the controls disagree (a probe-v0.38: 'pview' "
                                f"moved into its window under its old name): entries for no control {sorted(entries - enabled)[:5]}, "
                                f"controls without an entry {sorted(enabled - entries)[:5]}")
    wide = [oid for oid, b in ids.items() if b.get("text", "").startswith(("expr ", "vexpr "))
            and max(map(int, re.findall(r"\$[if](\d+)", b["text"])), default=0) > 9]
    assert not wide, f"expr with more than nine inputs, which Max refuses (Weld Kit's mask, Oct 18): {wide}"
    for oid, b in ids.items():        # a switch's states named in Live and on Push 3, not "val1" / "val2"
        if b.get("maxclass") == "live.text" and b.get("parameter_enable"):
            assert b.get("automation") and b.get("automationon") and "val1" not in (b["automation"], b["automationon"]), \
                f"{oid}: a live.text without 'automation' / 'automationon' shows its states as val1 / val2"
    for oid, b in ids.items():        # Live's Int holds 256 values (0-255): a wider one loses what it stores
        v = b.get("saved_attribute_attributes", {}).get("valueof", {})
        if v.get("parameter_type") == 1:
            n = v.get("parameter_mmax", 127) - v.get("parameter_mmin", 0) + 1
            assert n <= INT_VALUES, f"{oid}: an Int parameter of {n} values; Live's hold {INT_VALUES} (store it as a Float)"
    for b in ids.values():
        # a Python format placeholder that never got filled in
        assert not re.search(r"\{[A-Za-z_]", b.get("text", "")), f"{b['id']}: unformatted {{...}} in text"
    for ln in p["lines"]:
        s, d = ln["patchline"]["source"], ln["patchline"]["destination"]
        assert s[0] in ids and d[0] in ids, f"dangling line {s} -> {d}"
        assert s[1] < ids[s[0]]["numoutlets"], f"bad outlet {s}"
        assert d[1] < ids[d[0]]["numinlets"], f"bad inlet {d}"
        tb = ids[d[0]]   # (live.text labels checked below)
        assert not (tb.get("maxclass") == "live.text" and tb.get("mode", 1) == 1 and d[1] == 0
                    and sends_bang(ids[s[0]], s[1])), \
            f"{s[0]} bangs the switch {d[0]}: a bang flips a live.text; send it 'outputvalue' (Patch.again)"

    if gen:
        code = gen_code(p)
        from genlint import misused
        assert not misused(code), f"gen~'s own names used as variables (lib/genlint.py): {misused(code)}"
        from genlint import too_deep
        assert not too_deep(code), f"parentheses nested too deep for gen~ (lib/genlint.py): {too_deep(code)[:5]}"
        from genlint import long_chains
        assert not long_chains(code), f"'else if' chains too long for gen~ (lib/genlint.py): {long_chains(code)[:5]}"
        from genlint import undefined
        assert not undefined(code), f"names gen~ reads but never sets (lib/genlint.py): {undefined(code)[:5]}"
        gen_params = set(re.findall(r"^Param (\w+)\(", code, re.M))
        # hidden parameters (parameter_invisible 2: display only, e.g. Another device's engine buttons)
        hidden = {oid for oid, b in ids.items()
                  if b.get("saved_attribute_attributes", {}).get("valueof", {}).get("parameter_invisible") == 2}
        hidden |= set(ui_only)
        ui = {gen_name(ids, oid) for oid, b in ids.items() if b.get("parameter_enable") and oid not in hidden}
        assert ui == gen_params - set(internal) - set(fixed), f"UI {sorted(ui)} != gen Params {sorted(gen_params)}"
        assert not set(fixed) & ui and set(fixed) <= gen_params, f"fixed Params: {sorted(fixed)}"
        texts = {x.get("text") for x in ids.values()}
        for oid, b in ids.items():
            if b.get("parameter_enable") and oid not in hidden:
                assert f"prepend {gen_name(ids, oid)}" in texts, b["varname"]
        for name in internal:
            assert name in scripted or f"prepend {name}" in texts, name
    if strict:
        fan = {}
        for ln in p["lines"]:
            src = tuple(ln["patchline"]["source"])
            fan[src] = fan.get(src, 0) + 1
        for (oid, outlet), n in fan.items():
            is_trigger = ids[oid].get("text", "").split()[:1] in (["t"], ["trigger"])
            assert n == 1 or is_trigger, f"{oid} outlet {outlet} fans out to {n} inlets; use a trigger"
        for b in ids.values():
            # Max substitutes $1..$9 only as whole words: "$1-bar" or "slot$2" stay literal
            if b["maxclass"] == "message":
                assert not re.search(r"\$\d\S|\S\$\d", b["text"]), f"{b['id']}: $n glued to text"

    params = p["parameters"]
    longnames = [v[0] for k, v in params.items() if k in ids]
    assert len(set(longnames)) == len(longnames), "duplicate parameter long names"
    for bank in params["parameterbanks"].values():
        assert len(bank["parameters"]) == 8, bank["name"]
        for name in bank["parameters"]:
            assert name == "-" or name in longnames, f"unknown bank parameter {name}"

    for b in ids.values():
        if "presentation_rect" in b and b["id"] in top:
            x, y, w, h = b["presentation_rect"]
            assert x >= 0 and y >= 0 and x + w <= width and y + h <= HEIGHT, b["id"]
    return len(ids), len(p["lines"])


# ---------------------------------------------------------------- Info View text on every shown part (backlog E28)
INFO_LAYERS = ("jsui", "live.text", "live.tab", "umenu", "live.drop", "live.menu", "live.numbox", "live.dial",
               "live.slider", "live.toggle", "live.button")


def info_everywhere(patcher, texts, description, name):
    """Every part the panel shows given Info View text, as Live shows it at the bottom left when the part is hovered
    (Oct 21: a drawing showed "jsui", a page tab "live.text"). In order: a control's own text (lib/annotations.py,
    then `texts` by its long name, or a part's by its scripting name); a drawing or button laid over a control, that
    control's text (the value columns and screens are drawings with Live's control over them); anything else, the
    labels and cards included, the device's description, under its name. `patcher`: {"patcher": ...}, changed in
    place and returned. A control left without its own text is refused (a new control can't ship silent)."""
    from annotations import SHOWN_PATTERNS as patterns
    top = patcher["patcher"]["boxes"]

    def rect(b):
        return b.get("presentation_rect") or [0, 0, 0, 0]

    def overlap(a, b):
        ax, ay, aw, ah = rect(a)
        bx, by, bw, bh = rect(b)
        w, h = min(ax + aw, bx + bw) - max(ax, bx), min(ay + ah, by + bh) - max(ay, by)
        return w * h if w > 0 and h > 0 else 0.0

    def long(b):
        return b.get("saved_attribute_attributes", {}).get("valueof", {}).get("parameter_longname")

    def give(box, title, text):                          # (annotation_name is Live's controls' own: Max's reference
        box["annotation"] = text                          # gives it to no other class)
        if box.get("maxclass", "").startswith("live."):
            box["annotation_name"] = title

    missing = []
    shown = [b["box"] for b in top if b["box"].get("presentation")]
    for box in shown:                                     # the controls first: their own text
        if box.get("parameter_enable") and not box.get("annotation"):
            n = long(box)
            if n in texts:
                box["annotation_name"], box["annotation"] = n, texts[n]
            else:
                missing.append(n)
    assert not missing, f"{name}: controls without Info View text (lib/annotations.py SHOWN): {missing}"
    controls = [b for b in shown if b.get("parameter_enable") and b.get("annotation")]
    for box in shown:
        if box.get("annotation"):
            continue
        v = box.get("varname")
        if v and v in texts:
            give(box, box.get("annotation_name") or name, texts[v])
            continue
        hit = next((t for pat, t in patterns if v and re.search(pat, v)), None)
        if hit:
            give(box, name, hit)
            continue
        under = None
        if box.get("maxclass") in INFO_LAYERS:              # a drawing that is one control's face: that control
            area = rect(box)[2] * rect(box)[3]               # covers at least half of it, and no other one does
            over = [c for c in controls if area and overlap(box, c) >= 0.5 * area]
            if len(over) == 1:
                under = over[0]
        if under is not None:
            give(box, under["annotation_name"], under["annotation"])
        else:
            give(box, name, description)
    return dials_on_values(patcher)                       # (after: a drawing takes its text by the column's rect)


def dials_on_values(patcher):
    """Every dial laid transparent over a column taller than Live shows it moved onto the column's bottom, where the
    columns draw the value and its bar (backlog E39): Live shows a bare live.dial 28 high whatever its rect
    (lib/livesizes.py), so left at the column's top it took the drag on the word and the number's top only, and the
    bar under it did nothing (Tincture 2's FOLLOW, the owner, Oct 21: fixed there first, in v2.0.1, and checked in
    Live). A dial that already fits stays where it is, so running it twice changes nothing. Subpatchers too.
    `patcher`: {"patcher": ...}, changed in place and returned."""
    from livesizes import live_size

    def walk(boxes):
        for b in boxes:
            box = b["box"]
            r, tc = box.get("presentation_rect"), box.get("textcolor") or []
            if box.get("maxclass") == "live.dial" and r and len(tc) == 4 and tc[3] == 0:
                lh = live_size(box)[1]
                if r[3] > lh + 0.5:
                    box["presentation_rect"] = [r[0], round(r[1] + r[3] - lh, 2), r[2], lh]
            if isinstance(box.get("patcher"), dict):
                walk(box["patcher"].get("boxes", []))
    walk(patcher["patcher"]["boxes"])
    return patcher


def without_info(path_or_patcher):
    """The parts a panel shows with no Info View text: [(maxclass, scripting name or id)] (tests/test_info_view.py)."""
    p = read_amxd(path_or_patcher) if not isinstance(path_or_patcher, dict) else path_or_patcher
    return [(b["box"]["maxclass"], b["box"].get("varname") or b["box"]["id"]) for b in p["boxes"]
            if b["box"].get("presentation") and not b["box"].get("annotation")]


def everywhere(patcher, name):
    """info_everywhere with the device's own texts and description (lib/annotations.py SHOWN and DEVICE_INFO)."""
    from annotations import DEVICE_INFO, SHOWN
    texts = SHOWN.get(name, {})
    description = DEVICE_INFO.get(name) or texts.get("_device") or patcher["patcher"].get("description")
    assert description, f"{name}: no description for the parts with no text of their own (lib/annotations.py)"
    return info_everywhere(patcher, texts, description, name)
