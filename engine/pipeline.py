"""Orchestrate enrichment → cache → SIIS retrieval → extraction → mapping → validation."""

from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from engine.cache import SemanticCache
from engine.catalog import Catalog
from engine.enrichment import EnrichedQuery, enrich, normalize_query
from engine.extract import Extraction, clean_article, extract_goal, goal_from_llm
from engine.lexicon import SYMPTOMS
from engine.llm import GroqClient
from engine.schema import ContextDeeplinkResponse, ResponseMeta, TroubleshootResponse
from engine.store import deeplinks, siis_articles
from engine.validate import collect_urls, rule_violations
from engine.verify import DeviceSimulator, is_verifiable

ENGINE_MODEL = "deterministic-hybrid-v2"
NO_MATCH = "no_match"
NO_SIIS = "no_siis_context"
RETRIEVAL_FLOOR = 0.12  # below this no SIIS article is about the complaint
CONTENT_FLOOR = 0.012  # long articles vs one short sub-intent (symptom agreement also required)
RELEVANCE_FLOOR = 0.02  # provided SIIS that shares (almost) nothing with the complaint


class Stopwatch:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.last = self.t0
        self.stages: list[dict] = []

    def lap(self, name: str, **extra) -> None:
        now = time.perf_counter()
        self.stages.append({"stage": name, "ms": round((now - self.last) * 1000, 3), **extra})
        self.last = now

    def total(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 2)


def _siis_blob(raw: Any) -> str:
    title, body = clean_article(raw)
    return f"{title}\n{body}".strip()


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


