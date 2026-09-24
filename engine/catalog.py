"""Deeplink catalog: hygiene tags, on/off twins, and screen resolution over descriptive text.

Matching is done only on `description`, `message`, `qna_description` and the validation
`key` (the on-screen setting name). The masked URI is never looked at except to copy it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from engine.lexicon import SETTING_SYNONYMS

DUMMY_URI = "bixby://dummy_positive"
NON_PHONE_RE = re.compile(r"\b(tv settings|tv bixby|air conditioner|retrieves)\b", re.IGNORECASE)
GENERIC_KEYS = {"onurl", "offurl", "more options", "settings", "battery", "accessibility", "alarm"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+ ]+", " ", text.lower())).strip()


def row_kind(row: dict) -> str:
    """on | off | update | open | status."""
    t = row.get("originalType") or ""
    msg = (row.get("message") or "").lower()
    key = ((row.get("validation") or {}).get("key") or "").lower()
    if t == "onURL" or msg == "onurl" or key == "onurl":
        return "on"
    if t == "offURL" or msg == "offurl" or key == "offurl":
        return "off"
    if t == "updateURL":
        return "update"
    if t == "onClickURL":
        return "open"
    return "status"


@dataclass
class ScreenMatch:
    row: dict
    score: float
    reason: str
    candidates: list[dict] = field(default_factory=list)


class Catalog:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.by_uri = {r["deeplink"]: r for r in rows}
        self.by_id = {r["id"]: r for r in rows}
        self.allowed = set(self.by_uri)
        self.dummy = self.by_uri.get(DUMMY_URI)
        self.phone_rows = [r for r in rows if self._usable(r)]
        self.kinds = {r["id"]: row_kind(r) for r in rows}
        # Twins share a validation URI (the same on-screen switch, opposite direction).
        self.twins: dict[str, list[dict]] = {}
        for r in self.phone_rows:
            v = (r.get("validation") or {}).get("deeplink")
            if v:
                self.twins.setdefault(v, []).append(r)
        self.by_val = {
            (r.get("validation") or {}).get("deeplink"): r
            for r in rows
            if (r.get("validation") or {}).get("deeplink")
        }
        # Setting names (validation keys) that are specific enough to match verbatim.
        self.key_index: dict[str, list[dict]] = {}
        for r in self.phone_rows:
            key = _norm((r.get("validation") or {}).get("key") or "")
            if key and key not in GENERIC_KEYS and len(key) >= 4:
                self.key_index.setdefault(key, []).append(r)
        self._keys_sorted = sorted(self.key_index, key=len, reverse=True)
        texts = [self.text(r) for r in self.phone_rows]
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self.matrix = self.vectorizer.fit_transform(texts)

    @staticmethod
    def _usable(row: dict) -> bool:
        if row["deeplink"] == DUMMY_URI:
            return False
        blob = f"{row.get('description')} {row.get('message')}"
        if NON_PHONE_RE.search(blob):
            return False
        return row_kind(row) != "status"

    @staticmethod
    def text(row: dict) -> str:
        key = (row.get("validation") or {}).get("key") or ""
        return " ".join(
            [
                key,
                key,  # the setting name is the strongest signal
                row.get("message") or "",
                row.get("description") or "",
                row.get("qna_description") or "",
            ]
        )

    # ------------------------------------------------------------------ helpers
    def kind(self, row: dict | None) -> str:
        if not row:
            return "none"
        return self.kinds.get(row["id"], row_kind(row))

    def twin(self, row: dict, want: str) -> dict:
        """Return the on/off twin of a toggle row, if it exists."""
        v = (row.get("validation") or {}).get("deeplink")
        for r in self.twins.get(v, []):
            if self.kind(r) == want:
                return r
        return row

    def _pick_direction(self, rows: list[dict], direction: str) -> dict:
        prefs = {
            "on": ["on", "open", "update", "off"],
            "off": ["off", "open", "update", "on"],
            "increase": ["update", "open", "on", "off"],
            "decrease": ["update", "open", "off", "on"],
            "open": ["open", "on", "update", "off"],
        }[direction]
        return sorted(rows, key=lambda r: prefs.index(self.kind(r)) if self.kind(r) in prefs else 9)[0]

    # ------------------------------------------------------------------ resolve
    def exact_setting(self, text: str) -> tuple[str, list[dict]] | None:
        """Longest catalog setting name that appears verbatim in the step text."""
        blob = f" {_norm(text)} "
        for key in self._keys_sorted:
            if f" {key} " in blob:
                return key, self.key_index[key]
        return None

    def search(self, text: str, k: int = 5) -> list[tuple[dict, float]]:
        expanded = text
        low = text.lower()
        for phrase, repl in SETTING_SYNONYMS.items():
            if phrase in low:
                expanded += " " + repl
        q = self.vectorizer.transform([expanded])
        sims = (self.matrix @ q.T).toarray().ravel()
        order = np.argsort(-sims)[:k]
        return [(self.phone_rows[i], float(sims[i])) for i in order]

    def resolve(
        self, target_text: str, context: str, direction: str = "open", threshold: float = 0.42, exact: bool = True
    ) -> ScreenMatch | None:
        """Map a UI step run onto the most specific catalog screen.

        1. Verbatim setting name inside the step text (e.g. "Touch sensitivity").
        2. Otherwise TF-IDF over descriptive fields with an absolute similarity floor,
           so a vague step never gets a random parent menu.
        """
        cands = [
            {"id": r["id"], "message": r.get("message"), "score": round(s, 3)}
            for r, s in self.search(f"{target_text} {context}", k=5)
        ]
        mode = os.environ.get("ENGINE_MAPPER", "hybrid")  # hybrid | rules | tfidf (ablation switch)
        hit = self.exact_setting(target_text) if exact and mode != "tfidf" else None
        if hit:
            key, rows = hit
            chosen = self._pick_direction(rows, direction)
            return ScreenMatch(chosen, 0.95, f"setting name '{key}' named in step", cands)
        if mode == "rules":
            return None
        ranked = self.search(target_text, k=5)
        if not ranked:
            return None
        row, score = ranked[0]
        if score < threshold:
            return None
        if self.kind(row) in {"on", "off"} and direction in {"on", "off"}:
            row = self.twin(row, direction)
        return ScreenMatch(row, score, "descriptive similarity", cands)

    def by_validation_uri(self, uri: str) -> dict | None:
        return self.by_val.get(uri)
