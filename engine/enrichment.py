"""Query enrichment: canonical form, symptom signature, device, 8–10 paraphrases.

The canonical form is what the cache is keyed on, so two customers describing the same
fault in different words land on the same entry (PDF §7.1 "exact-string cache keying").
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from engine.lexicon import DEVICE_RE, STOPWORDS, SYMPTOM_BY_KEY, SYMPTOMS

LEADING_NUM_RE = re.compile(r"^\s*\d+\s*[.)]\s*")
QUOTES_RE = re.compile(r"[“”\"]")

CANON_MAP = [
    (r"\b(won'?t|will not|doesn'?t|does not|can'?t|cannot|isn'?t|is not)\b", "not"),
    (r"\b(completely|totally|suddenly|constantly|extremely|really|just|whole)\b", ""),
    (r"\b(phone|mobile|handset|smartphone|tablet)\b", "device"),
    (r"\b(display|screen|panel)\b", "screen"),
    (r"\b(flashes|flashing|flicker(s|ing)?|blinks?)\b", "flicker"),
    (r"\b(black|blank|dark|no image|no display)\b", "blank"),
    (r"\b(laggy|delayed?|delays?|slowly|slow to respond|lag(s|ging)?)\b", "lag"),
    (r"\b(plug(ged)? in|charging|connected to (the )?charger|charger is connected)\b", "charger"),
    (r"\b(shattered|smashed|broken glass)\b", "cracked"),
    (r"\b(no (picture|image)|nothing (at all|shows|displays))\b", "blank"),
    (r"\b(cracked|crack|shattered|smashed)\b", "cracked"),
    (r"\b(unresponsive|not respond(ing)?|doesn'?t respond)\b", "unresponsive"),
]


@dataclass
class EnrichedQuery:
    original: str
    cleaned: str
    canonical: str
    cache_key: str
    symptoms: list[str]
    device: str | None
    paraphrases: list[str]
    intents: list[str] = field(default_factory=list)


def clean_query(text: str) -> str:
    q = LEADING_NUM_RE.sub("", text or "")
    q = QUOTES_RE.sub("", q)
    return re.sub(r"\s+", " ", q).strip()


def detect_device(text: str) -> str | None:
    m = DEVICE_RE.search(text or "")
    if not m:
        return None
    dev = re.sub(r"\s+", " ", m.group(0)).strip()
    return dev if dev.lower().startswith(("galaxy", "tablet")) else f"Galaxy {dev}"


def detect_symptoms(text: str) -> list[str]:
    return [s.key for s in SYMPTOMS if s.pattern.search(text or "")]


GENERIC_CONTENT = {
    "screen",
    "device",
    "phone",
    "tablet",
    "display",
    "nexa",
    "techcorp",
    "galaxy",
    "samsung",
}


def normalize_query(text: str) -> str:
    q = clean_query(text).lower()
    q = DEVICE_RE.sub(" ", q)
    q = re.sub(r"[^a-z0-9'\s]+", " ", q)
    for pattern, repl in CANON_MAP:
        q = re.sub(pattern, repl, q)
    toks = [t for t in q.replace("'", "").split() if t not in STOPWORDS and len(t) > 1]
    seen: list[str] = []
    for t in toks:
        if t not in seen:
            seen.append(t)
    return " ".join(seen)


def content_tokens(text: str) -> set[str]:
    """Distinctive words after normalization — used to decide two complaints are about the same fault."""
    return {w for w in normalize_query(text).split() if len(w) > 2} - GENERIC_CONTENT


def semantic_cache_key(canonical: str, symptoms: list[str]) -> str:
    sig = "+".join(sorted(symptoms)) or "none"
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:10]
    return f"{sig}:{digest}"


def split_intents(text: str) -> list[str]:
    """Split compound complaints ("1. … 2. … 3. …") into separate intents."""
    q = QUOTES_RE.sub("", text or "")
    parts = re.split(r"(?:^|\s)\d+\s*[.)]\s+", q)
    parts = [p.strip(" .;") for p in parts if p and len(p.split()) >= 4]
    return parts if len(parts) >= 2 else [clean_query(text)]


def _typo(word: str) -> str:
    """One controlled transposition, e.g. 'screen' → 'sceren'."""
    if len(word) < 5:
        return word
    i = len(word) // 2
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]


def _short(text: str, n: int = 14) -> str:
    words = text.split()
    clause = re.split(r"[;,]| so | and then ", text)[0].strip()
    if 5 <= len(clause.split()) <= n:
        return clause
    return " ".join(words[:n])


def generate_paraphrases(original: str, symptoms: list[str], device: str | None) -> list[str]:
    """8–10 distinct paraphrases across registers (formal, casual, keyword, frustrated, typo)."""
    q = clean_query(original)
    dev = device or "Galaxy phone"
    dev_short = (device or "phone").replace("Galaxy ", "")
    sym = SYMPTOM_BY_KEY.get(symptoms[0]) if symptoms else None
    phrase = sym.phrase if sym else _short(q).rstrip(".").lower()
    phrase = re.sub(r"^(my|the)\s+", "the ", phrase)
    core = re.sub(r"^the\s+", "", phrase)
    kw = " ".join(dict.fromkeys(w for w in normalize_query(q).split()[:6]))
    extra = SYMPTOM_BY_KEY.get(symptoms[1]).phrase if len(symptoms) > 1 else ""
    typo_src = f"my {dev_short} {core}"
    typo_words = typo_src.split()
    longest = max(range(len(typo_words)), key=lambda i: len(typo_words[i]))
    typo_words[longest] = _typo(typo_words[longest])
    seeds = [
        q,
        f"My {dev} has an issue where {phrase}. How can I resolve this?",
        f"hey, {phrase} on my {dev_short} — any fix?",
        f"{dev_short} {kw}".strip(),
        f"This is so annoying, {phrase} again on my {dev_short}!",
        " ".join(typo_words),
        f"Why does my {dev_short} keep acting up? {phrase[0].upper() + phrase[1:]}.",
        f"Support request: {core} on {dev}. Please send troubleshooting steps.",
        f"{core} fix {dev_short}",
        f"What should I do when {phrase}{' and ' + extra if extra else ''}?",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for s in seeds:
        s = re.sub(r"\s+", " ", s).strip()
        k = s.lower()
        if s and k not in seen:
            seen.add(k)
            out.append(s)
    return out[:10]


def enrich(text: str) -> EnrichedQuery:
    cleaned = clean_query(text)
    symptoms = detect_symptoms(cleaned)
    device = detect_device(cleaned)
    canonical = normalize_query(cleaned)
    return EnrichedQuery(
        original=text,
        cleaned=cleaned,
        canonical=canonical,
        cache_key=semantic_cache_key(canonical, symptoms),
        symptoms=symptoms,
        device=device,
        paraphrases=generate_paraphrases(cleaned, symptoms, device),
        intents=split_intents(text),
    )
