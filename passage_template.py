#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""passage_template.py — Copy, rename, fill in.

Per-passage work is a tree and four content blocks; everything else lives in
bracket_toolkit.py. Then ONE command does Step 5J end to end:

    python3 bracket_toolkit.py <passage>.py --views      # while drafting the tree
    python3 bracket_toolkit.py <passage>.py --skeleton   # stubs for unwritten NOTES
    python3 bracket_toolkit.py <passage>.py              # deliver + checklist H

The full run prints both inline views, writes the two static HTML views and
the interactive artifact, and exits 0 only when every NOTES slot is written,
every PROSE depth exists, FULL is present, and checklist H passes everywhere.
"""

from bracket_toolkit import Leaf, Rel, n

PASSAGE = "xxx_0_0-0"          # file stem, e.g. "rom_8_31-39"
REF = "Romans 8:31–39"         # display reference
TEXT_W = 34                    # lower it if the inline view wraps

IDS = ["31a", "31b"]           # canonical Scripture order, no exceptions

# --------------------------------------------------------------- the tree
# Rel(children, spine_label=, arm_label=, star=, nid=, rel=, summary=)
#   rel     = full relationship name, e.g. "Negative-Positive"
#   summary = what this cluster says, shown when it is collapsed
p31a = Leaf("31a", "What then shall we say to these things?", arm_label="Id",
            star=True)
p31b = Leaf("31b", "If God is for us, who can be against us?", arm_label="Exp")
root = Rel([p31a, p31b], nid="root", rel="Idea-Explanation",
           summary="the question and its answer")

# ------------------------------------------------- hover content (Step 4)
# key "<nid>:<slot>", slot = spine | arm | star | prop (+ stop on a halt)
# n(kicker, ONE sentence, original-language line, "§ pointer")
NOTES = {}

# --------------------------------------------------- reading pane (depth)
# One panel per depth, 1 .. depth_of(root). PROSE EXPLAINS THE PASSAGE, NOT
# THE DIAGRAM: no proposition IDs, relationship names, or bracket vocabulary.
# Depth 1 = the passage in one sentence; each later panel is a delta.
PROSE = {
    1: ("The passage in one sentence", "<p>…</p>"),
}

# Whole-passage recap: authored, never concatenated from the panels.
FULL = ("<Reference> in plain terms", "<p>…</p>")

# Human phrases for the computed trace note.
PHRASE = {"root": "the Idea-Explanation at 31a"}
