"""Refreshes slides 2-10 of MSRIT_Brutal Bruteforcers_Submission.pptx in place.

Slide 1 (team details), 11 (checklist) and 12 (thank you) are never touched, and slide
titles keep whatever text/style the team gave them. Numbers come from eval/metrics.json
(offline headline), metrics_before.json and metrics_llm.json, so a new metrics run keeps
the deck in sync. Speaker notes hold a short reading script for the demo recording.

    python scripts/build_deck.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"

BLUE = RGBColor(0x14, 0x28, 0xA0)
INK = RGBColor(0x11, 0x18, 0x27)
GREY = RGBColor(0x4B, 0x55, 0x63)
LIGHT = RGBColor(0xF3, 0xF4, 0xF6)
SOFT = RGBColor(0xEE, 0xF2, 0xFF)
LINE = RGBColor(0xD1, 0xD5, 0xDB)
RED = RGBColor(0xB9, 0x1C, 0x1C)
AMBER = RGBColor(0xB4, 0x53, 0x09)
GREEN = RGBColor(0x04, 0x78, 0x57)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BODY = "Calibri"
MONO = "Consolas"


# ---------------------------------------------------------------- small helpers
def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, margin=0.0):
    """paras: list of (text, size, bold, color) or dicts with extra keys (font, align, space)."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, p in enumerate(paras):
        if isinstance(p, tuple):
            p = dict(zip(("text", "size", "bold", "color"), p))
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = p.get("align", PP_ALIGN.LEFT)
        para.space_after = Pt(p.get("space", 4))
        runs = p["text"] if isinstance(p["text"], list) else [(p["text"], p.get("bold", False), p.get("color", INK))]
        for t, bold, color in runs:
            r = para.add_run()
            r.text = t
            r.font.size = Pt(p.get("size", 14))
            r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = p.get("font", BODY)
    return box


def card(slide, x, y, w, h, fill=LIGHT, line=None, radius=0.08):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = radius
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1.25)
    shp.shadow.inherit = False
    return shp


def dot(slide, x, y, d, label, fill=BLUE, size=14):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid()
    c.fill.fore_color.rgb = fill
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = WHITE
    r.font.name = BODY
    return c


def arrow(slide, x1, y1, x2, y2, color=GREY, width=2):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = color
    ln.line.width = Pt(width)
    # arrow head: python-pptx has no API for it, so poke the XML
    from pptx.oxml.ns import qn
    lnxml = ln.line._get_or_add_ln()
    tail = lnxml.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    lnxml.append(tail)
    return ln


def picture(slide, path, x, y, w=None, h=None, border=True):
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(1)
    return pic


def reset_slide(slide, title):
    """Set the title and drop the empty body placeholder so our shapes own the space."""
    for shp in list(slide.placeholders):
        idx = shp.placeholder_format.idx
        if idx == 0:
            tf = shp.text_frame
            tf.paragraphs[0].runs[0].text = title
            for extra in tf.paragraphs[0].runs[1:]:
                extra.text = ""
        else:
            shp._element.getparent().remove(shp._element)


def title_size(slide, pt):
    for shp in slide.placeholders:
        if shp.placeholder_format.idx == 0:
            for r in shp.text_frame.paragraphs[0].runs:
                r.font.size = Pt(pt)


def notes(slide, body):
    slide.notes_slide.notes_text_frame.text = body


def tier_chip(slide, x, y, label, color):
    c = card(slide, x, y, 0.95, 0.3, fill=color, radius=0.5)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = WHITE
    r.font.name = BODY


# ---------------------------------------------------------------- slides
def clear_slide(slide):
    """Keep the slide title (text and style as the team left it), drop everything else."""
    for shp in list(slide.shapes):
        if shp.is_placeholder and shp.placeholder_format.idx == 0:
            continue
        shp._element.getparent().remove(shp._element)


def first_line(path: Path, n: int) -> list[str]:
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines[:n]


