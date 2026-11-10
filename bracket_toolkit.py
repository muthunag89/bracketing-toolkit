#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bracket_toolkit.py — PROJECT KNOWLEDGE FILE. The whole bracket toolchain.

Replaces bracket_renderer / bracket_svg / bracket_page / bracket_interactive /
verify_geometry. ONE geometry engine produces records; the inline code blocks
(to_ascii) and the interactive SVG (to_svg) are both serialisations of those
same records, so the two can never disagree.

ONE COMMAND per passage:
    python3 bracket_toolkit.py <passage>.py              # full delivery
    python3 bracket_toolkit.py <passage>.py --views      # draft: print views only
    python3 bracket_toolkit.py <passage>.py --skeleton   # print unwritten NOTES stubs

Full delivery: prints both inline views, writes <PASSAGE>_bracket_standard.html,
<PASSAGE>_bracket_mainpoint.html and <PASSAGE>_interactive.html to OUT, and runs
check() (Step 5H checklist, automated at every depth x both views). Exit 0 only
if every NOTES slot is written and every check passes.

PASSAGE MODULE CONTRACT (see passage_template.py)
  PASSAGE  file stem, e.g. "tit_1_5-9"        REF   display reference
  IDS      canonical IDs, Scripture order      root  Leaf/Rel tree
  NOTES    {"<nid>:<slot>": n(k, b, g?, r?)}   slot = spine|arm|star|prop|stop
  PROSE    {depth: (heading, html)}            explains the PASSAGE, never the diagram
  FULL     (heading, html)                     authored whole-passage recap
  PHRASE   {nid: "the Ground of 8b-8d"}        phrases for the computed trace note
  TEXT_W   wrap column (default 34)            OUT   output dir (default below)

TREE
  Leaf(pid, text, arm_label=None, star=False)
  Rel(children, spine_label=None, arm_label=None, star=False, nid=, rel=, summary=)
    spine_label  S, P, A, BL (on the spine)
    arm_label    this node's role on the arm to its PARENT (Id/Exp, Ac/Pur, If/Th,
                 -/+ halves; G, ∴, T, L, Csv, Cf on supporting arms)
    star=True    main point of the parent relationship (BL: both outer children)
    rel          full relationship name; summary = text shown when collapsed
