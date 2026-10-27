"""Run a gen~ codebox (GenExpr) offline in Python.

Translates the subset of GenExpr the Tincture devices use into a Python
function, so tests exercise the exact code that ships in the .amxd:

- declarations: Param, History, Data, Delay, Buffer (a buffer~ of the patch: a test fills it, Engine.load_buffer)
- statements: assignment, if / else if / else, for (i = a; cond; i = i + b) { }, Delay .write(), poke()
- expressions: ternary, || && == != < > <= >= + - * / %, unary - !
- builtins: see BUILTINS below

State (Params, Histories, Data, Delays) lives on the Engine; everything else
is a per-sample local. Histories behave as persistent variables: a write is
visible to later statements in the same sample and to the next sample.

    eng = Engine(code, samplerate=48000)
    eng.set("char_amt", 0.7)
    out1, out2 = eng.tick(in1, in2)
"""

import math
import random
import re

TOKEN = re.compile(r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<str>"[^"\n]*")
  | (?P<num>\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)
  | (?P<id>[A-Za-z_]\w*)
  | (?P<op>==|!=|<=|>=|&&|\|\||[-+*/%<>!?:=(),;{}.])
""", re.S | re.X)


def tokenize(src):
    pos, out, line = 0, [], 1         # line: the line pos is on (counted as it goes: a probe's code is long)
    for m in TOKEN.finditer(src):     # one token after another: a gap is a character no token takes
        if m.start() != pos:
            break
        tok = m.group()
        if m.lastgroup != "ws":
            out.append((m.lastgroup, tok, line))
        elif "\n" in tok:
            line += tok.count("\n")
        pos = m.end()
    if pos < len(src):
        raise SyntaxError(f"line {line}: unexpected {src[pos:pos + 20]!r}")
    out.append(("eof", "", -1))
    return out


# reads past a Delay's size or outside a Data's frames, as (what, index, size): gen~ clamps a Delay
# read and a peek outside a Data reads 0, as here, but the sound is then not what the code meant.
# tests/test_sample_rates.py empties this and checks it stays empty at every sample rate.
OVERRUNS = []


class Delay:
    def __init__(self, size):
        self.size = int(size)
        self.buf = [0.0] * self.size
        self.w = 0

    def read(self, t):
        # read-before-write: t samples back from the next write, linear interpolation
        if t > self.size - 1.0:
            OVERRUNS.append(("Delay read", t, self.size))
        t = min(max(t, 1.0), self.size - 1.0)
        i = int(t)
        frac = t - i
        a = self.buf[(self.w - i) % self.size]
        b = self.buf[(self.w - i - 1) % self.size]
        return a + (b - a) * frac

    def write(self, x):
        self.buf[self.w] = x
        self.w = (self.w + 1) % self.size


class Data:
    def __init__(self, frames, channels=1):
        self.frames, self.channels = int(frames), int(channels)
        self.ch = [[0.0] * self.frames for _ in range(self.channels)]


def _peek(d, i, c=0):
    i, c = int(math.floor(i)), int(c)
    if not 0 <= i < d.frames:
        OVERRUNS.append(("Data peek", i, d.frames))
    return d.ch[c][i] if 0 <= i < d.frames and 0 <= c < d.channels else 0.0


def _poke(d, v, i, c=0):
    i, c = int(math.floor(i)), int(c)
    if not 0 <= i < d.frames:
        OVERRUNS.append(("Data poke", i, d.frames))
    if 0 <= i < d.frames and 0 <= c < d.channels:
        d.ch[c][i] = v


def _dim(d):
    return float(d.frames)


def _channels(d):
    return float(d.channels)


def _wrap(x, lo, hi):
    r = hi - lo
    return lo + (x - lo) % r if r else lo


def _sign(x):
    return (x > 0) - (x < 0)


def _fixnan(x):
    return 0.0 if x != x else x


BUILTINS = {
    "tanh": "math.tanh", "sin": "math.sin", "cos": "math.cos", "tan": "math.tan", "atan2": "math.atan2",
    "exp": "math.exp", "sqrt": "math.sqrt", "pow": "math.pow", "abs": "abs",
    "floor": "math.floor", "min": "min", "max": "max", "log": "math.log", "log2": "math.log2", "log10": "math.log10",
    "clamp": "_clamp", "wrap": "_wrap", "sign": "_sign", "fixnan": "_fixnan",
    "noise": "_noise", "peek": "_peek", "poke": "_poke", "dim": "_dim", "channels": "_channels",
}
CONSTANTS = {"pi": "math.pi", "twopi": "(2*math.pi)", "halfpi": "(math.pi/2)"}
BINOPS = [["||"], ["&&"], ["==", "!="], ["<", ">", "<=", ">="], ["+", "-"], ["*", "/", "%"]]
PYOP = {"||": "or", "&&": "and", "%": "%"}


class Translator:
    def __init__(self, src, toks=None):
        self.toks = toks if toks is not None else tokenize(src)
        self.i = 0
        self.state = {}  # name -> (kind, args)
        self.params = {}  # name -> (default, min, max)
        self.out = []

    # ---- token helpers
    def peek(self, k=0):
        return self.toks[self.i + k]

    def take(self, value=None):
        tok = self.toks[self.i]
        if value is not None and tok[1] != value:
            raise SyntaxError(f"line {tok[2]}: expected {value!r}, got {tok[1]!r}")
        self.i += 1
        return tok

    # ---- expressions
    def expr(self):
        cond = self.binop(0)
        if self.peek()[1] == "?":
            self.take("?")
            a = self.expr()
            self.take(":")
            b = self.expr()
            return f"(({a}) if ({cond}) else ({b}))"
        return cond

    def binop(self, level):
        if level == len(BINOPS):
            return self.unary()
        left = self.binop(level + 1)
        while self.peek()[1] in BINOPS[level]:
            op = self.take()[1]
            right = self.binop(level + 1)
            if op in ("||", "&&"):
                left = f"(1.0 if (({left}) {PYOP[op]} ({right})) else 0.0)"
            elif op == "%":
                left = f"math.fmod({left}, {right})"
            else:
                left = f"({left} {op} {right})"
        return left

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            return f"(-{self.unary()})"
        if self.peek()[1] == "!":
            self.take()
            return f"(0.0 if ({self.unary()}) else 1.0)"
        return self.primary()

    def args(self):
        self.take("(")
        out = []
        while self.peek()[1] != ")":
            out.append(self.expr())
            if self.peek()[1] == ",":
                self.take(",")
        self.take(")")
        return out

    def primary(self):
        kind, val, line = self.take()
        if kind == "num":
            return repr(float(val))
        if val == "(":
            e = self.expr()
            self.take(")")
            return f"({e})"
        if kind != "id":
            raise SyntaxError(f"line {line}: unexpected {val!r}")
        if self.peek()[1] == ".":
            self.take(".")
            method = self.take()[1]
            if self.state.get(val, ("",))[0] != "Delay" or method not in ("read", "write"):
                raise SyntaxError(f"line {line}: unsupported {val}.{method}")
            return f"S.{val}.{method}({', '.join(self.args())})"
        if self.peek()[1] == "(":
            if val not in BUILTINS:
                raise SyntaxError(f"line {line}: unknown function {val}")
            a = self.args()
            if val in ("peek", "poke"):
                a[0] = f"S.{self.data_name(a[0], line)}"
            return f"{BUILTINS[val]}({', '.join(a)})"
        return self.name(val, line)

    def data_name(self, ref, line):
        name = ref[2:] if ref.startswith("S.") else ref
        if self.state.get(name, ("",))[0] not in ("Data", "Buffer"):
            raise SyntaxError(f"line {line}: {name} is not a Data or a Buffer")
        return name

    def name(self, val, line):
        if val in self.state:
            return f"S.{val}"
        if val in CONSTANTS:
            return CONSTANTS[val]
        if val == "samplerate":
            return "S.samplerate"
        if val in ("in1", "in2", "in3", "in4"):
            return val
        if re.fullmatch(r"out[1-9]\d*", val):             # out1 ... out14 (another device has fourteen)
            self.outs = max(getattr(self, "outs", 2), int(val[3:]))
            return val
        return "v_" + val

    # ---- statements
    def declaration(self, kind):
        self.take()
        name = self.take()[1]
        self.take("(")
        pos, kw = [], {}
        while self.peek()[1] != ")":
            if self.peek(1)[1] == "=":
                key = self.take()[1]
                self.take("=")
                kw[key] = self.const()
            elif self.peek()[0] == "str":           # a Buffer's buffer~ name
                pos.append(self.take()[1].strip('"'))
            else:
                pos.append(self.const())
            if self.peek()[1] == ",":
                self.take(",")
        self.take(")")
        self.take(";")
        self.state[name] = (kind, pos)
        if kind == "Param":
            self.params[name] = (pos[0] if pos else 0.0, kw.get("min"), kw.get("max"))

    def const(self):
        sign = -1.0 if self.peek()[1] == "-" and self.take() else 1.0
        return sign * float(self.take()[1])

    def block(self, indent):
        if self.peek()[1] == "{":
            self.take("{")
            n = len(self.out)
            while self.peek()[1] != "}":
                self.statement(indent)
            self.take("}")
            if len(self.out) == n:
                self.out.append("    " * indent + "pass")
        else:
            self.statement(indent)

    def assignment(self):
        kind, val, line = self.take()
        if kind != "id":
            raise SyntaxError(f"line {line}: expected a name, got {val!r}")
        self.take("=")
        target = self.name(val, line)
        if self.state.get(val, ("",))[0] in ("Param", "Data", "Delay"):
            raise SyntaxError(f"line {line}: cannot assign to {val}")
        return f"{target} = {self.expr()}"

    def statement(self, indent):
        pad = "    " * indent
        kind, val, line = self.peek()
        if val == "for":                     # for (init; condition; step) { ... }: a while loop, the step last
            self.take()
            self.take("(")
            self.out.append(pad + self.assignment())
            self.take(";")
            cond = self.expr()
            self.take(";")
            step = self.assignment()
            self.take(")")
            self.out.append(f"{pad}while {cond}:")
            self.block(indent + 1)
            self.out.append("    " * (indent + 1) + step)
            return
        if val == "if":
            self.take()
            self.take("(")
            cond = self.expr()
            self.take(")")
            self.out.append(f"{pad}if {cond}:")
            self.block(indent + 1)
            while self.peek()[1] == "else":
                self.take()
                if self.peek()[1] == "if":
                    self.take()
                    self.take("(")
                    cond = self.expr()
                    self.take(")")
                    self.out.append(f"{pad}elif {cond}:")
                else:
                    self.out.append(f"{pad}else:")
                self.block(indent + 1)
            return
        if kind == "id" and self.peek(1)[1] == "=":
            self.out.append(pad + self.assignment())
        else:
            self.out.append(f"{pad}{self.expr()}")
        self.take(";")

    def translate(self):
        while self.peek()[1] in ("Param", "History", "Data", "Delay", "Buffer"):
            self.declaration(self.peek()[1])
        while self.peek()[0] != "eof":
            self.statement(1)
        body = "\n".join(self.out)
        outs = [f"out{k}" for k in range(1, getattr(self, "outs", 2) + 1)]
        # tick returns (out1, out2); tick_all every output (gen~ codeboxes with out3 and up)
        return (f"def tick_all(S, in1, in2, in3=0.0, in4=0.0):\n    {' = '.join(outs)} = 0.0\n"
                f"{body}\n    return ({', '.join(outs)},)\n"
                "def tick(S, in1, in2, in3=0.0, in4=0.0):\n    return tick_all(S, in1, in2, in3, in4)[:2]\n")


def _py_env(rnd):
    """The globals the translated Python runs in; noise() draws from rnd."""
    return {"math": math, "_peek": _peek, "_poke": _poke, "_wrap": _wrap, "_dim": _dim, "_channels": _channels,
            "_sign": _sign, "_fixnan": _fixnan,
            "_clamp": lambda x, a, b: min(max(x, a), b),
            "_noise": lambda: rnd.uniform(-1.0, 1.0)}


class Engine:
    """The engine. Engine(code) runs it compiled to C (CEngine, below) when GENEXPR_BACKEND is "c" (the default)
    and every construct of the code translates; otherwise, and always with GENEXPR_BACKEND=python, in Python.
    Both answer the same calls, sample for sample the same (tests/test_genexpr_c.py)."""

    def __new__(cls, src, samplerate=48000.0, seed=1):
        if cls is Engine and backend() == "c" and _c_program(src) is not None:
            return object.__new__(CEngine)
        return object.__new__(cls)

    def __init__(self, src, samplerate=48000.0, seed=1):
        t = Translator(src)
        self.source = t.translate()
        self.params = t.params
        self.samplerate = float(samplerate)
        rnd = random.Random(seed)
        env = _py_env(rnd)
        exec(compile(self.source, "<genexpr>", "exec"), env)
        self._tick = env["tick"]
        self._tick_all = env["tick_all"]
        for name, (kind, args) in t.state.items():
            if hasattr(self, name):
                raise SyntaxError(f"state name {name!r} clashes with the Engine")
            if kind == "Param":
                setattr(self, name, args[0] if args else 0.0)
            elif kind == "History":
                setattr(self, name, args[0] if args else 0.0)
            elif kind == "Data":
                setattr(self, name, Data(*args))
            elif kind == "Delay":
                setattr(self, name, Delay(args[0]))
            elif kind == "Buffer":                 # empty (one silent frame) until a test loads a sound
                setattr(self, name, Data(1, 1))

    def set(self, name, value):
        """Set a Param the way the gen~ Param inlet does: clamped to its range. A Param the build
        renamed in gen~ (lib/genlint.py: 'rate' -> 'rate_p') answers to its control's name too."""
        if name not in self.params and name + "_p" in self.params:
            name = name + "_p"
        _, lo, hi = self.params[name]
        if lo is not None:
            value = max(value, lo)
        if hi is not None:
            value = min(value, hi)
        setattr(self, name, float(value))

    def load_buffer(self, name, *channels):
        """Fill a Buffer as a dropped file would: one list of samples per channel."""
        d = Data(len(channels[0]), len(channels))
        d.ch = [list(map(float, c)) for c in channels]
        setattr(self, name, d)

    def tick(self, in1, in2):
        return self._tick(self, in1, in2)

    def tick_all(self, in1, in2, in3=0.0, in4=0.0):
        """Every output of the codebox, out1 first (inputs 3 and 4 for four-input codeboxes)."""
        return self._tick_all(self, in1, in2, in3, in4)

    def run(self, left, right=None):
        right = left if right is None else right
        outL, outR = [], []
        for a, b in zip(left, right):
            l, r = self._tick(self, a, b)
            outL.append(l)
            outR.append(r)
        return outL, outR

    def ticks(self, n, k=None):
        """n samples with silent inputs: each sample's first k outputs (every output if k is None), as tick_all
        gives them, one tuple a sample."""
        f = self._tick_all
        if k is None:
            return [f(self, 0.0, 0.0, 0.0, 0.0) for _ in range(n)]
        return [f(self, 0.0, 0.0, 0.0, 0.0)[:k] for _ in range(n)]


