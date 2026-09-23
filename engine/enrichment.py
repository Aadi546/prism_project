"""Query enrichment: canonical form, semantic cache key, 8–10 paraphrases."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CANON_MAP = [
    (r"\b(phone|mobile|handset|galaxy|samsung)\b", "device"),
    (r"\b(dies fast|drains? fast|eats battery|battery percentage drops)\b", "battery drain"),
    (r"\b(got slow|laggy|stutter|stuttering|jank)\b", "slow performance"),
    (r"\b(after (the )?update|after one ui|after software update)\b", "after software update"),
    (r"\b(swipe(s)?|swype|gesture navigation|nav(igation)? bar)\b", "swipe navigation"),
    (r"\b(up or down|up and down|vertical(ly)?|wrong axis|wrong direction|wrong way)\b", "wrong axis"),
    (r"\b(flicker|flickers|flashes|pwm)\b", "screen flicker"),
    (r"\b(blurry|smeared|soft photos|hunts for focus)\b", "camera blur"),
    (r"\b(hot|overheat|overheats|warm while charging)\b", "charging heat"),
    (r"\b(storage (is )?full|no space|cannot save photos)\b", "storage full"),
]


def normalize_query(text: str) -> str:
    q = text.strip().lower()
    q = re.sub(r"[“”\"']", "", q)
    q = re.sub(r"[^a-z0-9\s]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    for pattern, repl in CANON_MAP:
        q = re.sub(pattern, repl, q)
    return q


def semantic_cache_key(canonical: str) -> str:
    tokens = tuple(sorted(set(canonical.split())))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:10]
    return f"{digest}:" + " ".join(tokens)


TYPO_MAP = str.maketrans({"e": "e", "i": "i"})


def _typo(word: str) -> str:
    if len(word) < 5:
        return word
    return word[0] + word[2] + word[1] + word[3:] if len(word) > 4 else word


def generate_paraphrases(original: str, canonical: str) -> list[str]:
    """8–10 distinct paraphrases across registers."""
    topic = canonical or original
    seeds = [
        original.strip(),
        canonical,
        f"Please advise how to fix this: {canonical}.",
        f"ugh my {canonical} this is so annoying",
        f"{canonical} help",
        " ".join(_typo(w) for w in canonical.split()),
        f"Device issue: {canonical}",
        f"why does my device {canonical}",
        f"Need troubleshooting for {canonical}",
        f"{canonical} after installing an app",
        f"How do I resolve {canonical} on a Galaxy?",
        f"{topic} settings path",
    ]
    seen: list[str] = []
    lower_seen: set[str] = set()
    for s in seeds:
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            continue
        key = s.lower()
        if key in lower_seen:
            continue
        lower_seen.add(key)
        seen.append(s)
        if len(seen) == 10:
            break
    while len(seen) < 8:
        extra = f"{canonical} variant {len(seen)+1}"
        if extra.lower() not in lower_seen:
            seen.append(extra)
            lower_seen.add(extra.lower())
        else:
            break
    return seen[:10]


@dataclass(frozen=True)
class EnrichedQuery:
    original: str
    canonical: str
    cache_key: str
    paraphrases: list[str]
