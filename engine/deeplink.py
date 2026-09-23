"""Map extracted actions onto catalog deeplinks using description/message/qna text."""

from __future__ import annotations

from engine.retrieve import HybridRetriever, RetrievalHit, catalog_text
from engine.schema import Deeplink, ValidationDeeplink
from engine.validate import DUMMY_URI, deeplink_allowed


class DeeplinkMapper:
    def __init__(self, catalog: list[dict]):
        self.catalog = catalog
        self.by_slug = {}
        self.by_uri = {}
        self.dummy = None
        real = []
        for row in catalog:
            uri = row["deeplink"]
            slug = uri.rsplit("/", 1)[-1]
            self.by_slug[slug] = row
            self.by_uri[uri] = row
            if uri == DUMMY_URI:
                self.dummy = row
            else:
                real.append(row)
        self.retriever = HybridRetriever(real, catalog_text)
        self.allowed = set(self.by_uri)

    def resolve_screen_key(self, screen_key: str | None) -> dict | None:
        if not screen_key:
            return None
        return self.by_slug.get(screen_key)

    def resolve_text(self, text: str, prefer_leaf: bool = True, allow_dummy: bool = False) -> dict | None:
        hits = self.retriever.query(text, k=8)
        if not hits or hits[0].score < 0.28:
            if allow_dummy:
                return self.dummy
            return None
        chosen = self._prefer_leaf(hits) if prefer_leaf else hits[0]
        uri = chosen.row["deeplink"]
        if not deeplink_allowed(uri, self.allowed):
            return None
        return chosen.row

    def _prefer_leaf(self, hits: list[RetrievalHit]) -> RetrievalHit:
        best = hits[0]
        for hit in hits:
            msg = (hit.row.get("message") or "").lower()
            # Prefer opening/enabling a screen over a disable toggle when scores are close
            if msg.startswith("disable") and best.score - hit.score < 0.05:
                continue
            if hit.score >= best.score * 0.9:
                return hit
        return best

    def to_model(self, row: dict | None) -> Deeplink | None:
        if not row:
            return None
        uri = row["deeplink"]
        if not deeplink_allowed(uri, self.allowed):
            return None
        return Deeplink(
            deeplink=uri,
            description=row.get("description") or "",
            message=row.get("message") or "",
            classes=row.get("classes"),
            originalType=row.get("originalType"),
        )

    def to_validation(self, row: dict | None) -> ValidationDeeplink | None:
        if not row:
            return None
        raw = row.get("validation")
        if not raw or not raw.get("deeplink"):
            return None
        return ValidationDeeplink(
            deeplink=raw["deeplink"],
            key=raw.get("key") or row.get("message") or "setting",
        )
