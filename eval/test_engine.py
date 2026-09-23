"""Contract, hygiene, mapping, cache, and API tests against the official Theme 2 kit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import app
from engine.pipeline import TroubleshootingEngine
from engine.schema import TroubleshootResponse
from engine.validate import DUMMY_URI, GOAL_RE, collect_urls, fit_description

ROOT = Path(__file__).resolve().parents[1]
CRACKED = "My Galaxy phone's screen is completely cracked, it's a total crack and I can't use the device."
BLACK = "My Galaxy S24 Ultra screen is completely black and won't turn on, even though the phone powers on, rings, and otherwise works; there is no physical damage."


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
    assert body["catalog"] >= 500
    assert body["indexes"]["deeplink"] is True
    assert body["indexes"]["cache"] is True


def test_schema_cracked_screen(engine: TroubleshootingEngine):
    out = engine.troubleshoot(CRACKED)
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


def test_no_url_leak(engine: TroubleshootingEngine):
    poison = (
        "Cracked screen. See https://www.samsung.com/support and "
        "[guide](http://example.com) www.google.com"
    )
    out = engine.troubleshoot(CRACKED, poison)
    blob = json.dumps(out.model_dump())
    assert not collect_urls(blob)
    assert "http://" not in blob.lower()
    assert "https://" not in blob.lower()
    assert "samsung.com" not in blob.lower()


def test_catalog_only_uris(engine: TroubleshootingEngine):
    allowed = {row["deeplink"] for row in engine.mapper.catalog}
    out = engine.troubleshoot(BLACK)
    blob = json.dumps(out.model_dump())
    for ctx in out.response.contexts:
        for action in ctx.actions:
            for g in action.stepGroups:
                if g.actionableDeeplink:
                    assert g.actionableDeeplink.deeplink in allowed
                    if g.actionableDeeplink.deeplink != DUMMY_URI:
                        assert g.actionableDeeplink.deeplink.startswith("bixby://masked/")


def test_unknown_intent_empty(engine: TroubleshootingEngine):
    out = engine.troubleshoot("universal remote cannot find the infrared blaster")
    assert out.response.contexts == [] or out.meta.fallback in {None, "no_match", "no_siis_context"}
    if not out.response.contexts:
        assert out.meta.fallback in {"no_match", "no_siis_context"}


def test_cache_hit_on_repeat(engine: TroubleshootingEngine):
    first = engine.troubleshoot(CRACKED)
    assert first.response.contexts
    third = engine.troubleshoot(CRACKED)
    assert third.meta.cache_hit is True
    assert third.meta.cost_usd == 0.0
    assert third.meta.latency_ms < 300


def test_description_helper():
    d = fit_description("lets you pick buttons")
    assert d.startswith("It will")
    assert 5 <= len(d.split()) <= 7


def test_api_roundtrip(client: TestClient):
    res = client.post("/v1/troubleshoot", json={"query": BLACK})
    assert res.status_code == 200
    body = res.json()
    assert "query_variations" in body
    assert "response" in body
    assert "```" not in json.dumps(body)
    assert body["response"]["contexts"]


def test_kit_queries_produce_plans(engine: TroubleshootingEngine):
    queries = json.loads((ROOT / "data" / "queries.json").read_text())
    hits = 0
    for row in queries:
        out = engine.troubleshoot(row["text"])
        if out.response.contexts:
            hits += 1
            g = out.response.contexts[0]
            assert GOAL_RE.match(g.goal)
    assert hits >= 12