"""

import html as _html
import importlib.util
import json
import os
import re
import sys
import textwrap

TEXT_W = 34
OUT = "/mnt/user-data/outputs"

# ================================================================== tree

class Leaf:
    def __init__(self, pid, text, arm_label=None, star=False, nid=None):
        self.pid, self.text = pid, text
        self.arm_label, self.star = arm_label, star
        self.nid = nid or pid
        self.children, self.spine_label = [], None


class Rel:
    def __init__(self, children, spine_label=None, arm_label=None, star=False,
                 nid=None, rel=None, summary=None):
        self.children = children
        self.spine_label, self.arm_label, self.star = spine_label, arm_label, star
        self.nid, self.rel, self.summary = nid, rel or spine_label or "?", summary
        self.pid = None


class Collapsed(Leaf):
    """A Rel folded into one summary row for the depth slider."""
    def __init__(self, src, pid, text):
        super().__init__(pid, text, src.arm_label, src.star, src.nid)
        self.src = src


def leaves_of(node, acc=None):
    acc = [] if acc is None else acc
    if not node.children:
        acc.append(node)
    for c in node.children:
        leaves_of(c, acc)
    return acc


def depth_of(node, d=0):
    return d if not node.children else max(depth_of(c, d + 1) for c in node.children)


def _max_label_len(node):
    n = max(len(node.arm_label or ""), len(node.spine_label or ""))
    return max([n] + [_max_label_len(c) for c in node.children])


ABBR = {"Series": "S", "Progression": "P", "Alternative": "A", "Inference": "∴",
        "Ground": "G", "Bilateral": "BL", "Negative-Positive": "−/+",
        "Comparison": "Cf", "Temporal": "T", "Locative": "L", "Concessive": "Csv",
        "Idea-Explanation": "Id/Exp", "Action-Manner": "Ac/Mn",
        "Action-Purpose": "Ac/Pur", "Action-Result": "Ac/Res",
        "Question-Answer": "Q/A", "Situation-Response": "Sit/R",
        "Conditional": "If/Th"}


def span_of(node):
    lv = leaves_of(node)
    return lv[0].pid, lv[-1].pid


def collapse_to_depth(node, cutoff, d=0):
    """Fold every Rel at depth >= cutoff into a single summary row."""
    if not node.children:
        return node
    if d >= cutoff:
        a, b = span_of(node)
        text = (f"[{ABBR.get(node.rel, node.rel)}]  {node.summary or node.rel}"
                f"  ({len(leaves_of(node))} propositions)")
        return Collapsed(node, a if a == b else f"{a}–{b}", text)
    return Rel([collapse_to_depth(c, cutoff, d + 1) for c in node.children],
               node.spine_label, node.arm_label, node.star, node.nid, node.rel,
               node.summary)

# ============================================================== geometry

class Geometry:
    """Records keyed to the originating node. Every output reads only these."""
    def __init__(self):
        self.spines, self.arms, self.stars = [], [], []
        self.rows, self.junctions, self.overlays = [], [], []


def build(root, ids, attach_main_point=False, text_w=TEXT_W, step=7):
    """Lay out the tree. Asserts canonical order (collapsed spans expand to IDS).

    attach_main_point=False: a cluster joins its parent at its spine midpoint.
    attach_main_point=True : it joins at its own main point's row, so the
      passage main point is the one unbroken line from the leftmost spine to
      the ID column. Coordinate (S/P/A) and Bilateral nodes fall back to the
      midpoint: the line stopping there is a finding, not a defect.
    """
    lv = leaves_of(root)
    flat = []
    for l in lv:
        a, b = span_of(l.src) if isinstance(l, Collapsed) else (l.pid, l.pid)
        flat += [a] if a == b else ids[ids.index(a):ids.index(b) + 1]
    assert flat == ids, f"CANONICAL ORDER VIOLATION:\n got {flat}\n exp {ids}"

    g = Geometry()
    row = 0
    for l in lv:
        lines = textwrap.wrap(l.text, text_w) or [""]
        l.lines, l.top = lines, row
        g.rows.append(dict(nid=l.nid, pid=l.pid, top=row, lines=lines,
                           collapsed=isinstance(l, Collapsed)))
        row += len(lines)

    STEP = max(step, _max_label_len(root) + 4)
    M = len(root.spine_label or "")        # left margin: room for a root spine label
    maxd = depth_of(root)
    id_w = max(len(l.pid) for l in lv)
    star_col = M + maxd * STEP + STEP
    id_col = star_col + 1
    text_col = id_col + id_w + 2

    def put(r, c, s, kind, nid):
        g.overlays.append(dict(row=r, col=c, text=s, kind=kind, nid=nid))

    def layout(node, d):
        if not node.children:
            return node.top, id_col
        my_col = M + d * STEP
        info = [(c,) + layout(c, d + 1) for c in node.children]
        first_r, last_r = info[0][1], info[-1][1]
        for c, ar, ac in info:
            c2 = ac if c.children else id_col - 2
            g.arms.append(dict(nid=c.nid, parent_nid=node.nid, rel=node.rel, row=ar,
                               c1=my_col, c2=c2, label=c.arm_label,
                               is_leaf=not c.children))
            if c.arm_label:
                put(ar, my_col + 1, c.arm_label, "arm-label", c.nid)
            if c.star:
                col = star_col if not c.children else my_col + 1 + len(c.arm_label or "")
                g.stars.append(dict(nid=c.nid, row=ar, col=col, rel=node.rel))
                put(ar, col, "★", "star", c.nid)
        mid = (first_r + last_r) // 2
        lab = node.spine_label
        g.spines.append(dict(nid=node.nid, rel=node.rel, col=my_col, r1=first_r,
                             r2=last_r, label=lab,
                             label_col=my_col - len(lab or ""), label_row=mid))
        if lab:
            put(mid, my_col - len(lab), lab, "spine-label", node.nid)
        starred = [ar for c, ar, _ in info if c.star]
        if attach_main_point and len(starred) == 1:
            g.junctions.append(dict(nid=node.nid, row=starred[0], on_crux=True))
            return starred[0], my_col
        rows = {ar for _, ar, _ in info}
        while mid in rows and mid < last_r:
            mid += 1
        g.junctions.append(dict(nid=node.nid, row=mid, on_crux=False))
        return mid, my_col

    layout(root, 0)
    g.meta = dict(total_rows=row, star_col=star_col, id_col=id_col,
                  text_col=text_col, width=text_col + text_w + 1, id_w=id_w,
                  text_w=text_w)
    g.root = root
    return g

# ========================================================= text serialiser

N_, S_, E_, W_ = 1, 2, 4, 8
CHAR = {N_ | S_: '│', E_ | W_: '─', S_ | E_: '┌', S_ | W_: '┐', N_ | E_: '└',
        N_ | W_: '┘', N_ | S_ | E_: '├', N_ | S_ | W_: '┤', E_ | W_ | S_: '┬',
        E_ | W_ | N_: '┴', N_ | S_ | E_ | W_: '┼', N_: '│', S_: '│', E_: '─',
        W_: '─'}


def _grid(g):
    m = g.meta
    grid = [[0] * m["width"] for _ in range(m["total_rows"])]
    for s in g.spines:
        for r in range(s["r1"], s["r2"] + 1):
            grid[r][s["col"]] |= (N_ if r > s["r1"] else 0) | (S_ if r < s["r2"] else 0)
    for a in g.arms:
        c1, c2 = sorted((a["c1"], a["c2"]))
        for c in range(c1, c2 + 1):
            grid[a["row"]][c] |= (W_ if c > c1 else 0) | (E_ if c < c2 else 0)
    return grid


def to_ascii(g):
    m = g.meta
    grid = _grid(g)
    over = [[None] * m["width"] for _ in range(m["total_rows"])]
    for o in g.overlays:
        for i, ch in enumerate(o["text"]):
            over[o["row"]][o["col"] + i] = ch
    out = [''.join(over[r][c] or (CHAR[grid[r][c]] if grid[r][c] else ' ')
                   for c in range(m["width"])).rstrip()
           for r in range(m["total_rows"])]
    for row in g.rows:
        for i, tl in enumerate(row["lines"]):
            r = row["top"] + i
            base = out[r].ljust(m["text_col"])
            if i == 0:
                base = (base[:m["id_col"]] + row["pid"].ljust(m["id_w"])
                        + base[m["id_col"] + m["id_w"]:])
            out[r] = (base[:m["text_col"]] + tl).rstrip()
    return "\n".join(out)


def render(root, ids, attach_main_point=False, text_w=TEXT_W):
    """The inline code block. ids = the full canonical ID list."""
    return to_ascii(build(root, ids, attach_main_point, text_w))


HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ margin:0; padding:1.5rem; background:#fbfaf8; color:#1a1a1a;
         font-family:ui-sans-serif,system-ui,sans-serif; }}
  h1   {{ font-size:1.05rem; font-weight:600; letter-spacing:.01em;
         margin:0 0 1rem; color:#5a5348; }}
  pre  {{ font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
         font-size:13px; line-height:1.45; white-space:pre; overflow-x:auto;
         background:#fff; border:1px solid #e5e0d8; border-radius:6px;
         padding:1rem; margin:0; -webkit-text-size-adjust:100%; }}
</style></head>
<body><h1>{title}</h1><pre>{body}</pre></body></html>
"""


