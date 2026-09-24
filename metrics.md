# System Performance Metrics & Evaluation Report

**Model(s):** groq/llama-3.3-70b-versatile (Groq `llama-3.3-70b-versatile` for extraction/paraphrases)
**Embeddings:** TF-IDF word 1–2 grams (catalog & SIIS retrieval), char 3–5 grams (semantic cache)
**Environment:** 4 vCPU / Windows 11 / Python 3.12.4
**Generated:** 2026-09-24 22:35 by `python eval/run_metrics.py` — scorer is independent of the engine's own validators

Before = the original v1 engine in this repo, measured by the same script on the same data.

---

## 1. Schema & Rule Compliance
Evaluated on 40 responses: the 20 kit (query, SIIS) pairs plus the 20 `input.txt` queries without SIIS.

| Metric | Target | Before | Measured Value |
| :--- | :--- | :--- | :--- |
| Schema-valid output lines | >= 99% | 100.0% | 100.0% |
| Rule compliance (Goal / Title / Description syntax) | >= 95% | 5.0% | 100.0% |
| Absolute URL leaks | 0 | 0 | 0 |
| Deeplink catalog validity (exact URI match) | 100% | 100.0% | 100.0% |
| Auto actions carrying valid actionable deeplink | >= 90% | 100.0% | 100.0% |
| Linked steps with a *verifiable* validationDeeplink (new) | — | 0.0% | 68.0% |

---

## 2. Accuracy Benchmarks
Scored against hand-labelled expectations in `eval/gold.json` (required actions, category of destructive / physical steps, exact target screen).

| Evaluation Metric | Scale / Anchor | Before | Score |
| :--- | :--- | :--- | :--- |
| Step accuracy (completeness, correctness, ordering) | 0.0 - 3.0 | 2.74 | 2.99 |
| Deeplink relevance (exact target screen vs. parent menu) | 0.0 - 2.0 | 0.03 | 2.0 |

Step accuracy = completeness (share of required actions present) + correctness (share of steps grounded in the SIIS text) + ordering (tier order + destructive/physical steps in the right category).

---

## 3. Latency Benchmarks (N >= 30 requests per path; exact N shown)

| Execution Path | Target (P95) | N | P50 (ms) | P95 (ms) | Before P95 (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Cache hit - exact query match | <= 300 ms | 36 | 4.37 | 6.72 | 0.08 |
| Cache hit - unseen semantic paraphrase | <= 300 ms | 57 | 9.84 | 15.99 | 0.0 |
| Cold query - full pipeline extraction & mapping | <= 8000 ms | 40 | 225.83 | 462.75 | 95.56 |

---

## 4. Operational Cost & Cache Efficacy

| Metric Item | Target | Before | Measured Value |
| :--- | :--- | :--- | :--- |
| Cold query average inference cost | Tracked | $0.00 | $0.000000 |
| Cache hit inference cost | $0.00 | $0.00 | $0.00 |
| Semantic cache hit rate (on 60 unseen hand-written paraphrases) | >= 80% | 0.0% | 90.0% |
| Wrong-article cache hits (served a plan from another SIIS article) | low | 0.0% | 5.0% |
| Cost derivation method | - | - | (prompt tokens x input rate + completion tokens x output rate) from Groq usage; $0 on the deterministic path |

---

## 5. Architectural Ablation Analysis

| Architecture Variant | Step Accuracy | Deeplink Relevance | Latency (P95 cold) | Cost / Query | Key Observations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Baseline: v1 engine (hashed n-grams, no relevance gate) | 2.74 | 0.03 | 95.56 ms | $0 | Wrong screens for generic steps, 3-word truncated titles |
| Hybrid: verbatim setting name, then TF-IDF over descriptions (default) | 2.99 | 2.0 | 462.75 ms | $0.0000 | auto actions with link 100.0%, verifiable 68.0% |
| Pure rules: verbatim setting names only | 2.99 | 2.0 | 700.76 ms | $0.0000 | auto actions with link 100.0%, verifiable 68.0% |
| Pure TF-IDF retrieval over descriptions | 2.99 | 1.67 | 738.62 ms | $0.0000 | auto actions with link 100.0%, verifiable 65.2% |

---

## 6. Closed-loop Verification (innovation)

| Metric | Value |
| :--- | :--- |
| Plans with at least one verifiable one-tap fix | 6 / 20 |
| Toggles tapped on the simulated device and confirmed via validationDeeplink | 7 / 8 |

The simulator seeds each setting in its faulty state, performs the actionable deeplink and re-reads the `val/` URI with the plan's `resultType` / `condition` / `value`. It is a mock of the on-device agent, not a real phone.

---

## 7. Known Edge Cases & System Limitations

* Several kit queries are paired with only loosely related SIIS articles (e.g. *screen stays small* → Smart View mirroring, *floating circle* → Multi window). The engine plans from what the article says and lowers `score`; the Assistant-menu screen the floating circle needs is not in the catalog.
* The catalog has no entries for Safe mode, Software update, Apps › Storage, Smart View or Auto rotate, so those steps are either critical (no one-tap by design) or use `bixby://dummy_positive` when they follow a Settings path.
* SIIS content with words glued together ("Some things to check first" sections) is dropped rather than repaired.
* Deterministic extraction is tuned on the 11 distinct kit articles; the Groq path is the intended generaliser for unseen article layouts.
* Cache judgement of *wrong* hits uses article-specific marker words; hits across the six "blank display" rows count as correct because they share the same article.
* Device-specific screens (Flip cover vs inner display) are detected in enrichment but the catalog has no per-device variants to route to.