class PyEngine(Engine):
    """The Python engine whatever GENEXPR_BACKEND says: the reference (tests/test_genexpr_c.py)."""


# ---------------------------------------------------------------------------------------------------------------
# The C back end (plans/process/testing-speed.md, step 3). The same parse as Translator, written as C instead of
# Python, compiled once with the machine's cc and cached under .cache/genexpr/ by a hash of the C, of this file and
# of the compiler; run through ctypes. Python stays the reference: every operator is written to give what the
# Python above gives (Python's min/max with NaN, wrap as Python's float %, % as math.fmod, noise() from the same
# Mersenne Twister, seeded from random.Random(seed)'s state, OVERRUNS recorded), and the compiler is told not to
# reorder or fuse arithmetic (-ffp-contract=off, no fast-math, no builtin substitutions). Anything the C translation
# does not cover makes Engine() run that code in Python instead (status(code) says why), never an error.
#
#     GENEXPR_BACKEND=python   every Engine in Python (run_tests.py --python-engine sets it)
#     GENEXPR_CACHE=<dir>      where the compiled engines are kept (default <repo>/.cache/genexpr)
#
# A test that reaches into the Python function (e._tick_all, e._tick: counting its operations, swapping its noise)
# gets it: the engine turns into the Python one from that moment, its state as it stands.

