"""The size Live gives each of its own controls (Oct 20: Logwood's LANES menus didn't open because Live showed the lanes'
sliders, 12.4 x 28 in the file, at 18 x 50, over the menus; the tests had taken the file's sizes).

Measured in Live 12 by tools/measure_live_sizes.py: every kind of control at forty sizes, what Live showed in
catalog/live_sizes.json; tests/test_live_sizes.py checks these rules give every measured size. A box keeps its place
(x, y); only its width and height change.

    live.dial      at least 27 wide; its height fixed by what it shows and its font: 28 bare; with its name 37-39,
                   its number 35-37, both 44-48 (DIAL_H)
    live.menu      at least 15 wide, 15 high, any font
    live.numbox    its height and least width fixed by its font: 12 high at 7 and 7.5, 13 at 8, 14 at 8.5 and 9
    live.text      at least 8 high (any font measured)
    live.tab       at least 8 high
    live.slider    vertical: at least 18 wide, 50 high; horizontal: at least 50 wide, 18 high exactly
    anything else  as in the file
"""

# (showname, shownumber) -> font size -> height; None: no fontsize set (Max's default: both shown)
DIAL_H = {(0, 0): {None: 28},
          (1, 0): {7.5: 37, 8.0: 37, 8.5: 38, 9.0: 38, None: 39},
          (0, 1): {7.5: 35, 8.0: 35, 8.5: 36, 9.0: 36, None: 37},
          (1, 1): {7.5: 44, 8.0: 45, 8.5: 46, 9.0: 47, None: 48}}
NUMBOX = {7.0: (11.97, 12), 7.5: (12.4, 12), 8.0: (12.82, 13), 8.5: (13.25, 14), 9.0: (13.68, 14)}   # font: (least w, h)


def _measured(table, key, what):
    if key not in table:
        raise KeyError(f"{what} at font size {key} isn't measured: add it to tools/measure_live_sizes.py's KINDS")
    return table[key]


def live_size(box):
    """(width, height) Live shows the box at, from its presentation_rect and its settings."""
    cls = box.get("maxclass")
    w, h = box["presentation_rect"][2:4]
    if cls == "live.dial":
        shows = DIAL_H[(int(box.get("showname", 1)), int(box.get("shownumber", 1)))]
        fs = box.get("fontsize")
        return max(w, 27), shows[None] if len(shows) == 1 else _measured(shows, None if fs is None else float(fs),
                                                                          "a live.dial's height")
    if cls == "live.menu":
        return max(w, 15), 15
    if cls == "live.numbox":
        lw, lh = _measured(NUMBOX, float(box.get("fontsize", 9.0)), "a live.numbox's size")
        return max(w, lw), lh
    if cls in ("live.text", "live.tab"):
        return w, max(h, 8)
    if cls == "live.slider":
        if int(box.get("orientation", 0)) == 1:
            return max(w, 50), 18
        return max(w, 18), max(h, 50)
    return w, h


def live_rect(box):
    """The box's presentation_rect as Live shows it."""
    x, y = box["presentation_rect"][:2]
    return [x, y, *live_size(box)]


def as_live(boxes):
    """The boxes (a patcher's 'boxes', each {"box": ...}) with every presentation_rect as Live shows it, inside
    subpatchers too; the boxes themselves are copied, the list's order kept."""
    out = []
    for b in boxes:
        box = dict(b["box"])
        if "presentation_rect" in box:
            box["presentation_rect"] = live_rect(box)
        if isinstance(box.get("patcher"), dict):
            box["patcher"] = dict(box["patcher"], boxes=as_live(box["patcher"].get("boxes", [])))
        out.append({**b, "box": box})
    return out


CLICKS = ("live.dial", "live.numbox", "live.menu", "live.text", "live.tab", "live.slider", "live.drop", "comment",
          "live.button", "live.toggle")