def slide_theme(s, m, kit):
    clear_slide(s)
    text(s, 0.92, 1.75, 11.5, 0.5, [("Theme 2: Smart Guided Troubleshooting Engine", 20, True, BLUE)])
    text(s, 0.92, 2.25, 5.4, 0.4, [("What customers actually type (kit input.txt)", 13, True, GREY)])
    for i, q in enumerate(kit["quotes"]):
        y = 2.7 + i * 1.08
        card(s, 0.92, y, 5.4, 0.92, fill=LIGHT)
        text(s, 1.12, y + 0.1, 5.0, 0.75, [(f"“{q}”", 13, False, INK)], anchor=MSO_ANCHOR.MIDDLE)
    arrow(s, 6.5, 4.25, 7.25, 4.25, color=BLUE, width=3)

    card(s, 7.45, 2.25, 4.95, 3.65, fill=WHITE, line=LINE)
    text(s, 7.7, 2.4, 4.5, 0.6, [
        ("What the engine sends back", 12, True, GREY),
        ("Follow these steps to perform this Touchscreen Troubleshooting", 14, True, INK),
    ])
    rows = [
        ("auto", BLUE, "Enable Touch Sensitivity", kit["touch_uri"]),
        ("manual", AMBER, "Check the Charger", "no link, done by hand"),
        ("critical", RED, "Restart in Safe Mode", "unlocked only if the rest fails"),
    ]
    for i, (tag, col, name, sub) in enumerate(rows):
        y = 3.45 + i * 0.78
        tier_chip(s, 7.7, y + 0.05, tag, col)
        text(s, 8.8, y - 0.02, 3.5, 0.7, [
            (name, 14, True, INK),
            {"text": sub, "size": 11, "color": GREY, "font": MONO if "://" in sub else BODY},
        ])
    text(s, 0.92, 6.15, 11.5, 0.8, [
        ("Goal: a vague complaint in, an ordered plan out, where every Settings step opens in one tap. "
         "Today that takes an agent ~15 minutes per ticket. The brief asks for < 300 ms on known issues and < 8 s on new ones.",
         14, False, GREY),
    ])
    notes(s, "Theme 2 is about turning vague complaints into a plan the phone can act on. On the left are three complaints straight "
             "from the kit. None of them name the setting that's wrong. On the right is a cut-down version of what our engine returns "
             "for the first one: an ordered plan with a one-tap link for the Settings step, a physical check, and a last-resort step "
             "that only unlocks if the others don't help. Right now an agent does this by hand in about fifteen minutes.")


def slide_gaps(s, m, before):
    clear_slide(s)
    text(s, 0.92, 1.8, 3.9, 0.4, [("How it's done today", 16, True, BLUE)])
    today = [
        ("Agent reads the SIIS article", "long help pages, half of it background"),
        ("Picks and orders steps by hand", "different agents, different answers"),
        ("Customer digs through menus", "Settings > Display > Navigation bar"),
    ]
    for i, (h, sub) in enumerate(today):
        y = 2.35 + i * 1.1
        dot(s, 0.92, y, 0.5, str(i + 1))
        text(s, 1.55, y - 0.05, 3.3, 0.95, [(h, 14, True, INK), (sub, 12, False, GREY)])
    card(s, 0.92, 5.7, 3.9, 1.05, fill=SOFT)
    text(s, 1.1, 5.78, 3.6, 0.9, [("~15 min", 26, True, BLUE), ("per ticket, per the brief", 12, False, GREY)])

    text(s, 5.25, 1.8, 7.2, 0.4, [("What we found missing", 16, True, BLUE)])
    gaps = [
        ("Brief", "validationDeeplink exists in the schema, but nothing says how to fill it, so no one checks the fix worked"),
        ("Brief", "“Return empty if no viable fix” is never defined, and a search always returns something"),
        ("Brief", "One problem per message is assumed. One kit complaint has three"),
        ("Brief", "A wrong plan in the cache is served to every paraphrase of it"),
        ("Starter code", "Titles cut to 3 words (“Some things to”), factory reset marked as a one-tap step"),
        ("Starter code", f"Rule compliance {before['compliance']['rule_compliance_pct']:.0f}%, 0% cache hits on real rephrasings"),
    ]
    tbl = s.shapes.add_table(len(gaps) + 1, 2, Inches(5.25), Inches(2.3), Inches(7.2), Inches(4.1)).table
    tbl.columns[0].width = Inches(1.35)
    tbl.columns[1].width = Inches(5.85)
    tbl.rows[0].height = Inches(0.42)
    for row in list(tbl.rows)[1:]:
        row.height = Inches(0.6)
    for c, h in enumerate(("Where", "Gap")):
        cell = tbl.cell(0, c)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = BLUE
        r = cell.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(12), True, WHITE, BODY
    for i, (where, g) in enumerate(gaps, start=1):
        for c, val in enumerate((where, g)):
            cell = tbl.cell(i, c)
            cell.text = val
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
            cell.margin_top = cell.margin_bottom = Inches(0.05)
            r = cell.text_frame.paragraphs[0].runs[0]
            r.font.size, r.font.name = Pt(12), BODY
            r.font.color.rgb = GREY if c == 0 else INK
            r.font.bold = c == 0
    notes(s, "Today an agent reads the article, picks steps by hand and the customer hunts through menus. When we read the brief "
             "closely we found holes: the validation field has no rule, 'return empty' is never defined, and multi-problem messages "
             "aren't covered. We also ran the starter code on the kit: titles were cut off, a factory reset was a one-tap step, and "
             "only five percent of plans passed the brief's own rules.")


