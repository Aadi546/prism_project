"""Load official Theme 2 kit assets (and fallback list-shaped files)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _load(name: str):
    path = DATA / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _unwrap(payload, list_key: str) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and list_key in payload:
        return payload[list_key]
    return []


@lru_cache(maxsize=1)
def deeplinks() -> list[dict]:
    return _unwrap(_load("deeplinks.json"), "deeplinks")


@lru_cache(maxsize=1)
def siis_articles() -> list[dict]:
    return _unwrap(_load("siis_responses.json"), "responses")


@lru_cache(maxsize=1)
def canned_queries() -> list[dict]:
    return _load("queries.json")


def article_by_id(article_id: str) -> dict | None:
    for row in siis_articles():
        if row.get("id") == article_id:
            return row
    return None
