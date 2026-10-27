"""Run a jsui drawing script (lib/visual.py writes them) in Node, as Max would: a stand-in for
Max's mgraphics records every drawing call, the messages the patch sent are called in order,
then paint(). Returns {"ops": [[call, args...]...], "values": the script's values(), "outlets":
[[outlet, args...]...] (what it sent out, as an editor does when clicked), "redraws": how many times it asked to be
redrawn}. Max's Task is there too, run only by the test's '__tick <n>' message (n of its intervals pass).

    jsrun.run(script_text, [["scalar", "g", 2.0], ["choose", 3]], (118, 134))

Max's JavaScript is ES5 and non-strict (the scripts use 'with (mgraphics)'); Node runs it in a
vm context the same way. Tests use this to check what a display draws, and that it draws at all
(no exception, a stroked curve) with any message the panel can send.

Every script runs in one Node worker for the Python process (WORKER, below): started at the first run, a request a
line, each in a fresh vm context with fresh globals, as a Node of its own did (one Node per run was nearly all of a
test's time: a probe's SWING section ran 5,068 scripts, ~55 ms each to start Node).
"""

import atexit
import json
import os
import subprocess
import threading

# (HARNESS and LOGIC are function bodies: WORKER runs one for each request, its input in `input`, and answers what it
# returns)
HARNESS = r"""
const ops = [], outs = [];
const rec = (name) => (...args) => { ops.push([name, ...args]); };
const mgraphics = { size: input.size, relative_coords: 0, autofill: 0 };
for (const f of ["init", "redraw", "set_source_rgba", "rectangle", "rectangle_rounded", "fill", "stroke",
                 "move_to", "line_to", "close_path", "set_line_width", "set_line_join", "set_line_cap",
                 "select_font_face", "set_font_size", "show_text", "arc", "ellipse", "rel_line_to",
                 "rel_move_to", "curve_to", "fill_preserve", "stroke_preserve", "path_roundcorners", "translate",
                 "rotate", "scale", "save", "restore", "identity_matrix"]) mgraphics[f] = rec(f);
// a colour Max can't take stops the drawing, as it does in Max ("mgraphics: not enough arguments for
// set_source_rgba", the owner, Oct 7: another device's lanes gave MAP's label a colour of three numbers): four
// numbers, or one list of four (a NaN is a number to Max: it draws nothing, says nothing)
mgraphics.set_source_rgba = (...a) => {
    const c = a.length === 1 && Array.isArray(a[0]) ? a[0] : a;
    if (c.length < 4 || c.slice(0, 4).some((x) => typeof x !== "number"))
        throw new Error("mgraphics: not enough arguments for set_source_rgba: " + JSON.stringify(a));
    ops.push(["set_source_rgba", ...a]);
};
let fsz = 7;                // text_measure follows the font size, as Max's does (about 0.62 em a character)
mgraphics.set_font_size = (z) => { fsz = z; ops.push(["set_font_size", z]); };
mgraphics.text_measure = (t) => [String(t).length * fsz * 0.62, fsz];
// Max's Buffer (a buffer~ by name): the test's data, a list of channels per name
class Buffer {
    constructor(name) { this.d = (input.buffers || {})[name] || []; }
    framecount() { return this.d.length ? this.d[0].length : 0; }
    channelcount() { return this.d.length; }
    peek(ch, frame, count) {
        const c = this.d[ch - 1] || [];
        return !count || count === 1 ? (c[frame] || 0) : c.slice(frame, frame + count);
    }
}
// Max's Task (a function run on the low-priority queue every `interval` ms once repeat()ed): here it runs only when the
// test sends '__tick <n>' (n intervals pass), so a test can count how often a script redraws over simulated time;
// redraws counts mgraphics.redraw() calls before paint (a probe)
const TASKS = [];
class Task {
    constructor(f, o) { this.f = f; this.o = o; this.interval = 0; }
    repeat() { if (TASKS.indexOf(this) < 0) TASKS.push(this); }
    cancel() { const i = TASKS.indexOf(this); if (i >= 0) TASKS.splice(i, 1); }
}
let redraws = 0;
mgraphics.redraw = () => { redraws++; ops.push(["redraw"]); };
const ctx = { mgraphics, post: () => {}, outlet: (...a) => { outs.push(a); }, box: { rect: [0, 0, ...input.size] },
              inlets: 1, outlets: 1, Math, Array, JSON, Buffer, Task,
              __tick: (n) => { for (let k = 0; k < (n || 1); k++) for (const t of TASKS.slice()) t.f.call(t.o); } };
vm.createContext(ctx);
vm.runInContext(input.script, ctx);
for (const m of input.messages) {
    if (typeof ctx[m[0]] !== "function") throw new Error("no function for message " + m[0]);
    ctx[m[0]](...m.slice(1));
}
ops.length = 0;
ctx.paint();
return { ops, values: ctx.values ? ctx.values() : null, outlets: outs, redraws };
"""