import ctypes
import functools
import hashlib
import importlib.util
import os
import pickle
import sys
import subprocess
import tempfile
from array import array
from pathlib import Path

C_STATUS = {}      # sha1 of a code -> "c" or "python: <why>", for each code an Engine was asked to run
OCAP = 1 << 14     # OVERRUNS a C call records before it hands back to Python to empty them
CFLAGS = ["-Og", "-fPIC", "-shared", "-ffp-contract=off", "-fno-fast-math", "-fno-builtin", "-fno-math-errno",
          "-fexcess-precision=standard", "-fwrapv"]
_ROOT = Path(__file__).resolve().parents[1]


def backend():
    b = os.environ.get("GENEXPR_BACKEND", "c").strip().lower()
    return "python" if b in ("python", "py") else "c"


class Unsupported(Exception):
    """A construct the C translation doesn't cover: that code runs in Python."""


C_PRELUDE = r"""
#include <math.h>
#include <stdint.h>
#include <stddef.h>
typedef struct { double *p; long frames; long chans; } GData;
typedef struct { double *buf; long size; long w; } GDelay;
#define OCAP %(ocap)d
typedef struct {
    double *sc; GData *dt; GDelay *dl;
    uint32_t mt[624]; int mti; int nover;
    int okind[OCAP]; double oval[OCAP]; double osize[OCAP];
} Ctx;
long g_ctx_size(void) { return (long)sizeof(Ctx); }
static inline void g_over(Ctx *c, int kind, double v, double size) {
    if (c->nover < OCAP) { c->okind[c->nover] = kind; c->oval[c->nover] = v; c->osize[c->nover] = size; }
    c->nover++;
}
/* CPython's random.random(): MT19937, genrand_res53 */
static uint32_t g_genrand(Ctx *c) {
    static const uint32_t mag01[2] = {0x0U, 0x9908b0dfU};
    uint32_t y, *mt = c->mt;
    if (c->mti >= 624) {
        int kk;
        for (kk = 0; kk < 624 - 397; kk++) {
            y = (mt[kk] & 0x80000000U) | (mt[kk + 1] & 0x7fffffffU);
            mt[kk] = mt[kk + 397] ^ (y >> 1) ^ mag01[y & 0x1U];
        }
        for (; kk < 623; kk++) {
            y = (mt[kk] & 0x80000000U) | (mt[kk + 1] & 0x7fffffffU);
            mt[kk] = mt[kk + (397 - 624)] ^ (y >> 1) ^ mag01[y & 0x1U];
        }
        y = (mt[623] & 0x80000000U) | (mt[0] & 0x7fffffffU);
        mt[623] = mt[396] ^ (y >> 1) ^ mag01[y & 0x1U];
        c->mti = 0;
    }
    y = mt[c->mti++];
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680U;
    y ^= (y << 15) & 0xefc60000U;
    y ^= (y >> 18);
    return y;
}
static inline double g_noise(Ctx *c) {          /* rnd.uniform(-1.0, 1.0) = -1.0 + 2.0 * random() */
    uint32_t a = g_genrand(c) >> 5, b = g_genrand(c) >> 6;
    double r = (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    return -1.0 + 2.0 * r;
}
double g_draw(Ctx *c) { return g_noise(c); }   /* noise() for the Python function run on a CEngine's state */
/* Python's min(a, b) and max(a, b): the first unless the second compares below (above) it */
static inline double g_min(double a, double b) { return (b < a) ? b : a; }
static inline double g_max(double a, double b) { return (b > a) ? b : a; }
static inline double g_clamp(double x, double a, double b) { return g_min(g_max(x, a), b); }
static inline double g_pymod(double x, double r) {   /* Python's float x %% r */
    double m = fmod(x, r);
    if (m != 0.0) { if ((r < 0) != (m < 0)) m += r; }
    else m = copysign(0.0, r);
    return m;
}
static inline double g_wrap(double x, double lo, double hi) {
    double r = hi - lo;
    return (r != 0.0) ? lo + g_pymod(x - lo, r) : lo;
}
/* Python's floor() is an int, which has no -0: floor(-0.0) is 0 */
static inline double g_floor(double x) { return floor(x) + 0.0; }
static inline double g_sign(double x) { return (double)((x > 0) - (x < 0)); }
static inline double g_fixnan(double x) { return (x != x) ? 0.0 : x; }
static inline double g_peek(Ctx *c, GData *d, double i, double ch) {
    double fi = floor(i);
    int in = (fi >= 0.0 && fi < (double)d->frames);
    long cc;
    if (!in) { g_over(c, 1, fi, (double)d->frames); return 0.0; }
    cc = (long)ch;
    if (cc < 0 || cc >= d->chans) return 0.0;
    return d->p[cc * d->frames + (long)fi];
}
static inline double g_poke(Ctx *c, GData *d, double v, double i, double ch) {
    double fi = floor(i);
    int in = (fi >= 0.0 && fi < (double)d->frames);
    long cc;
    if (!in) { g_over(c, 2, fi, (double)d->frames); return 0.0; }
    cc = (long)ch;
    if (cc >= 0 && cc < d->chans) d->p[cc * d->frames + (long)fi] = v;
    return 0.0;
}
static inline double g_dread(Ctx *c, GDelay *d, double t) {
    double hi = d->size - 1.0, m, frac, a, b;
    long i, ia, ib;
    if (t > hi) g_over(c, 0, t, (double)d->size);
    m = g_min(g_max(t, 1.0), hi);
    i = (long)m;
    frac = m - (double)i;
    ia = (d->w - i) %% d->size; if (ia < 0) ia += d->size;
    ib = (d->w - i - 1) %% d->size; if (ib < 0) ib += d->size;
    a = d->buf[ia]; b = d->buf[ib];
    return a + (b - a) * frac;
}
static inline double g_dwrite(GDelay *d, double x) {
    d->buf[d->w] = x;
    d->w = (d->w + 1) %% d->size;
    return 0.0;
}
"""