class TroubleshootingEngine:
    def __init__(self, prewarm: bool = True, use_llm: Optional[bool] = None):
        self.catalog = Catalog(deeplinks())
        self.articles = siis_articles()
        self.article_text = [
            f"{a.get('original_query') or ''} {_siis_blob(a.get('siis_response'))}" for a in self.articles
        ]
        self.siis_vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2))
        self.siis_matrix = self.siis_vec.fit_transform(self.article_text or ["empty"])
        # content-only view: sub-intents of a compound complaint must not match the whole ticket
        self.content_matrix = self.siis_vec.transform([_siis_blob(a.get("siis_response")) for a in self.articles] or ["empty"])
        corpus = [_siis_blob(a.get("siis_response")) for a in self.articles] + [
            f"{r.get('description')} {r.get('qna_description') or ''}" for r in self.catalog.rows
        ]
        self.cache = SemanticCache(corpus)
        self.sim = DeviceSimulator(self.catalog)
        self.llm = GroqClient()
        if use_llm is False or os.environ.get("ENGINE_DISABLE_LLM") == "1":
            self.llm._client = None
        self.ready = True
        self.prewarmed = 0
        if prewarm:
            self._prewarm()

    # ------------------------------------------------------------------ public
    @property
    def model_id(self) -> str:
        return f"groq/{self.llm.model}" if self.llm.enabled else ENGINE_MODEL

    def _prewarm(self) -> None:
        """Warm the fast path with the known (query, SIIS) pairs of the knowledge base."""
        for article in self.articles:
            seed = article.get("original_query")
            if seed:
                self.troubleshoot(seed, article.get("siis_response"), warm=True)
                self.prewarmed += 1

    def troubleshoot(self, query: str, siis_response: Any = None, trace: bool = False, warm: bool = False) -> TroubleshootResponse | tuple[TroubleshootResponse, dict]:
        sw = Stopwatch()
        eq = enrich(query)
        sw.lap("enrich", canonical=eq.canonical)
        provided = bool(_siis_blob(siis_response)) if siis_response else False
        info: dict = {"enrichment": self._enrich_info(eq), "llm": {"enabled": self.llm.enabled}}

        multi = not provided and len(eq.intents) > 1  # compound complaints are planned per intent
        if not provided and not warm and not multi:
            hit = self.cache.lookup([eq.cleaned, eq.canonical], eq.symptoms)
            sw.lap("cache_lookup", hit=bool(hit))
            if hit:
                data = dict(hit.payload)
                data["query"] = query
                data["meta"] = {**data["meta"], "cache_hit": True, "cost_usd": 0.0, "latency_ms": sw.total()}
                resp = TroubleshootResponse.model_validate(data)
                info["cache"] = {"hit": True, "similarity": hit.similarity, "matched": hit.matched_text, "method": hit.method}
                return (resp, self._trace(info, sw)) if trace else resp
            info["cache"] = {"hit": False}

        contexts, cost, fallback, model_used, retrievals, extractions = [], 0.0, None, ENGINE_MODEL, [], []
        intents = eq.intents if (not provided and len(eq.intents) > 1) else [eq.cleaned]
        for intent in intents:
            article, rel, retrieval = self._retrieve(intent, siis_response if provided else None, content_only=multi)
            retrievals.append(retrieval)
            sw.lap("retrieve", intent=intent[:60], score=round(rel, 3))
            if article is None:
                fallback = fallback or (NO_MATCH if provided else NO_SIIS)
                continue
            ex, used, c = self._extract(intent, article, rel)
            cost += c
            model_used = used if used != ENGINE_MODEL else model_used
            sw.lap("extract_map_validate", model=used)
            extractions.append(ex)
            if ex.goal is None:
                fallback = fallback or NO_MATCH
                continue
            sig = [a.actionName for a in ex.goal.actions]
            if any((g.title == ex.goal.title and g.goal == ex.goal.goal) or [a.actionName for a in g.actions] == sig for g in contexts):
                continue
            contexts.append(ex.goal)
        if contexts:
            fallback = None
        elif fallback is None:
            fallback = NO_MATCH

        resp = TroubleshootResponse(
            query=query,
            query_variations=self._paraphrases(eq, info),
            response=ContextDeeplinkResponse(contexts=contexts),
            meta=ResponseMeta(latency_ms=0.0, cache_hit=False, model=model_used, cost_usd=round(cost, 6), fallback=fallback),
        )
        assert not collect_urls(resp.response.model_dump_json()), "URL leak"
        sw.lap("assemble")
        best = max((g.score for g in contexts), default=0.0)
        if contexts:
            payload = resp.model_dump(mode="json")
            src = _hash("".join(r.get("hash", "") for r in retrievals))
            stored = self.cache.store(
                [eq.cleaned, eq.canonical, *resp.query_variations], eq.symptoms, payload, best, src
            )
            info["cache_store"] = {"stored": stored, "reason": "ok" if stored else f"score {best} below {self.cache.min_score}"}
        resp.meta.latency_ms = sw.total()
        if not trace:
            return resp
        info["retrieval"] = retrievals
        info["extraction"] = [self._extraction_info(e) for e in extractions]
        info["violations"] = [rule_violations(g) for g in contexts]
        return resp, self._trace(info, sw)

    # ------------------------------------------------------------------ stages
    def _retrieve(self, query: str, provided: Any, content_only: bool = False) -> tuple[Optional[dict], float, dict]:
        qv = self.siis_vec.transform([query])
        if provided is not None:
            blob = _siis_blob(provided)
            rel = float((self.siis_vec.transform([blob]) @ qv.T).toarray()[0, 0])
            art = {"id": "provided", "siis_response": provided}
            info = {"source": "request", "relevance": round(rel, 3), "hash": _hash(blob)}
            if rel < RELEVANCE_FLOOR and not self._symptom_overlap(query, blob):
                info["gate"] = "rejected: provided SIIS does not address the complaint"
                return None, rel, info
            return art, rel, info
        sims = ((self.content_matrix if content_only else self.siis_matrix) @ qv.T).toarray().ravel()
        if not len(sims):
            return None, 0.0, {"source": "index", "candidates": []}
        order = np.argsort(-sims)[:3]
        cands = [
            {
                "id": self.articles[i].get("id"),
                "title": (self.articles[i].get("siis_response") or {}).get("title"),
                "score": round(float(sims[i]), 3),
            }
            for i in order
        ]
        top = int(order[0])
        info = {"source": "index", "candidates": cands, "hash": _hash(self.article_text[top])}
        floor = CONTENT_FLOOR if content_only else RETRIEVAL_FLOOR
        if sims[top] < floor or (content_only and not self._symptom_overlap(query, self.article_text[top])):
            info["gate"] = f"rejected: best article {sims[top]:.3f} < {floor}"
            return None, float(sims[top]), info
        return self.articles[top], float(sims[top]), info

    @staticmethod
    def _symptom_overlap(query: str, text: str) -> bool:
        qs = {s.key for s in SYMPTOMS if s.pattern.search(query)}
        ts = {s.key for s in SYMPTOMS if s.pattern.search(text)}
        return bool(qs & ts)

    @staticmethod
    def coverage(query: str, article_text: str) -> float:
        """Share of the complaint's content words (5-char stems) that the reference talks about."""
        generic = {"screen", "devic", "displ", "phone", "galax", "samsu", "tablet"[:5]}
        q = {w[:5] for w in normalize_query(query).split() if len(w) > 2} - generic
        if not q:
            return 0.0
        doc = {w[:5] for w in re.findall(r"[a-z0-9]+", article_text.lower()) if len(w) > 2}
        return len(q & doc) / len(q)

    def _score(self, query: str, article_text: str, rel: float, ex: Extraction) -> float:
        """Calibrated confidence: complaint coverage by the reference + symptom agreement + deeplink coverage."""
        symptom = 1.0 if self._symptom_overlap(query, article_text) else 0.0
        cov_q = self.coverage(query, article_text)
        links = ex.deeplink_coverage if ex.goal else 0.0
        return round(min(0.97, 0.25 + 0.40 * cov_q + 0.20 * symptom + 0.12 * links), 2)

    def _extract(self, query: str, article: dict, rel: float) -> tuple[Extraction, str, float]:
        raw = article.get("siis_response")
        blob = _siis_blob(raw)
        cost = 0.0
        used = ENGINE_MODEL
        ex = None
        if self.llm.enabled:
            cands = []
            seen = set()
            for r, _ in self.catalog.search(f"{query} {blob[:3000]}", k=30):
                if r["id"] not in seen:
                    seen.add(r["id"])
                    cands.append({"id": r["id"], "message": r.get("message"), "description": r.get("description")})
            res = self.llm.extract(query, blob, cands)
            cost += res.cost_usd
            self._last_llm = res
            if res.data:
                ex = goal_from_llm(query, res.data, raw, self.catalog, 0.5, {c["id"] for c in cands})
                if ex.goal is not None:
                    used = f"groq/{res.model}"
                else:
                    ex = None
        if ex is None:
            ex = extract_goal(query, raw, self.catalog, 0.5)
        if ex.goal is not None:
            ex.goal.score = self._score(query, blob, rel, ex)
        return ex, used, cost

    def _paraphrases(self, eq: EnrichedQuery, info: dict) -> list[str]:
        if self.llm.enabled:
            res = self.llm.paraphrase(eq.cleaned)
            items = [str(p).strip() for p in (res.data or {}).get("paraphrases", []) if str(p).strip()]
            items = list(dict.fromkeys([eq.cleaned, *items]))
            if 8 <= len(items):
                info["llm"]["paraphrase_cost"] = res.cost_usd
                return items[:10]
        return eq.paraphrases

    # ------------------------------------------------------------------ trace helpers
    @staticmethod
    def _enrich_info(eq: EnrichedQuery) -> dict:
        return {
            "cleaned": eq.cleaned,
            "canonical": eq.canonical,
            "cache_key": eq.cache_key,
            "symptoms": eq.symptoms,
            "device": eq.device,
            "intents": eq.intents,
        }

    def _extraction_info(self, ex: Extraction) -> dict:
        verifiable = total = 0
        if ex.goal:
            for a in ex.goal.actions:
                for g in a.stepGroups:
                    if g.actionableDeeplink is not None:
                        total += 1
                        verifiable += int(is_verifiable(g.validationDeeplink))
        return {
            "siis_text": ex.text,
            "sections_used": ex.sections_used,
            "sections_dropped": ex.sections_dropped,
            "provenance": ex.provenance,
            "mapping": ex.mapping,
            "deeplink_coverage": round(ex.deeplink_coverage, 3),
            "verifiable_links": verifiable,
            "linked_groups": total,
        }

    @staticmethod
    def _trace(info: dict, sw: Stopwatch) -> dict:
        return {**info, "stages": sw.stages, "total_ms": sw.total()}

    def health(self) -> dict:
        return {
            "status": "ok" if self.ready else "starting",
            "catalog": len(self.catalog.rows),
            "catalog_phone_screens": len(self.catalog.phone_rows),
            "siis_articles": len(self.articles),
            "cache_entries": len(self.cache),
            "model": self.model_id,
            "llm": {"provider": "groq", "enabled": self.llm.enabled, "model": self.llm.model},
            "indexes": {"deeplink": True, "siis": True, "cache": self.cache.primed()},
        }
