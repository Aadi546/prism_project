"""Semantic fast-path cache.

Lookup order:
  1. exact match on the cleaned query or its canonical form
  2. char 3–5 gram cosine (typos) and word 1–2 gram cosine (paraphrases)
     — accepted at a high threshold, or at a lower one when distinctive tokens overlap.

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

from engine.enrichment import content_tokens


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
    def __init__(
        self,
        corpus: list[str],
        high: float = 0.55,
        low: float = 0.40,
        word_high: float = 0.28,
        word_low: float = 0.20,
        min_score: float = 0.55,
        path: Path | None = None,
    ):
        self.high = high
        self.low = low
        self.word_high = word_high
        self.word_low = word_low
        self.min_score = min_score
        self.path = path
        fit = corpus or ["device"]
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
        self.vectorizer.fit(fit)
        self.word_vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        self.word_vec.fit(fit)
        self._vectors = None
        self._word_vectors = None
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

    def _embed_words(self, texts: list[str]):
        return normalize(self.word_vec.transform(texts))

    @staticmethod
    def _token_agree(query_texts: list[str], entry: CacheEntry) -> bool:
        q = set()
        for t in query_texts:
            q |= content_tokens(t)
        e = set()
        for t in entry.texts:
            e |= content_tokens(t)
        return bool(q and e and len(q & e) >= 2)

    def lookup(self, texts: list[str], symptoms: list[str] | None = None) -> CacheHit | None:
        del symptoms  # kept for callers; matching is token/cosine, not lexicon keys
        texts = [t for t in texts if t and str(t).strip()]
        for t in texts:
            idx = self._exact.get(self._key(t))
            if idx is not None:
                self._entries[idx].hits += 1
                return CacheHit(self._entries[idx].payload, 1.0, t, "exact", self._entries[idx].source_hash)
        if self._vectors is None or not texts:
            return None
        q = self._embed(texts)
        char_sims = (self._vectors @ q.T).toarray().max(axis=1)
        word_sims = np.zeros_like(char_sims)
        if self._word_vectors is not None:
            qw = self._embed_words(texts)
            word_sims = (self._word_vectors @ qw.T).toarray().max(axis=1)
        order = np.unique(np.concatenate([np.argsort(-char_sims)[:8], np.argsort(-word_sims)[:8]]))
        best: CacheHit | None = None
        best_s = -1.0
        best_entry: CacheEntry | None = None
        for i in order:
            i = int(i)
            char_s = float(char_sims[i])
            word_s = float(word_sims[i])
            entry = self._entries[self._owners[i]]
            agree = self._token_agree(texts, entry)
            hit_char = char_s >= self.high or (char_s >= self.low and agree)
            hit_word = agree and word_s >= self.word_low
            if not (hit_char or hit_word):
                continue
            s = max(char_s, word_s)
            if s > best_s:
                method = "semantic-word" if word_s >= char_s and hit_word else "semantic"
                if char_s >= self.high and char_s >= word_s:
                    method = "semantic-high"
                elif hit_word and word_s >= self.word_high:
                    method = "semantic-word-high"
                best_s = s
                best_entry = entry
                best = CacheHit(entry.payload, round(s, 3), self._texts[i], method, entry.source_hash)
        if best_entry is not None:
            best_entry.hits += 1
        return best

    def store(self, texts: list[str], symptoms: list[str], payload: dict[str, Any], score: float, source_hash: str = "") -> bool:
        if score < self.min_score:
            self.rejected += 1
            return False
        texts = [t for t in dict.fromkeys(texts) if t and t.strip()]
        eid = len(self._entries)
        self._entries.append(CacheEntry(texts, symptoms, payload, source_hash))
        for t in texts:
            self._exact[self._key(t)] = eid
        from scipy.sparse import vstack

        vecs = self._embed(texts)
        self._vectors = vecs if self._vectors is None else vstack([self._vectors, vecs]).tocsr()
        wvecs = self._embed_words(texts)
        self._word_vectors = wvecs if self._word_vectors is None else vstack([self._word_vectors, wvecs]).tocsr()
        self._owners.extend([eid] * len(texts))
        self._texts.extend(texts)
        return True

    def invalidate(self, source_hash: str) -> int:
        """Drop plans built from a SIIS article that has since changed."""
        keep = [e for e in self._entries if e.source_hash != source_hash]
        dropped = len(self._entries) - len(keep)
        if dropped:
            entries, self._entries = keep, []
            self._vectors, self._word_vectors, self._owners, self._texts, self._exact = None, None, [], [], {}
            for e in entries:
                self.store(e.texts, e.symptoms, e.payload, 1.0, e.source_hash)
        return dropped

    def clear(self) -> None:
        self._entries, self._vectors, self._word_vectors, self._owners, self._texts, self._exact = [], None, None, [], [], {}

    def primed(self) -> bool:
        return bool(self._entries)

    def stats(self) -> dict:
        return {
            "entries": len(self._entries),
            "texts": len(self._texts),
            "hits": sum(e.hits for e in self._entries),
            "rejected_low_score": self.rejected,
            "thresholds": {
                "char_high": self.high,
                "char_low_with_token_overlap": self.low,
                "word_high": self.word_high,
                "word_low_with_token_overlap": self.word_low,
            },
        }

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.__dict__ for e in self._entries]
        self.path.write_text(json.dumps(data), encoding="utf-8")
