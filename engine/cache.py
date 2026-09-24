"""Semantic fast-path cache.

Lookup order:
  1. exact match on the cleaned query or its canonical form
  2. TF-IDF (char 3–5 grams) cosine against every stored text (query, canonical, paraphrases)
     — accepted at a high threshold, or at a lower one when the symptom signature agrees.

Only plans that passed validation with a healthy score are stored (cache-poisoning guard),
and every entry records the SIIS content hash it was built from so stale plans can be
invalidated when the knowledge base changes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


@dataclass
class CacheEntry:
    texts: list[str]
    symptoms: list[str]
    payload: dict[str, Any]
    source_hash: str = ""
    created: float = field(default_factory=time.time)
    hits: int = 0


@dataclass
class CacheHit:
    payload: dict[str, Any]
    similarity: float
    matched_text: str
    method: str
    source_hash: str = ""


class SemanticCache:
    def __init__(self, corpus: list[str], high: float = 0.55, low: float = 0.40, min_score: float = 0.55, path: Path | None = None):
        self.high = high
        self.low = low
        self.min_score = min_score
        self.path = path
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
        self.vectorizer.fit(corpus or ["device"])
        self._vectors = None
        self._owners: list[int] = []
        self._texts: list[str] = []
        self._entries: list[CacheEntry] = []
        self._exact: dict[str, int] = {}
        self.rejected = 0

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def _key(text: str) -> str:
        return " ".join(text.lower().split())

    def _embed(self, texts: list[str]):
        return normalize(self.vectorizer.transform(texts))

    def lookup(self, texts: list[str], symptoms: list[str]) -> CacheHit | None:
        for t in texts:
            idx = self._exact.get(self._key(t))
            if idx is not None:
                self._entries[idx].hits += 1
                return CacheHit(self._entries[idx].payload, 1.0, t, "exact", self._entries[idx].source_hash)
        if self._vectors is None or not texts:
            return None
        q = self._embed(texts)
        sims = (self._vectors @ q.T).toarray().max(axis=1)
        order = np.argsort(-sims)[:5]
        sig = set(symptoms)
        for i in order:
            s = float(sims[i])
            entry = self._entries[self._owners[i]]
            agree = bool(sig) and bool(sig & set(entry.symptoms)) and (not entry.symptoms or entry.symptoms[0] in sig)
            if s >= self.high or (s >= self.low and agree):
                entry.hits += 1
                return CacheHit(entry.payload, round(s, 3), self._texts[i], "semantic" if s < self.high else "semantic-high", entry.source_hash)
        return None

    def store(self, texts: list[str], symptoms: list[str], payload: dict[str, Any], score: float, source_hash: str = "") -> bool:
        if score < self.min_score:
            self.rejected += 1
            return False
        texts = [t for t in dict.fromkeys(texts) if t and t.strip()]
        eid = len(self._entries)
        self._entries.append(CacheEntry(texts, symptoms, payload, source_hash))
        for t in texts:
            self._exact[self._key(t)] = eid
        vecs = self._embed(texts)
        from scipy.sparse import vstack

        self._vectors = vecs if self._vectors is None else vstack([self._vectors, vecs]).tocsr()
        self._owners.extend([eid] * len(texts))
        self._texts.extend(texts)
        return True

    def invalidate(self, source_hash: str) -> int:
        """Drop plans built from a SIIS article that has since changed."""
        keep = [e for e in self._entries if e.source_hash != source_hash]
        dropped = len(self._entries) - len(keep)
        if dropped:
            entries, self._entries = keep, []
            self._vectors, self._owners, self._texts, self._exact = None, [], [], {}
            for e in entries:
                self.store(e.texts, e.symptoms, e.payload, 1.0, e.source_hash)
        return dropped

    def clear(self) -> None:
        self._entries, self._vectors, self._owners, self._texts, self._exact = [], None, [], [], {}

    def primed(self) -> bool:
        return bool(self._entries)

    def stats(self) -> dict:
        return {
            "entries": len(self._entries),
            "texts": len(self._texts),
            "hits": sum(e.hits for e in self._entries),
            "rejected_low_score": self.rejected,
            "thresholds": {"high": self.high, "low_with_symptom_agreement": self.low},
        }

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.__dict__ for e in self._entries]
        self.path.write_text(json.dumps(data), encoding="utf-8")
