"""Orchestrate enrichment → cache → SIIS retrieval → extraction → mapping."""

from __future__ import annotations

import time
from typing import Optional

from engine.cache import SemanticCache
from engine.deeplink import DeeplinkMapper
from engine.enrichment import EnrichedQuery, generate_paraphrases, normalize_query, semantic_cache_key
from engine.extract import extract_goal
from engine.retrieve import HybridRetriever, siis_text
from engine.schema import (
    ContextDeeplinkResponse,
    ResponseMeta,
    TroubleshootResponse,
)
from engine.store import deeplinks, siis_articles
from engine.validate import DUMMY_URI, collect_urls

MODEL_ID = "hybrid-bm25-ngram"
NO_MATCH = "no_match"
NO_SIIS = "no_siis_context"


class TroubleshootingEngine:
    def __init__(self):
        catalog = deeplinks()
        self.articles = siis_articles()
        self.mapper = DeeplinkMapper(catalog)
        self.siis_index = HybridRetriever(self.articles, siis_text)
        self.cache = SemanticCache(threshold=0.84)
        self.ready = True
        self._prewarm()

    def _prewarm(self) -> None:
        """Index paraphrases of known SIIS titles so first-user paraphrases can hit."""
        for article in self.articles:
            if not article.get("plan", {}).get("actions"):
                continue
            hints = article.get("query_hints") or []
            if not hints:
                continue
            seed = hints[0]
            # Build a plan once and cache under hints + paraphrases
            resp = self._run_pipeline(seed, None, from_prewarm=True)
            if resp.response.contexts:
                payload = resp.model_dump()
                payload["meta"]["cache_hit"] = True
                payload["meta"]["cost_usd"] = 0.0
                texts = [normalize_query(seed), seed, *resp.query_variations, *hints]
                self.cache.store(texts, payload)

    def _retrieve_article(self, query: str, raw_siis: Optional[str]) -> tuple[dict | None, float, Optional[str]]:
        if raw_siis and raw_siis.strip():
            hits = self.siis_index.query(raw_siis, k=1)
            if hits and hits[0].score >= 0.28:
                return hits[0].row, hits[0].score, None
            # Use the pasted text as the only evidence even if it does not match corpus
            return None, 0.55, None
        hits = self.siis_index.query(query, k=3)
        if not hits or hits[0].score < 0.28:
            return None, 0.0, NO_SIIS
        return hits[0].row, hits[0].score, None

    def _run_pipeline(
        self,
        query: str,
        siis_response: Optional[str],
        from_prewarm: bool = False,
    ) -> TroubleshootResponse:
        canonical = normalize_query(query)
        paraphrases = generate_paraphrases(query, canonical)
        article, score, fallback = self._retrieve_article(canonical + " " + query, siis_response)
        if article is not None:
            plan_actions = (article.get("plan") or {}).get("actions") or []
            if not plan_actions:
                return TroubleshootResponse(
                    query=query,
                    query_variations=paraphrases,
                    response=ContextDeeplinkResponse(contexts=[]),
                    meta=ResponseMeta(
                        latency_ms=0,
                        cache_hit=False,
                        model=MODEL_ID,
                        cost_usd=0.0,
                        fallback=NO_MATCH,
                    ),
                )
        if fallback == NO_SIIS and not (siis_response and siis_response.strip()):
            return TroubleshootResponse(
                query=query,
                query_variations=paraphrases,
                response=ContextDeeplinkResponse(contexts=[]),
                meta=ResponseMeta(
                    latency_ms=0,
                    cache_hit=False,
                    model=MODEL_ID,
                    cost_usd=0.0,
                    fallback=NO_SIIS,
                ),
            )
        goal = extract_goal(query, article, siis_response, self.mapper, score if score else 0.5)
        if goal is None or not goal.actions:
            return TroubleshootResponse(
                query=query,
                query_variations=paraphrases,
                response=ContextDeeplinkResponse(contexts=[]),
                meta=ResponseMeta(
                    latency_ms=0,
                    cache_hit=False,
                    model=MODEL_ID,
                    cost_usd=0.0,
                    fallback=NO_MATCH,
                ),
            )
        # Guard dummy URI
        dumped = goal.model_dump()
        assert DUMMY_URI not in str(dumped)
        assert not collect_urls(str(dumped))
        return TroubleshootResponse(
            query=query,
            query_variations=paraphrases,
            response=ContextDeeplinkResponse(contexts=[goal]),
            meta=ResponseMeta(
                latency_ms=0,
                cache_hit=False,
                model=MODEL_ID,
                cost_usd=0.0 if from_prewarm else 0.0,
                fallback=None,
            ),
        )

    def troubleshoot(self, query: str, siis_response: Optional[str] = None) -> TroubleshootResponse:
        started = time.perf_counter()
        canonical = normalize_query(query)
        lookup_keys = [query, canonical]
        cached = None
        if not (siis_response and siis_response.strip()):
            for key in lookup_keys:
                cached = self.cache.lookup(key)
                if cached:
                    break
        if cached:
            data = dict(cached)
            data["query"] = query
            meta = dict(data.get("meta") or {})
            meta["cache_hit"] = True
            meta["cost_usd"] = 0.0
            meta["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            data["meta"] = meta
            return TroubleshootResponse.model_validate(data)

        result = self._run_pipeline(query, siis_response)
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        result.meta.latency_ms = elapsed
        if result.response.contexts:
            store = result.model_dump()
            store["meta"]["cache_hit"] = True
            store["meta"]["cost_usd"] = 0.0
            texts = [query, canonical, *result.query_variations]
            self.cache.store(texts, store)
        return result

    def health(self) -> dict:
        return {
            "status": "ok" if self.ready else "starting",
            "catalog": len(self.mapper.catalog),
            "siis_articles": len(self.articles),
            "cache_entries": len(self.cache),
            "indexes": {
                "deeplink": True,
                "siis": True,
                "cache": self.cache.primed(),
            },
        }
