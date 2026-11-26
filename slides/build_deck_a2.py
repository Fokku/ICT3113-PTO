"""build_deck_a2.py -- renders slides/Group10_A2.pptx (Assignment 2, 8 slides).

Owner: Part 5 -- Koh Tong Wei (deck assembly). Content owners per slide are in
slides/outline_a2.md.

Styling: the deck is built ON slides/Group10.pptx (the submitted Assignment 1
deck), so it inherits that deck's theme, slide layouts and wave artwork. Every
shape below copies the A1 deck's own shape styles: Arial, indigo 241160 text,
blue-violet 545EEA / violet 8861F1 accents, cyan 01CFE6 step markers, lavender
E2E4FC cards, red B3261E emphasis, and the same header-row table style.

Every figure is copied from a committed file named in the slide's source line.
Anything that needs the A2 gate (a2-predictions-freeze) and the real runs is
shown as "pending" (violet, dashed), so a gap cannot be mistaken for a result.

Usage (from the repository root):  python slides/build_deck_a2.py [out.pptx]
Needs python-pptx and lxml.
"""
import copy
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "Group10.pptx"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "Group10_A2.pptx"

# ----------------------------------------------------------------- palette ---
# Taken from Group10.pptx's own shapes (slide 2 diagram, cards, tables).
INK = "241160"      # titles, body text, table header fill
BLUE = "545EEA"     # card headings, primary boxes
VIOLET = "8861F1"   # outlines, arrows, dashed boundaries
CYAN = "01CFE6"     # numbered step markers
CARD = "E2E4FC"     # lavender card fill
TINT = "F4F5FE"     # alternate table row, container fill
MUTED = "4A4670"    # secondary text
RED = "B3261E"      # emphasis (verdicts, key figures)
WHITE = "FFFFFF"
FONT = "Arial"
MONO = "Courier New"

# -------------------------------------------------------------------- data ---
# slides/Group10.pptx slide 1 (IDs) ; slides/team.yaml
MEMBERS = [("Loh Wen Xuan", "2401561"), ("Jolie Ngai Ning Li", "2403175"), ("Koh Tong Wei", "2402162"),
           ("Toh Si Pei", "2401835"), ("Yeo Kai Yuan", "2403201")]
REPO = "https://github.com/Fokku/ICT3113-PTO"
# docs/a2/accuracy_limits.md §1-2 ; analysis/output/accuracy/model_comparison.csv
CATS = [  # name, N, qwen correct, qwen %, limit %, pass needs, borderline (N = 11)
    ("Credit reporting", 25, 21, "84.0%", "69.00%", "18/25", False),
    ("Debt collection", 13, 10, "76.9%", "61.92%", "9/13", False),
    ("Mortgage", 11, 4, "36.4%", "21.36%", "3/11", True),
    ("Credit card", 11, 9, "81.8%", "66.82%", "8/11", True),
    ("Bank account or service", 16, 15, "93.8%", "78.75%", "13/16", False),
    ("Consumer loan", 14, 8, "57.1%", "42.14%", "6/14", False),
    ("Money transfer or service", 11, 8, "72.7%", "57.73%", "7/11", True),
]


def I(v):
    return Emu(int(round(v * 914400)))


# ----------------------------------------------------------------- helpers ---
def strip_style(shape):
    """Drop python-pptx's theme <p:style> so no theme fill/shadow leaks in."""
    st = shape._element.find(qn("p:style"))
    if st is not None:
        shape._element.remove(st)


def runs_into(tf, paras, size=10.5, color=INK, align=PP_ALIGN.LEFT, space_before=0, line=None):
    """paras: list of paragraphs; a paragraph is a str or a list of (text, opts) runs."""
    tf.clear()
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if i and space_before:
            p.space_before = Pt(space_before)
        if line:
            p.line_spacing = line
        if isinstance(para, str):
            para = [(para, {})]
        for text, o in para:
            r = p.add_run()
            r.text = text
            f = r.font
            f.name = o.get("font", FONT)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("b", False)
            f.italic = o.get("i", False)
            f.color.rgb = RGBColor.from_string(o.get("color", color))
            if o.get("link"):
                r.hyperlink.address = o["link"]