def run(script, messages, size, buffers=None):
    """What the script draws after these messages (lists: [name, args...]) at this size. buffers: {name: [channel,
    ...]}, what Max's Buffer finds by name (a buffer~'s samples)."""
    msgs = [m if isinstance(m, list) else str(m).split() for m in messages]
    msgs = [[m[0]] + [float(v) if isinstance(v, (int, float)) else v for v in m[1:]] for m in msgs]
    return _ask("draw", {"script": script, "messages": msgs, "size": list(size), "buffers": buffers or {}})


def svg(ops, w, h):
    """The drawing calls as an SVG of w x h (tools/render.py puts displays in images with it):
    paths, fills, strokes and text, which is what lib/visual.py's scripts use, and scale and translate."""
    out, path, col, lw, size, at = [], "", "rgba(0,0,0,1)", 1, 7, (0, 0)
    groups, saved = 0, []           # scale and translate as SVG groups, closed by restore (or at the end)
    for o in ops:
        k, a = o[0], o[1:]
        if k in ("scale", "translate"):
            out.append(f'<g transform="{k}({a[0]},{a[1]})">')
            groups += 1
            continue
        if k == "save":
            saved.append(groups)
            continue
        if k == "restore":
            back = saved.pop() if saved else 0
            out.append("</g>" * (groups - back))
            groups = back
            continue
        if k == "set_source_rgba":
            c = a[0] if len(a) == 1 else a
            col = f"rgba({c[0] * 255:.0f},{c[1] * 255:.0f},{c[2] * 255:.0f},{c[3] if len(c) > 3 else 1})"
        elif k == "set_line_width":
            lw = a[0]
        elif k == "set_font_size":
            size = a[0]
        elif k == "rectangle_rounded":
            x, y, rw, rh, r = a[:5]
            r = min(r / 2, rw / 2, rh / 2)        # mgraphics takes the corner's diameter
            path += (f"M{x + r},{y} h{rw - 2 * r} a{r},{r} 0 0 1 {r},{r} v{rh - 2 * r} a{r},{r} 0 0 1 {-r},{r} "
                     f"h{-(rw - 2 * r)} a{r},{r} 0 0 1 {-r},{-r} v{-(rh - 2 * r)} a{r},{r} 0 0 1 {r},{-r} Z ")
        elif k == "arc":
            import math
            cx, cy, r, a0, a1 = a[:5]
            x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            large = 1 if (a1 - a0) % (2 * math.pi) > math.pi else 0
            path += f"M{x0:.2f},{y0:.2f} A{r},{r} 0 {large} 1 {x1:.2f},{y1:.2f} "
        elif k == "ellipse":
            x, y, ew, eh = a[:4]
            path += (f"M{x},{y + eh / 2} a{ew / 2},{eh / 2} 0 1 0 {ew},0 a{ew / 2},{eh / 2} 0 1 0 {-ew},0 Z ")
        elif k == "rectangle":
            path += f"M{a[0]},{a[1]} h{a[2]} v{a[3]} h{-a[2]} Z "
        elif k == "move_to":
            path += f"M{a[0]},{a[1]} "
            at = (a[0], a[1])
        elif k == "line_to":
            path += f"L{a[0]},{a[1]} "
        elif k == "curve_to":
            path += f"C{a[0]},{a[1]} {a[2]},{a[3]} {a[4]},{a[5]} "
        elif k == "close_path":
            path += "Z "
        elif k == "fill":
            out.append(f'<path d="{path}" fill="{col}"/>')
            path = ""
        elif k == "stroke":
            out.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="{lw}" '
                       f'stroke-linejoin="round" stroke-linecap="round"/>')
            path = ""
        elif k == "show_text":
            out.append(f'<text x="{at[0]}" y="{at[1]}" font-size="{size}" font-weight="700" fill="{col}">{a[0]}</text>')
            path = ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'style="display:block">{"".join(out)}{"</g>" * groups}</svg>')


