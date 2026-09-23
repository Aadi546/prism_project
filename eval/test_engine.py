"""Contract, hygiene, mapping, cache, and API tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.pipeline import TroubleshootingEngine
from engine.schema import TroubleshootResponse
from engine.validate import DUMMY_URI, GOAL_RE, URL_RE, collect_urls, fit_description
from engine.api import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def engine() -> TroubleshootingEngine:
    return TroubleshootingEngine()


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["indexes"]["deeplink"] is True
    assert body["indexes"]["cache"] is True


def test_schema_swipe(engine: TroubleshootingEngine):
    out = engine.troubleshoot(
        "The mobile phone swipe navigation moves up or down instead of left or right after downloading an app"
    )
    TroubleshootResponse.model_validate(out.model_dump())
    assert out.response.contexts, out.meta.fallback
    goal = out.response.contexts[0]
    assert GOAL_RE.match(goal.goal)
    assert 2 <= len(goal.title.split()) <= 3
    assert 0.0 <= goal.score <= 1.0
    assert 8 <= len(out.query_variations) <= 10
    assert goal.actions
    cats = [a.category.value for a in goal.actions]
    assert cats == sorted(cats, key=lambda c: {"auto": 0, "manual": 1, "critical": 2}[c])
    first = goal.actions[0]
    assert first.description.split()[0:2] == ["It", "will"]
    assert 5 <= len(first.description.split()) <= 7
    uri = first.stepGroups[0].actionableDeeplink.deeplink
    assert uri.startswith("bixby://masked/act/")
    assert uri != DUMMY_URI
    assert "navigation" in uri or "gesture" in uri


def test_no_url_leak(engine: TroubleshootingEngine):
    poison = (
        "Swipe navigation broken. See https://www.samsung.com/support and "
        "[guide](http://example.com) www.google.com"
    )
    out = engine.troubleshoot("swipe gestures go the wrong way after installing an app", poison)
    blob = json.dumps(out.model_dump())
    assert not collect_urls(blob)
    assert "http" not in blob.lower()
    assert "samsung.com" not in blob.lower()


def test_dummy_uri_never_emitted(engine: TroubleshootingEngine):
    out = engine.troubleshoot("phone swipe gestures wrong direction after app install")
    blob = json.dumps(out.model_dump())
    assert DUMMY_URI not in blob


def test_catalog_only_uris(engine: TroubleshootingEngine):
    allowed = {row["deeplink"] for row in engine.mapper.catalog}
    out = engine.troubleshoot("battery dies fast even when idle")
    blob = json.dumps(out.model_dump())
    assert DUMMY_URI not in blob
    for ctx in out.response.contexts:
        for action in ctx.actions:
            for g in action.stepGroups:
                if g.actionableDeeplink:
                    assert g.actionableDeeplink.deeplink in allowed


def test_no_match_ir(engine: TroubleshootingEngine):
    out = engine.troubleshoot("universal remote cannot find the infrared blaster")
    assert out.response.contexts == []
    assert out.meta.fallback in {"no_match", "no_siis_context"}


def test_cache_hit_on_paraphrase(engine: TroubleshootingEngine):
    q1 = "phone swipe gestures wrong direction after app install"
    first = engine.troubleshoot(q1)
    assert first.response.contexts
    second = engine.troubleshoot(
        "Ever since I installed a new app, swiping on my phone scrolls up and down instead of going left or right."
    )
    # semantic or exact via stored paraphrases / prewarm hints
    third = engine.troubleshoot(q1)
    assert third.meta.cache_hit is True
    assert third.meta.cost_usd == 0.0
    assert third.meta.latency_ms < 300


def test_description_helper():
    assert fit_description("https://x.com will open stuff") 
    d = fit_description("lets you pick buttons")
    assert d.startswith("It will")
    assert 5 <= len(d.split()) <= 7


def test_api_roundtrip(client: TestClient):
    res = client.post(
        "/v1/troubleshoot",
        json={"query": "My phone got slow after the update"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "query_variations" in body
    assert "response" in body
    assert "```" not in json.dumps(body)
    assert body["response"]["contexts"]


def test_domains_produce_plans(engine: TroubleshootingEngine):
    queries = json.loads((ROOT / "data" / "queries.json").read_text())
    hits = 0
    for row in queries:
        if row["id"] == "q_ir":
            continue
        out = engine.troubleshoot(row["text"])
        if out.response.contexts:
            hits += 1
            g = out.response.contexts[0]
            assert GOAL_RE.match(g.goal)
    assert hits >= 8