def textbox(s, x, y, w, h, paras, size=10.5, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
            margin=0.02, space_before=0, line=None):
    tb = s.shapes.add_textbox(I(x), I(y), I(w), I(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.vertical_anchor = anchor
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", I(margin))
    runs_into(tf, paras, size, color, align, space_before, line)
    return tb


def card(s, x, y, w, h, fill=CARD, line=None, dash=False, lw=1.25, adj=None, paras=None, size=10.5,
         color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, margin=(0.12, 0.04), space_before=2,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sp = s.shapes.add_shape(shape, I(x), I(y), I(w), I(h))
    strip_style(sp)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sp.adjustments[0] = adj if adj is not None else min(0.5, 0.07 / min(w, h))
    if fill:
        sp.fill.solid()
        sp.fill.fore_color.rgb = RGBColor.from_string(fill)
    else:
        sp.fill.background()
    if line:
        sp.line.color.rgb = RGBColor.from_string(line)
        sp.line.width = Pt(lw)
        if dash:
            ln = sp.line._get_or_add_ln()
            pd = etree.SubElement(ln, qn("a:prstDash"))
            pd.set("val", "dash")
    else:
        sp.line.fill.background()
    if paras is not None:
        tf = sp.text_frame
        tf.word_wrap = True
        tf.auto_size = None
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = I(margin[0])
        tf.margin_top = tf.margin_bottom = I(margin[1])
        runs_into(tf, paras, size, color, align, space_before)
    return sp


def arrow(s, x1, y1, x2, y2, color=INK, w=1.5):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, I(x1), I(y1), I(x2), I(y2))
    strip_style(c)
    c.line.color.rgb = RGBColor.from_string(color)
    c.line.width = Pt(w)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return c


def line(s, x1, y1, x2, y2, color, w=1.0, dash=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, I(x1), I(y1), I(x2), I(y2))
    strip_style(c)
    c.line.color.rgb = RGBColor.from_string(color)
    c.line.width = Pt(w)
    if dash:
        pd = etree.SubElement(c.line._get_or_add_ln(), qn("a:prstDash"))
        pd.set("val", dash)
    return c


def step(s, x, y, n, d=0.26):
    card(s, x, y, d, d, fill=CYAN, shape=MSO_SHAPE.OVAL, paras=[[(str(n), {"b": True})]], size=10,
         align=PP_ALIGN.CENTER, margin=(0, 0))


PENDING = object()


def table(s, rows, x, y, w, col_w, row_h=0.24, size=10, head_size=None, first_bold=True):
    """A1 table style: indigo header, white/tint banding, no visible borders, Arial."""
    nr, nc = len(rows), len(rows[0])
    gf = s.shapes.add_table(nr, nc, I(x), I(y), I(w), I(row_h * nr))
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for k in ("firstRow", "bandRow", "firstCol", "lastRow", "lastCol", "bandCol"):
        tblPr.attrib.pop(k, None)
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{68164A90-5C4F-4A6D-B3D8-F2779BC5A639}"
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = I(cw)
    for r in range(nr):
        tbl.rows[r].height = I(row_h)
        for c in range(nc):
            cell = tbl.cell(r, c)
            val = rows[r][c]
            head = r == 0
            fill = INK if head else (TINT if r % 2 == 0 else WHITE)
            o = {"b": head or (first_bold and c == 0), "color": WHITE if head else INK,
                 "size": (head_size or size) if head else size}
            text = val
            if val is PENDING:
                text, o = "pending", {**o, "i": True, "color": VIOLET, "b": False}
            elif isinstance(val, tuple):
                text, extra = val
                o = {**o, **extra}
                fill = extra.get("fill", fill)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(fill)
            cell.margin_left = cell.margin_right = I(0.06)
            cell.margin_top = cell.margin_bottom = I(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            runs_into(cell.text_frame, [[(str(text), o)]], size=o["size"],
                      align=o.get("align", PP_ALIGN.LEFT))
            # transparent borders, as in the A1 tables
            tcPr = cell._tc.get_or_add_tcPr()
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tcPr, qn(tag))
                ln.set("w", "9525")
                sf = etree.SubElement(ln, qn("a:solidFill"))
                clr = etree.SubElement(sf, qn("a:srgbClr"))
                clr.set("val", "000000")
                etree.SubElement(clr, qn("a:alpha")).set("val", "0")
            # schema order: borders before fill
            fill_el = tcPr.find(qn("a:solidFill"))
            if fill_el is not None:
                tcPr.remove(fill_el)
                tcPr.append(fill_el)
    return gf


def pending_card(s, x, y, w, h, what, size=10.5):
    return card(s, x, y, w, h, fill=TINT, line=VIOLET, dash=True, lw=1.25,
                paras=[[("Pending — ", {"b": True, "color": VIOLET}), (what, {"color": MUTED})]], size=size)


def source(s, text):
    textbox(s, 1.3, 5.11, 7.8, 0.25, [[("Source: " + text, {"color": MUTED, "i": True})]], size=7.5)


# ---------------------------------------------------------- deck from A1 ---
prs = Presentation(str(TEMPLATE))
sldIdLst = prs.slides._sldIdLst
for sldId in list(sldIdLst):
    prs.part.drop_rel(sldId.rId)
    sldIdLst.remove(sldId)

LAYOUT = {l.name: l for l in prs.slide_layouts}


def content_slide(title):
    s = prs.slides.add_slide(LAYOUT["TITLE_AND_BODY"])
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx != 0:
            ph._element.getparent().remove(ph._element)
    s.shapes.title.text = title
    return s


# ============================================================ 1. Cover ===
s = prs.slides.add_slide(LAYOUT["TITLE"])
t = s.placeholders[0]
runs_into(t.text_frame, [[("ICT3113 Assignment 2 – Fast Triage Within an Accuracy Floor", {})]], size=26)
for r in t.text_frame.paragraphs[0].runs:  # inherit the layout's title font, as in A1
    r.font.name = None
t.left, t.top, t.width, t.height = I(0.84), I(1.26), I(8.32), I(0.97)
sub = s.placeholders[1]
names = [[("Group P2-10:", {"b": True})]] + [[(f"{n} ({sid})", {})] for n, sid in MEMBERS] + \
        [[("Repository:", {"b": True})], [("github.com/Fokku/ICT3113-PTO", {"link": REPO})]]
runs_into(sub.text_frame, names, size=11.5, space_before=5)
for p in sub.text_frame.paragraphs:
    for r in p.runs:
        r.font.name = None
sub.left, sub.top, sub.width, sub.height = I(0.96), I(2.33), I(3.75), I(2.66)
# top model + limits
card(s, 4.95, 2.33, 4.2, 0.78, fill=BLUE, paras=[
    [("Top A1 model  ", {"color": WHITE}), ("qwen2.5:7b  74.0%", {"b": True, "color": WHITE, "size": 12}),
     ("  148/200", {"color": WHITE})],
    [("Overall limit  ", {"color": WHITE}), ("64.26%", {"b": True, "color": WHITE, "size": 12}),
     ("  pass ≥ 65/101 test tickets", {"color": WHITE})]], size=10)
rows = [("Per-category limit", "Limit", "Pass ≥")] + [
    ((("⚠ " if b else "") + n, {"color": RED} if b else {}), lim, needs) for n, N, c, p, lim, needs, b in CATS]
table(s, rows, 4.95, 3.2, 4.2, [2.4, 0.9, 0.9], row_h=0.205, size=9)
textbox(s, 4.95, 4.88, 4.2, 0.3, [[("qwen2.5:7b on the 101 test-set tickets −10 pp overall, −15 pp per category. "
                                     "⚠ N = 11: one ticket = 9.1 pp. Source: docs/a2/accuracy_limits.md",
                                     {"i": True, "color": MUTED})]], size=7.5)

# ==================================================== 2. Cascade design ===
s = content_slide("Cascade Design")
card(s, 0.65, 1.4, 1.2, 2.3, fill=None, line=VIOLET, dash=True, adj=0.05, anchor=MSO_ANCHOR.TOP,
     paras=[[("Separate machine", {"i": True, "color": VIOLET})]], size=9.5, align=PP_ALIGN.CENTER)
card(s, 0.75, 1.95, 1.0, 0.85, fill=WHITE, line=VIOLET, paras=[
    [("JMeter", {"b": True})], [("one ticket per", {"color": MUTED, "size": 9})],
    [("POST /tickets", {"color": MUTED, "size": 9})]], size=10.5, align=PP_ALIGN.CENTER, margin=(0.05, 0.03))
card(s, 2.05, 1.4, 3.85, 2.3, fill=TINT, line=BLUE, lw=1, adj=0.04, anchor=MSO_ANCHOR.TOP,
     paras=[[("System under test — one POST /tickets request", {"b": True, "color": BLUE})]], size=9.5,
     align=PP_ALIGN.CENTER)
card(s, 2.2, 1.95, 1.4, 0.85, fill=BLUE, paras=[
    [("Small model", {"color": WHITE, "size": 9})], [("granite4:3b", {"b": True, "color": WHITE, "size": 12})],
    [("always called", {"color": WHITE, "size": 9})]], align=PP_ALIGN.CENTER, margin=(0.05, 0.03))
card(s, 4.0, 1.95, 1.75, 0.85, fill=WHITE, line=VIOLET, paras=[
    [("Escalation rule", {"b": True})], [("category in", {"color": MUTED, "size": 9})],
    [("ACCEPT[setting]?", {"font": MONO, "size": 9, "b": True})]], size=10.5, align=PP_ALIGN.CENTER,
     margin=(0.05, 0.03))
card(s, 4.0, 3.0, 1.75, 0.6, fill=INK, paras=[
    [("Large model", {"color": WHITE, "size": 9})], [("qwen2.5:7b", {"b": True, "color": WHITE, "size": 12})]],
     align=PP_ALIGN.CENTER, margin=(0.05, 0.02))
card(s, 2.2, 3.0, 1.4, 0.6, fill=WHITE, line=BLUE, paras=[
    [("Response", {"b": True})], [("{id, category, request_id}", {"color": MUTED, "size": 8})]],
     size=10.5, align=PP_ALIGN.CENTER, margin=(0.03, 0.02))
arrow(s, 1.75, 2.375, 2.2, 2.375)
arrow(s, 3.6, 2.375, 4.0, 2.375)
arrow(s, 4.875, 2.8, 4.875, 3.0, RED)
arrow(s, 4.0, 3.3, 3.6, 3.3)
arrow(s, 4.1, 2.8, 3.45, 3.0, BLUE)
step(s, 1.85, 2.07, 1)
step(s, 3.67, 2.07, 2)
step(s, 3.62, 2.66, 3)
step(s, 5.0, 2.78, 4)
textbox(s, 0.65, 3.78, 5.3, 0.5, [
    [("1 ", {"b": True, "color": BLUE}), ("ticket in   ", {"color": MUTED}), ("2 ", {"b": True, "color": BLUE}),
     ("granite's category to the rule   ", {"color": MUTED}), ("3 ", {"b": True, "color": BLUE}),
     ("accepted → returned as is", {"color": MUTED})],
    [("4 ", {"b": True, "color": BLUE}),
     ("escalated (incl. UNPARSEABLE) → qwen2.5:7b, same frozen prompt; the caller cannot tell which answered",
      {"color": MUTED})]], size=9)
card(s, 0.65, 4.3, 5.25, 0.72, paras=[
    [("Memory check. ", {"b": True, "color": BLUE}),
     ("omarchy, 31.3 GiB, no container limit (2026-11-19). ", {}),
     ("ollama ps", {"font": MONO}), (" lists both models after alternating calls, 0 reloads, for every pair: "
                                     "1B + 7B 5.65 GiB · 3B + 7B 7.10 GiB · ", {}),
     ("granite + 7B 7.05 GiB (chosen)", {"b": True, "color": RED}), (".", {})]], size=9.5)
# right column
textbox(s, 6.1, 1.38, 3.0, 0.28, [[("The rule in full (category-based)", {"b": True, "size": 12})]])
card(s, 6.1, 1.7, 3.0, 0.72, paras=[
    [("escalate = small.predicted_category", {"font": MONO, "size": 8.5, "b": True})],
    [("           not in ACCEPT[setting]", {"font": MONO, "size": 8.5, "b": True})],
    [("Reads only granite's normalised category, never the label.", {"color": MUTED, "size": 9})]],
     margin=(0.1, 0.03), space_before=1)
table(s, [("Tuning (99)", "Setting A", "Setting B"),
          ("ACCEPT", ("Mortgage, Cons. loan, Debt coll.", {"size": 8}), ("A + Credit card", {"size": 8})),
          ("Escalated", "78/99 (78.8%)", "59/99 (59.6%)"),
          ("Correct", "75/99", "74/99"),
          ("Slipped by", ("0 of 30", {"color": RED, "b": True}), ("8 of 30", {"color": RED, "b": True}))],
      6.1, 2.5, 3.0, [0.8, 1.15, 1.05], row_h=0.24, size=8.5, head_size=8.5)
card(s, 6.1, 3.88, 3.0, 1.14, paras=[
    [("Why this rule. ", {"b": True, "color": BLUE}),
     ("No extra model call. Agreement escalates the same 59/99 as B for +2 correct, but adds a second small call "
      "to every ticket. Length does not predict granite's errors (71% vs 66% right). Confidence needs a prompt "
      "change or an extra call. Tuned on odd rows only.", {})]], size=9, anchor=MSO_ANCHOR.TOP,
     margin=(0.1, 0.05))
source(s, "cascade/escalation_rule.md §1–3 (settings pending whole-team sign-off, W.1); "
          "docs/environment/a2-memory-check/20261119T073203Z/summary.md")

# ============================================== 3. Environment & method ===
s = content_slide("Test Environment and Method")
chain = [("3.339 s", "S: middle of 3 qwen2.5:7b timings (3.851 / 3.339 / 3.029 s)", CARD, INK),
         ("8.98", "tickets a minute = 60 / (2 × S), one every 6.68 s", BLUE, WHITE),
         ("300 s", "per run (5-min minimum), ≈ 45 tickets, 3 runs", CARD, INK),
         ("≈ 370×", "the client's modelled peak of 0.024 a minute", CARD, INK)]
ops = ["× 2", "≥ 5 min", "vs peak"]
cw, gap = 1.62, 0.6
for i, (big, small, fill, col) in enumerate(chain):
    x = 0.7 + i * (cw + gap)
    card(s, x, 1.28, cw, 0.95, fill=fill, paras=[[(big, {"b": True, "size": 18, "color": col})],
                                                [(small, {"size": 9, "color": col})]], margin=(0.1, 0.04),
         space_before=1)
    if i < 3:
        textbox(s, x + cw, 1.36, gap, 0.3, [[(ops[i], {"b": True, "size": 10})]], align=PP_ALIGN.CENTER)
        arrow(s, x + cw + 0.08, 1.8, x + cw + gap - 0.08, 1.8)
textbox(s, 0.7, 2.38, 4.3, 0.28, [[("Each run (playbook cascade-test.md)", {"b": True, "size": 12})]])
steps = [("Gate.", "a2_gate.py exits 0; gate.json kept with the run."),
         ("Restart.", "Ollama restarted: no model loaded, prompt cache empty."),
         ("Warm-up.", "3 fixed tickets, timings discarded; cascade: ollama ps lists both models."),
         ("Measure.", "JMeter open model at 8.98/min over the fixed 100-ticket list, recycle off."),
         ("Drain.", "360 s pause outlasts the 300 s timeout; GET /stats before and after; .jtl reconciled.")]
for i, (h, d) in enumerate(steps):
    y = 2.72 + i * 0.47
    step(s, 0.72, y + 0.02, i + 1)
    textbox(s, 1.08, y - 0.02, 3.95, 0.47, [[(h + " ", {"b": True}), (d, {})]], size=9.5)
card(s, 5.2, 2.38, 3.9, 0.82, paras=[
    [("Machines unchanged. ", {"b": True, "color": BLUE}),
     ("Same three as Assignment 1: service and Ollama on omarchy (Ryzen 9 5900X, 31.3 GiB), JMeter on "
      "kais-macbook-pro. No container limit: the whole host, as in A1.", {})]], size=9.5)
card(s, 5.2, 3.28, 3.9, 0.82, paras=[
    [("Checked unchanged before every configuration. ", {"b": True, "color": BLUE}),
     ("Ollama 0.34.3, all 4 digests, NUM_PARALLEL / MAX_LOADED_MODELS = 0, num_ctx 4096, seed 42, prompt hash.",
      {})]], size=9.5)
card(s, 5.2, 4.18, 3.9, 0.86, paras=[
    [("Workload tickets. ", {"b": True, "color": BLUE}),
     ("100 fixed non-golden rows (70 typical, 30 long), same order for every configuration. ", {}),
     ("Changed from A1: ", {"b": True, "color": RED}),
     ("rate from S, fixed list, 3 warm-ups, two-model check, no p99.", {})]], size=9.5)
source(s, "docs/a2/arrival-rate.md §1–4; docs/a2/env_baseline.json; docs/test-environment.md; "
          "workload/speed_test_rows_a2.txt; docs/playbooks/cascade-test.md §4")

# ================================================== 4. Accuracy results ===
s = content_slide("Accuracy Results")
cfgs = ["granite 3B", "llama 3B", "llama 1B", "Casc. A", "Casc. B"]
rows = [("Category (N)", "Limit", "Pass ≥", "qwen 7B (ref.)") + tuple(cfgs)]
for n, N, c, p, lim, needs, b in CATS:
    rows.append(((("⚠ " if b else "") + f"{n.replace(' or service', '')} ({N})", {"color": RED} if b else {}), lim, needs, f"{c}/{N} ({p})")
                + (PENDING,) * 5)
rows.append((("Overall (101)", {"fill": CARD}), ("64.26%", {"fill": CARD, "b": True}), ("65/101", {"fill": CARD, "b": True}),
             ("75/101 (74.3%)", {"fill": CARD, "b": True})) + (PENDING,) * 5)
rows.append(("Passes both?", "", "", ("reference", {"b": True, "color": BLUE})) + (PENDING,) * 5)
table(s, rows, 0.7, 1.25, 8.4, [1.85, 0.72, 0.65, 1.13, 0.81, 0.81, 0.81, 0.81, 0.81], row_h=0.235, size=9, head_size=9)
pending_card(s, 0.7, 3.85, 4.1, 1.17, "escalation fraction on the test set (Setting A and B), and accuracy of "
                                      "escalated vs accepted tickets, from the cascade accuracy run's service log.")
card(s, 5.0, 3.85, 4.1, 1.17, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.07), paras=[
    [("Reused, not re-run. ", {"b": True, "color": BLUE}),
     ("The four single models are re-scored from their Assignment 1 answers on the 101 even rows: same digests, "
      "prompt, Ollama 0.34.3 and machine. Only the cascade is new.", {})],
    [("⚠ N = 11: ", {"b": True, "color": RED}),
     ("a verdict rests on one or two tickets; Mortgage's 3/11 is barely a test.", {})]], size=9.5, space_before=3)
source(s, "docs/a2/accuracy_limits.md §1–3 (limits, qwen2.5:7b); analysis/output/accuracy_a2/ (other columns, "
          "once produced); exact counts decide pass/fail")

# ===================================================== 5. Speed results ===
s = content_slide("Speed Results")
rows = [("Configuration", "p50/run", "Mean±SD", "p95 [n]", "Thru", "Err %", "Esc.")]
for name, esc in [("qwen2.5:7b (ref.)", "n/a"), ("Passing singles", "n/a"), ("Cascade A", None), ("Cascade B", None)]:
    rows.append((name,) + (PENDING,) * 5 + ((esc, {"color": MUTED}) if esc else PENDING,))
table(s, rows, 0.7, 1.3, 5.5, [1.3, 0.75, 0.75, 0.7, 0.66, 0.66, 0.68], row_h=0.3, size=9, head_size=9)
textbox(s, 0.7, 2.88, 5.5, 0.45, [[("Latency in seconds; p95 pooled over the 3 runs with its count; Thru in "
                                     "tickets an hour. No p99: the sample is too small.", {"color": MUTED})]],
        size=9.5)
pending_card(s, 0.7, 3.45, 5.5, 0.7, "sent / completed / errored / unfinished per run, and the no-queue check "
                                    "(halves within 20%, queue wait under 100 ms).", size=9.5)
pending_card(s, 0.7, 4.27, 5.5, 0.75, "escalation under load vs on the test set, per setting; a gap over 15 pp "
                                    "is explained.", size=9.5)
card(s, 6.4, 1.3, 2.7, 1.15, paras=[
    [("Same load for all. ", {"b": True, "color": BLUE}),
     ("8.98 a minute for 300 s, 3 runs, the same 100 tickets: ≈ 135 requests behind each pooled p95.", {})]],
     size=9.5)
card(s, 6.4, 2.58, 2.7, 1.15, paras=[
    [("Fresh numbers only. ", {"b": True, "color": BLUE}),
     ("No Assignment 1 speed figure is reused, ", {}), ("qwen2.5:7b included", {"b": True, "color": RED}),
     (".", {})]], size=9.5)
card(s, 6.4, 3.86, 2.7, 1.16, paras=[
    [("Nothing dropped. ", {"b": True, "color": BLUE}),
     ("A cascade setting failing accuracy is still shown, marked ", {}),
     ("not passing", {"b": True, "color": RED}), ("; unfinished requests are reported.", {})]], size=9.5)
source(s, "analysis/output/speed_a2/per_config.csv, per_run.csv (analysis/summarise_load_a2.py); "
          "every run reconciled by analysis/reconcile.py")

# ========================================================= 6. Trade-off ===
s = content_slide("Trade-off: Accuracy vs Latency")
cx, cy, cwid, ch = 1.25, 1.35, 4.95, 3.3
line(s, cx, cy, cx, cy + ch, MUTED, 1)
line(s, cx, cy + ch, cx + cwid, cy + ch, MUTED, 1)


def yof(p):
    return cy + ch - (p - 50) / 30 * ch


for p in (50, 60, 70, 80):
    textbox(s, cx - 0.5, yof(p) - 0.1, 0.45, 0.2, [[(f"{p}%", {"color": MUTED})]], size=8.5, align=PP_ALIGN.RIGHT)
    if p > 50:
        line(s, cx, yof(p), cx + cwid, yof(p), CARD, 0.75)
line(s, cx, yof(64.26), cx + cwid, yof(64.26), RED, 1.75, "dash")
textbox(s, cx + cwid - 2.2, yof(64.26) - 0.24, 2.2, 0.22, [[("Overall limit 64.26%", {"b": True, "color": RED})]],
        size=9, align=PP_ALIGN.RIGHT)
line(s, cx, yof(74.26), cx + cwid, yof(74.26), BLUE, 1.25, "sysDot")
textbox(s, cx + cwid - 2.6, yof(74.26) - 0.24, 2.6, 0.22, [[("qwen2.5:7b on the test set 74.26%",
                                                             {"color": BLUE})]], size=9, align=PP_ALIGN.RIGHT)
textbox(s, 0.55, cy + ch / 2 - 0.3, 0.6, 0.4, [[("Test-set accuracy", {"color": MUTED})]], size=8.5,
        align=PP_ALIGN.CENTER)
textbox(s, cx, cy + ch + 0.05, cwid, 0.22, [[("Median latency (mean of per-run p50)  →  faster to the left",
                                              {"color": MUTED})]], size=8.5, align=PP_ALIGN.CENTER)
pending_card(s, cx + 0.45, yof(57) - 0.22, cwid - 0.9, 0.5, "one point per configuration and setting; failing "
                                                             "points drawn hollow.", size=9.5)
card(s, 6.45, 1.3, 2.65, 1.5, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.07), paras=[
    [("How to read it. ", {"b": True, "color": BLUE}),
     ("Up is more accurate, left is faster. The pick is the left-most point above the red line, and it must be ", {}),
     ("distinguishably faster", {"b": True, "color": RED}), (" than qwen2.5:7b.", {})]], size=9.5)