LOGIC = r"""
const calls = [], outs = [];
// the Live set, as input.live describes it: {playing: slot, slots: [has a clip, ...], clips: {slot: {length,
// notes: [note dicts]}}}; ids as lib/maxsim.py's FakeLive: live_set 1, the track 50, clip slot i 100 + i,
// its clip 200 + i. As in Max, an id is a string, and "0" when the path finds nothing (an empty slot's
// clip): `if (!api.id)` never catches that, `Number(api.id) === 0` does
const live = input.live || { playing: -1, slots: [], clips: {} };
// the track's devices, as input.live.track describes them: {self: this device's id, devices: [{id, name, params:
// [{id, name, items (a menu's or switch's, else none)}], chains: [{id, devices: [...]}], drum}]}; the track is id 50
const track = live.track || { self: 40, devices: [] };
const DEV = {}, PAR = {}, CHAIN = {};
(function index(devs) {
    for (const d of devs || []) {
        DEV[d.id] = d;
        for (const q of d.params || []) PAR[q.id] = q;
        for (const c of d.chains || []) { CHAIN[c.id] = c; index(c.devices); }
    }
})(track.devices);
const ids = (list) => [].concat(...(list || []).map((x) => ["id", x.id]));
function LiveAPI(cb, path) {
    if (typeof cb === "string") path = cb;
    this.path = String(path || "");
    let m, id;
    if (this.path === "this_device") id = track.self;
    else if ((m = /^id (\d+)$/.exec(this.path))) id = parseInt(m[1]);
    else if ((m = /clip_slots (\d+) clip$/.exec(this.path))) {
        const i = parseInt(m[1]);
        id = (live.clips || {})[i] || (live.slots || [])[i] ? 200 + i : 0;
    }
    else if ((m = /clip_slots (\d+)$/.exec(this.path))) id = 100 + parseInt(m[1]);
    else if (/canonical_parent$/.test(this.path)) id = 50;
    else if (this.path === "live_set") id = 1;
    else id = this.path ? 1 : 0;
    this.id = String(id);
}
LiveAPI.prototype.call = function (fn, ...args) {
    calls.push([Number(this.id), fn, ...args]);
    if (fn === "create_clip" && this.id >= 100 && this.id < 200) {    // the slot has a clip from now on
        live.slots = live.slots || [];
        live.slots[this.id - 100] = 1;
    }
    const clip = live.clips[this.id - 200];
    if (fn === "get_notes_extended" && clip) return JSON.stringify({ notes: clip.notes });
    if (fn === "create_automation_envelope") return 0;   // Max for Live's Clip has none (lib/maxsim.py's FakeLive, Oct 20)
    return 0;
};
LiveAPI.prototype.get = function (prop) {
    const dev = DEV[this.id], par = PAR[this.id], chain = CHAIN[this.id];
    if (Number(this.id) === 50 && prop === "devices") return ids(track.devices);
    if (chain && prop === "devices") return ids(chain.devices);
    if (dev && prop === "name") return [dev.name];
    if (dev && prop === "parameters") return ids(dev.params);
    if (dev && prop === "can_have_chains") return [dev.chains ? 1 : 0];
    if (dev && prop === "can_have_drum_pads") return [dev.drum ? 1 : 0];
    if (dev && prop === "chains") return ids(dev.chains);
    if (par && prop === "name") return [par.name];
    if (par && prop === "is_quantized") return [par.items ? 1 : 0];
    if (par && prop === "value_items") return par.items || [];
    if (prop === "playing_slot_index") return [live.playing];
    if (prop === "has_clip") return [(live.slots || [])[this.id - 100] ? 1 : 0];
    const clip = live.clips[this.id - 200];
    if (prop === "length" && clip) return [clip.length];
    return [0];
};
LiveAPI.prototype.getcount = function (child) { return child === "clip_slots" ? (live.slots || []).length : 0; };
LiveAPI.prototype.set = function () { calls.push([Number(this.id), "set", ...Array.from(arguments)]); };
// Max's own: max.version, and this.patcher.getnamed(varname) -> {maxclass} (input.live.boxes: varname -> class)
const max = { version: String(live.maxversion || "8.6.5") };
// (and, for a named live.push, Maxobj.getattr(name): its attribute as set, input.live.attrs: varname -> {attr: words})
const patcher = { getnamed: (n) => (live.boxes && n in live.boxes ? { maxclass: live.boxes[n],
    getattr: (a) => (live.attrs && live.attrs[n] && a in live.attrs[n] ? live.attrs[n][a].join(" ") : null) } : null) };
// Max's Global: an object every js in Max shares by its name (lib/surface.py's table). The script is replayed from
// its first message each time, so input.globals holds, for each message, the Globals as they were when it arrived
// (other devices change them between); they are put back before it, and what they are after the last is returned
const GLOBALS = {};
function Global(name) { if (!GLOBALS[name]) GLOBALS[name] = {}; return GLOBALS[name]; }
const ctx = { post: () => {}, outlet: (...a) => { outs.push(a); }, LiveAPI, Math, Array, JSON, Object, Global,
              inlets: 1, outlets: 1, autowatch: 0, max, patcher };
vm.createContext(ctx);
vm.runInContext(input.script, ctx);
// the messages, in order: these, and (a state kept, below) the ones sent after them; what it asked and sent from
// `since` on ([calls, outlets] already had), and how many of each in all
const feed = (messages, globals) => messages.forEach((m, i) => {
    if (globals) {
        const was = globals[i] || {};
        for (const n of Object.keys(GLOBALS)) for (const k of Object.keys(GLOBALS[n])) delete GLOBALS[n][k];
        for (const n of Object.keys(was)) Object.assign(Global(n), JSON.parse(JSON.stringify(was[n])));
    }
    if (typeof m[0] === "number" && typeof ctx.list === "function") { ctx.list(...m); return; }   // as Max: a list
    if (typeof ctx[m[0]] !== "function") throw new Error("no function for message " + m[0]);
    ctx[m[0]](...m.slice(1));
});
const result = (since) => ({ calls: calls.slice(since[0]), outlets: outs.slice(since[1]), globals: GLOBALS,
                             ncalls: calls.length, nouts: outs.length });
feed(input.messages, input.globals);
return { feed, result };
"""