# tick_all and tick callable from Python directly (a CPython extension in the same library: a third of ctypes' cost
# a call), when the machine has Python's headers; OVERRUNS appended to as the Python engine does.
C_PYEXT = r"""
#ifdef G_PYEXT
#define PY_SSIZE_T_CLEAN
#include <Python.h>
static PyObject *g_overruns = NULL, *g_names[3] = {NULL, NULL, NULL};
static int g_report(Ctx *c) {
    int j, n = c->nover < OCAP ? c->nover : OCAP;
    for (j = 0; j < n; j++) {
        int k = c->okind[j];
        PyObject *v = k == 0 ? PyFloat_FromDouble(c->oval[j]) : PyLong_FromDouble(c->oval[j]);
        PyObject *s = PyLong_FromDouble(c->osize[j]), *t;
        if (!v || !s) { Py_XDECREF(v); Py_XDECREF(s); return -1; }
        t = PyTuple_Pack(3, g_names[k], v, s);
        Py_DECREF(v); Py_DECREF(s);
        if (!t || PyList_Append(g_overruns, t) < 0) { Py_XDECREF(t); return -1; }
        Py_DECREF(t);
    }
    c->nover = 0;
    return 0;
}
static PyObject *g_run(PyObject *const *args, Py_ssize_t nargs, int all) {
    Ctx *c;
    double in[4] = {0.0, 0.0, 0.0, 0.0}, out[G_NOUTS];
    Py_ssize_t i, n = all ? G_NOUTS : 2;
    PyObject *t;
    if (nargs < 3 || nargs > (all ? 5 : 3)) {
        PyErr_Format(PyExc_TypeError, "tick%s() takes %s inputs", all ? "_all" : "", all ? "2 to 4" : "2");
        return NULL;
    }
    c = (Ctx *)PyLong_AsVoidPtr(args[0]);
    if (!c) return NULL;
    for (i = 1; i < nargs; i++) {
        in[i - 1] = PyFloat_AsDouble(args[i]);
        if (in[i - 1] == -1.0 && PyErr_Occurred()) return NULL;
    }
    c->nover = 0;
    g_body(c, in[0], in[1], in[2], in[3], out);
    if (c->nover && g_report(c) < 0) return NULL;
    t = PyTuple_New(n);
    if (!t) return NULL;
    for (i = 0; i < n; i++) {
        PyObject *x = PyFloat_FromDouble(out[i]);
        if (!x) { Py_DECREF(t); return NULL; }
        PyTuple_SET_ITEM(t, i, x);
    }
    return t;
}
static PyObject *g_py_tick_all(PyObject *m, PyObject *const *a, Py_ssize_t n) { (void)m; return g_run(a, n, 1); }
static PyObject *g_py_tick(PyObject *m, PyObject *const *a, Py_ssize_t n) { (void)m; return g_run(a, n, 0); }
static PyObject *g_py_init(PyObject *m, PyObject *const *a, Py_ssize_t n) {
    int k;
    (void)m;
    if (n != 4 || !PyList_Check(a[0])) { PyErr_SetString(PyExc_TypeError, "init(OVERRUNS, three names)"); return NULL; }
    Py_INCREF(a[0]); Py_XDECREF(g_overruns); g_overruns = a[0];
    for (k = 0; k < 3; k++) { Py_INCREF(a[k + 1]); Py_XDECREF(g_names[k]); g_names[k] = a[k + 1]; }
    Py_RETURN_NONE;
}
static PyMethodDef g_methods[] = {
    {"tick_all", (PyCFunction)(void (*)(void))g_py_tick_all, METH_FASTCALL, NULL},
    {"tick", (PyCFunction)(void (*)(void))g_py_tick, METH_FASTCALL, NULL},
    {"init", (PyCFunction)(void (*)(void))g_py_init, METH_FASTCALL, NULL},
    {NULL, NULL, 0, NULL}};
static struct PyModuleDef g_module = {PyModuleDef_HEAD_INIT, "genexpr_engine", NULL, -1, g_methods,
                                      NULL, NULL, NULL, NULL};
PyMODINIT_FUNC PyInit_genexpr_engine(void) { return PyModule_Create(&g_module); }
#endif
"""

C_FUNCS = {   # name: (C function, number of arguments)
    "tanh": ("tanh", 1), "sin": ("sin", 1), "cos": ("cos", 1), "tan": ("tan", 1), "atan2": ("atan2", 2),
    "exp": ("exp", 1), "sqrt": ("__builtin_sqrt", 1), "pow": ("pow", 2), "abs": ("__builtin_fabs", 1),
    "floor": ("g_floor", 1), "log": ("log", 1), "log2": ("log2", 1), "log10": ("log10", 1),
    "clamp": ("g_clamp", 3), "wrap": ("g_wrap", 3), "sign": ("g_sign", 1), "fixnan": ("g_fixnan", 1),
    "noise": ("g_noise(c)", 0),
}
C_CONSTANTS = {"pi": repr(math.pi), "twopi": repr(2 * math.pi), "halfpi": repr(math.pi / 2)}

# An expression in C is (code, effects, reads): effects, it writes (noise(), poke, a Delay's write); reads, it reads
# what such a write changes. C leaves the order of a call's arguments and of an operator's operands open, Python goes
# left to right: the parts are put in order (a GCC statement expression) where it could matter.