pending_card(s, 6.45, 2.95, 2.65, 1.75, "short interpretation: where each cascade setting sits relative to the "
                                       "single models, and whether it beats the best qualifying one on speed.",
             size=9.5)
source(s, "Slide 4 (test-set accuracy) × Slide 5 (mean per-run p50); analysis/output/accuracy_a2/, "
          "analysis/output/speed_a2/")

# ======================================= 7. Predictions, recommendation ===
s = content_slide("Predictions, Recommendation and Defence")
rows = [("Prediction", "Predicted", "Measured", "Why we were off"),
        ("Fastest config passing both limits", PENDING, PENDING, PENDING),
        ("Setting A: escalation, accuracy, p50", PENDING, PENDING, PENDING),
        ("Setting B: escalation, accuracy, p50", PENDING, PENDING, PENDING),
        ("Categories losing most when accepted", PENDING, PENDING, PENDING)]
table(s, rows, 0.7, 1.3, 8.4, [2.7, 1.7, 1.7, 2.3], row_h=0.4, size=10, head_size=10)
card(s, 0.7, 3.5, 4.1, 1.4, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.08), paras=[
    [("Recommended configuration. ", {"b": True, "color": BLUE}), ("pending", {"i": True, "color": VIOLET})],
    [("Against the overall limit and all seven category limits; speed gain vs qwen2.5:7b; accuracy cost in counts. "
      "If the cascade lost: why, citing the measured escalation fraction and both latencies.", {"color": MUTED})]],
     size=9.5, space_before=4)
