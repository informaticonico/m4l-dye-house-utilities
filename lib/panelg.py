"""Panel G's shared pieces (the probes' panel: screens and value columns, every value one of Live's own controls laid
transparent over its drawing, so Push, automation, Racks and Live's LFO Map reach each; plans/labs/logwood-probe.md,
G). Taken from a probe, which uses them from here, so a
device moving to the probes' panel reuses them rather than copying them. No word under 7 px (WORD), the probes'
readability rule. The scripts are ES5 for Max's jsui (lib/visual.py's HEAD) and draw only.

    OVERLAY, lay()     what each of Live's controls draws, and a control laid transparent over its drawing (still
                       Live's own: a click selects it, so it maps)
    feed()             a control's value to a script, 'v <control> <value>' (lib/visual.py's tap: the control keeps
                       its own lines)
    columns_script()   values as columns: the word inverted in the colour, the value large, its unit small, a bar
                       filled to it; a value that does nothing now drawn pale
    tabs_script()      tabs drawn (a live.tab lies over them, transparent): the one shown lit in its colour

The Dye House Utilities' panels (Oct 15, plans/ideas/utilities-panels.md) added, each new (nothing above changed):

    text(), card(), screen()   a word placed by its baseline (never under WORD), a card with its stripe and title, a
                       dark screen: the mockups' pieces as Max boxes
    cable_tab()        the family cable selector, A · B · C · D: one live.tab (Live's own menu parameter) laid
                       transparent over segments_script()'s drawing, its label pill over the segments, the chosen one
                       filled (Warp and Weft; the probes' cable choices can take it, Off first, as they're rebuilt)
"""

import json

from m4l import BG, BORDER, CARD, CLEAR, FONT, INK, MUTED, TEXT
from visual import HEAD, SCREEN, rgba, tap

WORD = 7                     # the smallest word drawn (Live's 100 %)
OVERLAY = {                  # what each of Live's controls draws, made transparent
    "live.dial": ["activedialcolor", "activefgdialcolor", "activeneedlecolor", "bordercolor", "dialcolor",
                  "fgdialcolor", "focusbordercolor", "needlecolor", "panelcolor", "textcolor", "tricolor"],
    "live.menu": ["activebgcolor", "bordercolor", "focusbordercolor", "inactivelcdcolor", "lcdbgcolor", "lcdcolor",
                  "textcolor", "tricolor"],
    "live.text": ["activebgcolor", "activebgoncolor", "activetextcolor", "activetextoncolor", "bgcolor", "bgoncolor",
                  "bordercolor", "focusbordercolor", "textcolor", "textoffcolor"],
    "live.numbox": ["activebgcolor", "activeslidercolor", "activetricolor", "activetricolor2", "bordercolor",
                    "focusbordercolor", "inactivelcdcolor", "lcdbgcolor", "lcdcolor", "textcolor", "tricolor", "tricolor2"],
    "live.tab": ["activebgcolor", "activebgoncolor", "activetextcolor", "activetextoncolor", "bgcolor", "bgoncolor",
                 "bordercolor", "focusbordercolor", "textcolor", "textoncolor"],
}


TAB_ROW = 1.34       # a blank tab's font at most its row's height / this: measured on four 10 px rows only (the Ghost
                     # a probe, Oct 25: 9 pt left the last out of reach, 7.5 and 6 pt didn't). Not a general rule: Tincture
                     # 2's eight 6.8 px rows at 8.5 pt take every click (the owner)
BLANK_TABS = False   # a device's build sets True (other devices, Oct 25); the devices on sale keep their text until
                     # their own fix (the owner: "2")