class CTranslator(Translator):
    def __init__(self, src, state, toks=None):
        super().__init__(src, toks)
        self.cstate = state            # name -> (kind, index)
        self.locals = set()
        self.ntmp = 0
        self.lines = []

    def seq(self, parts, build):
        flags = (any(p[1] for p in parts), any(p[2] for p in parts))
        if not flags[0] or sum(1 for p in parts if p[1] or p[2]) < 2:
            return (build([p[0] for p in parts]),) + flags
        names, decl = [], []
        for p in parts:
            t = f"_t{self.ntmp}"
            self.ntmp += 1
            decl.append(f"double {t} = ({p[0]});")
            names.append(t)
        return (f"({{ {' '.join(decl)} {build(names)}; }})",) + flags

    # ---- expressions
    def expr(self):
        cond = self.binop(0)
        if self.peek()[1] == "?":
            self.take("?")
            a = self.expr()
            self.take(":")
            b = self.expr()
            return (f"(({cond[0]}) ? ({a[0]}) : ({b[0]}))", cond[1] or a[1] or b[1], cond[2] or a[2] or b[2])
        return cond

    def binop(self, level):
        if level == len(BINOPS):
            return self.unary()
        left = self.binop(level + 1)
        while self.peek()[1] in BINOPS[level]:
            op = self.take()[1]
            right = self.binop(level + 1)
            if op in ("||", "&&"):        # short-circuit, left first, as Python's and/or
                left = (f"((({left[0]}) {op} ({right[0]})) ? 1.0 : 0.0)", left[1] or right[1], left[2] or right[2])
            elif op == "%":
                left = self.seq([left, right], lambda a: f"fmod({a[0]}, {a[1]})")
            elif op in ("==", "!=", "<", ">", "<=", ">="):
                left = self.seq([left, right], lambda a, op=op: f"((double)(({a[0]}) {op} ({a[1]})))")
            else:
                left = self.seq([left, right], lambda a, op=op: f"(({a[0]}) {op} ({a[1]}))")
        return left

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            u = self.unary()
            return (f"(-({u[0]}))", u[1], u[2])
        if self.peek()[1] == "!":
            self.take()
            u = self.unary()
            return (f"(({u[0]}) ? 0.0 : 1.0)", u[1], u[2])
        return self.primary()

    def primary(self):
        kind, val, line = self.take()
        if kind == "num":
            v = float(val)
            if not math.isfinite(v):
                raise Unsupported(f"line {line}: the number {val}")
            return (repr(v), False, False)
        if val == "(":
            e = self.expr()
            self.take(")")
            return (f"({e[0]})", e[1], e[2])
        if kind != "id":
            raise SyntaxError(f"line {line}: unexpected {val!r}")
        if self.peek()[1] == ".":
            self.take(".")
            method = self.take()[1]
            k = self.cstate.get(val, ("", 0))
            if k[0] != "Delay" or method not in ("read", "write"):
                raise Unsupported(f"line {line}: {val}.{method}")
            a = self.args()
            if len(a) != 1:
                raise Unsupported(f"line {line}: {val}.{method} with {len(a)} arguments")
            if method == "read":
                return (f"g_dread(c, &dl[{k[1]}], {a[0][0]})", a[0][1], True)
            return (f"g_dwrite(&dl[{k[1]}], {a[0][0]})", True, a[0][2])
        if self.peek()[1] == "(":
            if val not in BUILTINS:
                raise SyntaxError(f"line {line}: unknown function {val}")
            return self.call(val, self.args(), line)
        return self.name(val, line)

    def data_ref(self, a, line):
        if not a[0].startswith("@D:") or self.cstate[a[0][3:]][0] not in ("Data", "Buffer"):
            raise Unsupported(f"line {line}: a Data or Buffer's name expected, got {a[0]}")
        return f"&dt[{self.cstate[a[0][3:]][1]}]"

    def call(self, val, a, line):
        if val in ("min", "max"):
            if len(a) < 2:
                raise Unsupported(f"line {line}: {val} with {len(a)} arguments")

            def build(x, f="g_" + val):
                out = x[0]
                for y in x[1:]:
                    out = f"{f}({out}, {y})"
                return out
            return self.seq(a, build)
        if val in ("peek", "poke"):
            if not a:
                raise Unsupported(f"line {line}: {val}()")
            d = self.data_ref(a[0], line)
            rest = a[1:]
            if val == "peek":
                if len(rest) not in (1, 2):
                    raise Unsupported(f"line {line}: peek with {len(a)} arguments")
                rest = rest + [("0.0", False, False)] * (2 - len(rest))
                e = self.seq(rest, lambda x: f"g_peek(c, {d}, {x[0]}, {x[1]})")
                return (e[0], e[1], True)
            if len(rest) not in (2, 3):
                raise Unsupported(f"line {line}: poke with {len(a)} arguments")
            rest = rest + [("0.0", False, False)] * (3 - len(rest))
            e = self.seq(rest, lambda x: f"g_poke(c, {d}, {x[0]}, {x[1]}, {x[2]})")
            return (e[0], True, e[2])
        if val in ("dim", "channels"):
            if len(a) != 1:
                raise Unsupported(f"line {line}: {val} with {len(a)} arguments")
            d = self.data_ref(a[0], line)
            return (f"((double)({d})->{'frames' if val == 'dim' else 'chans'})", False, True)
        if val not in C_FUNCS:
            raise Unsupported(f"line {line}: {val}")
        f, n = C_FUNCS[val]
        if len(a) != n:
            raise Unsupported(f"line {line}: {val} with {len(a)} arguments")
        if val == "noise":
            return (f, True, True)
        return self.seq(a, lambda x: f"{f}({', '.join(x)})")

    def name(self, val, line):
        if val in self.cstate:
            kind, k = self.cstate[val]
            if kind in ("Param", "History"):
                return (f"sc[{k}]", False, False)
            return (f"@D:{val}", False, False)        # a Data, Buffer or Delay: only as peek/poke/dim's first
        if val in C_CONSTANTS:
            return (f"({C_CONSTANTS[val]})", False, False)
        if val == "samplerate":
            return ("sc[0]", False, False)
        if val in ("in1", "in2", "in3", "in4"):
            return (val, False, False)
        if re.fullmatch(r"out[1-9]\d*", val):
            self.outs = max(getattr(self, "outs", 2), int(val[3:]))
            return (val, False, False)
        self.locals.add(val)
        return ("v_" + val, False, False)

    # ---- statements
    def block(self, indent):
        if self.peek()[1] == "{":
            self.take("{")
            while self.peek()[1] != "}":
                self.statement(indent)
            self.take("}")
        else:
            self.statement(indent)

    def assignment(self):
        kind, val, line = self.take()
        if kind != "id":
            raise SyntaxError(f"line {line}: expected a name, got {val!r}")
        self.take("=")
        target = self.name(val, line)[0]
        if not re.fullmatch(r"sc\[\d+\]|v_\w+|out\d+|in[1-4]", target) or self.cstate.get(val, ("",))[0] == "Param":
            raise Unsupported(f"line {line}: assigning to {val}")
        return f"{target} = {self.expr()[0]};"

    def statement(self, indent):
        pad = "    " * indent
        kind, val, line = self.peek()
        if val == "for":
            self.take()
            self.take("(")
            self.lines.append(pad + self.assignment())
            self.take(";")
            cond = self.expr()
            self.take(";")
            step = self.assignment()
            self.take(")")
            self.lines.append(f"{pad}while ({cond[0]}) {{")
            self.block(indent + 1)
            self.lines.append("    " * (indent + 1) + step)
            self.lines.append(pad + "}")
            return
        if val == "if":
            self.take()
            self.take("(")
            cond = self.expr()
            self.take(")")
            self.lines.append(f"{pad}if ({cond[0]}) {{")
            self.block(indent + 1)
            while self.peek()[1] == "else":
                self.take()
                if self.peek()[1] == "if":
                    self.take()
                    self.take("(")
                    cond = self.expr()
                    self.take(")")
                    self.lines.append(f"{pad}}} else if ({cond[0]}) {{")
                else:
                    self.lines.append(f"{pad}}} else {{")
                self.block(indent + 1)
            self.lines.append(pad + "}")
            return
        if kind == "id" and self.peek(1)[1] == "=":
            self.lines.append(pad + self.assignment())
        else:
            self.lines.append(f"{pad}(void)({self.expr()[0]});")
        self.take(";")

    def translate(self):
        while self.peek()[1] in ("Param", "History", "Data", "Delay", "Buffer"):
            self.declaration(self.peek()[1])
        while self.peek()[0] != "eof":
            self.statement(1)
        body = "\n".join(self.lines)
        if "@D:" in body:
            raise Unsupported("a Data, Buffer or Delay used as a number")
        nouts = getattr(self, "outs", 2)
        outs = [f"out{k}" for k in range(1, nouts + 1)]
        decl = "".join(f"    double v_{v} = 0.0;\n" for v in sorted(self.locals))
        src = (C_PRELUDE % {"ocap": OCAP}
               + "static void g_body(Ctx *c, double in1, double in2, double in3, double in4, double *out) {\n"
               "    double *sc = c->sc; GData *dt = c->dt; GDelay *dl = c->dl;\n"
               "    (void)sc; (void)dt; (void)dl;\n"
               f"    double {', '.join(o + ' = 0.0' for o in outs)};\n" + decl + body + "\n"
               + "".join(f"    out[{k}] = {o};\n" for k, o in enumerate(outs)) + "}\n"
               "int g_tick(Ctx *c, double in1, double in2, double in3, double in4, double *out) {\n"
               "    c->nover = 0;\n    g_body(c, in1, in2, in3, in4, out);\n    return c->nover;\n}\n"
               "/* n samples (an input NULL: silent), the outputs one sample after another; stops early, after a\n"
               "   sample, once OVERRUNS fill half the log; returns the samples run */\n"
               "long g_block(Ctx *c, const double *i1, const double *i2, const double *i3, const double *i4,\n"
               "             long n, double *out) {\n"
               "    long k;\n    c->nover = 0;\n"
               "    for (k = 0; k < n; k++) {\n"
               "        g_body(c, i1 ? i1[k] : 0.0, i2 ? i2[k] : 0.0, i3 ? i3[k] : 0.0, i4 ? i4[k] : 0.0,\n"
               f"               out + k * {nouts});\n"
               "        if (c->nover > OCAP / 2) return k + 1;\n"
               "    }\n    return n;\n}\n"
               f"#define G_NOUTS {nouts}\n" + C_PYEXT)
        return src, nouts