card(s, 5.0, 3.5, 4.1, 1.4, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.08), paras=[
    [("Decision rule, fixed before measuring. ", {"b": True, "color": BLUE}),
     ("Rank by the mean of the three per-run p50s; A beats B only if A's p50 range lies wholly below B's. "
      "Ties: higher accuracy, then the simpler configuration. ", {}),
     ("Not distinguishably faster than qwen2.5:7b → recommend qwen2.5:7b.", {"b": True, "color": RED})]], size=9.5)
source(s, "predictions/prediction_record_a2.md (frozen under tag a2-predictions-freeze, checked by "
          "scripts/a2_gate.py); Slides 4–6")

# ================================= 8. Limitations, references, AI use ===
s = content_slide("Limitations, References and AI Use")
lims = [("Small sample.", "101 test tickets; three categories at N = 11 (one ticket = 9.1 pp)."),
        ("Seen tickets.", "Test tickets were already classified in A1; single models are re-scored, not re-run."),
        ("One machine.", "One desktop CPU; a server with more memory channels would differ."),
        ("One arrival rate.", "8.98 a minute for 5 min, ≈ 370× the modelled peak (itself an assumed ×2), so it "
                              "covers the peak, not bursts."),
        ("Service overhead.", "≈ 0.55 s a ticket is SQLite's fsync on btrfs, equal in every configuration.")]
