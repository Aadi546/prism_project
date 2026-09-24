"""REST API.

Contract endpoints (Theme 2 brief):
  POST /v1/troubleshoot   → Appendix-B payload (pure JSON). `?trace=1` adds a `trace` object.
  GET  /health            → {"status": "ok", …} once catalog, indexes and cache are ready.

Console / evaluation helpers:
  GET  /v1/examples, /v1/siis, /v1/catalog, /v1/batch, /v1/metrics
  POST /v1/sim/start, /v1/sim/tap, /v1/verify   (closed-loop verification on a simulated device)
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from engine.pipeline import TroubleshootingEngine
from engine.schema import TroubleshootRequest
from engine.store import DATA, ROOT, canned_queries


@lru_cache(maxsize=1)
def get_engine() -> TroubleshootingEngine:
    return TroubleshootingEngine()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_engine()
    yield


app = FastAPI(title="Smart Guided Troubleshooting Engine", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def _bad_request(_req: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "invalid_request", "detail": exc.errors()})


@app.exception_handler(Exception)
async def _server_error(_req: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": type(exc).__name__})


@app.get("/health")
def health():
    return get_engine().health()


@app.post("/v1/troubleshoot")
def troubleshoot(body: TroubleshootRequest, trace: bool = False):
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    engine = get_engine()
    if trace:
        resp, tr = engine.troubleshoot(body.query, body.siis_response, trace=True)
        return {**resp.model_dump(mode="json"), "trace": tr}
    return engine.troubleshoot(body.query, body.siis_response).model_dump(mode="json")


@app.get("/v1/examples")
def examples():
    return {"queries": canned_queries()}


@app.get("/v1/siis")
def siis():
    return {
        "articles": [
            {
                "id": a.get("id"),
                "title": (a.get("siis_response") or {}).get("title"),
                "query": a.get("original_query"),
                "siis_response": a.get("siis_response"),
            }
            for a in get_engine().articles
        ]
    }


@app.get("/v1/catalog")
def catalog(q: Optional[str] = None, id: Optional[str] = None, uri: Optional[str] = None, k: int = 8):
    cat = get_engine().catalog
    if id:
        row = cat.by_id.get(id)
        if not row:
            raise HTTPException(404, "unknown catalog id")
        return row
    if uri:
        row = cat.by_uri.get(uri) or cat.by_validation_uri(uri)
        if not row:
            raise HTTPException(404, "unknown deeplink")
        return row
    if q:
        return {"results": [{**r, "score": round(s, 3)} for r, s in cat.search(q, k=min(k, 25))]}
    return {"count": len(cat.rows), "phone_screens": len(cat.phone_rows)}


@app.get("/v1/batch")
def batch():
    """Run every line of data/input.txt; returns rows plus results.jsonl text."""
    engine = get_engine()
    lines = [l.strip() for l in (DATA / "input.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, jsonl = [], []
    for q in lines:
        resp = engine.troubleshoot(q).model_dump(mode="json")
        jsonl.append(json.dumps(resp, ensure_ascii=False))
        ctx = resp["response"]["contexts"]
        rows.append({
            "query": q,
            "titles": [c["title"] for c in ctx],
            "actions": sum(len(c["actions"]) for c in ctx),
            "score": max((c["score"] for c in ctx), default=0.0),
            "fallback": resp["meta"]["fallback"],
            "cache_hit": resp["meta"]["cache_hit"],
            "latency_ms": resp["meta"]["latency_ms"],
            "response": resp,
        })
    return {"rows": rows, "jsonl": "\n".join(jsonl) + "\n"}


@app.get("/v1/metrics")
def metrics():
    out = {}
    for name in ("metrics.json", "metrics_before.json"):
        path = ROOT / "eval" / name
        if path.exists():
            out[name.replace(".json", "")] = json.loads(path.read_text(encoding="utf-8"))
    return out


class SimStart(BaseModel):
    response: dict[str, Any]
    seed: Optional[int] = None


class SimTap(BaseModel):
    session: str
    deeplink: str
    validation: Optional[dict[str, Any]] = None


class SimVerify(BaseModel):
    session: str
    validationDeeplink: dict[str, Any]


@app.post("/v1/sim/start")
def sim_start(body: SimStart):
    sim = get_engine().sim
    sess = sim.start(body.response, body.seed)
    return sim.snapshot(sess.id)


@app.post("/v1/sim/tap")
def sim_tap(body: SimTap):
    sim = get_engine().sim
    if body.session not in sim.sessions:
        raise HTTPException(404, "unknown session")
    if body.deeplink not in get_engine().catalog.allowed:
        raise HTTPException(422, "deeplink is not in the catalog")
    return sim.tap(body.session, body.deeplink, body.validation)


@app.post("/v1/verify")
def verify(body: SimVerify):
    sim = get_engine().sim
    if body.session not in sim.sessions:
        raise HTTPException(404, "unknown session")
    return sim.verify(body.session, body.validationDeeplink)