class _GData(ctypes.Structure):
    _fields_ = [("p", ctypes.POINTER(ctypes.c_double)), ("frames", ctypes.c_long), ("chans", ctypes.c_long)]


class _GDelay(ctypes.Structure):
    _fields_ = [("buf", ctypes.POINTER(ctypes.c_double)), ("size", ctypes.c_long), ("w", ctypes.c_long)]


class _Ctx(ctypes.Structure):
    _fields_ = [("sc", ctypes.POINTER(ctypes.c_double)), ("dt", ctypes.POINTER(_GData)),
                ("dl", ctypes.POINTER(_GDelay)), ("mt", ctypes.c_uint32 * 624), ("mti", ctypes.c_int),
                ("nover", ctypes.c_int), ("okind", ctypes.c_int * OCAP), ("oval", ctypes.c_double * OCAP),
                ("osize", ctypes.c_double * OCAP)]


_CC = []


def _cc_version():
    if not _CC:
        try:
            r = subprocess.run(["cc", "--version"], capture_output=True, text=True, timeout=30)
            _CC.append(r.stdout.splitlines()[0] if r.returncode == 0 and r.stdout else None)
        except (OSError, subprocess.SubprocessError):
            _CC.append(None)
    return _CC[0]


_SELF = []


def _key(*parts):
    """A hash of parts and of this file (a change here builds every engine again)."""
    if not _SELF:
        _SELF.append(Path(__file__).read_text())
    h = hashlib.sha256()
    for part in parts + (_SELF[0],):
        h.update(part.encode())
        h.update(b"\0")
    return h.hexdigest()[:32]


def _cache_dir():
    return Path(os.environ.get("GENEXPR_CACHE") or _ROOT / ".cache" / "genexpr")


def _pyext_flags():
    """The flags that build tick_all as a Python extension too, or [] (no Python headers: ctypes only)."""
    import sysconfig
    inc = sysconfig.get_paths().get("include")
    return ["-DG_PYEXT", f"-I{inc}"] if inc and (Path(inc) / "Python.h").exists() else []


def _compile(csrc, extra=()):
    """The path of the compiled library for csrc (built once, kept in the cache), or raises Unsupported."""
    cc = _cc_version()
    if cc is None:
        raise Unsupported("no C compiler (cc)")
    flags = CFLAGS + list(extra)
    key = _key(csrc, " ".join(flags), cc, sys.version if extra else "")
    cache = _cache_dir()
    so = cache / f"{key}.so"
    if so.exists():
        return so
    cache.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=key + "-", suffix=".c", dir=cache)
    with os.fdopen(fd, "w") as f:
        f.write(csrc)
    out = tmp[:-2] + ".so"
    try:
        r = subprocess.run(["cc", *flags, "-o", out, tmp, "-lm"], capture_output=True, text=True, timeout=900)
        if r.returncode:
            errs = [x for x in r.stderr.splitlines() if "error" in x] or r.stderr.splitlines() or ["?"]
            raise Unsupported("cc failed: " + errs[0].split(": ", 1)[-1][:300])
        os.replace(out, so)           # atomic: two processes building the same engine both end with one file
    except (OSError, subprocess.SubprocessError) as ex:
        raise Unsupported(f"cc: {ex}")
    finally:
        for p in (tmp, out):
            try:
                os.unlink(p)
            except OSError:
                pass
    return so


class _CProgram:
    """One code, translated and compiled: what every CEngine of it shares."""

    def __init__(self, src):
        meta_path = _cache_dir() / f"{_key(src, 'meta')}.meta"
        try:
            meta = pickle.loads(meta_path.read_bytes())
        except Exception:
            meta = None
        if meta is None:
            meta = self.translate(src)
        self.__dict__.update(meta)
        self.lib, self.fast = None, None
        ext = _pyext_flags()
        if ext:
            try:
                path = _compile(self.csource, ext)
                spec = importlib.util.spec_from_file_location("genexpr_engine", path)
                self.fast = importlib.util.module_from_spec(spec)
                self.fast.init(OVERRUNS, *_OVER_NAMES)
                self.lib = ctypes.CDLL(str(path))
            except Exception:
                self.lib, self.fast = None, None
        if self.lib is None:
            self.lib = ctypes.CDLL(str(_compile(self.csource)))
        if self.lib.g_ctx_size() != ctypes.sizeof(_Ctx):
            raise Unsupported("the C and ctypes layouts differ")
        self.tick = self.lib.g_tick
        self.tick.argtypes = [ctypes.c_void_p] + [ctypes.c_double] * 4 + [ctypes.c_void_p]
        self.tick.restype = ctypes.c_int
        self.block = self.lib.g_block
        self.block.argtypes = [ctypes.c_void_p] * 5 + [ctypes.c_long, ctypes.c_void_p]
        self.block.restype = ctypes.c_long
        self.draw = self.lib.g_draw
        self.draw.argtypes = [ctypes.c_void_p]
        self.draw.restype = ctypes.c_double
        self._py = None
        if not meta_path.exists():
            try:
                fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=meta_path.parent)
                with os.fdopen(fd, "wb") as f:
                    f.write(pickle.dumps(meta))
                os.replace(tmp, meta_path)
            except OSError:
                pass

    def translate(self, src):
        t = Translator(src)
        self.py_source = t.translate()
        self.params = t.params
        self.decl = t.state
        clash = set(dir(Engine)) | {"source", "params", "samplerate", "_tick", "_tick_all"}
        for name in t.state:
            if name in clash:
                raise Unsupported(f"state name {name!r} clashes with the Engine")
        self.sidx, self.didx, self.lidx = {"samplerate": 0}, {}, {}
        cstate = {}
        for name, (kind, args) in t.state.items():
            idx = self.sidx if kind in ("Param", "History") else self.didx if kind in ("Data", "Buffer") else self.lidx
            idx[name] = len(idx)
            cstate[name] = (kind, idx[name])
            if kind == "Delay" and int(args[0]) < 1:
                raise Unsupported(f"Delay {name} of size {args[0]}")
        self.csource, self.nouts = CTranslator(src, cstate, t.toks).translate()
        return {k: getattr(self, k) for k in ("py_source", "params", "decl", "sidx", "didx", "lidx", "csource",
                                              "nouts")}

    def python_code(self):
        if self._py is None:
            self._py = compile(self.py_source, "<genexpr>", "exec")
        return self._py