def render_html(diagram, title):
    esc = diagram.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTML_TEMPLATE.format(title=title, body=esc)

# =============================================== Step 5H checklist, automated

def check(root, ids, text_w=TEXT_W):
    """Run checklist H on every depth x both views. Returns a list of problems.

    Canonical order is asserted by build(). Here: no label or ★ overwrites
    another label or ★, no label covers a spine, every label lands inside the
    grid, every ★ sits on its arm's row. Contiguity and non-crossing hold by
    construction (a tree of contiguous spans cannot cross).
    """
    probs, maxd = [], depth_of(root)
    for d in range(1, maxd + 1):
        tree = collapse_to_depth(root, d) if d < maxd else root
        for amp in (False, True):
            g = build(tree, ids, amp, text_w)
            tag = f"depth {d} {'main-point' if amp else 'standard'}"
            grid, seen = _grid(g), {}
            arm_rows = {a["nid"]: a["row"] for a in g.arms}
            for o in g.overlays:
                for i in range(len(o["text"])):
                    r, c = o["row"], o["col"] + i
                    if c < 0 or c >= g.meta["star_col"] + 1:
                        probs.append(f"{tag}: {o['kind']} '{o['text']}' ({o['nid']}) "
                                     f"outside the bracket area")
                    elif (r, c) in seen:
                        probs.append(f"{tag}: {o['kind']} '{o['text']}' ({o['nid']}) "
                                     f"overwrites {seen[(r, c)]}")
                    elif grid[r][c] & (N_ | S_):
                        probs.append(f"{tag}: {o['kind']} '{o['text']}' ({o['nid']}) "
                                     f"covers a spine at column {c}")
                    seen[(r, c)] = f"{o['kind']} '{o['text']}' ({o['nid']})"
            for s in g.stars:
                if arm_rows.get(s["nid"]) != s["row"]:
                    probs.append(f"{tag}: ★ for {s['nid']} is off its arm row")
    return probs

# ============================================================= main-point trace

def main_point_path(root, g):
    """Segments of the unbroken main-point line, plus why it stopped."""
    spine = {s["nid"]: s for s in g.spines}
    arm = {a["nid"]: a for a in g.arms}
    segs, node = [], root
    while True:
        if not node.children:
            return segs, dict(kind="leaf", nid=node.nid, pid=node.pid)
        s = spine[node.nid]
        starred = [c for c in node.children if c.star]
        if len(starred) != 1:
            return segs, dict(kind="bilateral" if starred else "coordinate",
                              nid=node.nid, rel=node.rel, col=s["col"],
                              row=s["label_row"])
        a = arm[starred[0].nid]
        segs += [dict(kind="v", col=s["col"], r1=s["r1"], r2=a["row"]),
                 dict(kind="h", row=a["row"], c1=a["c1"], c2=a["c2"])]
        node = starred[0]


def row_pid(g, row):
    for r in g.rows:
        if r["top"] <= row < r["top"] + len(r["lines"]):
            return r["pid"]


def trace_report(root, ids, text_w=TEXT_W):
    g = build(root, ids, True, text_w)
    chain, node = [root], root
    while node.children:
        st = [c for c in node.children if c.star]
        if len(st) != 1:
            break
        node = st[0]
        chain.append(node)
    if not node.children:
        stop = dict(kind="leaf", nid=node.nid, rel=None, pid=node.pid)
    else:
        st = [c for c in node.children if c.star]
        stop = dict(kind="bilateral" if st else "coordinate", nid=node.nid,
                    rel=node.rel, pid=None)
    tally = {}
    for j in g.junctions:
        if j["on_crux"]:
            tally.setdefault(j["row"], []).append(j["nid"])
    busiest = None
    if tally:
        row = max(tally, key=lambda r: len(tally[r]))
        busiest = dict(pid=row_pid(g, row), count=len(tally[row]), nids=tally[row])
    return dict(chain=chain, stop=stop, busiest=busiest)

# ============================================================ SVG serialiser

CW, LH, PAD_X, PAD_Y = 8.0, 21.0, 14, 14
_x = lambda c: PAD_X + c * CW
_y = lambda r: PAD_Y + (r + 0.5) * LH
_ty = lambda r: PAD_Y + (r + 0.5) * LH + 4.6
_esc = lambda s: _html.escape(str(s), quote=True)