def slide_arch(s, m, llm):
    clear_slide(s)
    picture(s, IMG / "system_architecture.png", 0.92, 1.72, w=11.5, border=False)
    llm_p50 = f"{llm['latency']['cold']['p50'] / 1000:.1f}" if llm else "~4"
    text(s, 0.92, 7.0, 11.5, 0.35, [(
        f"Offline by default: a new complaint takes ~{m['latency']['cold']['p50']:.0f} ms, a cached one ~{m['latency']['exact']['p95']:.0f} ms. "
        "The LLM is optional and never gets the last word: its output goes through the same checks.", 12, False, GREY)])
    notes(s, "Four layers. On top, the clients: our web console, the batch and eval runner, and the closed-loop phone check. They all "
             "call one FastAPI service. In the engine, a complaint is enriched first, then we try the semantic cache. On a hit the plan "
             "comes back in a couple of milliseconds. On a miss we look up the SIIS article, stop with an empty plan if nothing fits, "
             "extract steps, map each Settings step to its exact catalog deeplink, and validate everything against the brief's rules. "
             "Groq is optional and only drafts; our validators decide.")


def slide_demo(s, m):
    clear_slide(s)
    picture(s, IMG / "demo_plan.png", 0.92, 1.75, w=7.35)
    picture(s, IMG / "demo_trace.png", 8.55, 1.75, w=3.9)
    text(s, 8.55, 4.3, 3.9, 0.35, [("Trace tab: hover a step, its source sentence lights up", 11, False, GREY)])
    steps = [
        "Pick a kit complaint (or type one)",
        "Plan comes back in 3 tiers: phone, by hand, last resort",
        "Run safe steps: the phone opens each screen and reads the setting back",
        "Trace + JSON tabs: where every step came from",
    ]
    for i, t in enumerate(steps):
        y = 4.8 + i * 0.52
        dot(s, 8.55, y, 0.36, str(i + 1), size=12)
        text(s, 9.05, y - 0.02, 3.4, 0.5, [(t, 12, False, INK)], anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.92, 6.45, 7.35, 0.5, [
        ("Touchscreen complaint with its SIIS article, then Run safe steps. Pages: Troubleshoot, Batch run, Metrics, Gaps.", 11, False, GREY),
    ])
    notes(s, "Recording order: pick the touchscreen complaint, show the plan in its three tiers, press Run safe steps and watch the "
             "phone open each screen and confirm the setting, unlock the last-resort tier, then open the Trace tab and hover a step "
             "to show the exact sentence it came from. Finish on Batch run for all twenty complaints.")


