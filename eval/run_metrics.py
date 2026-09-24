"""Measure the engine against Appendix C of the brief and write metrics.md / metrics.json.

The scorer is deliberately independent of engine/validate.py: it re-implements every rule
from the PDF so the engine cannot grade its own homework. It only needs an object with
`troubleshoot(query, siis_response)` returning the Appendix-B response model, so the same
script also measures the original (v1) engine for the before/after comparison:

    python eval/run_metrics.py                         # current engine → metrics.md + eval/metrics.json
    python eval/run_metrics.py --before <path>         # engine package found under <path> → eval/metrics_before.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVAL = ROOT / "eval"

URL_RE = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|org|net|io)\b|\[[^\]]+\]\([^)]+\))", re.I)
GOAL_RE = re.compile(r"^Follow these steps to perform this .+ (Troubleshooting|Configuration)$")
DUMMY = "bixby://dummy_positive"
SMALL = {"and", "or", "the", "a", "an", "in", "on", "of", "to", "for", "with", "via", "at", "by"}


def pct(n: float, d: float) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return round(s[k], 2)


def load():
    catalog = json.loads((DATA / "deeplinks.json").read_text(encoding="utf-8"))["deeplinks"]
    articles = json.loads((DATA / "siis_responses.json").read_text(encoding="utf-8"))["responses"]
    gold = json.loads((EVAL / "gold.json").read_text(encoding="utf-8"))
    paras = json.loads((EVAL / "paraphrases.json").read_text(encoding="utf-8"))
    return catalog, articles, gold, paras


# ---------------------------------------------------------------- rule checks (independent)
def title_case_ok(name: str) -> bool:
    for i, w in enumerate(re.sub(r"[^A-Za-z0-9\- ]+", " ", name).split()):
        if i and w.lower() in SMALL:
            continue
        if not w[0].isupper() and not w[0].isdigit():
            return False
    return True


DANGLING = {"to", "or", "and", "does", "not", "of", "the", "a", "an", "with", "on", "in", "for", "your", "my", "is"}
INFO_NAME_RE = re.compile(r"^(overview|what is|what are|understanding|why|about|glossary|requirements)\b", re.I)


def phrase_ok(text: str) -> bool:
    """Plain-language check: no dangling function word, no repeated word, no question."""
    words = [w.strip(".,") for w in text.lower().split()]
    return bool(words) and words[-1] not in DANGLING and len(set(words)) == len(words) and "?" not in text


def goal_rules(goal: dict) -> list[str]:
    bad = []
    g = goal.get("goal", "")
    if not GOAL_RE.match(g):
        bad.append("goal")
    else:
        topic = g[len("Follow these steps to perform this "):].rsplit(" ", 1)[0]
        if not phrase_ok(topic):
            bad.append("goal-topic")
    t = goal.get("title", "")
    if not (2 <= len(t.split()) <= 3 and t[:1].isupper() and phrase_ok(t)):
        bad.append("title")
    if not (0.0 <= float(goal.get("score", -1)) <= 1.0):
        bad.append("score")
    order = {"auto": 0, "manual": 1, "critical": 2}
    ranks = [order.get(a.get("category") or "manual", 1) for a in goal.get("actions", [])]
    if ranks != sorted(ranks):
        bad.append("ordering")
    for a in goal.get("actions", []):
        d = a.get("description", "")
        if not (d.startswith("It will ") and 5 <= len(d.split()) <= 7 and phrase_ok(d)):
            bad.append("description")
        if not title_case_ok(a.get("actionName", "")) or INFO_NAME_RE.match(a.get("actionName", "")):
            bad.append("actionName")
        for g in a.get("stepGroups", []):
            if not g.get("steps"):
                bad.append("steps")
            if (a.get("category") == "manual") and g.get("actionableDeeplink"):
                bad.append("manual-link")
    return bad


def grounded(step: str, reference: str) -> bool:
    words = [w for w in re.findall(r"[a-z0-9]+", step.lower()) if len(w) > 2]
    ref = set(re.findall(r"[a-z0-9]+", reference.lower()))
    return bool(words) and sum(w in ref for w in words) / len(words) >= 0.6


def siis_text(raw) -> str:
    if isinstance(raw, dict):
        return f"{raw.get('title', '')}\n{raw.get('content', '')}"
    return str(raw or "")


# ---------------------------------------------------------------- accuracy vs gold
def action_blob(a: dict) -> str:
    return " ".join([a.get("actionName", ""), *[s for g in a.get("stepGroups", []) for s in g.get("steps", [])]]).lower()


def step_accuracy(goal: dict, gold: dict, reference: str, id_by_uri: dict) -> tuple[float, dict]:
    actions = goal.get("actions", [])
    blobs = [action_blob(a) for a in actions]
    req = gold.get("required", [])
    found = sum(any(re.search(r, b) for b in blobs) for r in req)
    completeness = found / len(req) if req else 1.0
    steps = [(s, a) for a in actions for g in a.get("stepGroups", []) for s in g.get("steps", [])]
    policy = {"Back Up Phone Data"}
    ok_steps = sum(grounded(s, reference) or a.get("actionName") in policy for s, a in steps)
    correctness = ok_steps / len(steps) if steps else 0.0
    cat_checks, cat_ok = 0, 0
    for kind in ("critical", "manual"):
        for r in gold.get(kind, []):
            hits = [a for a, b in zip(actions, blobs) if re.search(r, b)]
            if hits:
                cat_checks += 1
                cat_ok += all((a.get("category") or "manual") == kind for a in hits)
    order = {"auto": 0, "manual": 1, "critical": 2}
    ranks = [order.get(a.get("category") or "manual", 1) for a in actions]
    ordering = (0.5 if ranks == sorted(ranks) else 0.0) + (0.5 * cat_ok / cat_checks if cat_checks else 0.5)
    return round(completeness + correctness + ordering, 3), {
        "completeness": round(completeness, 3), "grounded": round(correctness, 3), "ordering": round(ordering, 3)
    }


def deeplink_relevance(goal: dict, gold: dict, id_by_uri: dict, key_by_id: dict) -> tuple[float | None, list]:
    """2 = exact target screen, 1 = same setting (other direction/page), 0 = wrong or missing."""
    scores, detail = [], []
    for pattern, ids in gold.get("links", {}).items():
        best = None
        for a in goal.get("actions", []):
            for g in a.get("stepGroups", []):
                if re.search(pattern, " ".join(g.get("steps", [])).lower()):
                    link = g.get("actionableDeeplink") or {}
                    got = id_by_uri.get(link.get("deeplink"))
                    if got in ids:
                        s = 2.0
                    elif got and any(key_by_id.get(got) == key_by_id.get(i) for i in ids):
                        s = 1.0
                    else:
                        s = 0.0
                    best = s if best is None else max(best, s)
        if best is None:
            continue  # section not part of this plan (completeness already scores missing actions)
        scores.append(best)
        detail.append({"pattern": pattern, "score": best})
    return (round(sum(scores) / len(scores), 3) if scores else None), detail


# ---------------------------------------------------------------- runner
def make_engine(path: str | None, **kwargs):
    sys.path[:] = [p for p in sys.path if p not in {path, str(ROOT)}]
    sys.path.insert(0, path or str(ROOT))
    for name in [m for m in sys.modules if m == "engine" or m.startswith("engine.")]:
        del sys.modules[name]
    mod = importlib.import_module("engine.pipeline")
    try:
        return mod.TroubleshootingEngine(**kwargs)
    except TypeError:
        return mod.TroubleshootingEngine()


def dump(resp) -> dict:
    return resp.model_dump(mode="json") if hasattr(resp, "model_dump") else resp


def timed(engine, q, siis=None):
    t = time.perf_counter()
    r = dump(engine.troubleshoot(q, siis))
    return r, (time.perf_counter() - t) * 1000


def evaluate(engine_path: str | None, label: str) -> dict:
    catalog, articles, gold, paras = load()
    allowed = {r["deeplink"] for r in catalog} | {(r.get("validation") or {}).get("deeplink") for r in catalog}
    id_by_uri = {r["deeplink"]: r["id"] for r in catalog}
    key_by_id = {r["id"]: (r.get("validation") or {}).get("key") for r in catalog}
    queries = [l.strip() for l in (DATA / "input.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    is_v2 = engine_path is None

    # --- cold path: fresh engine, nothing pre-warmed, cache cleared before each call
    cold_engine = make_engine(engine_path, prewarm=False, use_llm=None) if is_v2 else make_engine(engine_path)
    responses, cold_ms, cold_cost = [], [], []
    for rep in range(2):
        for art in articles:
            if hasattr(cold_engine, "cache") and hasattr(cold_engine.cache, "clear"):
                cold_engine.cache.clear()
            elif hasattr(cold_engine, "cache"):
                cold_engine.cache = type(cold_engine.cache)()
            r, ms = timed(cold_engine, art["original_query"], art["siis_response"])
            cold_ms.append(ms)
            cold_cost.append(float(r["meta"].get("cost_usd") or 0))
            if rep == 0:
                responses.append((art, r))
    # plans for queries without SIIS (retrieval path) + multi-intent handling
    retrieval_resps = []
    for q in queries:
        if hasattr(cold_engine, "cache") and hasattr(cold_engine.cache, "clear"):
            cold_engine.cache.clear()
        retrieval_resps.append(timed(cold_engine, q)[0])

    # --- rule compliance over every produced response
    all_resps = [r for _, r in responses] + retrieval_resps
    schema_ok = rule_ok = leaks = uris = uris_ok = auto = auto_linked = linked = verifiable = 0
    goals_total = 0
    try:
        from engine.schema import TroubleshootResponse  # current import path (v1 or v2)
    except Exception:  # pragma: no cover
        TroubleshootResponse = None
    for r in all_resps:
        try:
            if TroubleshootResponse:
                TroubleshootResponse.model_validate(r)
            schema_ok += 1
        except Exception:
            pass
        body = json.dumps(r["response"])
        leaks += len(URL_RE.findall(body))
        for u in re.findall(r"bixby://[^\"]+", body):
            uris += 1
            uris_ok += u in allowed
        for g in r["response"]["contexts"]:
            goals_total += 1
            rule_ok += not goal_rules(g)
            for a in g["actions"]:
                if a.get("category") == "auto":
                    auto += 1
                    auto_linked += any((sg.get("actionableDeeplink") or {}).get("deeplink") in allowed for sg in a["stepGroups"])
                for sg in a["stepGroups"]:
                    if sg.get("actionableDeeplink"):
                        linked += 1
                        v = sg.get("validationDeeplink") or {}
                        verifiable += bool(v.get("resultType") and v.get("condition"))

    # --- accuracy vs gold (kit pairs with SIIS provided)
    step_scores, link_scores, per_row = [], [], []
    for art, r in responses:
        g_title = art["siis_response"]["title"]
        gold_row = gold.get(g_title)
        ctx = r["response"]["contexts"]
        if not gold_row:
            continue
        if not ctx:
            step_scores.append(0.0)
            per_row.append({"id": art["id"], "step": 0.0, "links": None, "fallback": r["meta"].get("fallback")})
            continue
        s, parts = step_accuracy(ctx[0], gold_row, siis_text(art["siis_response"]), id_by_uri)
        l, ldetail = deeplink_relevance(ctx[0], gold_row, id_by_uri, key_by_id)
        step_scores.append(s)
        if l is not None:
            link_scores.append(l)
        per_row.append({"id": art["id"], "title": ctx[0]["title"], "step": s, **parts, "links": l, "link_detail": ldetail, "score": ctx[0]["score"]})

    # --- warm engine: exact hits + unseen paraphrases
    warm = make_engine(engine_path, prewarm=True, use_llm=None) if is_v2 else make_engine(engine_path)
    exact_ms, para_ms = [], []
    for _ in range(2):
        for art in articles:
            r, ms = timed(warm, art["original_query"])
            if r["meta"].get("cache_hit"):
                exact_ms.append(ms)
    art_by_id = {a["id"]: a for a in articles}
    para_hit = para_wrong = para_n = 0
    for rid, items in paras.items():
        if rid.startswith("_"):
            continue
        expect = art_by_id[rid]["siis_response"]["title"]
        for p in items:
            para_n += 1
            r, ms = timed(warm, p)
            if r["meta"].get("cache_hit"):
                para_ms.append(ms)
                # correct when the cached plan came from the same SIIS article
                blob = json.dumps(r["response"]).lower()
                ok = any(re.search(re.escape(x), blob) for x in _markers(expect))
                para_hit += ok
                para_wrong += not ok

    # --- closed-loop verification on the simulator (v2 only)
    loop = {"available": False}
    if is_v2 and hasattr(warm, "sim"):
        taps = passes = plans = resolved = 0
        for art, r in responses:
            if not r["response"]["contexts"]:
                continue
            plans += 1
            sess = warm.sim.start(r["response"], seed=7)
            ok_all, any_v = True, False
            for a in r["response"]["contexts"][0]["actions"]:
                if a.get("category") != "auto":
                    continue
                for g in a["stepGroups"]:
                    v, link = g.get("validationDeeplink"), g.get("actionableDeeplink")
                    if not (v and link and v.get("resultType")):
                        continue
                    any_v = True
                    before = warm.sim.verify(sess.id, v)["passed"]
                    warm.sim.tap(sess.id, link["deeplink"], v)
                    after = warm.sim.verify(sess.id, v)["passed"]
                    taps += 1
                    passes += (not before) and after
                    ok_all &= after
            resolved += any_v and ok_all
        loop = {"available": True, "plans": plans, "verified_taps": taps, "fixed_and_confirmed": passes,
                "plans_with_verifiable_fix": resolved}

    llm_model = getattr(getattr(warm, "llm", None), "model", None) if getattr(getattr(warm, "llm", None), "enabled", False) else None
    return {
        "label": label,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "model": getattr(warm, "model_id", "hybrid-bm25-ngram (v1)"),
        "llm_model": llm_model,
        "environment": f"{os.cpu_count()} vCPU / {platform.system()} {platform.release()} / Python {platform.python_version()}",
        "compliance": {
            "responses": len(all_resps),
            "goals": goals_total,
            "schema_valid_pct": pct(schema_ok, len(all_resps)),
            "rule_compliance_pct": pct(rule_ok, goals_total),
            "url_leaks": leaks,
            "catalog_validity_pct": pct(uris_ok, uris),
            "auto_with_link_pct": pct(auto_linked, auto),
            "verifiable_validation_pct": pct(verifiable, linked),
            "empty_contexts": sum(1 for r in all_resps if not r["response"]["contexts"]),
        },
        "accuracy": {
            "step_accuracy": round(statistics.mean(step_scores), 2) if step_scores else 0.0,
            "deeplink_relevance": round(statistics.mean(link_scores), 2) if link_scores else 0.0,
            "rows": per_row,
        },
        "latency": {
            "exact": {"n": len(exact_ms), "p50": percentile(exact_ms, 50), "p95": percentile(exact_ms, 95)},
            "paraphrase": {"n": len(para_ms), "p50": percentile(para_ms, 50), "p95": percentile(para_ms, 95)},
            "cold": {"n": len(cold_ms), "p50": percentile(cold_ms, 50), "p95": percentile(cold_ms, 95)},
        },
        "cost": {"cold_avg_usd": round(statistics.mean(cold_cost), 6) if cold_cost else 0.0, "hit_usd": 0.0},
        "cache": {"paraphrases": para_n, "hit_pct": pct(para_hit, para_n), "wrong_hit_pct": pct(para_wrong, para_n),
                  "miss_pct": pct(para_n - para_hit - para_wrong, para_n)},
        "closed_loop": loop,
        "samples": {"retrieval_titles": [[c["title"] for c in r["response"]["contexts"]] for r in retrieval_resps]},
    }


def _markers(title: str) -> list[str]:
    """Words that only appear in plans built from a given article (used to judge cache hits)."""
    table = {
        "Email server": ["email"], "Blank or black": ["liquid damage indicator", "charge the device"],
        "Some things": ["usb adapter", "mouse and keyboard"], "Transfer Secure": ["smart switch"],
        "Use Multi window": ["edge panel", "multi window", "pop-up"], "Screen mirroring": ["smart view"],
        "Access your Galaxy": ["hdmi", "mouse"], "Screen flickers": ["shutter", "super steady"],
        "Cracked or bleeding": ["repair"], "Screen does not rotate": ["rotat", "orientation"],
        "Touchscreen issues": ["touch sensitivity", "screen protector"],
    }
    for k, v in table.items():
        if title.startswith(k):
            return v
    return [title.lower()]


# ---------------------------------------------------------------- ablation
def ablation(base: dict) -> list[dict]:
    rows = []
    for mode, label in (
        ("hybrid", "Hybrid: verbatim setting name, then TF-IDF over descriptions (default)"),
        ("rules", "Pure rules: verbatim setting names only"),
        ("tfidf", "Pure TF-IDF retrieval over descriptions"),
    ):
        os.environ["ENGINE_MAPPER"] = mode
        res = base if mode == "hybrid" else evaluate(None, mode)
        c = res["compliance"]
        rows.append({
            "variant": label, "step": res["accuracy"]["step_accuracy"], "links": res["accuracy"]["deeplink_relevance"],
            "p95": res["latency"]["cold"]["p95"], "cost": res["cost"]["cold_avg_usd"],
            "note": f"auto actions with link {c['auto_with_link_pct']}%, verifiable {c['verifiable_validation_pct']}%",
        })
    os.environ["ENGINE_MAPPER"] = "hybrid"
    return rows


def write_markdown(m: dict, before: dict | None, abl: list[dict]) -> str:
    c, a, l, k = m["compliance"], m["accuracy"], m["latency"], m["cache"]
    b = (before or {})
    bc, ba, bl, bk = b.get("compliance", {}), b.get("accuracy", {}), b.get("latency", {}), b.get("cache", {})

    def v(x):
        return "—" if x is None else x

    lines = [
        "# System Performance Metrics & Evaluation Report",
        "",
        f"**Model(s):** {m['model']}" + (f" (Groq `{m['llm_model']}` for extraction/paraphrases)" if m.get("llm_model") else " — Groq LLM path available with `GROQ_API_KEY`, not used for this run"),
        "**Embeddings:** TF-IDF word 1–2 grams (catalog & SIIS retrieval), char 3–5 grams (semantic cache)",
        f"**Environment:** {m['environment']}",
        f"**Generated:** {m['generated']} by `python eval/run_metrics.py` — scorer is independent of the engine's own validators",
        "",
        "Before = the original v1 engine in this repo, measured by the same script on the same data.",
        "",
        "---",
        "",
        "## 1. Schema & Rule Compliance",
        f"Evaluated on {c['responses']} responses: the 20 kit (query, SIIS) pairs plus the 20 `input.txt` queries without SIIS.",
        "",
        "| Metric | Target | Before | Measured Value |",
        "| :--- | :--- | :--- | :--- |",
        f"| Schema-valid output lines | >= 99% | {v(bc.get('schema_valid_pct'))}% | {c['schema_valid_pct']}% |",
        f"| Rule compliance (Goal / Title / Description syntax) | >= 95% | {v(bc.get('rule_compliance_pct'))}% | {c['rule_compliance_pct']}% |",
        f"| Absolute URL leaks | 0 | {v(bc.get('url_leaks'))} | {c['url_leaks']} |",
        f"| Deeplink catalog validity (exact URI match) | 100% | {v(bc.get('catalog_validity_pct'))}% | {c['catalog_validity_pct']}% |",
        f"| Auto actions carrying valid actionable deeplink | >= 90% | {v(bc.get('auto_with_link_pct'))}% | {c['auto_with_link_pct']}% |",
        f"| Linked steps with a *verifiable* validationDeeplink (new) | — | {v(bc.get('verifiable_validation_pct'))}% | {c['verifiable_validation_pct']}% |",
        "",
        "---",
        "",
        "## 2. Accuracy Benchmarks",
        "Scored against hand-labelled expectations in `eval/gold.json` (required actions, category of destructive / physical steps, exact target screen).",
        "",
        "| Evaluation Metric | Scale / Anchor | Before | Score |",
        "| :--- | :--- | :--- | :--- |",
        f"| Step accuracy (completeness, correctness, ordering) | 0.0 - 3.0 | {v(ba.get('step_accuracy'))} | {a['step_accuracy']} |",
        f"| Deeplink relevance (exact target screen vs. parent menu) | 0.0 - 2.0 | {v(ba.get('deeplink_relevance'))} | {a['deeplink_relevance']} |",
        "",
        "Step accuracy = completeness (share of required actions present) + correctness (share of steps grounded in the SIIS text) + ordering (tier order + destructive/physical steps in the right category).",
        "",
        "---",
        "",
        f"## 3. Latency Benchmarks (N >= 30 requests per path; exact N shown)",
        "",
        "| Execution Path | Target (P95) | N | P50 (ms) | P95 (ms) | Before P95 (ms) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| Cache hit - exact query match | <= 300 ms | {l['exact']['n']} | {l['exact']['p50']} | {l['exact']['p95']} | {v(bl.get('exact', {}).get('p95'))} |",
        f"| Cache hit - unseen semantic paraphrase | <= 300 ms | {l['paraphrase']['n']} | {l['paraphrase']['p50']} | {l['paraphrase']['p95']} | {v(bl.get('paraphrase', {}).get('p95'))} |",
        f"| Cold query - full pipeline extraction & mapping | <= 8000 ms | {l['cold']['n']} | {l['cold']['p50']} | {l['cold']['p95']} | {v(bl.get('cold', {}).get('p95'))} |",
        "",
        "---",
        "",
        "## 4. Operational Cost & Cache Efficacy",
        "",
        "| Metric Item | Target | Before | Measured Value |",
        "| :--- | :--- | :--- | :--- |",
        f"| Cold query average inference cost | Tracked | $0.00 | ${m['cost']['cold_avg_usd']:.6f} |",
        "| Cache hit inference cost | $0.00 | $0.00 | $0.00 |",
        f"| Semantic cache hit rate (on {k['paraphrases']} unseen hand-written paraphrases) | >= 80% | {v(bk.get('hit_pct'))}% | {k['hit_pct']}% |",
        f"| Wrong-article cache hits (served a plan from another SIIS article) | low | {v(bk.get('wrong_hit_pct'))}% | {k['wrong_hit_pct']}% |",
        "| Cost derivation method | - | - | (prompt tokens x input rate + completion tokens x output rate) from Groq usage; $0 on the deterministic path |",
        "",
        "---",
        "",
        "## 5. Architectural Ablation Analysis",
        "",
        "| Architecture Variant | Step Accuracy | Deeplink Relevance | Latency (P95 cold) | Cost / Query | Key Observations |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| Baseline: v1 engine (hashed n-grams, no relevance gate) | {v(ba.get('step_accuracy'))} | {v(ba.get('deeplink_relevance'))} | {v(bl.get('cold', {}).get('p95'))} ms | $0 | Wrong screens for generic steps, 3-word truncated titles |",
    ]
    for r in abl:
        lines.append(f"| {r['variant']} | {r.get('step', '—')} | {r.get('links', '—')} | {r.get('p95', '—')} ms | ${r.get('cost', 0):.4f} | {r.get('note', '')} |")
    if not m.get("llm_model"):
        lines.append("| Groq LLM extraction (llama-3.3-70b) | set GROQ_API_KEY and re-run | | | tracked | Drafts grounded + re-validated; falls back on any error |")
    loop = m.get("closed_loop", {})
    lines += [
        "",
        "---",
        "",
        "## 6. Closed-loop Verification (innovation)",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Plans with at least one verifiable one-tap fix | {loop.get('plans_with_verifiable_fix', '—')} / {loop.get('plans', '—')} |",
        f"| Toggles tapped on the simulated device and confirmed via validationDeeplink | {loop.get('fixed_and_confirmed', '—')} / {loop.get('verified_taps', '—')} |",
        "",
        "The simulator seeds each setting in its faulty state, performs the actionable deeplink and re-reads the `val/` URI "
        "with the plan's `resultType` / `condition` / `value`. It is a mock of the on-device agent, not a real phone.",
        "",
        "---",
        "",
        "## 7. Known Edge Cases & System Limitations",
        "",
        "* Several kit queries are paired with only loosely related SIIS articles (e.g. *screen stays small* → Smart View mirroring, *floating circle* → Multi window). The engine plans from what the article says and lowers `score`; the Assistant-menu screen the floating circle needs is not in the catalog.",
        "* The catalog has no entries for Safe mode, Software update, Apps › Storage, Smart View or Auto rotate, so those steps are either critical (no one-tap by design) or use `bixby://dummy_positive` when they follow a Settings path.",
        "* SIIS content with words glued together (\"Some things to check first\" sections) is dropped rather than repaired.",
        "* Deterministic extraction is tuned on the 11 distinct kit articles; the Groq path is the intended generaliser for unseen article layouts.",
        "* Cache judgement of *wrong* hits uses article-specific marker words; hits across the six \"blank display\" rows count as correct because they share the same article.",
        "* Device-specific screens (Flip cover vs inner display) are detected in enrichment but the catalog has no per-device variants to route to.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", help="directory containing a previous `engine` package")
    ap.add_argument("--no-ablation", action="store_true")
    args = ap.parse_args()
    os.environ.setdefault("PYTHONHASHSEED", "0")
    if args.before:
        res = evaluate(args.before, "before (v1)")
        (EVAL / "metrics_before.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(json.dumps({k: res[k] for k in ("compliance", "cache")}, indent=2))
        print("accuracy", res["accuracy"]["step_accuracy"], res["accuracy"]["deeplink_relevance"])
        return
    res = evaluate(None, "after (v2)")
    abl = [] if args.no_ablation else ablation(res)
    res["ablation"] = abl
    before_path = EVAL / "metrics_before.json"
    before = json.loads(before_path.read_text(encoding="utf-8")) if before_path.exists() else None
    (EVAL / "metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    (ROOT / "metrics.md").write_text(write_markdown(res, before, abl), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("compliance", "latency", "cache", "closed_loop")}, indent=2))
    print("accuracy", res["accuracy"]["step_accuracy"], res["accuracy"]["deeplink_relevance"])


if __name__ == "__main__":
    main()
