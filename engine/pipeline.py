"""Orchestrate enrichment → cache → SIIS retrieval → extraction → mapping."""

from __future__ import annotations

import time
from typing import Any, Optional

from engine.cache import SemanticCache
from engine.deeplink import DeeplinkMapper
from engine.enrichment import generate_paraphrases, normalize_query
from engine.extract import extract_goal, flatten_siis
from engine.retrieve import HybridRetriever, siis_text
from engine.schema import (
    ContextDeeplinkResponse,
    ResponseMeta,
    TroubleshootResponse,
)
from engine.store import deeplinks, siis_articles
from engine.validate import collect_urls

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
        for article in self.articles:
            seed = article.get("original_query") or (article.get("query_hints") or [None])[0]
            if not seed:
                continue
            resp = self._run_pipeline(seed, None, from_prewarm=True)
            if resp.response.contexts:
                payload = resp.model_dump()
                payload["meta"]["cache_hit"] = True
                payload["meta"]["cost_usd"] = 0.0
                texts = [normalize_query(seed), seed, *resp.query_variations]
                title = ""
                raw = article.get("siis_response")
                if isinstance(raw, dict):
                    title = raw.get("title") or ""
                if title:
                    texts.append(title)
                self.cache.store(texts, payload)

    def _retrieve_article(
        self, query: str, raw_siis: Any
    ) -> tuple[dict | None, float, Optional[str]]:
        blob = flatten_siis(raw_siis, None)
        if blob:
            hits = self.siis_index.query(blob, k=1)
            if hits and hits[0].score >= 0.28:
                return hits[0].row, hits[0].score, None
            return None, 0.55, None
        hits = self.siis_index.query(query, k=3)
        if not hits or hits[0].score < 0.28:
            return None, 0.0, NO_SIIS
        return hits[0].row, hits[0].score, None

    def _run_pipeline(
        self,
        query: str,
        siis_response: Any = None,
        from_prewarm: bool = False,
    ) -> TroubleshootResponse:
        canonical = normalize_query(query)
        paraphrases = generate_paraphrases(query, canonical)
        article, score, fallback = self._retrieve_article(canonical + " " + query, siis_response)
        blob = flatten_siis(siis_response, article)
        if fallback == NO_SIIS and not blob:
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
        dumped = goal.model_dump()
        assert not collect_urls(str(dumped))
        return TroubleshootResponse(
            query=query,
            query_variations=paraphrases,
            response=ContextDeeplinkResponse(contexts=[goal]),
            meta=ResponseMeta(
                latency_ms=0,
                cache_hit=False,
                model=MODEL_ID,
                cost_usd=0.0,
                fallback=None,
            ),
        )

    def troubleshoot(self, query: str, siis_response: Any = None) -> TroubleshootResponse:
        started = time.perf_counter()
        canonical = normalize_query(query)
        lookup_keys = [query, canonical]
        cached = None
        if not flatten_siis(siis_response, None):
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
