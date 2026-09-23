"""Map extracted actions onto catalog deeplinks; never emit dummy or parent-only URIs when a leaf exists."""

from __future__ import annotations

from engine.retrieve import HybridRetriever, RetrievalHit, catalog_text
from engine.schema import Deeplink
from engine.validate import DUMMY_URI, deeplink_allowed

PARENT_SLUGS = {
    "battery",
    "display",
    "camera",
    "device_care",
    "camera_settings",
}


class DeeplinkMapper:
    def __init__(self, catalog: list[dict]):
        self.catalog = catalog
        self.by_slug = {}
        self.by_uri = {}
        for row in catalog:
            uri = row["deeplink"]
            slug = uri.rsplit("/", 1)[-1]
            self.by_slug[slug] = row
            self.by_uri[uri] = row
        self.retriever = HybridRetriever(catalog, catalog_text)
        self.allowed = set(self.by_uri)

    def resolve_screen_key(self, screen_key: str | None) -> dict | None:
        if not screen_key:
            return None
        return self.by_slug.get(screen_key)

    def resolve_text(self, text: str, prefer_leaf: bool = True) -> dict | None:
        hits = self.retriever.query(text, k=8)
        if not hits:
            return None
        if hits[0].score < 0.22:
            return None
        chosen = self._prefer_leaf(hits) if prefer_leaf else hits[0]
        uri = chosen.row["deeplink"]
        if uri == DUMMY_URI or not deeplink_allowed(uri, self.allowed):
            return None
        return chosen.row

    def _prefer_leaf(self, hits: list[RetrievalHit]) -> RetrievalHit:
        best = hits[0]
        for hit in hits:
            slug = hit.row["deeplink"].rsplit("/", 1)[-1]
            if slug in PARENT_SLUGS:
                continue
            if hit.score >= best.score * 0.86:
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
