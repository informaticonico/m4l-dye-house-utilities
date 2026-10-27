"""gen~'s own names, which a codebox can't use as its variables or Params: Max's compiler reads
`gate`, `wave` or `mix` as the operator and stops ("function call missing '('"), the whole codebox
fails to compile and gen~ answers every message with "doesn't understand" (another device, Oct 1:
silent in Live). lib/genexpr.py runs such code happily, so the build checks it here.

    misused(code) -> sorted [(name, how)]: how is 'Param', 'History', 'Data', 'Delay' or 'variable'
    undefined(code) -> sorted [(name, line)]: names read but never declared or assigned (gen~ refuses them)

A Param that shares an operator's name keeps its control's name and is renamed in gen~ only
(dsp.GEN_ALIAS, lib/m4l.py's Patch.to_gen); a variable is simply renamed.
"""

import json
import re
from pathlib import Path

# gen~'s operators: Max's own GenExpr reference (catalog/max_reference.json, refreshed by tools/max_audit.py), so a
# name the reference gains is reserved here too (it lacked poltocar when this list was typed by hand), and the
# names Max was found to refuse beyond it (a probe, Oct 1: another device silent in Live)
REFUSED_IN_LIVE = {"f", "i", "r", "s", "maximum", "minimum"}
OPERATORS = set(json.loads((Path(__file__).resolve().parents[1] / "catalog" / "max_reference.json").read_text())["gen"]) \
    | REFUSED_IN_LIVE
CONSTANTS = set(("e E pi PI twopi TWOPI halfpi HALFPI invpi INVPI ln2 LN2 ln10 LN10 log2e LOG2E log10e LOG10E "
                 "sqrt2 SQRT2 sqrt1_2 SQRT1_2 degtorad DEGTORAD radtodeg RADTODEG phi PHI samplerate SAMPLERATE "
                 "vectorsize VECTORSIZE").split())
OPERATORS -= CONSTANTS
RESERVED = OPERATORS | CONSTANTS - {"in", "out"}
DECL = re.compile(r"^\s*(Param|History|Data|Delay|Buffer)\s+(\w+)\s*\(", re.M)