def lay(box, rect=None):
    """A control (its box) laid transparent over its drawing, at rect if given: still Live's own control, so Push,
    automation, a Rack's macros and Live's LFO Map reach it, and a click selects it."""
    if rect is not None:
        box["presentation"] = 1
        box["presentation_rect"] = [round(v, 2) for v in rect]
    from livesizes import on_value_row
    on_value_row(box)                                 # a menu or number on its value row (a tester, Oct 21)
    for attr in OVERLAY[box["maxclass"]]:
        box[attr] = list(CLEAR)
    if box["maxclass"] == "live.dial":
        box.update(showname=0, shownumber=0)
    if box["maxclass"] == "live.tab" and BLANK_TABS:
        # a picture of nothing for each item, so a switched-off device shows only its drawing (Live 12 Beta draws a
        # tab's text itself then, whatever its colours: a probe, Oct 25); the names stay the parameter's
        from m4l import BLANK_PICTURE
        n = len(box["saved_attribute_attributes"]["valueof"]["parameter_enum"])
        box.update(usepicture=1, pictures=[BLANK_PICTURE] * n)
        # and its font small enough for its rows (another device's Warble was out of reach at 9 pt, Oct 25: a probe's
        # G-J); its text isn't shown, so this costs nothing
        rows = box.get("num_lines_presentation") or 1
        box["fontsize"] = min(box.get("fontsize", 10.0), round(box["presentation_rect"][3] / rows / TAB_ROW - 0.05, 1))
    return box


def feed(p, oid, var, dest, x, y=1500):
    """A control's value to a script as 'v <var> <value>' (tap: the control keeps its own lines)."""
    tap(p, oid, x, y)
    pid = f"{dest}-v-{var}"
    p.obj(pid, f"prepend v {var}", 1, 1, x, y + 40)
    p.line(oid, pid)
    p.line(pid, dest)


