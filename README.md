# Smart Guided Troubleshooting Engine (Samsung PRISM · Theme 2)

Turns vague Galaxy device complaints into schema-valid, one-tap Settings plans with masked Bixby deeplinks, and then **verifies each fix in a closed loop** by reading the setting back through its `validationDeeplink`.

A customer says *"my S22 touch is laggy and inputs are delayed"*. The engine:

0. **Enriches** the query: canonical form, symptom signature, device, split into separate intents, 8–10 paraphrases.
3. **Checks the semantic cache**: exact match, then character-gram cosine with a symptom-agreement gate. Hits return in about 1 ms at $0.
1. On a miss it **retrieves the SIIS article** and applies a relevance gate. With nothing relevant it returns `contexts: []` and a `no_siis_context` / `no_match` fallback instead of inventing steps.
1. **Extracts** a `Goal`: sections become imperative, atomic steps, informational sections are dropped, and each action covers one screen. Every step keeps the span of the sentence it came from.
2. **Maps deeplinks**: first the verbatim setting name (e.g. *Touch sensitivity*), otherwise TF-IDF over catalog descriptions (never the URI). The on/off twin is chosen from the step's wording. `dummy_positive` is used only for real Settings paths the catalog lacks.
4. **Validates and serves pure JSON**: field rules, URL scrubbing, and category rules (destructive steps are critical, physical steps are manual and never linked), ordered auto → manual → critical.
★ **Closed loop**: each auto step carries a checkable `validationDeeplink` (onURL → `boolean = True`, offURL → `False`, updateURL → `integer >/<`). The console runs the plan on a simulated device and confirms each fix.

`data/` holds the **official Theme 2 kit** (byte-identical to `participant-kit/Theme02_Input_Kit.zip`): 578 masked deeplinks, 20 SIIS articles, `input.txt`, `schema.py`.
The unzipped `participant-kit/participant-kit/` folder is the **Theme 5 (Interruptible Agents)** kit and is not used here.

## Results (from `metrics.md`, same scorer on v1 and v2)

| | v1 (before) | v2 (now) |
|---|---|---|
| Rule compliance (goal / title / description / names) | 5% | 100% |
| Deeplink relevance, 0–2 (exact target screen) | 0.03 | 2.0 |
| Step accuracy, 0–3 (vs hand-labelled gold) | 2.74 | 2.99 |
| Cache hit rate on 60 unseen hand-written paraphrases | 0% | 90% |
| Linked steps with a verifiable validationDeeplink | 0% | 68% |
| Schema-valid / URL leaks / catalog-valid URIs | 100% / 0 / 100% | 100% / 0 / 100% |

Exact numbers, latency percentiles and the ablation are in [metrics.md](metrics.md). The gap analysis for the PPT is in [docs/GAPS_AND_INNOVATION.md](docs/GAPS_AND_INNOVATION.md).

## Run locally

Python 3.11+ and Node 20+.

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

In another terminal:

```bash
cd web && npm install && npm run dev
```

- Engine: http://127.0.0.1:8765/health
- Console: http://127.0.0.1:43123 (proxies `/v1/*` to `ENGINE_URL`, default `http://127.0.0.1:8765`)

### Optional: Groq LLM path

Copy `.env.example` to `.env` and set `GROQ_API_KEY`. The engine loads that file automatically.

```bash
# or export instead of `.env`
export GROQ_API_KEY=...        # PowerShell: $env:GROQ_API_KEY="..."
export GROQ_MODEL=llama-3.3-70b-versatile   # or llama-3.1-8b-instant
```

With a key, Groq drafts the structure and paraphrases. Every step is re-grounded against the SIIS text (≥60% token overlap), deeplinks may only come from the catalog candidates we offer, and the same validators run afterwards. Any error or timeout falls back to the deterministic path. `meta.model` and `meta.cost_usd` report what actually ran. `ENGINE_DISABLE_LLM=1` forces the deterministic path.

## API

`POST /v1/troubleshoot` (Appendix B response). Add `?trace=1` for stage timings, retrieval candidates, provenance and mapping reasons.

```json
{ "query": "phone swipe gestures wrong direction after app install", "siis_response": null }
```

`siis_response` may be the kit's `{title, content}` object or raw text. When it is omitted, the engine uses the pre-warmed semantic cache, then knowledge-base retrieval.

`GET /health` returns `{"status": "ok", ...}` once the catalog, SIIS index and cache are ready.

Console helpers: `GET /v1/examples`, `/v1/siis`, `/v1/catalog?q=`, `/v1/batch`, `/v1/metrics`, and `POST /v1/sim/start`, `/v1/sim/tap`, `/v1/verify`.

## Reproduce the deliverables

```bash
python -m pytest -q                     # contract, hygiene, mapping, cache, verification, API
python scripts/run_batch.py --samples   # results.jsonl for input.txt + data/samples/
python eval/run_metrics.py              # metrics.md + eval/metrics.json (+ ablation)
```

The "before" column comes from the original engine: `python eval/run_metrics.py --before <dir containing the v1 engine package>` writes `eval/metrics_before.json`.

## Layout

- `engine/`
  - `lexicon.py`: symptoms, category rules, informational headings
  - `catalog.py`: deeplink hygiene, twins, screen resolution
  - `extract.py`: SIIS → Goal, with provenance
  - `validate.py`: field rules
  - `verify.py`: validationDeeplink + device simulator
  - `enrichment.py`, `cache.py`, `pipeline.py`, `llm.py` (Groq), `api.py`
- `eval/`: `gold.json` (hand labels), `paraphrases.json` (60 unseen paraphrases), `run_metrics.py` (independent scorer), `test_engine.py`
- `web/`: Next.js console with Troubleshoot (plan · trace · JSON · phone simulator), Batch run, Metrics, and Gaps & innovation pages
- `scripts/run_batch.py`: `results.jsonl`. `scripts/legacy/` holds the old synthetic-data scripts, now guarded so they cannot overwrite `data/`.