_PROGRAMS = {}


def _c_program(src):
    """The compiled program for src, or None (it runs in Python; C_STATUS says why)."""
    if src in _PROGRAMS:
        return _PROGRAMS[src]
    key = hashlib.sha1(src.encode()).hexdigest()
    try:
        prog = _CProgram(src)
        C_STATUS[key] = "c"
    except SyntaxError:
        prog = None                  # Python's own translation says what's wrong (Engine raises it)
        C_STATUS[key] = "python: the code does not translate"
    except Unsupported as ex:
        prog = None
        C_STATUS[key] = f"python: {ex}"
    except Exception as ex:          # the C back end never fails a test: that code runs in Python
        prog = None
        C_STATUS[key] = f"python: {type(ex).__name__}: {ex}"
    _PROGRAMS[src] = prog
    return prog


def status(src):
    """'c' if Engine(src) runs compiled, else 'python: <why>'."""
    if backend() != "c":
        return "python: GENEXPR_BACKEND=python"
    _c_program(src)
    return C_STATUS[hashlib.sha1(src.encode()).hexdigest()]


def _doubles(n):
    a = (ctypes.c_double * max(int(n), 1))()
    return a, memoryview(a).cast("B").cast("d")


class CData:
    """A Data or Buffer of a CEngine: frames, channels, and ch[c][i] read and written in place."""

    def __init__(self, frames, channels=1):
        self.frames, self.channels = int(frames), int(channels)
        self._arr, mv = _doubles(self.frames * self.channels)
        self.ch = [mv[c * self.frames:(c + 1) * self.frames] for c in range(self.channels)]


class CDelay:
    """A Delay of a CEngine: size, buf (in place) and w."""

    def __init__(self, size, slot):
        self.size = int(size)
        self._arr, self.buf = _doubles(self.size)
        self._slot = slot

    @property
    def w(self):
        return self._slot.w

    @w.setter
    def w(self, v):
        self._slot.w = int(v)

    read = Delay.read              # (the Python function run on this state: the same code, on buf and w)
    write = Delay.write


_NOISE = (lambda r=None: r.uniform(-1.0, 1.0)).__code__


def _own_stream(f):
    """The random.Random f draws noise from when f is `lambda r=<a Random>: r.uniform(-1.0, 1.0)` (a test giving
    an engine a noise stream of its own); else None."""
    c = getattr(f, "__code__", None)
    if c is None or (c.co_code, c.co_consts, c.co_names) != (_NOISE.co_code, _NOISE.co_consts, _NOISE.co_names):
        return None
    d = getattr(f, "__defaults__", None)
    if not d or len(d) != 1 or f.__kwdefaults__ or f.__closure__ or type(d[0]) is not random.Random:
        return None
    return d[0]


class _Globals(dict):
    """The globals of a CEngine's Python function (e._tick_all): noise() given a stream of its own, the lambda
    above, stays in C (the stream's state moves there); anything else replaced (math, to count) hands the engine to
    Python, which then runs with it."""

    engine = None

    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        e = self.engine
        if e is None or "_prog" not in e.__dict__:
            return
        r = _own_stream(v) if k == "_noise" else None
        if r is not None:
            e._noise_from(r)
        else:
            e._to_python()


_OVER_NAMES = ("Delay read", "Data peek", "Data poke")
_C_ATTRS = ("_prog", "_sc", "_objs", "_dt", "_dl", "_ctx", "_ctxa", "_out", "_outa", "_outmv", "_tickf", "_blockf",
           "_csrc",
           "tick_all", "tick")