# the columns, as tools/sketches/madder_probe.py draws them (column())
COLUMNS = """
function v(name, x) { VAL[String(name)] = Number(x); mgraphics.redraw(); }
function get(name, d) { return VAL.hasOwnProperty(name) ? VAL[name] : d; }
function clampf(x, a, b) { return Math.max(a, Math.min(b, x)); }

function holds(cs) {
	for (var k = 0; k < cs.length; k++) if (cs[k][1].indexOf(Math.round(get(cs[k][0], cs[k][2]))) < 0) return false;
	return true;
}

// the value as the column shows it, and its unit
function fmt(it, x) {
	if (it.f == "seed") return [String(Math.round(seedOf(it))), ""];
	if (it.f == "menu") return [String(it.items[clampf(Math.round(x), 0, it.items.length - 1)]), ""];
	if (it.f == "pct") return [String(Math.round(x * 100)), "%"];
	if (it.f == "f2") return [x.toFixed(2), ""];
	if (it.f == "s100") { var r = Math.round(x * 100); return [(r > 0 ? "+" : "") + r, ""]; }
	return [String(Math.round(x)), ""];
}

// SEED (v0.5): the seed playing while the card is free, its Seed while locked
function locked(it) { return it.lock && get(it.lock, 0) > 0.5; }
function seedOf(it) { return locked(it) ? get(it.v, it.d) : get(it.run, get(it.v, it.d)); }

function word(x, y, s, size, c, anchor) {
	mgraphics.select_font_face(FONTN);
	mgraphics.set_font_size(size);
	var tw = mgraphics.text_measure(s)[0];
	mgraphics.set_source_rgba(c);
	mgraphics.move_to(anchor == 1 ? x - tw / 2 : x, y);
	mgraphics.show_text(s);
	return tw;
}

// the largest size up to `size` (never under WORD) at which s fits in w
function fit(s, size, w) {
	mgraphics.select_font_face(FONTN);
	mgraphics.set_font_size(size);
	var tw = mgraphics.text_measure(s)[0];
	return Math.max(WORD, tw > w ? size * w / tw : size);
}

function bar(x, y, w, h, it, val) {
	mgraphics.set_source_rgba(C);
	if (it.f == "seed") {
		// LOCK: a closed bar while it holds; free, open ends (the seeds move on)
		mgraphics.set_line_width(0.8);
		if (locked(it)) { mgraphics.rectangle(x, y, w, h); mgraphics.fill(); }
		else { for (var d = x; d < x + w; d += 2.2) { mgraphics.rectangle(d, y + 0.2, 0.6, 0.6); mgraphics.rectangle(d, y + h - 0.8, 0.6, 0.6); } mgraphics.fill(); }
		return;
	}
	mgraphics.set_line_width(0.8);
	if (it.f == "menu") {
		// a choice: dotted, the chosen one filled
		var n = it.items.length, seg = w / n;
		for (var d = x; d < x + w; d += 2.2) { mgraphics.rectangle(d, y + 0.2, 0.6, 0.6); mgraphics.rectangle(d, y + h - 0.8, 0.6, 0.6); }
		mgraphics.fill();
		mgraphics.rectangle(x + seg * clampf(Math.round(val), 0, n - 1), y, seg, h);
		mgraphics.fill();
		return;
	}
	mgraphics.rectangle(x + 0.4, y + 0.4, w - 0.8, h - 0.8);
	mgraphics.stroke();
	var f = clampf((val - it.lo) / (it.hi - it.lo), 0, 1);
	if (it.e) f = Math.pow(f, 1 / it.e);          // where a knob would stand (Live's curve: Level's)
	if (it.lo < 0 && it.hi > 0) {
		// both ways: filled from the centre, the centre marked
		var a = Math.min(0.5, f), b = Math.max(0.5, f);
		mgraphics.rectangle(x + w * a, y, Math.max(w * (b - a), 0.8), h);
		mgraphics.fill();
		mgraphics.set_source_rgba(TXT);
		mgraphics.set_line_width(0.7);
		mgraphics.move_to(x + w / 2, y - 1.2);
		mgraphics.line_to(x + w / 2, y + h + 1.2);
		mgraphics.stroke();
	} else {
		mgraphics.rectangle(x, y, w * f, h);
		mgraphics.fill();
	}
}

function paint() {
	var w = mgraphics.size[0], h = mgraphics.size[1], n = ITEMS.length, cw = w / n;
	for (var i = 0; i < n; i++) {
		var it = ITEMS[i], x = i * cw, val = get(it.v, it.d), pair = fmt(it, val), lw = cw - 2;
		// the word, inverted in the colour
		var lab = it.f == "seed" && locked(it) ? "LOCK" : it.l;
		mgraphics.set_source_rgba(C);
		mgraphics.rectangle_rounded(x + 1, 0, lw, 9.5, 3, 3);
		if (it.f == "seed" && !locked(it)) {
			// SEED free: the word outlined, LOCK filled when it holds
			mgraphics.set_line_width(0.8);
			mgraphics.stroke();
			word(x + 1 + lw / 2, 7.6, lab, fit(lab, WORD, lw - 2), C, 1);
		} else {
			mgraphics.fill();
			word(x + 1 + lw / 2, 7.6, lab, fit(lab, WORD, lw - 2), INKC, 1);
		}
		// the value large, its unit small after it
		mgraphics.select_font_face(FONTN);
		mgraphics.set_font_size(WORD);
		var uw = pair[1] ? mgraphics.text_measure(pair[1])[0] + 1 : 0;
		var vs = fit(pair[0], pair[0].length <= 4 ? 9.5 : 8, cw - 4 - uw);
		mgraphics.set_font_size(vs);
		var tw = mgraphics.text_measure(pair[0])[0], vy = 9.5 + (h - 15) / 2 + vs * 0.4, x0 = x + (cw - tw - uw) / 2;
		word(x0, vy, pair[0], vs, TXT, 0);
		if (pair[1]) word(x0 + tw + 1, vy, pair[1], WORD, DIMT, 0);
		bar(x + 2, h - 5, cw - 4, 4, it, val);
		if (it.when && !holds(it.when)) {
			// it does nothing now (its card is off): pale, the card's ground over it
			mgraphics.set_source_rgba(CELL[0], CELL[1], CELL[2], PALE);
			mgraphics.rectangle(x, 0, cw, h);
			mgraphics.fill();
		}
	}
}

// for the tests: each column's value as shown, and whether it is pale
function values() {
	var out = [];
	for (var i = 0; i < ITEMS.length; i++) {
		var it = ITEMS[i];
		out.push([it.v, fmt(it, get(it.v, it.d)).join(""), it.when && !holds(it.when) ? 1 : 0]);
	}
	return out;
}
"""
PALE = 0.6