def slide_stack(s, m, llm):
    clear_slide(s)
    model = (llm or {}).get("llm_model") or "openai/gpt-oss-120b"
    groups = [
        ("Engine", ["Python 3.12", "FastAPI + Uvicorn", "Pydantic (kit schema.py)"], "REST API, validators, simulator"),
        ("Retrieval", ["scikit-learn TF-IDF", "word + char n-grams", "NumPy / SciPy"], "SIIS lookup, deeplink map, cache"),
        ("LLM (optional)", ["Groq Cloud", model, "OpenAI-compatible client"], "drafts get re-checked, falls back offline"),
        ("Console", ["Next.js 16 + React 19", "Tailwind 4 + shadcn", "light / dark theme"], "plan, trace, phone simulator"),
        ("Testing", ["pytest", "own Appendix C scorer", "gold labels, 60 paraphrases"], "before/after numbers"),
    ]
    w, gap = 2.18, 0.15
    for i, (head, items, used) in enumerate(groups):
        x = 0.92 + i * (w + gap)
        card(s, x, 1.95, w, 3.3, fill=LIGHT)
        text(s, x + 0.18, 2.1, w - 0.3, 0.45, [(head, 17, True, BLUE)])
        text(s, x + 0.18, 2.65, w - 0.3, 1.5, [(t, 14 if len(t) < 22 else 12, False, INK) for t in items])
        text(s, x + 0.18, 4.2, w - 0.3, 0.95, [("used for", 11, True, GREY), (used, 12, False, GREY)])
    text(s, 0.92, 5.6, 11.5, 0.7, [
        ("Runs with no API key at all. The default path is deterministic and costs $0 per query; "
         "a GROQ_API_KEY in .env switches the LLM path on.", 13, False, GREY),
    ])
    notes(s, "The engine is plain Python with FastAPI. Retrieval is scikit-learn TF-IDF, no GPU and no paid model needed. "
             "The LLM path uses Groq's gpt-oss-120b and is optional. The console is Next.js with a light and dark theme, and we test "
             "with pytest plus our own scorer for the Appendix C metrics.")


def slide_impact(s, m, before):
    clear_slide(s)
    stats = [
        (f"{m['latency']['cold']['p95']:.0f} ms", "P95 for a brand-new complaint", "vs ~15 min manual, target 8 s"),
        (f"{m['latency']['exact']['p95']:.0f} ms", "P95 when the cache already knows it", "$0, no model call"),
        (f"{m['cache']['hit_pct']:.0f}%", "of 60 unseen rephrasings answered from cache", f"was {before['cache']['hit_pct']:.0f}% before"),
    ]
    for i, (big, label, sub) in enumerate(stats):
        x = 0.92 + i * 3.9
        card(s, x, 1.85, 3.65, 1.6, fill=SOFT)
        text(s, x + 0.25, 1.95, 3.2, 1.5, [(big, 34, True, BLUE), (label, 13, True, INK), (sub, 11, False, GREY)])
    text(s, 0.92, 3.9, 5.6, 0.4, [("A typical ticket", 16, True, BLUE)])
    story = [
        "“Nexa X1 touch is laggy and inputs are delayed”",
        "Plan: Touch sensitivity, nav bar to buttons, check the charger",
        "Phone confirms each setting really changed",
        "Still laggy? Only then restart, safe mode, reset (backup first)",
    ]
    for i, t in enumerate(story):
        y = 4.4 + i * 0.6
        dot(s, 0.92, y, 0.38, str(i + 1), size=12)
        text(s, 1.45, y - 0.03, 5.1, 0.5, [(t, 13, False, INK)], anchor=MSO_ANCHOR.MIDDLE)
    picture(s, IMG / "demo_batch.png", 7.55, 3.95, w=4.85)
    text(s, 7.55, 7.03, 4.85, 0.3, [("Batch run: all 20 kit complaints in one go", 11, False, GREY)])
    notes(s, "The three numbers are from our metrics run. A new complaint is answered in about a tenth of a second at worst, "
             "a known one in a couple of milliseconds with no model call, and most rephrasings are recognised from the cache. "
             "For a customer it means one tap per fix, and the disruptive steps only come up when they're really needed.")