def to_svg(g, view, notes=None, svg_id="d"):
    notes, m = notes or {}, g.meta
    W = _x(m["width"]) + PAD_X
    H = PAD_Y * 2 + m["total_rows"] * LH

    def hit(nid, slot):
        key = f"{nid}:{slot}"
        return f' data-note="{_esc(key)}" class="hit"' if key in notes else ' class="hit nonote"'

    o = [f'<svg id="{svg_id}" class="bracket" viewBox="0 0 {W:.0f} {H:.0f}" '
         f'width="{W:.0f}" height="{H:.0f}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
         f'font-size="13">', '<g class="props">']
    for r in g.rows:
        top, n = r["top"], len(r["lines"])
        o.append(f'<g class="{"prop collapsed" if r["collapsed"] else "prop"}" '
                 f'data-nid="{_esc(r["nid"])}" data-slot="prop" data-pid="{_esc(r["pid"])}">')
        o.append(f'<text class="pid" x="{_x(m["id_col"]):.1f}" y="{_ty(top):.1f}">'
                 f'{_esc(r["pid"])}</text>')
        for i, ln in enumerate(r["lines"]):
            o.append(f'<text class="txt" x="{_x(m["text_col"]):.1f}" '
                     f'y="{_ty(top + i):.1f}">{_esc(ln)}</text>')
        o.append(f'<rect x="{_x(m["id_col"]) - 4:.1f}" y="{PAD_Y + top * LH:.1f}" '
                 f'width="{W - _x(m["id_col"]):.1f}" height="{n * LH:.1f}"'
                 f'{hit(r["nid"], "prop")}/>')
        o.append('</g>')
    o += ['</g>', '<g class="spines">']
    for s in g.spines:
        x, y1, y2 = _x(s["col"]), _y(s["r1"]), _y(s["r2"])
        o.append(f'<g class="spine" data-nid="{_esc(s["nid"])}" data-slot="spine" '
                 f'data-rel="{_esc(s["rel"])}">')
        o.append(f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}"/>')
        if s["label"]:
            o.append(f'<text class="lbl spine-lbl" x="{_x(s["label_col"]):.1f}" '
                     f'y="{_ty(s["label_row"]):.1f}">{_esc(s["label"])}</text>')
        o.append(f'<rect x="{x - 6:.1f}" y="{y1 - 6:.1f}" width="12" '
                 f'height="{y2 - y1 + 12:.1f}"{hit(s["nid"], "spine")}/>')
        o.append('</g>')
    o += ['</g>', '<g class="arms">']
    for a in g.arms:
        x1, x2, y = _x(a["c1"]), _x(a["c2"]), _y(a["row"])
        o.append(f'<g class="arm{" leafarm" if a["is_leaf"] else ""}" '
                 f'data-nid="{_esc(a["nid"])}" data-slot="arm" '
                 f'data-parent="{_esc(a["parent_nid"])}" data-rel="{_esc(a["rel"])}">')
        o.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}"/>')
        if a["label"]:
            o.append(f'<text class="lbl arm-lbl" x="{_x(a["c1"] + 1):.1f}" '
                     f'y="{_ty(a["row"]):.1f}">{_esc(a["label"])}</text>')
        o.append(f'<rect x="{min(x1, x2):.1f}" y="{y - 8:.1f}" '
                 f'width="{abs(x2 - x1):.1f}" height="16"{hit(a["nid"], "arm")}/>')
        o.append('</g>')
    o += ['</g>', '<g class="stars">']
    for st in g.stars:
        x, y = _x(st["col"]), _ty(st["row"])
        o.append(f'<g class="star" data-nid="{_esc(st["nid"])}" data-slot="star" '
                 f'data-rel="{_esc(st["rel"])}">')
        o.append(f'<text x="{x:.1f}" y="{y:.1f}">★</text>')
        o.append(f'<rect x="{x - 2:.1f}" y="{y - 14:.1f}" width="14" height="18"'
                 f'{hit(st["nid"], "star")}/>')
        o.append('</g>')
    o.append('</g>')
    if view == "mainpoint":
        segs, stop = main_point_path(g.root, g)
        d = []
        for i, s in enumerate(segs):
            if s["kind"] == "v":
                d.append(f'{"M" if i == 0 else "L"}{_x(s["col"]):.1f} {_y(s["r1"]):.1f}'
                         f'L{_x(s["col"]):.1f} {_y(s["r2"]):.1f}')
            else:
                d.append(f'L{_x(s["c2"]):.1f} {_y(s["row"]):.1f}')
        o.append(f'<g class="trace-layer"><path class="trace" pathLength="1" d="{"".join(d)}"/>')
        if stop["kind"] in ("coordinate", "bilateral"):
            x, y = _x(stop["col"]), _y(stop["row"])
            o.append(f'<g class="stopmark" data-nid="{_esc(stop["nid"])}" '
                     f'data-slot="stop" data-rel="{_esc(stop.get("rel", ""))}">')
            o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
            o.append(f'<rect x="{x - 9:.1f}" y="{y - 9:.1f}" width="18" height="18"'
                     f'{hit(stop["nid"], "stop")}/>')
            o.append('</g>')
        o.append('</g>')
    o.append('</svg>')
    return "\n".join(o)

# ========================================================== authoring aids

DIAGNOSTIC = {
    "Series": "Are these independent points forming a conceptual cluster where reordering does not change the logical force?",
    "Progression": "Are these steps in a sequence where reordering would eliminate a climax or diminish the argument?",
    "Alternative": "Are these distinct, mutually exclusive options being presented?",
    "Action-Manner": "Does this explain how the action was performed (method/means/manner)?",
    "Comparison": "Does this clarify the idea by analogy — saying “it is like X”?",
    "Negative-Positive": "Is one idea being denied so that the other is enforced through contrast?",
    "Question-Answer": "Is a direct answer being provided to a genuine (non-rhetorical) question?",
    "Idea-Explanation": "Does this clarify the meaning of the preceding idea without adding substantially new content?",
    "Ground": "Does the following piece answer “why?” — providing a logical basis or cause for the preceding claim?",
    "Inference": "Is the following piece a logical conclusion drawn from a preceding reason or set of premises?",
    "Bilateral": "Does this middle piece function as logical support for BOTH the preceding AND the following piece simultaneously?",
    "Action-Result": "Is this a real, often unintended consequence — the actual outcome of an action?",
    "Action-Purpose": "Is this the intended goal for which the action was performed?",
    "Conditional": "Is the outcome contingent on a potential, not yet actual, condition?",
    "Temporal": "Does this specify when the main statement is true, without adding new propositional content?",
    "Locative": "Does this specify where the main statement is true, without adding new propositional content?",
    "Concessive": "Is the main idea affirmed in spite of a contrary reality that is explicitly acknowledged?",
    "Situation-Response": "Is the response surprising or counter-intuitive given the situation described?",
}


def n(k, b, g=None, r=None):
    """One hover note: kicker, ONE sentence, original-language line, § pointer."""
    d = {"k": k, "b": b}
    if g:
        d["g"] = g
    if r:
        d["r"] = r
    return d