# the hooks a device may ask of columns_script (each replaces one piece of COLUMNS; none asked: COLUMNS as it is)
_FMT_END = '\treturn [String(Math.round(x)), ""];\n}\n\n// SEED'
_MENU_BAR = ('\tif (it.f == "menu") {\n\t\t// a choice: dotted, the chosen one filled\n\t\tvar n = it.items.length, '
             'seg = w / n;')
_MENU_AT = "mgraphics.rectangle(x + seg * clampf(Math.round(val), 0, n - 1), y, seg, h);"
_VALUE_SIZE = "pair[0].length <= 4 ? 9.5 : 8"


def columns_script(title, color, items, source="lib/panelg.py", formats="", steps=False, value_size=None):
    """Values as columns: items [{v, l, f (pct, f2, s100, menu; more in formats), lo, hi, d, items, when, e}], each
    as wide. Messages: v <control> <value>. formats: more of fmt()'s lines (JS, before its default), as
    'if (it.f == "s1") return [x.toFixed(1), "s"];'. steps: f "step", a whole number lo..hi with a choice's bar (a
    segment a value). value_size: the value's size when short (9.5 if not given)."""
    text = COLUMNS
    if formats:
        assert text.count(_FMT_END) == 1
        text = text.replace(_FMT_END, "\t" + formats.strip() + "\n" + _FMT_END)
    if steps:
        assert text.count(_MENU_BAR) == 1 and text.count(_MENU_AT) == 1
        text = text.replace(_MENU_BAR, '\tif (it.f == "menu" || it.f == "step") {\n\t\t// a choice: dotted, the chosen '
                            'one filled (a step: one of lo..hi)\n\t\tvar st = it.f == "step", n = st ? it.hi - it.lo + 1 '
                            ': it.items.length, seg = w / n;')
        text = text.replace(_MENU_AT, "mgraphics.rectangle(x + seg * clampf(Math.round(val) - (st ? it.lo : 0), 0, "
                            "n - 1), y, seg, h);")
    if value_size is not None:
        assert text.count(_VALUE_SIZE) == 1
        text = text.replace(_VALUE_SIZE, f"pair[0].length <= 4 ? {value_size:g} : {value_size - 1.5:g}")
    return f"""// {title}: its values as columns. Generated by {source}; edit that, not this.
// Messages: v <control> <value>. Draws only (Live's controls lie over it).
{HEAD}
var C = {rgba(color)}, TXT = {rgba(TEXT)}, DIMT = {rgba(MUTED)}, INKC = {rgba(INK)}, CELL = {rgba(CARD)};
var WORD = {WORD}, PALE = {PALE}, FONTN = "{FONT}";
var ITEMS = {json.dumps(items)}, VAL = {{}};
for (var i0 = 0; i0 < ITEMS.length; i0++) VAL[ITEMS[i0].v] = ITEMS[i0].d;
{text}"""