def slide_results(s, m, before, llm):
    clear_slide(s)
    title_size(s, 36)
    text(s, 0.92, 1.75, 6.3, 0.4, [("Before (starter code) vs after, same scorer", 14, True, BLUE)])
    cats = ["Rule compliance", "Exact deeplink screen", "Rephrasing cache hits", "Checkable validation"]
    b = [before["compliance"]["rule_compliance_pct"], before["accuracy"]["deeplink_relevance"] / 2 * 100,
         before["cache"]["hit_pct"], before["compliance"]["verifiable_validation_pct"]]
    a = [m["compliance"]["rule_compliance_pct"], m["accuracy"]["deeplink_relevance"] / 2 * 100,
         m["cache"]["hit_pct"], m["compliance"]["verifiable_validation_pct"]]
    data = CategoryChartData()
    data.categories = cats
    data.add_series("Before", [round(v, 1) for v in b])
    data.add_series("After", [round(v, 1) for v in a])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.92), Inches(2.15), Inches(6.4), Inches(3.2), data)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    ch.value_axis.minimum_scale = 0
    ch.value_axis.maximum_scale = 108
    ch.value_axis.major_unit = 20
    ch.value_axis.has_major_gridlines = True
    ch.value_axis.major_gridlines.format.line.color.rgb = LINE
    ch.value_axis.tick_labels.font.size = Pt(10)
    ch.value_axis.tick_labels.font.color.rgb = GREY
    ch.value_axis.format.line.fill.background()
    ch.category_axis.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.color.rgb = INK
    plot = ch.plots[0]
    plot.gap_width = 70
    plot.overlap = -10
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(10)
    plot.data_labels.number_format = '0"%"'
    plot.data_labels.number_format_is_linked = False
    plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    for ser, col in zip(plot.series, (RGBColor(0x9C, 0xA3, 0xAF), BLUE)):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = col
    llm_line = ""
    if llm:
        share = max(llm.get("llm_share_pct", 0.0), 0.1) / 100
        llm_line = (f" LLM mode ({llm['llm_model']}) works, ~${llm['cost']['cold_avg_usd'] / share:.4f} per LLM-made plan; "
                    f"on Groq's free tier only {llm.get('llm_share_pct', 0):.0f}% of batch plans got through before rate limits, "
                    "the rest fell back offline.")
    text(s, 0.92, 5.4, 6.4, 0.6, [(
        f"Step accuracy {before['accuracy']['step_accuracy']} → {m['accuracy']['step_accuracy']} (of 3). "
        f"URL leaks 0, catalog-valid links 100%.{llm_line}", 10, False, GREY)])

    text(s, 0.92, 6.05, 6.4, 0.35, [("Limitations", 14, True, BLUE)])
    text(s, 0.92, 6.4, 6.4, 0.9, [
        ("A few kit complaints come with only loosely related articles; the score drops, the plan stays honest.", 11, False, INK),
        (f"{m['cache']['wrong_hit_pct']:.0f}% of rephrasings hit a plan from a neighbouring article. The phone is simulated.", 11, False, INK),
    ])

    text(s, 7.7, 1.75, 4.75, 0.4, [("Innovation: check the fix actually worked", 14, True, BLUE)])
    picture(s, IMG / "closed_loop.png", 7.7, 2.2, w=4.75, border=False)
    loop = m["closed_loop"]
    text(s, 7.7, 5.25, 4.75, 1.9, [
        ("We fill validationDeeplink from the catalog: onURL means expect True, offURL means False, "
         "updateURL means the value went up or down.", 12, False, INK),
        (f"On the kit, {loop.get('fixed_and_confirmed', '-')} of {loop.get('verified_taps', '-')} simulated toggles were "
         "confirmed. Restart and reset stay locked until the safe fixes are done.", 12, False, INK),
        ("Also: step-to-sentence trace, relevance gate, one plan per problem.", 12, False, GREY),
    ])
    notes(s, "Left: the same scorer run on the starter code and on ours. Rule compliance goes from five to a hundred percent, and "
             "every Settings step now lands on its exact screen. Right is the part we're proudest of: a one-tap link only proves a "
             "screen opened, so we read the setting back through its validation link and only then move on. We're upfront about the "
             "limits: the phone is simulated, and a few kit complaints only have loosely related articles.")