class Gone(Exception):
    """run_logic(after=...): the state to go on from isn't kept (the worker started again, or another call went on
    from it): replay from the first message."""


_names = [0]


def run_logic(script, messages, live=None, globals=None, since=(0, 0), keep=False, after=None):
    """A plain js object's script (no drawing) after these messages, with a stand-in LiveAPI that
    records what it's asked: {"calls": [[object id, function, args...]...], "outlets": [...]}.
    since: (calls, outlets) already had: only those after them are returned ("ncalls" and "nouts": how many in all).
    keep: the worker keeps the script's state after these messages, under the name returned as "kept"; after: such a
    name, to go on from that state, the messages and globals then only those since (the script and the Live set as
    they were: a replay from the first message in a fresh context plays the same, for a script without Math.random or
    Date). A kept state is gone once gone on from (its next is kept instead, when keep is set), or raises Gone.
    live: the Live set it sees, {"playing": slot, "clips": {slot: {"length", "notes": [dicts]}}, "track": {"self": id,
    "devices": [{"id", "name", "params": [{"id", "name", "items"}], "chains": [{"id", "devices"}]}]}} (a clip in slot i
    has id 200 + i, as lib/maxsim.py's FakeLive; the track is 50). globals: for each message, Max's Globals (by name)
    as they were when it arrived (the result's "globals": as they are after the last)."""
    msgs = [m if isinstance(m, list) else str(m).split() for m in messages]
    msgs = [[m[0]] + [float(v) if isinstance(v, (int, float)) else v for v in m[1:]] for m in msgs]
    req = {"script": script, "messages": msgs, "live": live, "globals": globals, "since": list(since)}
    if keep:
        _names[0] += 1
        req["keep"] = f"{os.getpid()}-{_names[0]}"
    if after:
        req["after"] = after
    return _ask("logic", req)