def note_skeleton(root, existing=None, quiet=False):
    """List every addressable slot not yet in `existing`; print stubs unless quiet."""
    existing, out = existing or {}, []

    def walk(node, parent=None):
        nid = node.nid or node.pid
        if node.children:
            q = DIAGNOSTIC.get(node.rel, "")
            out.append((f"{nid}:spine", f'n("{node.rel}", "DIAGNOSTIC: {q} VERDICT: ...", "GREEK: ...", "§...")'))
        else:
            out.append((f"{nid}:prop", 'n("PID", "division rule + why this is its own proposition", "GREEK: ...", "§...")'))
        if parent is not None:
            out.append((f"{nid}:arm", f'n("role in {parent.rel}", "what this piece contributes; Rule I1 note if the arm attaches at a cluster", None, "§...")'))
            if node.star:
                out.append((f"{nid}:star", f'n("★ Main point of the {parent.rel}", "why this piece and not the other", None, "§...")'))
        for c in node.children:
            walk(c, node)

    walk(root)
    missing = [(k, v) for k, v in out if k not in existing]
    if not quiet:
        print(f"# {len(out)} slots; {len(missing)} unwritten\nNOTES.update({{")
        for k, v in missing:
            print(f'    "{k}": {v},')
        print("})")
    return [k for k, _ in missing]


_BRACKET_WORDS = [
    "idea-explanation", "negative-positive", "action-purpose", "action-result",
    "action-manner", "situation-response", "question-answer", "bilateral",
    "concessive", "locative", "progression", "inference", "coordinate",
    "subordinate", "the ground", "a ground", "grounds ", "the series",
    "main point", "premise block", "resolves into", "attaches at", "attaches to",
    "the spine", "the arm", "arm label", "cluster", "proposition", "bracket",
    "diagram", "half-label", "star marks"]
_ID_RE = re.compile(r"\b\d{1,3}[a-f](–\d{1,3}[a-f])?\b")


def prose_lint(prose):
    """Advisory: flag panels that describe the bracket instead of the passage."""
    problems = []
    for d in sorted(prose, key=str):
        text = re.sub(r"<[^>]+>", " ", prose[d][1])
        hits = sorted({w.strip() for w in _BRACKET_WORDS
                       if re.search(r"(?<![a-z])" + re.escape(w), text.lower())})
        ids = sorted(set(m.group(0) for m in _ID_RE.finditer(text)))
        if hits or ids:
            problems.append((d, hits, ids))
    return problems

# ============================================================ page shell

STOP_KIND = {
    "coordinate": ("a coordinate relationship has no main point by definition, "
                   "so there is no single row beneath this joint for the line "
                   "to continue to"),
    "bilateral": ("Bilateral carries two main points, so the line has nowhere "
                  "single to go"),
}


def trace_addendum(tree, depth, ids, phrase, text_w=TEXT_W):
    """Computed note on where the main-point line runs and halts. Never hand-written."""
    r = trace_report(tree, ids, text_w)
    stop, busiest = r["stop"], r["busiest"]
    hops = len(r["chain"]) - 1
    step = "one step" if hops == 1 else f"{hops} steps"
    if stop["kind"] == "leaf":
        run = (f"The line leaves the leftmost spine and reaches "
               f"<b>{stop['pid']}</b> in {step}, ending on a proposition row "
               f"rather than a spine — but only because the main point is "
               f"folded into a single row at this depth. Expand one notch and "
               f"the line may stop short.")
    else:
        run = (f"{step.capitalize()}, then a halt. The line reaches the main "
               f"point and stops at <b>{phrase.get(stop['nid'], stop['nid'])}"
               f"</b> — {STOP_KIND[stop['kind']]}. This is a finding, not a "
               f"rendering defect.")
    crux = ""
    if busiest and busiest["count"] > 1:
        names = ", ".join(phrase.get(x, x) for x in busiest["nids"])
        crux = (f"Below that, {busiest['count']} cluster junctions stack on row "
                f"<b>{busiest['pid']}</b>: the geometry reporting that this one "
                f"row is simultaneously the main point of {names}. It is the "
                f"deepest thing the diagram says without a single label.")
    elif busiest:
        who = phrase.get(busiest["nids"][0], busiest["nids"][0])
        crux = (f"So far one cluster junction only, on row "
                f"<b>{busiest['pid']}</b> — {who} attaching at its own main "
                f"point. The stacking that marks an inner crux has not yet "
                f"appeared.")
    return (f'<p class="h">Attach-to-main-point · depth {depth}</p>'
            f'<p>{run}</p>' + (f'<p>{crux}</p>' if crux else ""))


DEFAULT_FOOTER = (
    "<b>Trace note.</b> Switching to the attach-to-main-point view pins a short "
    "note above the reading pane describing where the line runs and where it "
    "halts at that depth. It is generated from the tree, not written by hand, "
    "so it cannot drift from what the diagram draws.<br><br>"
    "<b>The reading pane.</b> On <i>This level</i> the prose is keyed to the "
    "same slider as the diagram: move it one notch and the explanation "
    "accounts for exactly what just became visible, and no more. Switch to "
    "<i>Whole passage</i> at any point for the continuous exposition, "
    "independent of where the slider sits.<br><br>"
    "<b>How to read this.</b> Hover (or tap) any spine, arm, label, ★, or "
    "proposition row. Each gives one sentence and a pointer into the Step 4 "
    "commentary — the prose remains primary; this is an index into it, not a "
    "replacement for it.<br><br>"
    "<b>Structure slider.</b> Collapsing folds every relationship below the "
    "chosen depth into a single summary row, so the macro-level structure is "
    "visible before the micro-level detail.")

