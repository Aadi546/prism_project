"""REST API: POST /v1/troubleshoot and GET /health."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine.pipeline import TroubleshootingEngine
from engine.schema import TroubleshootRequest
from engine.store import canned_queries


@lru_cache(maxsize=1)
def get_engine() -> TroubleshootingEngine:
    return TroubleshootingEngine()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_engine()
    yield


app = FastAPI(
    title="Smart Guided Troubleshooting Engine",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return get_engine().health()


@app.get("/v1/examples")
def examples():
    return {"queries": canned_queries()}


@app.post("/v1/troubleshoot")
def troubleshoot(body: TroubleshootRequest):
    result = get_engine().troubleshoot(body.query, body.siis_response)
    return result.model_dump()