def takes_clicks(box):
    """Whether the box takes a click in Live: Live's controls and comments, and screens (jsui) and panels that don't
    ignore clicks; a background panel is behind everything."""
    if box.get("ignoreclick"):
        return False
    if box.get("maxclass") in ("jsui", "panel"):
        return not box.get("background")
    return box.get("maxclass") in CLICKS


def reach(boxes, together=lambda a, b: True, step=1.0, params_only=True):
    """{index: the share of where the control at that index is drawn (its file rect, as far as Live's rect takes
    clicks) where a click reaches it in Live} for every parameter's control in boxes (a patcher's boxes' "box"
    dicts, in its order). Live draws the background layer behind the rest and, in a layer, the box listed first on
    top (lib/m4l.py); together(a, b): whether two boxes are shown at once (on one page)."""
    shown = [(i, b) for i, b in enumerate(boxes) if b.get("presentation") and "presentation_rect" in b]
    live = {i: live_rect(b) for i, b in shown}
    layer = sorted(shown, key=lambda ib: (bool(ib[1].get("background")), ib[0]))     # top first
    out = {}
    for i, c in shown:
        if (params_only and not c.get("parameter_enable")) or c.get("maxclass") not in CLICKS or not takes_clicks(c):
            continue
        fx, fy, fw, fh = c["presentation_rect"]
        lx, ly, lw, lh = live[i]
        x0, y0, x1, y1 = max(fx, lx), max(fy, ly), min(fx + fw, lx + lw), min(fy + fh, ly + lh)
        above = []
        for j, s in layer:
            if j == i:
                break
            if takes_clicks(s) and together(c, s):
                sx, sy, sw, sh = live[j]
                if sx < x1 and x0 < sx + sw and sy < y1 and y0 < sy + sh:
                    above.append(live[j])
        if x1 <= x0 or y1 <= y0:
            out[i] = 0.0
            continue
        n = hit = 0
        y = y0 + step / 2
        while y < y1:
            x = x0 + step / 2
            while x < x1:
                n += 1
                hit += not any(sx <= x < sx + sw and sy <= y < sy + sh for sx, sy, sw, sh in above)
                x += step
            y += step
        out[i] = hit / n if n else 1.0
    return out


def pages(boxes):
    """{scripting name: its page} from a paged device's 'page-m<k>' messages (page k's boxes shown, the others hidden),
    as tests/test_mapping.py reads them; a box on no page, or a device without them: not in it."""
    import re
    out = {}
    for b in boxes:
        m = re.fullmatch(r"page-m(\d+)", b["box"].get("id", ""))
        if m and b["box"].get("maxclass") == "message":
            for part in b["box"].get("text", "").split(","):
                words = part.split()
                if words[:2] == ["script", "show"] and len(words) > 2:
                    out[words[2]] = int(m.group(1))
    return out