CSS = """
:root{
  --bg:#fbfaf8; --ink:#1a1a1a; --rule:#5a5348; --faint:#cfc7ba;
  --accent:#8a5a2b; --trace:#b4531f; --panel:#fff; --edge:#e5e0d8;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;
  -webkit-text-size-adjust:100%}
header{padding:1.1rem 1.4rem .6rem;border-bottom:1px solid var(--edge)}
h1{font-size:1.02rem;font-weight:600;margin:0 0 .15rem;color:var(--rule);
  letter-spacing:.01em}
.sub{font-size:.78rem;color:#8b8172;margin:0}
.controls{display:flex;flex-wrap:wrap;gap:1.1rem;align-items:center;
  padding:.7rem 1.4rem;border-bottom:1px solid var(--edge);background:#fff;
  position:sticky;top:0;z-index:5}
.ctl{display:flex;align-items:center;gap:.45rem;font-size:.78rem;color:#6b6355}
.seg{display:inline-flex;border:1px solid var(--edge);border-radius:5px;
  overflow:hidden}
.seg button{border:0;background:#fff;padding:.3rem .7rem;font:inherit;
  font-size:.78rem;cursor:pointer;color:#6b6355}
.seg button[aria-pressed=true]{background:#f0ebe2;color:#3a352c;font-weight:600}
.seg button:disabled{opacity:.4;cursor:not-allowed}
input[type=range]{width:150px;accent-color:var(--rule)}
.depthlbl{font-variant-numeric:tabular-nums;min-width:8.5rem}
.stage{display:flex;gap:1.5rem;align-items:flex-start;
  padding:1.1rem 1.4rem 2rem}
.diagram{flex:1 1 auto;min-width:0;overflow-x:auto;padding-bottom:.6rem}
.view{display:none}
.view.on{display:block}
.prose{flex:0 0 25rem;max-width:25rem;border-left:1px solid var(--edge);
  padding:0 .2rem 1rem 1.3rem;font-size:.855rem;line-height:1.64;
  color:#2f2b24;max-height:calc(100vh - 9.5rem);overflow-y:auto;
  position:sticky;top:4.2rem}
.pmode{display:flex;gap:.5rem;align-items:center;margin:0 0 .9rem;
  padding-bottom:.7rem;border-bottom:1px solid var(--edge)}
.pmode .lb{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;
  color:#8b8172;font-weight:700}
.pmode .seg button{padding:.24rem .6rem;font-size:.74rem}
.addenda{margin-bottom:1rem}
.add{display:none;background:#fdf7ef;border:1px solid #ecdcc6;
  border-left:3px solid var(--trace);border-radius:5px;padding:.6rem .75rem;
  font-size:.8rem;line-height:1.55;color:#4a4034}
.add.on{display:block}
.add .h{font-size:.63rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--trace);font-weight:700;margin-bottom:.3rem}
.add p{margin:0 0 .5rem}
.add p:last-child{margin-bottom:0}
.pane{display:none}
.pane.on{display:block}
.pane.full .head{color:var(--rule)}
.pane .head{font-size:.66rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin:0 0 .55rem}
.prose p{margin:0 0 .72rem}
.prose p.q{font-size:.79rem;color:#8b8172;font-style:italic;
  border-top:1px dashed var(--edge);padding-top:.55rem;margin-top:.9rem}
.prose h2{font-size:.9rem;color:var(--rule);margin:1.5rem 0 .5rem;
  padding-top:.7rem;border-top:1px solid var(--edge)}
.prose h2:first-child{margin-top:0;padding-top:0;border-top:0}
.prose h3{font-size:.83rem;color:var(--rule);margin:1.1rem 0 .45rem}
.prose blockquote{margin:0 0 .8rem;padding:.15rem 0 .15rem .85rem;
  border-left:2px solid var(--faint);color:#4a4437;font-style:italic}
.prose ul{margin:0 0 .8rem;padding-left:1.1rem}
.prose li{margin-bottom:.3rem}
.prose::-webkit-scrollbar{width:9px}
.prose::-webkit-scrollbar-thumb{background:#ded7cc;border-radius:5px}

svg.bracket line{stroke:var(--rule);stroke-width:1.25;
  shape-rendering:crispEdges}
svg.bracket text{fill:var(--ink)}
svg.bracket .pid{fill:#8b8172;font-size:11.5px}
svg.bracket .lbl{fill:var(--accent);font-size:11.5px;font-weight:600}
svg.bracket .star text,svg.bracket .star{fill:var(--accent)}
svg.bracket .star text{font-size:12px}
svg.bracket .collapsed .txt{fill:#7a7161;font-style:italic}
svg.bracket .collapsed .pid{font-weight:600;fill:#5a5348}
rect.hit{fill:transparent;pointer-events:all;cursor:help}
rect.hit.nonote{cursor:default}
g.lit line{stroke:var(--accent);stroke-width:2.4}
g.lit text{fill:var(--accent)}
g.lit circle{fill:var(--accent)}
g.dim{opacity:.28}

path.trace{fill:none;stroke:var(--trace);stroke-width:3.2;opacity:0;
  stroke-linecap:round;stroke-linejoin:round;
  stroke-dasharray:1;stroke-dashoffset:1}
.traced path.trace{opacity:.92;stroke-dashoffset:0;
  transition:stroke-dashoffset 1.5s ease-in-out,opacity .2s}
.stopmark circle{fill:#fff;stroke:var(--trace);stroke-width:2;opacity:0}
.traced .stopmark circle{opacity:1;transition:opacity .25s .9s}

#tip{position:fixed;max-width:23rem;background:var(--panel);
  border:1px solid var(--edge);border-radius:7px;
  box-shadow:0 6px 22px rgba(60,50,35,.16);padding:.6rem .75rem;
  font-size:.8rem;line-height:1.45;pointer-events:none;opacity:0;
  transition:opacity .1s;z-index:20}
#tip.on{opacity:1}
#tip .k{font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin-bottom:.22rem}
#tip .b{color:#2a2620}
#tip .g{margin-top:.4rem;font-family:ui-monospace,Menlo,monospace;
  font-size:.76rem;color:#4a4437}
#tip .r{margin-top:.45rem;padding-top:.4rem;border-top:1px dashed var(--edge);
  font-size:.72rem;color:#8b8172;font-style:italic}
footer{padding:0 1.4rem 2.5rem;font-size:.78rem;color:#8b8172;max-width:52rem;
  line-height:1.6}
footer b{color:#5a5348}
@media (max-width:980px){
  .stage{flex-direction:column;gap:1.1rem}
  .diagram{width:100%}
  .prose{flex:1 1 auto;max-width:none;width:100%;border-left:0;
    border-top:1px solid var(--edge);padding:1rem 0 0;position:static;
    max-height:none;overflow:visible}
}
@media (max-width:640px){
  .controls{gap:.7rem;padding:.6rem .9rem}
  .stage{padding:.9rem}
  #tip{max-width:min(21rem,92vw)}
}
"""

