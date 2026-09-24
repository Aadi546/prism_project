"""Programmatic hygiene: URLs, field phrasing, catalog membership, categories, ordering.

The PDF is explicit that prompt-only constraints are unreliable, so every field rule is
enforced here on the way out — for both the deterministic and the LLM path.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from engine.catalog import DUMMY_URI
from engine.lexicon import CRITICAL_RE, MANUAL_RE
from engine.schema import Action, ActionCategory, Deeplink, Goal, StepGroup

URL_RE = re.compile(
    r"(https?://\S*|www\.\S*|\b[\w-]+\.(com|org|net|io|co)(/\S*)?\b|\[[^\]]+\]\([^)]+\))",
    re.IGNORECASE,
)
MARKDOWN_FENCE_RE = re.compile(r"```")
GOAL_RE = re.compile(r"^Follow these steps to perform this [A-Z][A-Za-z0-9 ]* (Troubleshooting|Configuration)$")
SMALL_WORDS = {"and", "or", "the", "a", "an", "in", "on", "of", "to", "for", "with", "via", "at", "by"}
DANGLING = SMALL_WORDS | {"your", "my", "its", "their", "this", "that", "from", "into", "when", "if", "is", "are"}

# Short benefit phrases for well-known procedures (the "It will …" line).
DESCRIPTION_TEMPLATES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"factory (data )?reset", re.I), "It will restore original factory settings"),
    (re.compile(r"safe mode", re.I), "It will isolate problematic third-party apps"),
    (re.compile(r"force (a )?restart", re.I), "It will reboot an unresponsive device"),
    (re.compile(r"restart", re.I), "It will refresh the running system"),
    (re.compile(r"software update|update (device )?software", re.I), "It will install the latest software fixes"),
    (re.compile(r"clear (the )?(\w+ )?cache", re.I), "It will remove temporary app files"),
    (re.compile(r"clear (the )?(\w+'?s? )?data", re.I), "It will reset the app completely"),
    (re.compile(r"back ?up", re.I), "It will keep your data safe"),
    (re.compile(r"physical damage|liquid", re.I), "It will reveal physical or liquid damage"),
    (re.compile(r"charge", re.I), "It will restore enough battery power"),
    (re.compile(r"power on", re.I), "It will confirm the device starts"),
    (re.compile(r"charger", re.I), "It will rule out a faulty charger"),
    (re.compile(r"repair|service cent|walk-in|premium care", re.I), "It will get the screen professionally repaired"),
    (re.compile(r"contact|support|assistance", re.I), "It will connect you with expert help"),
    (re.compile(r"internet|wi-?fi|connection", re.I), "It will confirm a stable network connection"),
    (re.compile(r"account", re.I), "It will refresh your email account setup"),
    (re.compile(r"pc|computer", re.I), "It will isolate account versus phone problems"),
    (re.compile(r"mouse|keyboard|usb", re.I), "It will let you reach your data"),
    (re.compile(r"hdmi|monitor|tv", re.I), "It will show your screen externally"),
    (re.compile(r"smart switch|transfer", re.I), "It will move data between devices"),
    (re.compile(r"orientation|rotat", re.I), "It will fix screen orientation behavior"),
    (re.compile(r"touch sensitivity", re.I), "It will tune touch response sensitivity"),
    (re.compile(r"navigation|gesture", re.I), "It will stop gestures misreading touches"),
    (re.compile(r"protector|clean|moisture", re.I), "It will remove touch interference sources"),
    (re.compile(r"flicker|shutter|lighting", re.I), "It will reduce visible screen flicker"),
    (re.compile(r"multi ?window|split screen|pop-up", re.I), "It will manage multiple app windows"),
    (re.compile(r"edge panel", re.I), "It will customize quick access panels"),
    (re.compile(r"timeout", re.I), "It will keep the screen on longer"),
    (re.compile(r"aspect ratio", re.I), "It will enlarge the mirrored screen image"),
]


def strip_urls(text: str) -> str:
    cleaned = URL_RE.sub("", text or "")
    cleaned = MARKDOWN_FENCE_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" -:,")


def collect_urls(payload: str) -> list[str]:
    return [m.group(0) for m in URL_RE.finditer(payload)]


def title_case_action(name: str) -> str:
    words = re.sub(r"[^A-Za-z0-9+\- ]+", " ", name).split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i != 0 and lw in SMALL_WORDS:
            out.append(lw)
        elif (w.isupper() and len(w) > 1) or any(c.isupper() for c in w[1:]):
            out.append(w)  # keep acronyms such as PC, USB, HDMI
        elif "-" in w:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
        else:
            out.append(w[0].upper() + w[1:].lower() if len(w) > 1 else w.upper())
    return " ".join(out) or "Open Settings"


def sentence_case_title(text: str) -> str:
    words = re.sub(r"[^A-Za-z0-9 ]+", " ", text).split()
    words = [w for w in words if w.lower() not in {"the", "a", "an", "your", "my"}][:3]
    while words and words[-1].lower() in DANGLING:
        words.pop()
    if len(words) < 2:
        words = (words or ["Device"]) + ["settings"]
    first, *rest = words
    return " ".join([first[0].upper() + first[1:].lower(), *[w if w.isupper() else w.lower() for w in rest]])


PROPER_NOUNS = {"Samsung", "Galaxy", "Smart", "View", "Switch", "SmartThings", "Wi-Fi", "Bluetooth", "Edge", "Google", "PC"}
CUT_BEFORE = {"for", "to", "with", "when", "so", "and", "by", "in", "on", "that", "which", "while", "from", "if"}


def _trim_phrase(words: list[str], hi: int) -> list[str]:
    if len(words) > hi:
        for i in range(3, hi + 1):
            if i < len(words) and words[i].lower() in CUT_BEFORE:
                words = words[:i]
                break
    words = words[:hi]
    while len(words) > 3 and words[-1].lower().strip(",.") in DANGLING:
        words.pop()
    return words


def fit_description(text: str, hint: str = "") -> str:
    """Exactly 5-7 words, starting with "It will", no filler padding."""
    text = strip_urls(text).rstrip(".?!")
    words = text.split()
    if words[:2] and " ".join(words[:2]).lower() == "it will":
        words = words[2:]
    words = [w.strip(",;:()\"") for w in words if w.strip(",;:()\"")]
    rest = _trim_phrase(words, 5)
    if 3 <= len(rest) <= 5 and not re.search(r"[?]", " ".join(rest)):
        return "It will " + " ".join(rest)
    for pattern, template in DESCRIPTION_TEMPLATES:
        if pattern.search(f"{hint} {text}"):
            return template
    base = rest or ["open", "the", "needed", "screen"]
    if len(base) < 3:
        base = ["help", "you", *base][:5]
    while len(base) < 3:
        base.append("safely")
    return "It will " + " ".join(base)


def describe_action(action_name: str, qna: str | None = None) -> str:
    """Benefit sentence: catalog qna text for Settings screens, templates otherwise."""
    if qna:
        words = re.sub(r"[^A-Za-z0-9\- ]+", " ", qna).split()
        if words:
            words[0] = words[0].lower()
            rest = _trim_phrase(words, 5)
            if len(rest) >= 3:
                return "It will " + " ".join(rest)
    name, _, heading = action_name.partition("|")
    for source in (name, heading):
        for pattern, template in DESCRIPTION_TEMPLATES:
            if source and pattern.search(source):
                return template
    words = [
        w if (w.isupper() or any(c.isupper() for c in w[1:]) or w in PROPER_NOUNS) else w.lower()
        for w in name.strip().split()
    ]
    return fit_description("It will " + " ".join(words), name)


def description_ok(text: str) -> bool:
    words = text.split()
    return text.startswith("It will ") and 5 <= len(words) <= 7 and len(set(w.lower() for w in words)) == len(words)


def make_goal_line(topic: str, kind: str) -> str:
    topic = re.sub(r"[^A-Za-z0-9 ]+", " ", strip_urls(topic)).strip() or "Device"
    topic = " ".join(w[0].upper() + w[1:] for w in topic.split())
    kind = "Configuration" if kind.lower().startswith("config") else "Troubleshooting"
    return f"Follow these steps to perform this {topic} {kind}"


def catalog_uris(catalog: Iterable[dict]) -> set[str]:
    return {row["deeplink"] for row in catalog}


def deeplink_allowed(uri: str, allowed: set[str]) -> bool:
    if not uri or uri not in allowed:
        return False
    return uri == DUMMY_URI or uri.startswith("bixby://masked/")


def clean_step(step: str) -> str:
    cleaned = strip_urls(step).strip(" .")
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned


def sanitize_steps(steps: Sequence[str]) -> list[str]:
    out: list[str] = []
    for step in steps:
        cleaned = clean_step(step)
        if len(cleaned.split()) < 2 or cleaned in out:
            continue
        out.append(cleaned)
    return out


def sanitize_deeplink(raw: Deeplink | None, allowed: set[str], catalog_by_uri: dict) -> Deeplink | None:
    if raw is None or not deeplink_allowed(raw.deeplink, allowed):
        return None
    if raw.deeplink == DUMMY_URI:
        # The placeholder may carry a screen-specific description (see Appendix B).
        return Deeplink(
            deeplink=DUMMY_URI,
            description=strip_urls(raw.description) or "Open the relevant Settings screen",
            message=strip_urls(raw.message or ""),
        )
    src = catalog_by_uri[raw.deeplink]
    return Deeplink(
        deeplink=src["deeplink"],
        description=strip_urls(src.get("description") or ""),
        message=strip_urls(src.get("message") or ""),
        originalType=src.get("originalType"),
    )


def category_rank(cat: ActionCategory | None) -> int:
    return {ActionCategory.auto: 0, ActionCategory.manual: 1, ActionCategory.critical: 2}.get(
        cat or ActionCategory.manual, 1
    )


def infer_category(name: str, steps: Sequence[str], has_screen: bool) -> ActionCategory:
    """critical > manual > auto. Auto requires a reachable Settings screen."""
    head = name.lower()
    blob = " ".join([name, *steps])
    if CRITICAL_RE.search(head) or (CRITICAL_RE.search(blob) and not has_screen):
        return ActionCategory.critical
    if has_screen and not MANUAL_RE.search(head):
        return ActionCategory.auto
    return ActionCategory.manual


def _validation_uris(catalog_by_uri: dict) -> set[str]:
    key = id(catalog_by_uri)
    if key not in _VAL_CACHE:
        _VAL_CACHE[key] = {
            (r.get("validation") or {}).get("deeplink") for r in catalog_by_uri.values()
        } - {None}
    return _VAL_CACHE[key]


_VAL_CACHE: dict[int, set[str]] = {}


def sanitize_action(action: Action, allowed: set[str], catalog_by_uri: dict) -> Action | None:
    val_uris = _validation_uris(catalog_by_uri)
    groups = []
    for group in action.stepGroups:
        steps = sanitize_steps(group.steps)
        if not steps:
            continue
        link = sanitize_deeplink(group.actionableDeeplink, allowed, catalog_by_uri)
        val = group.validationDeeplink
        if val is not None and val.deeplink not in val_uris:
            val = None
        if action.category == ActionCategory.manual:
            link, val = None, None  # physical steps can never be one-tap
        groups.append(StepGroup(steps=steps, validationDeeplink=val, actionableDeeplink=link))
    if not groups:
        return None
    return Action(
        actionName=title_case_action(action.actionName),
        description=action.description if description_ok(action.description) else fit_description(action.description, action.actionName),
        stepGroups=groups,
        category=action.category or ActionCategory.manual,
    )


def sanitize_goal(goal: Goal, allowed: set[str], catalog_by_uri: dict) -> Goal | None:
    actions = [a for a in (sanitize_action(a, allowed, catalog_by_uri) for a in goal.actions) if a]
    if not actions:
        return None
    actions.sort(key=lambda a: category_rank(a.category))  # stable: keeps source order in a tier
    title = sentence_case_title(goal.title)
    goal_line = goal.goal if GOAL_RE.match(goal.goal) else make_goal_line(title, "Troubleshooting")
    score = round(min(1.0, max(0.0, float(goal.score))), 2)
    return Goal(goal=goal_line, title=title, actions=actions, score=score)


def rule_violations(goal: Goal) -> list[str]:
    """Human-readable list of contract breaches (empty == compliant)."""
    issues = []
    if not GOAL_RE.match(goal.goal):
        issues.append("goal syntax")
    if not 2 <= len(goal.title.split()) <= 3:
        issues.append("title length")
    if goal.title[:1] != goal.title[:1].upper():
        issues.append("title case")
    ranks = [category_rank(a.category) for a in goal.actions]
    if ranks != sorted(ranks):
        issues.append("action ordering")
    for a in goal.actions:
        if a.actionName != title_case_action(a.actionName):
            issues.append(f"actionName case: {a.actionName}")
        if not description_ok(a.description):
            issues.append(f"description: {a.description}")
        for g in a.stepGroups:
            if not g.steps:
                issues.append("empty stepGroup")
            if a.category == ActionCategory.manual and g.actionableDeeplink is not None:
                issues.append("manual action with deeplink")
    if collect_urls(goal.model_dump_json()):
        issues.append("url leak")
    return issues