# One Node for every run: a request a line on stdin, {"kind": "draw" or "logic", "input"}, and its answer a line on
# stdout, {"ok": what HARNESS or LOGIC returned} or {"error"}. Each request runs its body as a function of its own, so
# everything it makes (the vm context, the recorded calls, Max's Globals, the Live set) is new, as in a Node of its
# own; only Node's Math, Array, JSON and Object, which the contexts are given, are shared (no script assigns to them).
# A script that throws answers the line a Node of its own printed last as it stopped ("Node.js v22.22.0": Node's
# version), and the worker reads the next request
WORKER = r"""
const vm = require("vm");
const KINDS = { draw: function (input) {
%s
}, logic: function (input) {
%s
} };
// the logic scripts' states kept (run_logic's keep), by name, the oldest dropped past KEPT_MOST
const KEPT = new Map(), KEPT_MOST = 64;
function logic(input) {
    let s;
    if (input.after) {
        s = KEPT.get(input.after);
        if (!s) return { gone: 1 };
        KEPT.delete(input.after);
        s.feed(input.messages, input.globals);
    } else {
        s = KINDS.logic(input);
    }
    const res = s.result(input.since || [0, 0]);
    if (input.keep) {
        KEPT.set(input.keep, s);
        if (KEPT.size > KEPT_MOST) KEPT.delete(KEPT.keys().next().value);
        res.kept = input.keep;
    }
    return res;
}
require("readline").createInterface({ input: process.stdin, crlfDelay: Infinity }).on("line", (line) => {
    let answer, req;
    try {
        req = JSON.parse(line);
        answer = JSON.stringify({ ok: req.kind === "logic" ? logic(req.input) : KINDS[req.kind](req.input) });
    } catch (e) {
        if (req && req.input && req.input.after) KEPT.delete(req.input.after);
        answer = JSON.stringify({ error: "Node.js " + process.version });
    }
    process.stdout.write(answer + "\n");
});
""" % (HARNESS, LOGIC)

_worker = None              # [the Node, the Python process that started it] (a forked child starts its own)
_lock = threading.Lock()    # one request at a time: the answers come back in order


def _ask(kind, request):
    """The worker's answer to one request, started (or started again, if it died) as needed. A request it died on is
    asked once more of a fresh one; a script that throws raises RuntimeError with the line Node stopped with."""
    global _worker
    line = (json.dumps({"kind": kind, "input": request}) + "\n").encode("utf-8")
    with _lock:
        for _ in range(2):
            if _worker is None or _worker[1] != os.getpid() or _worker[0].poll() is not None:
                _worker = [subprocess.Popen(["node", "-e", WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL), os.getpid()]
            try:
                _worker[0].stdin.write(line)
                _worker[0].stdin.flush()
                answer = _worker[0].stdout.readline()
            except OSError:         # (a broken pipe: it died)
                answer = b""
            if answer:
                break
            _stop()
        else:
            raise RuntimeError("node failed")
    res = json.loads(answer.decode("utf-8"))
    if "error" in res:
        raise RuntimeError(res["error"])
    if res["ok"].get("gone") if kind == "logic" else False:
        raise Gone(request.get("after"))
    return res["ok"]


def _stop():
    """The worker told to finish (its stdin closed) and waited for; killed if it doesn't."""
    global _worker
    if _worker is None or _worker[1] != os.getpid():
        _worker = None
        return
    node, _worker = _worker[0], None
    try:
        node.stdin.close()
        node.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        node.kill()
        node.wait()
    node.stdout.close()


atexit.register(_stop)