card(s, 0.7, 1.28, 4.1, 2.62, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.07),
     paras=[[("What the results do not show", {"b": True, "color": BLUE, "size": 11})]] +
           [[(h + " ", {"b": True}), (d, {})] for h, d in lims], size=9, space_before=3)
card(s, 0.7, 3.98, 4.1, 1.06, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.07), paras=[
    [("AI use. ", {"b": True, "color": BLUE}),
     ("Claude Code (Anthropic) wrote the cascade code, A2 scripts, JMeter plan and tests, computed limits and "
      "tuning counts by script, and drafted documents and slides. ", {}),
     ("The team chose the rule and settings, made the predictions, ran every test and made the recommendation.",
      {"b": True})]], size=9)
refs = [
    "[1] US CFPB, \"Consumer Complaint Database.\" consumerfinance.gov/data-research/consumer-complaints/.",
    "[2] ICT3113 teaching team, \"Assignment 1 ticket extract (ict3113_tickets.csv),\" from [1], xSiTe.",
    "[3] ICT3113 teaching team, \"Assignment 2: Fast Triage Within an Accuracy Floor,\" xSiTe, 2026.",
    "[4] Apache Software Foundation, \"Apache JMeter,\" v5.6.3. jmeter.apache.org.",
    "[5] Ollama, \"Ollama,\" v0.34.3, MIT License. ollama.com.",
    "[6] Meta Platforms, \"Llama 3.2 Community License Agreement,\" 25 Sep. 2024.",
    "[7] IBM Granite Team, \"granite-4.0-micro\" (granite4:3b; Apache-2.0).",
    "[8] Qwen Team, Alibaba Cloud, \"Qwen2.5-7B-Instruct\" (qwen2.5:7b; Apache-2.0).",
    "[9] Service stack: Docker 29.7.2, Python 3.11.17, FastAPI 0.142.4, SQLite 3.46.1.",
]
textbox(s, 5.0, 1.28, 4.1, 0.25, [[("References", {"b": True, "size": 11})]])
textbox(s, 5.0, 1.52, 4.1, 2.42, [[(r, {})] for r in refs], size=8, space_before=2)
card(s, 5.0, 3.98, 4.1, 1.06, anchor=MSO_ANCHOR.TOP, margin=(0.12, 0.07), paras=[
    [("Licences. ", {"b": True, "color": BLUE}),
     ("Built with Llama. Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright © Meta Platforms, "
      "Inc. All Rights Reserved [6]. granite4:3b [7] and qwen2.5:7b [8] are Apache-2.0. No new models in A2.", {})]],
     size=9)
source(s, "docs/a2/accuracy_limits.md §2; docs/a2/arrival-rate.md §1, §4; docs/references.md; "
          "models/candidates.md; docs/a2/ai-use-log.md")

prs.core_properties.title = "Group 10: Fast Triage Within an Accuracy Floor"
prs.save(str(OUT))
print(f"wrote {OUT}")