def tabs_script(title, names, colors, tabs_w, gap=3, size=7.5):
    """Tabs drawn, tabs_w across from the left in equal cells gap apart (as a live.tab with spacing_x gap lies over
    them, transparent, so a click is Live's): the one shown its card's ground, edged and topped in its colour, the
    others the panel's. Messages: page <k>. The rest of the box is the device's to draw (after()): its script's
    function after(w, h), if it has one."""
    return f"""// {title}: the tabs. Generated by lib/panelg.py; edit that, not this.
// Messages: page <k>. Draws only (Live's live.tab lies over the tabs).
{HEAD}
var NAMES = {json.dumps(list(names))}, COLS = [{", ".join(rgba(c) for c in colors)}], TABSW = {tabs_w}, GAP = {gap};
var CELL = {rgba(CARD)}, GROUND = {rgba(BG)}, EDGE = {rgba(BORDER)}, TXT = {rgba(TEXT)}, DIMT = {rgba(MUTED)};
var INKC = {rgba(INK)}, SCREENC = {rgba(SCREEN)}, WORD = {WORD}, FONTN = "{FONT}", PAGE = 0, VAL = {{}};

function page(k) {{ PAGE = Math.max(0, Math.min(NAMES.length - 1, Math.round(Number(k)))); mgraphics.redraw(); }}
function v(name, x) {{ VAL[String(name)] = Number(x); mgraphics.redraw(); }}
function get(name, d) {{ return VAL.hasOwnProperty(name) ? VAL[name] : d; }}

function word(x, y, s, size, c, anchor) {{
	mgraphics.select_font_face(FONTN);
	mgraphics.set_font_size(size);
	var tw = mgraphics.text_measure(s)[0];
	mgraphics.set_source_rgba(c);
	mgraphics.move_to(anchor == 1 ? x - tw / 2 : (anchor == 2 ? x - tw : x), y);
	mgraphics.show_text(s);
	return tw;
}}

function paint() {{
	var w = mgraphics.size[0], h = mgraphics.size[1], n = NAMES.length, tw = (TABSW - GAP * (n - 1)) / n;
	for (var k = 0; k < n; k++) {{
		var x = k * (tw + GAP), on = k == PAGE, c = COLS[k];
		mgraphics.set_source_rgba(on ? CELL : GROUND);
		mgraphics.rectangle_rounded(x + 0.45, 0.45, tw - 0.9, h - 0.9, 6, 6);
		mgraphics.fill();
		mgraphics.set_source_rgba(on ? c : EDGE);
		mgraphics.set_line_width(0.9);
		mgraphics.rectangle_rounded(x + 0.45, 0.45, tw - 0.9, h - 0.9, 6, 6);
		mgraphics.stroke();
		if (on) {{
			mgraphics.set_source_rgba(c);
			mgraphics.rectangle(x + 1, 0, tw - 2, 2.2);
			mgraphics.fill();
		}}
		word(x + tw / 2, h / 2 + {size} * 0.36 + 0.5, NAMES[k], {size}, on ? TXT : DIMT, 1);
	}}
	if (typeof after == "function") after(w, h);
}}

// for the tests: the tab shown
function values() {{ return [PAGE]; }}
"""


# ---- the family's text screens and cards (the Utilities' panels, Oct 15: plans/ideas/utilities-panels.md) ----------
def text(p, oid, words, x, base, size, color, anchor="start", w=None, bold=True, h=None):
    """A comment placed by its baseline, as the mockups place their words (tools/sketches/utilities_panels.py):
    anchor start, middle or end at x. No word under WORD px."""
    assert size >= WORD, (oid, size)
    w = w if w is not None else max(12.0, len(str(words)) * size * 0.62 + 6)
    left = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
    p.comment(oid, words, [round(left, 2), round(base - size * 0.95, 2), round(w, 2), h or round(size * 1.3 + 1, 2)],
              color, size=size, bold=bold, justify={"start": 0, "middle": 1, "end": 2}[anchor])
    return oid


def card(p, oid, rect, color, title, note=None, note_color=MUTED):
    """A card: its colour along the top, its title in it, a note at its right (7 px)."""
    x, y, w, h = rect
    p.panel(oid, rect, CARD, rounded=10)
    p.panel(f"{oid}-stripe", [x, y, w, 2.5], color, rounded=3)
    text(p, f"{oid}-title", title, x + 6, y + 13, 8.5, color)
    if note:
        text(p, f"{oid}-note", note, x + w - 4, y + 13, WORD, note_color, anchor="end")
    return oid


def screen(p, oid, rect):
    """A dark screen (the displays' ground) for words or a drawing on it."""
    p.panel(oid, rect, SCREEN, rounded=6)
    return oid


# ---- the family's cable selector: A · B · C · D, one menu parameter (Live's own live.tab) --------------------------
CABLE_ITEMS = ["A", "B", "C", "D"]
SEG_GAP = 2.0                # px between two segments (the live.tab's spacing_x)
SEG_TOP = 12.0               # the segments start under the label pill


