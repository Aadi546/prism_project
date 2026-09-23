"""Turn SIIS reference text into a Goal. Steps must come from the reference."""

from __future__ import annotations

import re
from typing import Any, Optional

from engine.deeplink import DeeplinkMapper
from engine.schema import Action, ActionCategory, Goal, StepGroup
from engine.validate import (
    fit_description,
    infer_category,
    make_goal_line,
    sanitize_goal,
    sanitize_steps,
    sentence_case_title,
    strip_urls,
    title_case_action,
)

HEADING_RE = re.compile(
    r"^(#{1,3})\s+(?:(?:step\s+)?\d+[.:)]\s+)?(.+)$",
    re.IGNORECASE,
)
INSTRUCT_RE = re.compile(
    r"\b(tap|go to|navigate|open|swipe|press|hold|connect|remove|restart|turn|enable|disable|select|check|inspect|contact|visit|schedule|clear|wipe|plug|unplug|force)\b",
    re.IGNORECASE,
)


def flatten_siis(raw: Any, article: Optional[dict] = None) -> str:
    if isinstance(raw, dict):
        return f"{raw.get('title') or ''}\n{raw.get('content') or ''}".strip()
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if not article:
        return ""
    payload = article.get("siis_response")
    if isinstance(payload, dict):
        return f"{payload.get('title') or ''}\n{payload.get('content') or ''}".strip()
    return (article.get("body") or article.get("content") or "").strip()


def _sentences(text: str) -> list[str]:
    text = strip_urls(text.replace("\n", " "))
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:
        p = p.strip(" -*")
        if len(p.split()) < 4:
            continue
        out.append(p)
    return out


def parse_sections(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    title = "Overview"
    buf: list[str] = []
    for line in lines:
        stripped = line.strip()
        m = HEADING_RE.match(stripped)
        if m:
            if buf:
                sections.append((title, buf))
            title = m.group(2).strip()
            buf = []
        else:
            buf.append(stripped)
    if buf:
        sections.append((title, buf))
    return [(t, " ".join(b).strip()) for t, b in sections if " ".join(b).strip()]


def _steps_from_section(title: str, body: str) -> list[str]:
    numbered = re.findall(r"(?:^|\s)(?:\d+[.)]|[-*])\s+([A-Z][^.]{12,180})", body)
    if numbered:
        return numbered[:5]
    sents = [s for s in _sentences(body) if INSTRUCT_RE.search(s)]
    if not sents:
        sents = _sentences(body)[:3]
    return sents[:4]


def _actions_from_plan(plan: dict, mapper: DeeplinkMapper) -> list[Action]:
    actions: list[Action] = []
    for raw in plan.get("actions") or []:
        groups = []
        for g in raw.get("stepGroups") or []:
            screen = g.get("screen_key")
            row = mapper.resolve_screen_key(screen)
            if row is None:
                blob = " ".join(g.get("steps") or []) + " " + raw.get("actionName", "")
                row = mapper.resolve_text(blob)
            groups.append(
                StepGroup(
                    steps=sanitize_steps(g.get("steps") or []),
                    actionableDeeplink=mapper.to_model(row),
                    validationDeeplink=mapper.to_validation(row),
                )
            )
        groups = [g for g in groups if g.steps]
        if not groups:
            continue
        name = title_case_action(raw.get("actionName") or "Open Settings")
        steps_flat = [s for g in groups for s in g.steps]
        cat = infer_category(name, steps_flat, raw.get("category"))
        actions.append(
            Action(
                actionName=name,
                description=fit_description(raw.get("description") or "It will open the settings screen"),
                stepGroups=groups,
                category=cat,
            )
        )
    return actions


def _settings_intent(title: str, steps: list[str]) -> bool:
    blob = " ".join([title, *steps]).lower()
    return any(
        w in blob
        for w in (
            "settings",
            "tap",
            "toggle",
            "enable",
            "disable",
            "wifi",
            "wi-fi",
            "backup",
            "display",
            "apps",
            "edge panel",
            "navigation",
        )
    )


def _actions_from_siis(text: str, mapper: DeeplinkMapper) -> list[Action]:
    sections = parse_sections(text)
    actions: list[Action] = []
    for title, body in sections:
        if title.lower() in {"overview"} and not INSTRUCT_RE.search(body):
            continue
        steps = sanitize_steps(_steps_from_section(title, body))
        if not steps:
            continue
        cat = infer_category(title, steps, None)
        allow_dummy = cat == ActionCategory.auto and _settings_intent(title, steps)
        row = mapper.resolve_text(title + " " + " ".join(steps), allow_dummy=allow_dummy)
        if cat != ActionCategory.auto:
            # service / critical steps should not force a random settings match
            if row and cat == ActionCategory.manual:
                row = None
        actions.append(
            Action(
                actionName=title_case_action(title),
                description=fit_description(f"It will {title.lower()}"),
                stepGroups=[
                    StepGroup(
                        steps=steps,
                        actionableDeeplink=mapper.to_model(row) if cat == ActionCategory.auto else None,
                        validationDeeplink=mapper.to_validation(row) if cat == ActionCategory.auto else None,
                    )
                ],
                category=cat,
            )
        )
        if len(actions) >= 6:
            break
    return actions


def extract_goal(
    query: str,
    article: Optional[dict],
    raw_siis: Any,
    mapper: DeeplinkMapper,
    score: float,
) -> Optional[Goal]:
    plan = (article or {}).get("plan") if article else None
    if plan and plan.get("actions"):
        actions = _actions_from_plan(plan, mapper)
        topic = plan.get("topic") or "Device"
        kind = plan.get("kind") or "Troubleshooting"
        title = sentence_case_title(plan.get("title") or topic)
        goal = Goal(
            goal=make_goal_line(topic, kind),
            title=title,
            actions=actions,
            score=score,
        )
        return sanitize_goal(goal, mapper.allowed, mapper.by_uri)

    blob = flatten_siis(raw_siis, article)
    if not blob:
        return None
    actions = _actions_from_siis(blob, mapper)
    if not actions:
        return None
    si_title = ""
    if article:
        payload = article.get("siis_response")
        if isinstance(payload, dict):
            si_title = payload.get("title") or ""
    title_src = si_title or query
    title = sentence_case_title(title_src)
    topic = title_src.split(" on ")[0].strip() if " on " in title_src else title
    topic = re.sub(r"[^A-Za-z0-9 ]+", " ", topic).strip() or "Device"
    topic = " ".join(topic.split()[:4])
    goal = Goal(
        goal=make_goal_line(topic, "Troubleshooting"),
        title=title,
        actions=actions,
        score=min(1.0, max(0.35, score if score else 0.55)),
    )
    return sanitize_goal(goal, mapper.allowed, mapper.by_uri)
