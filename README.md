# Smart Guided Troubleshooting Engine

Turns vague Galaxy device complaints into schema-valid, one-tap Settings plans with masked Bixby deeplinks.

A customer can say “swipe gestures go the wrong way after I installed an app.” The engine enriches that into a canonical query, retrieves SIIS customer-care text, extracts a `Goal` with ordered actions, maps each action to a **leaf** screen in the deeplink catalog, and serves JSON from `POST /v1/troubleshoot`. Repeat paraphrases hit an in-process semantic cache (no model call, target P95 ≤ 300 ms).

The official ~575-entry Samsung dump was not bundled with the problem PDF. `data/` is a faithful four-domain starter set (Battery, Display, Camera, Performance) using the same schema, so a real `deeplinks.json` / `siis_responses.json` can drop in later.

## Pipeline

0. **Query enrichment** — normalize jargon, build a semantic cache key, emit 8–10 paraphrases.
1. **Structure extraction** — SIIS article (or pasted `siis_response`) → `Goal` / `Action` / UI steps. Field rules are enforced in `engine/validate.py`, not only in prompts.
2. **Deeplink mapping** — hybrid BM25 + hashed n-gram dense retrieval over catalog **descriptions**, never over opaque URIs. Parent menus lose to more specific children. `bixby://dummy_positive` is rejected.
3. **Fast-path cache** — store the validated plan under the canonical query and all paraphrases.
4. **REST** — pure JSON, zero markdown wrapping.

Hard rules: no `http`/`https`/`www` leakage, catalog-only URIs, empty `contexts` with `no_match` / `no_siis_context` instead of invented steps, auto → manual → critical ordering, descriptions that start with “It will” and contain 5–7 words.

## Run locally

Python 3.12+ and Node 20+ (for the console).

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=. python3 -m uvicorn app:app --host 0.0.0.0 --port 8765

# another terminal
cd web && npm install && npm run dev
```

- Engine: http://127.0.0.1:8765/health
- Console: http://127.0.0.1:43123 (proxies `/v1/*` to the engine)

No API key is required. The default path is retrieval + deterministic extractors. If you later set `OPENAI_API_KEY`, keep the validators in place; they still rewrite illegal fields.

Regenerate starter assets after editing `scripts/generate_data.py`:

```bash
python3 scripts/generate_data.py
PYTHONPATH=. python3 scripts/dump_samples.py
```

## API

`POST /v1/troubleshoot`

```json
{
  "query": "phone swipe gestures wrong direction after app install",
  "siis_response": null
}
```

`siis_response` is optional. When omitted, the engine searches `data/siis_responses.json`.

`GET /health` returns `{ "status": "ok", ... }` once the catalog, SIIS index, and cache are loaded.

`GET /v1/examples` lists canned complaints for the console.

## Tests and metrics

```bash
PYTHONPATH=. python3 -m pytest eval/test_engine.py -q
PYTHONPATH=. python3 eval/run_metrics.py
```

Results land in `metrics.md`. Gold input/output pairs are in `data/samples/`.

## Layout

- `engine/` — schema, enrichment, retrieval, mapping, cache, FastAPI
- `schema.py` — public Pydantic contract alias
- `data/` — `deeplinks.json`, `siis_responses.json`, `queries.json`, samples
- `web/` — Next.js + Tailwind + shadcn/ui operator console
- `eval/` — pytest contract tests and the metrics report generator