JS = """
const NOTES = __NOTES__;
const tip = document.getElementById('tip');
let depth = __MAXD__, view = 'standard', traced = false, pmode = 'level';

function active(){ return document.querySelector('.view.on svg'); }

function sync(){
  document.querySelectorAll('.view').forEach(v=>{
    v.classList.toggle('on', +v.dataset.depth===depth && v.dataset.view===view);
  });
  const lvl = (pmode==='level');
  document.querySelectorAll('.add').forEach(a=>
    a.classList.toggle('on', lvl && +a.dataset.depth===depth && a.dataset.view===view));
  document.querySelectorAll('.pane').forEach(p=>
    p.classList.toggle('on', lvl ? (+p.dataset.depth===depth)
                                 : (p.dataset.depth==='full')));
  document.querySelectorAll('[data-pmode-btn]').forEach(b=>
    b.setAttribute('aria-pressed', b.dataset.pmodeBtn===pmode));
  document.getElementById('dlab').textContent =
    depth===__MAXD__ ? 'full depth ('+__MAXD__+')' : 'depth '+depth+' of '+__MAXD__;
  document.querySelectorAll('[data-view-btn]').forEach(b=>
    b.setAttribute('aria-pressed', b.dataset.viewBtn===view));
  const tb = document.getElementById('tracebtn');
  tb.disabled = (view!=='mainpoint');
  if(view!=='mainpoint'){ traced=false; }
  tb.setAttribute('aria-pressed', traced);
  document.querySelectorAll('.view svg').forEach(s=>s.classList.remove('traced'));
  if(traced && active()){
    const s = active();
    s.classList.remove('traced'); void s.getBoundingClientRect(); s.classList.add('traced');
  }
}

document.getElementById('depth').addEventListener('input', e=>{
  const prev = depth; depth = +e.target.value; sync();
  if(prev!==depth){ const pr=document.querySelector('.prose'); if(pr) pr.scrollTop=0; }
});
document.querySelectorAll('[data-view-btn]').forEach(b=>
  b.addEventListener('click', ()=>{ view=b.dataset.viewBtn; sync(); }));
document.querySelectorAll('[data-pmode-btn]').forEach(b=>
  b.addEventListener('click', ()=>{
    pmode = b.dataset.pmodeBtn; sync();
    const pr=document.querySelector('.prose'); if(pr) pr.scrollTop=0;
  }));
document.getElementById('tracebtn').addEventListener('click', ()=>{
  traced=!traced; sync();
});

function show(el, key, ev){
  const n = NOTES[key]; if(!n) return;
  tip.innerHTML = '<div class="k">'+n.k+'</div><div class="b">'+n.b+'</div>'
    + (n.g ? '<div class="g">'+n.g+'</div>' : '')
    + (n.r ? '<div class="r">Step 4 commentary \\u2192 '+n.r+'</div>' : '');
  tip.classList.add('on');
  place(ev);
  const g = el.closest('g[data-nid]');
  if(g) g.classList.add('lit');
}
function place(ev){
  const r = tip.getBoundingClientRect();
  let x = ev.clientX + 16, y = ev.clientY + 16;
  if(x + r.width > innerWidth - 10) x = ev.clientX - r.width - 14;
  if(y + r.height > innerHeight - 10) y = ev.clientY - r.height - 14;
  tip.style.left = Math.max(8,x)+'px'; tip.style.top = Math.max(8,y)+'px';
}
document.addEventListener('mouseover', e=>{
  const h = e.target.closest('rect.hit[data-note]'); if(!h) return;
  show(h, h.dataset.note, e);
});
document.addEventListener('mousemove', e=>{ if(tip.classList.contains('on')) place(e); });
document.addEventListener('mouseout', e=>{
  const h = e.target.closest('rect.hit[data-note]'); if(!h) return;
  tip.classList.remove('on');
  document.querySelectorAll('g.lit').forEach(g=>g.classList.remove('lit'));
});
// touch: tap to pin
document.addEventListener('click', e=>{
  const h = e.target.closest('rect.hit[data-note]');
  document.querySelectorAll('g.lit').forEach(g=>g.classList.remove('lit'));
  if(!h){ tip.classList.remove('on'); return; }
  show(h, h.dataset.note, {clientX:e.clientX, clientY:e.clientY});
});
sync();
"""

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style></head>
<body>
<header><h1>{title}</h1><p class="sub">{sub}</p></header>
<div class="controls">
  <div class="ctl"><span>View</span>
    <span class="seg">
      <button data-view-btn="standard" aria-pressed="true">Standard (midpoint)</button>
      <button data-view-btn="mainpoint" aria-pressed="false">Attach to main point</button>
    </span>
  </div>
  <div class="ctl"><span>Trace</span>
    <span class="seg"><button id="tracebtn" aria-pressed="false" disabled>Main-point line</button></span>
  </div>
  <div class="ctl"><span>Structure</span>
    <input id="depth" type="range" min="1" max="{maxd}" value="{maxd}" step="1">
    <span class="depthlbl" id="dlab"></span>
  </div>