def misused(code):
    code = re.sub(r"//[^\n]*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    out = set()
    for kind, name in DECL.findall(code):
        if name in RESERVED:
            out.add((name, kind))
    body = DECL.sub(lambda m: f"{m.group(1)} __decl__(", code)
    body = re.sub(r"\b(min|max)\s*=", "", body)                  # Param attributes
    body = re.sub(r"\.\s*\w+", "", body)                          # .read(), .write(), .peek()
    body = re.sub(r"\b(in|out)\d+\b", "", body)                   # in1, out2
    for m in re.finditer(r"\b([A-Za-z_]\w*)\b(?!\s*\()", body):
        name = m.group(1)
        if name in RESERVED and name not in CONSTANTS:
            out.add((name, "variable"))
        elif name in CONSTANTS and re.match(r"\s*=(?!=)", body[m.end():]):
            out.add((name, "variable"))                           # a constant assigned to
    return sorted(out)


def sanitize(code):
    """The codebox with every misused name renamed: a Param to '<name>_p' (returned in the map, so
    the patch's 'prepend <name>' into gen~ can follow), any other variable to '<name>_v'. Code
    without such names comes back unchanged."""
    bad = misused(code)
    if not bad:
        return code, {}
    params = {n for n, how in bad if how == "Param"}
    names = {n for n, _ in bad}
    renamed = {n: n + ("_p" if n in params else "_v") for n in names}
    out, i = [], 0
    # identifiers outside comments, not called, not a Param attribute, not after a '.'
    token = re.compile(r"//[^\n]*|/\*.*?\*/|\b([A-Za-z_]\w*)\b", re.S)
    for m in token.finditer(code):
        name = m.group(1)
        if not name or name not in renamed:
            continue
        rest = code[m.end():]
        before = code[:m.start()].rstrip()
        if re.match(r"\s*\(", rest) and not re.search(r"(Param|History|Data|Delay|Buffer)\s*$", before):
            continue                                              # a call of the operator itself
        if re.match(r"\s*=(?!=)", rest) and re.search(r"\(\s*[^()]*$", before) and name in ("min", "max"):
            continue
        if before.endswith("."):
            continue
        out.append(code[i:m.start()] + renamed[name])
        i = m.end()
    out.append(code[i:])
    fixed = "".join(out)
    assert not misused(fixed), misused(fixed)
    return fixed, {n: renamed[n] for n in params}


MAX_DEPTH = 16          # parentheses Max's gen~ has compiled (another device's 16-deep MPE lines); 26 failed


def too_deep(code, limit=MAX_DEPTH):
    """[(line number, depth)] of the lines nesting parentheses deeper than limit: Max's gen~ parser
    gives up on them with "function call missing '('" (another device's scale chains, Oct 1, a probe)."""
    out = []
    for n, line in enumerate(code.splitlines(), 1):
        d = m = 0
        for ch in re.sub(r"//.*", "", line):
            if ch == "(":
                d += 1
                m = max(m, d)
            elif ch == ")":
                d -= 1
        if m > limit:
            out.append((n, m))
    return out


MAX_CHAIN = 22         # 'else if' in a row Max's gen~ has compiled (Tincture's effect menu); another device's 80 failed


def long_chains(code, limit=MAX_CHAIN):
    """[(line number, length)] of the 'if ... else if ...' chains longer than limit: each 'else if' nests one level
    more in Max's gen~ parser, which gives up as it does on parentheses ("function call missing '('": another device's
    and another device's 80-way scale tables, Oct 18). branches() writes such a table log2 deep instead."""
    code = re.sub(r"/\*.*?\*/", " ", re.sub(r"//[^\n]*", " ", code), flags=re.S)
    out, run, depth = [], {}, 0
    for n, line in enumerate(code.splitlines(), 1):
        for m in re.finditer(r"\belse\s+if\b|\bif\b|[{};]", line):
            tok = m.group(0)
            if tok == "{":
                depth += 1
            elif tok == "}":
                depth -= 1
            elif tok == ";":
                run[depth] = [0, n]                       # a statement between them ends a chain
            elif tok == "if":
                run[depth] = [0, n]
            else:
                r = run.setdefault(depth, [0, n])
                r[0] += 1
                if r[0] == limit + 1:
                    out.append((r[1], None))
                if r[0] > limit:
                    out[-1] = (r[1], r[0])
    return out


def branches(var, bodies, indent="\t"):
    """Lines choosing one of bodies (lists of lines) by var's value 0 .. len(bodies) - 1, as a balanced tree of
    'if (var < k)': log2 of the count deep where an 'else if' chain is as deep as it is long (long_chains())."""
    def pick(lo, hi, ind):
        if hi - lo == 1:
            return [ind + ln for ln in bodies[lo]]
        mid = (lo + hi) // 2
        return ([f"{ind}if ({var} < {mid}) {{"] + pick(lo, mid, ind + "\t") + [f"{ind}}}", f"{ind}else {{"]
                + pick(mid, hi, ind + "\t") + [f"{ind}}}"])
    return pick(0, len(bodies), indent)


KEYWORDS = {"if", "else", "for", "while", "return", "break", "continue"}


def undefined(code):
    """[(name, line)] of the names the codebox reads but never declares or assigns: Max refuses the whole codebox
    ("variable o1wr_v3 is not defined", a probe-v0.37: silent in Live), where lib/genexpr.py stumbles only
    when that line runs (there, Poly's neighbour sync, which no test played). Not where or in which block a name is set,
    only that it is somewhere."""
    from genexpr import tokenize
    code = re.sub(r"/\*.*?\*/", " ", re.sub(r"//[^\n]*", " ", code), flags=re.S)
    declared = {name for _, name in DECL.findall(code)}
    toks = tokenize("\n".join(line for line in code.splitlines() if not DECL.match(line)))
    assigned, read = set(), {}
    for i, (kind, name, line) in enumerate(toks):
        if kind != "id" or name in KEYWORDS:
            continue
        before, after = (toks[i - 1][1] if i else ""), (toks[i + 1][1] if i + 1 < len(toks) else "")
        if before == "." or after == "(":                          # .read(), a call
            continue
        if after == "=":
            assigned.add(name)
        else:
            read.setdefault(name, line)
    known = declared | assigned | CONSTANTS | OPERATORS
    return sorted((n, ln) for n, ln in read.items() if n not in known and not re.fullmatch(r"(in|out)\d+", n))