def slide_next(s, m):
    clear_slide(s)
    steps = [
        ("Real device check", "Run the val/ reads through the voice agent on a real phone instead of our simulator."),
        ("Learn from outcomes", "Log which fix actually closed the ticket and rank plans with that."),
        ("Hindi / Hinglish", "Most complaints in India mix languages. Add normalisation and multilingual embeddings."),
        ("Per-device screens", "Fold cover vs inner display, tablets. We detect the model already; the catalog doesn't split yet."),
    ]
    y_line = 2.75
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(1.4), Inches(y_line), Inches(11.9), Inches(y_line))
    ln.line.color.rgb = LINE
    ln.line.width = Pt(3)
    for i, (h, body) in enumerate(steps):
        x = 0.92 + i * 2.95
        dot(s, x + 0.3, y_line - 0.35, 0.7, str(i + 1), size=18)
        card(s, x, 3.45, 2.7, 2.05, fill=LIGHT)
        text(s, x + 0.2, 3.6, 2.35, 1.85, [(h, 17, True, INK), (body, 14, False, GREY)])
    text(s, 0.92, 5.85, 11.5, 0.6, [
        ("Soon: warm the cache from real ticket history, and move to a paid LLM tier so it isn't rate-limited.", 13, False, GREY),
    ])
    notes(s, "Next steps, roughly in order. The most important is running the closed loop on a real phone, since today it's simulated. "
             "Then learning from which fix actually solved the ticket, supporting Hindi and Hinglish complaints, and per-device screens.")


def slide_diff(s, m, before):
    clear_slide(s)
    items = [
        ("We measured it", "Our own scorer, hand-labelled gold and 60 rephrasings we wrote. Run on the starter code too, so the "
                           f"“before” is real ({before['compliance']['rule_compliance_pct']:.0f}% → "
                           f"{m['compliance']['rule_compliance_pct']:.0f}% rule compliance)."),
        ("Fixes get checked", "A deeplink only proves a screen opened. We read the setting back and only then move on."),
        ("Nothing made up", "Every step points to the sentence in the SIIS text it came from. No fit means an empty plan, not a guess."),
        ("Works offline", "No API key needed, $0 per query. The LLM is an optional extra, re-checked like everything else."),
    ]
    for i, (h, body) in enumerate(items):
        col, row = i % 2, i // 2
        x, y = 0.92 + col * 3.55, 1.95 + row * 2.2
        card(s, x, y, 3.35, 2.0, fill=SOFT if i % 3 == 0 else LIGHT)
        text(s, x + 0.22, y + 0.18, 2.95, 1.7, [(h, 17, True, BLUE), (body, 13, False, INK)])
    picture(s, IMG / "demo_metrics.png", 8.15, 1.95, w=4.3)
    text(s, 8.15, 4.75, 4.3, 0.6, [("Metrics page in the console, same numbers as metrics.md", 11, False, GREY)])
    notes(s, "What sets us apart: we measured ourselves honestly, including the starter code; our fixes get checked, not just linked; "
             "nothing in a plan is invented; and it all runs offline for free.")


def kit_facts() -> dict:
    catalog = json.loads((ROOT / "data" / "deeplinks.json").read_text(encoding="utf-8"))["deeplinks"]
    touch = next(r["deeplink"] for r in catalog if r["id"] == "DL-0126")
    lines = [l.strip() for l in (ROOT / "data" / "input.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    picks = [next(l for l in lines if "inputs are delayed" in l),
             next(l for l in lines if "cracked" in l and "Fold" not in l),
             next(l for l in lines if "completely black and won" in l)]
    short = [re.split(r"[,;]\s", p)[0].rstrip(".") + "." for p in picks]
    return {"quotes": short, "touch_uri": touch}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default=str(ROOT / "MSRIT_Brutal Bruteforcers_Submission.pptx"),
                    help="edited in place: slides 1, 11 and 12 are never touched")
    args = ap.parse_args()
    m = json.loads((ROOT / "eval" / "metrics.json").read_text(encoding="utf-8"))
    before = json.loads((ROOT / "eval" / "metrics_before.json").read_text(encoding="utf-8"))
    llm_path = ROOT / "eval" / "metrics_llm.json"
    llm = json.loads(llm_path.read_text(encoding="utf-8")) if llm_path.exists() else None

    prs = Presentation(args.deck)
    sl = prs.slides
    slide_theme(sl[1], m, kit_facts())
    slide_gaps(sl[2], m, before)
    slide_arch(sl[3], m, llm)
    slide_demo(sl[4], m)
    slide_stack(sl[5], m, llm)
    slide_impact(sl[6], m, before)
    slide_results(sl[7], m, before, llm)
    slide_next(sl[8], m)
    slide_diff(sl[9], m, before)
    prs.save(args.deck)
    print("saved", args.deck)


if __name__ == "__main__":
    main()
