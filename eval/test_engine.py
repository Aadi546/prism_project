"""Contract, hygiene, mapping, cache, verification and API tests against the official Theme 2 kit."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import app
from engine.catalog import DUMMY_URI
from engine.pipeline import TroubleshootingEngine
from engine.schema import ActionCategory, ContextDeeplinkResponse, TroubleshootResponse
from engine.validate import GOAL_RE, collect_urls, description_ok, fit_description, rule_violations

ROOT = Path(__file__).resolve().parents[1]
KIT_QUERIES = [l.strip() for l in (ROOT / "data" / "input.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
ARTICLES = json.loads((ROOT / "data" / "siis_responses.json").read_text(encoding="utf-8"))["responses"]
CATALOG = json.loads((ROOT / "data" / "deeplinks.json").read_text(encoding="utf-8"))["deeplinks"]
ALLOWED = {r["deeplink"] for r in CATALOG}
VAL_ALLOWED = {(r.get("validation") or {}).get("deeplink") for r in CATALOG}
CRACKED = "My smartphone's screen is completely cracked, it's a total crack and I can't use the device."
TOUCH = "My Nexa X1 screen inputs are delayed and the touch responsiveness is laggy, causing a noticeable delay when I try to interact with the phone."


@pytest.fixture(scope="session")
def engine() -> TroubleshootingEngine:
    return TroubleshootingEngine(prewarm=False, use_llm=False)


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _all_plans(engine):
    for art in ARTICLES:
        yield art, engine.troubleshoot(art["original_query"], art["siis_response"])


# ---------------------------------------------------------------- contract
def test_every_kit_pair_is_schema_valid_and_rule_clean(engine):
    for art, resp in _all_plans(engine):
        TroubleshootResponse.model_validate(resp.model_dump(mode="json"))
        ContextDeeplinkResponse.model_validate(resp.response.model_dump(mode="json"))
        for goal in resp.response.contexts:
            assert rule_violations(goal) == [], (art["id"], rule_violations(goal))
            assert GOAL_RE.match(goal.goal)
            assert 2 <= len(goal.title.split()) <= 3
            assert 0.0 <= goal.score <= 1.0


def test_query_variations_count_and_distinct(engine):
    resp = engine.troubleshoot(CRACKED + " (variations)")
    assert 8 <= len(resp.query_variations) <= 10
    assert len({v.lower() for v in resp.query_variations}) == len(resp.query_variations)


def test_no_url_leak_and_catalog_only(engine):
    for _, resp in _all_plans(engine):
        blob = resp.model_dump_json()
        assert not collect_urls(resp.response.model_dump_json())
        assert "```" not in blob
        for uri in re.findall(r"(?:voiceassist|bixby)://[^\"]+", blob):
            assert uri in ALLOWED or uri in VAL_ALLOWED


def test_manual_never_has_deeplink_and_critical_last(engine):
    for _, resp in _all_plans(engine):
        for goal in resp.response.contexts:
            cats = [a.category for a in goal.actions]
            order = {ActionCategory.auto: 0, ActionCategory.manual: 1, ActionCategory.critical: 2}
            assert [order[c] for c in cats] == sorted(order[c] for c in cats)
            for a in goal.actions:
                if a.category == ActionCategory.manual:
                    assert all(g.actionableDeeplink is None for g in a.stepGroups)


def test_factory_reset_and_safe_mode_are_critical(engine):
    resp = engine.troubleshoot(TOUCH, ARTICLES[[a["id"] for a in ARTICLES].index("row_21")]["siis_response"])
    names = {a.actionName: a.category for g in resp.response.contexts for a in g.actions}
    assert names["Perform a Factory Data Reset"] == ActionCategory.critical
    assert names["Restart in Safe Mode"] == ActionCategory.critical


def test_touch_sensitivity_maps_to_exact_toggle_with_validation(engine):
    resp = engine.troubleshoot(TOUCH, ARTICLES[[a["id"] for a in ARTICLES].index("row_21")]["siis_response"])
    groups = [g for c in resp.response.contexts for a in c.actions for g in a.stepGroups if g.actionableDeeplink]
    touch = [g for g in groups if "touch sensitivity" in (g.actionableDeeplink.message or "").lower()]
    assert touch, "touch sensitivity toggle not mapped"
    on = [g for g in touch if g.validationDeeplink and g.validationDeeplink.value == "True"]
    assert on and on[0].validationDeeplink.resultType.value == "boolean"
    assert on[0].validationDeeplink.condition.value == "equal"


def test_dummy_positive_only_for_settings_paths(engine):
    for _, resp in _all_plans(engine):
        for goal in resp.response.contexts:
            for a in goal.actions:
                for g in a.stepGroups:
                    if g.actionableDeeplink and g.actionableDeeplink.deeplink == DUMMY_URI:
                        assert any("settings" in s.lower() for s in g.steps)


def test_description_helper():
    assert description_ok(fit_description("It will open the screen settings"))
    assert description_ok(fit_description("restart the device"))
    assert not description_ok("It will overview settings settings")


# ---------------------------------------------------------------- fallbacks & gates
def test_unknown_intent_returns_empty_contexts(engine):
    resp = engine.troubleshoot("My phone's infrared blaster no longer controls my AC remote app")
    assert resp.response.contexts == []
    assert resp.meta.fallback in {"no_match", "no_siis_context"}


def test_irrelevant_provided_siis_is_rejected(engine):
    blank = ARTICLES[[a["id"] for a in ARTICLES].index("row_2")]["siis_response"]
    resp = engine.troubleshoot("My phone's infrared blaster no longer controls my AC remote app", blank)
    assert resp.response.contexts == []
    assert resp.meta.fallback == "no_match"


def test_multi_intent_complaint_yields_multiple_goals(engine):
    q = KIT_QUERIES[16]
    assert q.startswith("1.") and "2." in q
    resp = engine.troubleshoot(q + " ")
    assert len(resp.response.contexts) >= 2


# ---------------------------------------------------------------- cache
def test_cache_hit_on_repeat_and_paraphrase():
    eng = TroubleshootingEngine(prewarm=True, use_llm=False)
    first = eng.troubleshoot(CRACKED)
    assert first.meta.cache_hit is True  # pre-warmed from the knowledge base pair
    para = eng.troubleshoot("The display on my smartphone is completely shattered, I can't use it")
    assert para.meta.cache_hit is True
    assert para.meta.cost_usd == 0.0
    assert para.meta.latency_ms < 300


def test_low_score_plans_are_not_cached():
    eng = TroubleshootingEngine(prewarm=False, use_llm=False)
    eng.cache.min_score = 0.99
    eng.troubleshoot(CRACKED)
    assert len(eng.cache) == 0 and eng.cache.rejected == 1


@pytest.fixture(scope="module")
def warm_engine():
    return TroubleshootingEngine(prewarm=True, use_llm=False)


@pytest.mark.parametrize(
    "para,kit_q",
    [
        ("The display on my smartphone is completely shattered, I can't use it", CRACKED),
        ("My new smartphone screen not fitting full screen", KIT_QUERIES[6]),
        ("Nexa X1 touch is laggy and delayed when I tap", TOUCH),
        ("There's a floating circle on my Nexa I want gone", KIT_QUERIES[10]),
    ],
)
def test_kit_paraphrases_reuse_the_same_plan(warm_engine, para, kit_q):
    gold = warm_engine.troubleshoot(kit_q)
    got = warm_engine.troubleshoot(para)
    assert gold.response.contexts, kit_q
    assert got.response.contexts, para
    assert got.response.contexts[0].title == gold.response.contexts[0].title
    assert got.response.contexts[0].goal == gold.response.contexts[0].goal


def test_unknown_intents_stay_empty_after_prewarm(warm_engine):
    for q in (
        "My phone's infrared blaster no longer controls my AC remote app",
        "The wireless charging coil in my phone is dead",
    ):
        resp = warm_engine.troubleshoot(q)
        assert resp.response.contexts == [], q
        assert resp.meta.fallback in {"no_match", "no_siis_context"}


# ---------------------------------------------------------------- verification loop
def test_closed_loop_verification_on_simulator(engine):
    resp = engine.troubleshoot(TOUCH, ARTICLES[[a["id"] for a in ARTICLES].index("row_21")]["siis_response"])
    payload = resp.response.model_dump(mode="json")
    sess = engine.sim.start(payload, seed=1)
    groups = [
        g
        for c in payload["contexts"]
        for a in c["actions"]
        for g in a["stepGroups"]
        if g["validationDeeplink"]
        and g["validationDeeplink"].get("resultType") == "boolean"
        and g.get("actionableDeeplink")
    ]
    assert groups, "expected a boolean validation deeplink"
    group = next(
        (g for g in groups if engine.sim.verify(sess.id, g["validationDeeplink"])["passed"] is False),
        None,
    )
    assert group is not None
    before = engine.sim.verify(sess.id, group["validationDeeplink"])
    assert before["passed"] is False
    engine.sim.tap(sess.id, group["actionableDeeplink"]["deeplink"], group["validationDeeplink"])
    after = engine.sim.verify(sess.id, group["validationDeeplink"])
    assert after["passed"] is True


# ---------------------------------------------------------------- API
def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["catalog"] >= 500
    assert body["indexes"] == {"deeplink": True, "siis": True, "cache": True, "kit_query": True}


def test_api_roundtrip_pure_json(client):
    res = client.post("/v1/troubleshoot", json={"query": CRACKED})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    body = res.json()
    assert set(body) == {"query", "query_variations", "response", "meta"}
    assert set(body["meta"]) >= {"latency_ms", "cache_hit", "model", "cost_usd"}


def test_api_trace_and_verify(client):
    art = ARTICLES[[a["id"] for a in ARTICLES].index("row_21")]
    body = client.post("/v1/troubleshoot?trace=1", json={"query": TOUCH, "siis_response": art["siis_response"]}).json()
    assert "trace" in body and body["trace"]["stages"]
    assert body["trace"]["extraction"][0]["provenance"]
    sess = client.post("/v1/sim/start", json={"response": body["response"], "seed": 3}).json()
    assert sess["state"]


def test_api_rejects_empty_query(client):
    assert client.post("/v1/troubleshoot", json={"query": "  "}).status_code == 422
