"""In-memory semantic cache keyed by embeddings of canonical queries and paraphrases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from engine.retrieve import DIM, hashed_ngrams


@dataclass
class CacheEntry:
    texts: list[str]
    payload: dict[str, Any]


class SemanticCache:
    def __init__(self, threshold: float = 0.86):
        self.threshold = threshold
        self._vectors = np.zeros((0, DIM), dtype=np.float32)
        self._entry_ids: list[int] = []
        self._entries: list[CacheEntry] = []
        self._exact: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def lookup(self, text: str) -> dict[str, Any] | None:
        key = " ".join(text.lower().split())
        if key in self._exact:
            return self._entries[self._exact[key]].payload
        if self._vectors.shape[0] == 0:
            return None
        q = hashed_ngrams(text)
        sims = self._vectors @ q
        idx = int(np.argmax(sims))
        if float(sims[idx]) < self.threshold:
            return None
        return self._entries[self._entry_ids[idx]].payload

    def store(self, texts: list[str], payload: dict[str, Any]) -> None:
        eid = len(self._entries)
        self._entries.append(CacheEntry(texts=list(texts), payload=payload))
        for t in texts:
            self._exact[" ".join(t.lower().split())] = eid
        vecs = np.vstack([hashed_ngrams(t) for t in texts])
        if self._vectors.shape[0] == 0:
            self._vectors = vecs
            self._entry_ids = [eid] * len(texts)
        else:
            self._vectors = np.vstack([self._vectors, vecs])
            self._entry_ids.extend([eid] * len(texts))

    def primed(self) -> bool:
        return self._vectors.shape[0] > 0