def live_order(boxes):
    """The boxes (a patcher's, each {"box": ...}) with Live's controls reordered so that each is on top where it's
    drawn: of two of Live's controls that overlap at the sizes Live shows them, the lower one (then the one further
    right) is listed first (Live grows a box right and down from its corner). Every other two boxes that overlap
    keep their order (a drawing over its control, a panel behind it), and that wins where the two disagree; boxes
    that overlap nothing keep their slots (Oct 20: Logwood's lanes' sliders, listed before LANES' menus, took their
    clicks; the first version also moved controls past their drawings)."""
    slots = [i for i, b in enumerate(boxes) if b["box"].get("presentation") and "presentation_rect" in b["box"]]
    if len(slots) < 2:
        return list(boxes)
    files = [boxes[i]["box"]["presentation_rect"] for i in slots]
    rects = [live_rect(boxes[i]["box"]) for i in slots]
    control = [boxes[i]["box"].get("maxclass", "").startswith("live.") and takes_clicks(boxes[i]["box"])
               for i in slots]
    corner = [(-r[1], -r[0]) for r in rects]                  # lower, then further right, first

    def meet(p, q, by=0.0):
        return (min(p[0] + p[2], q[0] + q[2]) - max(p[0], q[0]) > by
                and min(p[1] + p[3], q[1] + q[3]) - max(p[1], q[1]) > by)

    page = pages(boxes)
    names = [boxes[i]["box"].get("varname") for i in slots]

    def apart(a, b):
        pa, pb = page.get(names[a]), page.get(names[b])
        return pa is not None and pb is not None and pa != pb

    after = {k: set() for k in range(len(slots))}            # k -> the boxes that must come after it
    swaps = []
    for a in range(len(slots)):
        for b in range(a + 1, len(slots)):
            live, filed = meet(rects[a], rects[b]), meet(files[a], files[b], 1.0)   # (a file's rounding aside)
            if not (live or filed):
                continue
            if control[a] and control[b]:
                # two controls drawn in one place are on two views (a view's controls never share a place: each
                # device's UI test); where Live grows one over the other, the lower goes first
                if live and corner[b] != corner[a]:
                    swaps.append((b, a) if corner[b] < corner[a] else (a, b))
            elif apart(a, b):
                continue        # on two pages: never shown together (other pages' drawings would pin Weld's MOD rows)
            else:
                after[a].add(b)                               # as listed: a drawing over its control, a panel

    def reaches(x, y):
        seen, todo = set(), [x]
        while todo:
            k = todo.pop()
            if k == y:
                return True
            for t in after[k]:
                if t not in seen:
                    seen.add(t)
                    todo.append(t)
        return False

    for first, then in swaps:
        if not reaches(then, first):
            after[first].add(then)
    need = [0] * len(slots)
    for k in after:
        for t in after[k]:
            need[t] += 1
    import heapq
    ready = [k for k in range(len(slots)) if not need[k]]
    heapq.heapify(ready)
    order = []
    while ready:
        k = heapq.heappop(ready)
        order.append(k)
        for t in after[k]:
            need[t] -= 1
            if not need[t]:
                heapq.heappush(ready, t)
    assert len(order) == len(slots)
    out = list(boxes)
    for i, k in zip(slots, order):
        out[i] = boxes[slots[k]]
    return out


def at_foot(box):
    """A control Live shows shorter than the column it's laid over (a live.menu 15 high over a 29 px column, a bare
    live.dial 28 high over 57) moved to the column's foot, over its value and bar: at the top it took the label and
    missed the value drawn under it (a probe's and a probe's, Oct 25). Called by a
    device on its own columns, not by lay(): devices on sale keep their places."""
    x, y, w, h = box["presentation_rect"]
    lh = live_size(box)[1]
    if h - lh >= 4:
        box["presentation_rect"] = [x, round(y + h - lh, 2), w, lh]
    return box


VALUE_ROW = (11, 15)       # a 39 px column's value row: its top from the column's last 39 px, and its height


def on_value_row(box):
    """A live.menu or live.numbox laid over a column (39 px or more) moved onto the column's value row, where its value
    and the menu's arrow are drawn: Live shows it 15 px high whatever its rect (above), so left at the column's top it
    took clicks on the label only (a tester, Oct 20, on Mordant; Oct 21 on Weld, Weld Kit and Logwood). The Mordant
    a probe's panel_c.lay did it first; the column drawings put the value 11-26 px into a column's last 39 px."""
    r = box.get("presentation_rect")
    if box.get("maxclass") in ("live.menu", "live.numbox") and r and r[3] >= 39:
        x, y, w, h = r
        box["presentation_rect"] = [x, round(y + h - 39 + VALUE_ROW[0], 2), w, VALUE_ROW[1]]


def dial_rect(column):
    """Where a bare dial laid over a value column lies (backlog E39, lib/m4l.py's dials_on_values): over the column's
    bottom, as high as Live shows it (28), where the number and the bar are; over a column no taller, the column."""
    x, y, w, h = column
    bare = DIAL_H[(0, 0)][None]
    return [x, round(y + h - bare, 2), w, bare] if h > bare + 0.5 else list(column)