class CEngine(Engine):
    """Engine, compiled (see above). Its state lives in C; reading or setting a Param or a History, a Data's ch,
    load_buffer, tick, tick_all, run and ticks work as on the Python engine."""

    def __init__(self, src, samplerate=48000.0, seed=1):
        prog = _c_program(src)
        if prog is None:
            raise Unsupported(status(src))
        d = self.__dict__
        d["_prog"] = prog
        d["source"] = prog.py_source
        d["params"] = dict(prog.params)
        d["_csrc"] = prog.csource
        sc = (ctypes.c_double * len(prog.sidx))()
        sc[0] = float(samplerate)
        dt = (_GData * max(len(prog.didx), 1))()
        dl = (_GDelay * max(len(prog.lidx), 1))()
        objs = {}
        d["_sc"], d["_objs"], d["_dt"], d["_dl"] = sc, objs, dt, dl
        for name, (kind, args) in prog.decl.items():
            if kind in ("Param", "History"):
                sc[prog.sidx[name]] = args[0] if args else 0.0
            elif kind == "Data":
                self._put_data(name, CData(*args))
            elif kind == "Buffer":                 # empty (one silent frame) until a test loads a sound
                self._put_data(name, CData(1, 1))
            else:
                k = prog.lidx[name]
                o = CDelay(args[0], dl[k])
                dl[k].buf = ctypes.cast(o._arr, ctypes.POINTER(ctypes.c_double))
                dl[k].size, dl[k].w = o.size, 0
                objs[name] = o
        ctx = _Ctx()
        ctx.sc = ctypes.cast(sc, ctypes.POINTER(ctypes.c_double))
        ctx.dt = ctypes.cast(dt, ctypes.POINTER(_GData))
        ctx.dl = ctypes.cast(dl, ctypes.POINTER(_GDelay))
        _, mt, _ = random.Random(seed).getstate()     # noise(): the Python engine's generator, as it starts
        ctx.mt[:] = mt[:624]
        ctx.mti = mt[624]
        d["_ctx"], d["_ctxa"] = ctx, ctypes.addressof(ctx)
        out = (ctypes.c_double * prog.nouts)()
        d["_out"], d["_outa"], d["_outmv"] = out, ctypes.addressof(out), memoryview(out).cast("B").cast("d")
        d["_tickf"], d["_blockf"] = prog.tick, prog.block
        if prog.fast is not None:          # straight into C: these shadow the methods below
            d["tick_all"] = functools.partial(prog.fast.tick_all, d["_ctxa"])
            d["tick"] = functools.partial(prog.fast.tick, d["_ctxa"])

    def _put_data(self, name, o):
        slot = self._dt[self._prog.didx[name]]
        slot.p = ctypes.cast(o._arr, ctypes.POINTER(ctypes.c_double))
        slot.frames, slot.chans = o.frames, o.channels
        self._objs[name] = o

    def __getattr__(self, name):
        d = self.__dict__
        prog = d.get("_prog")
        if prog is not None:
            if name in ("_tick", "_tick_all"):
                return self._python_env()[name[1:]]
            k = prog.sidx.get(name)
            if k is not None:
                return d["_sc"][k]
            o = d["_objs"].get(name)
            if o is not None:
                return o
        raise AttributeError(name)

    def __setattr__(self, name, value):
        d = self.__dict__
        prog = d.get("_prog")
        if prog is not None:
            k = prog.sidx.get(name)
            if k is not None:
                d["_sc"][k] = value
                return
            if name in d["_objs"]:              # a whole Data or Delay replaced: from now on, in Python
                self._to_python()
        object.__setattr__(self, name, value)

    def _python_env(self):
        """The Python function's globals, run on this engine's C state (made once): noise() draws from C's."""
        d = self.__dict__
        if "_env" not in d:
            draw, a = d["_prog"].draw, d["_ctxa"]
            env = _Globals(_py_env(None))
            d["_cdraw"] = lambda: draw(a)
            dict.__setitem__(env, "_noise", d["_cdraw"])
            exec(d["_prog"].python_code(), env)
            env.engine = self
            d["_env"] = env
        return d["_env"]

    def _noise_from(self, r):
        """noise() from now on as r.uniform(-1.0, 1.0) would draw it, in C (r kept, to give its state back)."""
        st = r.getstate()[1]
        self._ctx.mt[:] = st[:624]
        self._ctx.mti = st[624]
        self.__dict__["_stream"] = r

    def _to_python(self):
        """From now on this engine is the Python one, its state as it stands (noise() goes on where C was)."""
        d = self.__dict__
        prog, ctx = d["_prog"], d["_ctx"]
        if ctx.nover:
            self._drain()
        mt = (3, tuple(ctx.mt) + (ctx.mti,), None)
        env = self._python_env()
        env.engine = None
        noise = env["_noise"]
        if noise is d.get("_cdraw"):
            rnd = random.Random()
            rnd.setstate(mt)
            dict.__setitem__(env, "_noise", lambda: rnd.uniform(-1.0, 1.0))
        elif d.get("_stream") is not None and _own_stream(noise) is d["_stream"]:
            d["_stream"].setstate(mt[:2] + (d["_stream"].getstate()[2],))
        state = {name: d["_sc"][k] for name, k in prog.sidx.items()}
        for name in prog.didx:
            o = d["_objs"][name]
            py = Data.__new__(Data)
            py.frames, py.channels = o.frames, o.channels
            py.ch = [c.tolist() for c in o.ch]
            state[name] = py
        for name in prog.lidx:
            o = d["_objs"][name]
            py = Delay.__new__(Delay)
            py.size, py.buf, py.w = o.size, o.buf.tolist(), o.w
            state[name] = py
        for k in _C_ATTRS + ("_env", "_stream", "_cdraw"):
            d.pop(k, None)
        d.update(state)
        d["_tick"], d["_tick_all"] = env["tick"], env["tick_all"]
        object.__setattr__(self, "__class__", Engine)

    def _drain(self):
        c = self._ctx
        for j in range(min(c.nover, OCAP)):
            k = c.okind[j]
            v = c.oval[j]
            OVERRUNS.append((_OVER_NAMES[k], v if k == 0 else int(v), int(c.osize[j])))
        c.nover = 0

    def load_buffer(self, name, *channels):
        if name not in self._prog.didx:
            self._to_python()
            return Engine.load_buffer(self, name, *channels)
        chans = [array("d", map(float, c)) for c in channels]
        frames = len(chans[0])
        o = CData(frames, len(chans))
        for c, a in enumerate(chans):
            m = min(len(a), frames)
            if m:
                ctypes.memmove(ctypes.addressof(o._arr) + 8 * c * frames, a.buffer_info()[0], 8 * m)
        self._put_data(name, o)

    def tick_all(self, in1, in2, in3=0.0, in4=0.0):
        if self._tickf(self._ctxa, in1, in2, in3, in4, self._outa):
            self._drain()
        return tuple(self._outmv.tolist())

    def tick(self, in1, in2):
        if self._tickf(self._ctxa, in1, in2, 0.0, 0.0, self._outa):
            self._drain()
        return tuple(self._outmv.tolist()[:2])

    def _blocks(self, ins, n):
        """Runs n samples; ins: up to four array('d')s (missing ones silent). The outputs, sample after sample."""
        nouts = self._prog.nouts
        out = array("d", bytes(8 * nouts * max(n, 1)))
        base = out.buffer_info()[0]
        ptrs = [a.buffer_info()[0] if len(a) else None for a in ins] + [None] * (4 - len(ins))
        done = 0
        while done < n:
            k = self._blockf(self._ctxa, *[p + 8 * done if p else None for p in ptrs], n - done,
                             base + 8 * nouts * done)
            if self._ctx.nover:
                self._drain()
            done += k
        return out

    def run(self, left, right=None):
        right = left if right is None else right
        L, R = array("d", map(float, left)), array("d", map(float, right))
        n = min(len(L), len(R))
        if not n:
            return [], []
        out = self._blocks([L[:n], R[:n]], n)
        nouts = self._prog.nouts
        return out[0:nouts * n:nouts].tolist(), out[1:nouts * n:nouts].tolist()

    def ticks(self, n, k=None):
        if n <= 0:
            return []
        nouts = self._prog.nouts
        out = self._blocks([], n)
        k = nouts if k is None else max(0, min(k, nouts))
        if not k:
            return [()] * n
        return list(zip(*[out[j:nouts * n:nouts].tolist() for j in range(k)]))


# ---- compiled helpers for the tests' own analysis, written to give Python's results bit for bit (the same
# operations in the same order, the same libm): lib/synthtest.py's mag() spends longer than the engine once the
# engine is in C. None when there is no compiler: the caller then does it in Python.

HELPERS_C = r"""
#include <math.h>
/* lib/synthtest.py's mag(): the windowed sums, before the hypot */
void g_mag(const double *ys, long n, double f, double fs, double *out) {
    double re = 0.0, im = 0.0;
    const double tp = 6.283185307179586;        /* 2 * math.pi */
    long i;
    for (i = 0; i < n; i++) {
        double y = ys[i];
        double w = 0.5 - 0.5 * cos(tp * (double)i / (double)n);
        re = re + y * w * cos(tp * f * (double)i / fs);
        im = im + y * w * sin(tp * f * (double)i / fs);
    }
    out[0] = re;
    out[1] = im;
}
"""
_HELPERS = []


def _helpers():
    if not _HELPERS:
        lib = None
        if backend() == "c":
            try:
                lib = ctypes.CDLL(str(_compile(HELPERS_C)))
                lib.g_mag.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_double, ctypes.c_double,
                                      ctypes.c_void_p]
                lib.g_mag.restype = None
            except Exception:
                lib = None
        _HELPERS.append(lib)
    return _HELPERS[0]


def mag_sums(ys, f, fs):
    """(re, im) of lib/synthtest.py's mag() for ys, computed in C exactly as that loop does; None when it can't
    be (no compiler, GENEXPR_BACKEND=python, values that aren't plain numbers)."""
    lib = _helpers()
    if lib is None or not len(ys) or not all(isinstance(v, (int, float)) for v in (f, fs)):
        return None
    try:
        a = array("d", ys)
    except TypeError:
        return None
    out = (ctypes.c_double * 2)()
    lib.g_mag(a.buffer_info()[0], len(a), f, fs, ctypes.addressof(out))
    return out[0], out[1]


def in_python(f):
    """A test function whose engines run in Python whatever GENEXPR_BACKEND says: for the checks that time the
    simulator itself (their limits were set on the Python engine's costs, which follow the code's operations; in C
    the shared part of a voice weighs more, and a quarter second takes milliseconds)."""
    @functools.wraps(f)
    def wrapped(*a, **kw):
        old = os.environ.get("GENEXPR_BACKEND")
        os.environ["GENEXPR_BACKEND"] = "python"
        try:
            return f(*a, **kw)
        finally:
            if old is None:
                del os.environ["GENEXPR_BACKEND"]
            else:
                os.environ["GENEXPR_BACKEND"] = old
    return wrapped