def segments_script(title, color, items, label="CABLE"):
    """A choice drawn as segments under its label pill, the chosen one filled in the colour (a live.tab lies over
    the segments, transparent: Live's own menu parameter, so a click, Push, a map and automation reach it).
    Messages: v <name> <index> (feed()). The Warp & Weft family cable selector; the probes' cable choices (Off
    first) can take it as they are rebuilt."""
    return f"""// {title}: a choice as segments. Generated by lib/panelg.py; edit that, not this.
// Messages: v <name> <index>. Draws only (Live's live.tab lies over the segments).
{HEAD}
var C = {rgba(color)}, INKC = {rgba(INK)}, ITEMS = {json.dumps([str(i) for i in items])}, LABEL = {json.dumps(label)};
var GAP = {SEG_GAP}, TOP = {SEG_TOP}, WORD = {WORD}, FONTN = "{FONT}", CH = 0;

function v(name, x) {{ CH = Math.max(0, Math.min(ITEMS.length - 1, Math.round(Number(x)))); mgraphics.redraw(); }}

function word(x, y, s, size, c) {{
	mgraphics.select_font_face(FONTN);
	mgraphics.set_font_size(size);
	var tw = mgraphics.text_measure(s)[0];
	mgraphics.set_source_rgba(c);
	mgraphics.move_to(x - tw / 2, y);
	mgraphics.show_text(s);
}}

function paint() {{
	var w = mgraphics.size[0], h = mgraphics.size[1], n = ITEMS.length, sw = (w - GAP * (n - 1)) / n;
	mgraphics.set_source_rgba(C);
	mgraphics.rectangle_rounded(0, 0, w, 9.5, 3, 3);
	mgraphics.fill();
	word(w / 2, 7.6, LABEL, WORD, INKC);
	var sh = h - TOP, size = Math.max(WORD, Math.min(10, sh * 0.55));
	for (var k = 0; k < n; k++) {{
		var x = k * (sw + GAP), on = k == CH;
		mgraphics.set_source_rgba(on ? C : INKC);
		mgraphics.rectangle_rounded(x + 0.45, TOP + 0.45, sw - 0.9, sh - 0.9, 5, 5);
		mgraphics.fill();
		mgraphics.set_source_rgba(C);
		mgraphics.set_line_width(0.9);
		mgraphics.rectangle_rounded(x + 0.45, TOP + 0.45, sw - 0.9, sh - 0.9, 5, 5);
		mgraphics.stroke();
		word(x + sw / 2, TOP + sh / 2 + size * 0.36, ITEMS[k], size, on ? INKC : C);
	}}
}}

// for the tests: the segment chosen
function values() {{ return [CH, ITEMS[CH]]; }}
"""


def cable_tab(p, oid, longname, rect, color, x, y=1500, items=None, initial=0, label="CABLE", short=None):
    """The family's cable selector at rect (its label pill on top, the segments under it): one live.tab, Live's own
    menu parameter `longname` (items A-D unless given), laid transparent over the segments it is drawn as. Returns
    the drawing's id. The control's value also goes where the device wires it (feed's tap keeps its lines)."""
    from visual import embed_script
    items = list(items or CABLE_ITEMS)
    rx, ry, rw, rh = rect
    js = embed_script(p, f"{oid}-seg", rect, segments_script(longname, color, items, label), x, y)
    p.param(oid, longname, short or longname,
            dict(parameter_type=2, parameter_initial=[float(initial)], parameter_mmax=len(items) - 1,
                 parameter_enum=list(items)),
            maxclass="live.tab", patching_rect=[x, y - 40, rw, 16], presentation=1,
            presentation_rect=[rx, ry + SEG_TOP, rw, rh - SEG_TOP], varname=oid, numinlets=1, numoutlets=3,
            outlettype=["", "", "float"], num_lines_patching=1, num_lines_presentation=1, fontname=FONT,
            fontsize=8.0, rounded=5, spacing_x=SEG_GAP, spacing_y=0.0)
    lay(next(b["box"] for b in p.boxes if b["box"].get("id") == oid))
    feed(p, oid, oid, js, x + 120, y)
    return js
