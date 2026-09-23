"""Load JSON starter assets from data/."""

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


@lru_cache(maxsize=1)
def deeplinks() -> list[dict]:
    return _load("deeplinks.json")


@lru_cache(maxsize=1)
def siis_articles() -> list[dict]:
    return _load("siis_responses.json")


@lru_cache(maxsize=1)
def canned_queries() -> list[dict]:
    return _load("queries.json")


def article_by_id(article_id: str) -> dict | None:
    for row in siis_articles():
        if row["id"] == article_id:
            return row
    return None