</div>
<div class="stage">
  <div class="diagram">
{views}
  </div>
  <aside class="prose">
{pmode}
    <div class="addenda">
{addenda}
    </div>
{panes}
{fullpane}
  </aside>
</div>
<footer>{footer}</footer>
<div id="tip"></div>
<script>{js}</script>
</body></html>
"""


def build_interactive(root, ids, title, sub, notes, prose, phrase, out,
                      text_w=TEXT_W, footer=None, full_prose=None):
    """Render every depth x view, attach content, write the artifact."""
    maxd = depth_of(root)
    views, adds = [], []
    for d in range(1, maxd + 1):
        tree = collapse_to_depth(root, d) if d < maxd else root
        adds.append(f'<div class="add" data-depth="{d}" data-view="mainpoint">'
                    f'{trace_addendum(tree, d, ids, phrase, text_w)}</div>')
        for view in ("standard", "mainpoint"):
            g = build(tree, ids, view == "mainpoint", text_w)
            views.append(f'<div class="view" data-depth="{d}" data-view="{view}">'
                         f'{to_svg(g, view, notes, svg_id=f"svg_{d}_{view}")}</div>')
    if full_prose:
        fullpane = (f'<div class="pane full" data-depth="full">'
                    f'<p class="head">{full_prose[0]}</p>{full_prose[1]}</div>')
        pmode = ('    <div class="pmode"><span class="lb">Reading</span>'
                 '<span class="seg">'
                 '<button data-pmode-btn="level" aria-pressed="true">This level</button>'
                 '<button data-pmode-btn="full" aria-pressed="false">Whole passage</button>'
                 '</span></div>')
    else:
        fullpane, pmode = "", ""
    panes = [f'<div class="pane" data-depth="{d}"><p class="head">{h}</p>{b}</div>'
             for d, (h, b) in sorted(prose.items())]
    js = JS.replace("__NOTES__", json.dumps(notes)).replace("__MAXD__", str(maxd))
    page = PAGE.format(title=title, sub=sub, css=CSS, js=js, maxd=maxd,
                       views="\n".join(views), panes="\n".join(panes),
                       addenda="\n".join(adds), fullpane=fullpane, pmode=pmode,
                       footer=DEFAULT_FOOTER if footer is None else footer)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return out

# ================================================================ deliver

def load(path):
    name = os.path.splitext(os.path.basename(path))[0].replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def deliver(path, mode="full"):
    """Everything Step 5J needs, in one call. Returns the exit code."""
    m = load(path)
    tw = getattr(m, "TEXT_W", TEXT_W)
    if mode == "skeleton":
        note_skeleton(m.root, getattr(m, "NOTES", {}))
        return 0
    std = render(m.root, m.IDS, False, tw)
    mp = render(m.root, m.IDS, True, tw)
    print(f"=== STANDARD VIEW ===\n{std}\n\n=== ATTACH-TO-MAIN-POINT VIEW ===\n{mp}\n")
    rep = trace_report(m.root, m.IDS, tw)
    st, bz = rep["stop"], rep["busiest"]
    print(f"trace: stops at {st['kind']} ({st.get('pid') or st.get('rel')}, {st['nid']})"
          + (f"; {bz['count']} junction(s) stack on {bz['pid']}" if bz else ""))
    if mode == "views":
        return 0

    out = getattr(m, "OUT", OUT)
    os.makedirs(out, exist_ok=True)
    stem, ref = m.PASSAGE, m.REF
    for suffix, body, label in (("standard", std, "Standard view (midpoint)"),
                                ("mainpoint", mp, "Attach-to-main-point view")):
        with open(f"{out}/{stem}_bracket_{suffix}.html", "w", encoding="utf-8") as f:
            f.write(render_html(body, f"{ref} — {label}"))
    build_interactive(
        m.root, m.IDS, title=f"{ref} — Interactive Propositional Bracket",
        sub=("Biblearc convention · ESV · hover for relationship, diagnostic "
             "verdict, and original-language notes"),
        notes=m.NOTES, prose=m.PROSE, phrase=m.PHRASE,
        full_prose=getattr(m, "FULL", None),
        out=f"{out}/{stem}_interactive.html", text_w=tw)

    missing = note_skeleton(m.root, m.NOTES, quiet=True)
    want = set(range(1, depth_of(m.root) + 1))
    panels_missing = sorted(want - set(m.PROSE))
    lint = prose_lint({**m.PROSE, **({"full": m.FULL} if getattr(m, "FULL", None) else {})})
    probs = check(m.root, m.IDS, tw)
    fail = bool(missing or panels_missing or probs or not getattr(m, "FULL", None))

    print(f"\nwrote {out}/{stem}_bracket_standard.html, _bracket_mainpoint.html, "
          f"_interactive.html")
    print(f"notes: {len(m.NOTES)} written, {len(missing)} unwritten"
          + (f" -> {missing[:8]}" if missing else ""))
    print(f"prose: {len(m.PROSE)} panels" + (f", MISSING depths {panels_missing}"
          if panels_missing else "") + ("" if getattr(m, "FULL", None)
          else ", NO whole-passage recap (FULL)"))
    for d, hits, ids in lint:
        print(f"prose lint (advisory) {d}: {', '.join(hits + ids)}")
    print(f"checklist H: {2 * depth_of(m.root)} views checked, "
          + ("all pass" if not probs else f"{len(probs)} problem(s)"))
    for p in probs:
        print("  " + p)
    print("RESULT: " + ("FAIL — fix before delivering" if fail else "PASS"))
    return 1 if fail else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    sys.path.insert(0, os.path.dirname(os.path.abspath(a[0])) or ".")
    sys.exit(deliver(a[0], "skeleton" if "--skeleton" in a
                     else "views" if "--views" in a else "full"))
