"""Hybrid BM25 + hashed n-gram dense retrieval over catalog text fields only."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9]+")
NGRAM = 3
DIM = 256


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def hashed_ngrams(text: str, dim: int = DIM) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    blob = f" {text.lower()} "
    for i in range(len(blob) - NGRAM + 1):
        gram = blob[i : i + NGRAM]
        h = int.from_bytes(__import__("hashlib").md5(gram.encode()).digest()[:4], "little") % dim
        vec[h] += 1.0
    n = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec


class BM25Index:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(d) for d in documents]
        self.n = len(self.docs)
        self.df: dict[str, int] = {}
        for doc in self.docs:
            for t in set(doc):
                self.df[t] = self.df.get(t, 0) + 1
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.n)

    def score(self, query: str) -> np.ndarray:
        q = tokenize(query)
        scores = np.zeros(self.n, dtype=np.float32)
        for i, doc in enumerate(self.docs):
            if not doc:
                continue
            tf: dict[str, int] = {}
            for t in doc:
                tf[t] = tf.get(t, 0) + 1
            dl = len(doc)
            s = 0.0
            for t in q:
                n_qi = self.df.get(t, 0)
                if n_qi == 0:
                    continue
                idf = math.log(1 + (self.n - n_qi + 0.5) / (n_qi + 0.5))
                freq = tf.get(t, 0)
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                s += idf * (freq * (self.k1 + 1)) / denom
            scores[i] = s
        return scores


@dataclass
class RetrievalHit:
    index: int
    score: float
    row: dict


class HybridRetriever:
    def __init__(self, rows: list[dict], text_fn):
        self.rows = rows
        self.texts = [text_fn(r) for r in rows]
        self.bm25 = BM25Index(self.texts)
        self.dense = np.vstack(
            [hashed_ngrams(t) for t in self.texts]
        ) if self.texts else np.zeros((0, DIM), dtype=np.float32)

    def query(self, text: str, k: int = 5) -> list[RetrievalHit]:
        if not self.rows:
            return []
        b = self.bm25.score(text)
        if b.max() > 0:
            b = b / (b.max() + 1e-9)
        qv = hashed_ngrams(text)
        dense = self.dense @ qv
        dense = (dense + 1.0) / 2.0
        depths = np.array([float(r.get("depth") or 1) for r in self.rows], dtype=np.float32)
        max_d = max(float(depths.max()) if len(depths) else 1.0, 1.0)
        specificity = depths / max_d
        combined = 0.5 * b + 0.4 * dense + 0.1 * specificity
        order = np.argsort(-combined)
        hits = []
        for idx in order[:k]:
            hits.append(
                RetrievalHit(index=int(idx), score=float(combined[idx]), row=self.rows[int(idx)])
            )
        return hits


def catalog_text(row: dict) -> str:
    # Match on descriptive metadata only — never the opaque URI.
    parts = [
        row.get("description") or "",
        row.get("message") or "",
        row.get("qna_description") or "",
        row.get("domain") or "",
        (row.get("classes") or {}).get("screen") or "",
    ]
    return " ".join(parts)


def siis_text(row: dict) -> str:
    hints = " ".join(row.get("query_hints") or [])
    return " ".join(
        [
            row.get("title") or "",
            hints,
            row.get("body") or "",
            row.get("domain") or "",
            (row.get("plan") or {}).get("title") or "",
            (row.get("plan") or {}).get("topic") or "",
        ]
    )
