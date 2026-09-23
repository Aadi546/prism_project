"""Programmatic hygiene: URLs, field phrasing, catalog membership, ordering."""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from engine.schema import Action, ActionCategory, Deeplink, Goal, StepGroup

URL_RE = re.compile(
    r"(https?://|www\.|samsung\.com/support|\[[^\]]+\]\([^)]+\))",
    re.IGNORECASE,
)
MARKDOWN_FENCE_RE = re.compile(r"```")
DUMMY_URI = "bixby://dummy_positive"
GOAL_RE = re.compile(
    r"^Follow these steps to perform this .+ (Troubleshooting|Configuration)$"
)


def strip_urls(text: str) -> str:
    cleaned = URL_RE.sub("", text)
    cleaned = MARKDOWN_FENCE_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" -:,.")


def title_case_action(name: str) -> str:
    small = {"and", "or", "the", "a", "an", "in", "on", "of", "to", "for"}
    words = re.sub(r"[^A-Za-z0-9 ]+", " ", name).split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i != 0 and lw in small:
            out.append(lw)
        else:
            out.append(lw.capitalize())
    return " ".join(out) or "Open Settings"


def sentence_case_title(text: str) -> str:
    words = re.sub(r"[^A-Za-z0-9 ]+", " ", text).split()
    if not words:
        return "Device settings"
    words = words[:3]
    if len(words) < 2:
        words.append("settings")
    first, *rest = words
    return " ".join([first.capitalize(), *[w.lower() for w in rest]])


def fit_word_range(text: str, lo: int, hi: int) -> str:
    words = [w for w in text.split() if w]
    if len(words) < lo:
        pad = ["carefully", "now", "here", "please", "today"]
        i = 0
        while len(words) < lo:
            words.append(pad[i % len(pad)])
            i += 1
    return " ".join(words[:hi])


def fit_description(text: str) -> str:
    text = strip_urls(text)
    lowered = text.lower()
    if lowered.startswith("it will"):
        rest = text.split()[2:]
    else:
        rest = text.split()
    rest = [w for w in rest if w]
    if not rest:
        rest = ["open", "the", "needed", "settings", "screen"]
    # description is exactly 5-7 words total including "It will"
    # "It" "will" + 3 to 5 more = 5 to 7
    extra = rest[:5]
    while len(extra) < 3:
        extra.append("settings")
    return "It will " + " ".join(extra)


def make_goal_line(topic: str, kind: str) -> str:
    topic = strip_urls(topic) or "Device"
    kind = "Configuration" if kind.lower().startswith("config") else "Troubleshooting"
    return f"Follow these steps to perform this {topic} {kind}"


def catalog_uris(catalog: Iterable[dict]) -> set[str]:
    return {row["deeplink"] for row in catalog}


def deeplink_allowed(uri: str, allowed: set[str]) -> bool:
    if not uri:
        return False
    if uri == DUMMY_URI:
        return False
    if not uri.startswith("bixby://masked/act/"):
        return False
    return uri in allowed


def sanitize_steps(steps: Sequence[str]) -> list[str]:
    out = []
    for step in steps:
        cleaned = strip_urls(step)
        if not cleaned:
            continue
        if cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        if not cleaned.endswith("."):
            cleaned += "."
        out.append(cleaned)
    return out or ["Open Settings and review the related screen."]


def sanitize_deeplink(raw: dict | None, allowed: set[str], catalog_by_uri: dict) -> Deeplink | None:
    if not raw:
        return None
    uri = raw.get("deeplink", "")
    if not deeplink_allowed(uri, allowed):
        return None
    src = catalog_by_uri[uri]
    return Deeplink(
        deeplink=src["deeplink"],
        description=strip_urls(src.get("description") or ""),
        message=strip_urls(src.get("message") or "") or "",
        classes=src.get("classes"),
        originalType=src.get("originalType"),
    )


def category_rank(cat: ActionCategory | None) -> int:
    order = {
        ActionCategory.auto: 0,
        ActionCategory.manual: 1,
        ActionCategory.critical: 2,
    }
    return order.get(cat or ActionCategory.manual, 1)


CRITICAL_HINTS = (
    "factory reset",
    "safe mode",
    "firmware",
    "restart",
    "reboot",
    "wipe",
)


def infer_category(name: str, steps: Sequence[str], given: str | None) -> ActionCategory:
    blob = " ".join([name, *steps]).lower()
    if given in {c.value for c in ActionCategory}:
        # still force critical last-class if the action is destructive
        if any(h in blob for h in ("factory reset", "wipe all data")):
            return ActionCategory.critical
        return ActionCategory(given)
    if any(h in blob for h in CRITICAL_HINTS):
        return ActionCategory.critical
    if any(h in blob for h in ("clean", "wipe lens", "cloth", "service", "port")):
        return ActionCategory.manual
    return ActionCategory.auto


def sanitize_action(
    action: Action,
    allowed: set[str],
    catalog_by_uri: dict,
) -> Action:
    groups = []
    for group in action.stepGroups:
        deeplink = sanitize_deeplink(
            group.actionableDeeplink.model_dump() if group.actionableDeeplink else None,
            allowed,
            catalog_by_uri,
        )
        groups.append(
            StepGroup(
                steps=sanitize_steps(group.steps),
                validationDeeplink=group.validationDeeplink,
                actionableDeeplink=deeplink,
            )
        )
    cat = action.category or ActionCategory.manual
    # Auto actions should carry a catalog deeplink when one exists
    if cat == ActionCategory.auto and groups and groups[0].actionableDeeplink is None:
        # keep auto only if we truly have no screen; otherwise still auto without URI
        pass
    if cat == ActionCategory.critical:
        # critical may keep a deeplink for safe-mode info / restart screens
        pass
    return Action(
        actionName=title_case_action(action.actionName),
        description=fit_description(action.description),
        stepGroups=groups or [StepGroup(steps=sanitize_steps([]))],
        category=cat,
    )


def sanitize_goal(goal: Goal, allowed: set[str], catalog_by_uri: dict) -> Goal:
    actions = [sanitize_action(a, allowed, catalog_by_uri) for a in goal.actions]
    actions.sort(key=lambda a: category_rank(a.category))
    title = sentence_case_title(goal.title)
    goal_line = goal.goal
    if not GOAL_RE.match(goal_line):
        goal_line = make_goal_line(title.rsplit(" ", 1)[0] if title else "Device", "Troubleshooting")
        if not GOAL_RE.match(goal_line):
            goal_line = make_goal_line("Device", "Troubleshooting")
    score = min(1.0, max(0.0, float(goal.score)))
    return Goal(goal=goal_line, title=title, actions=actions, score=score)


def collect_urls(payload: str) -> list[str]:
    return URL_RE.findall(payload)
