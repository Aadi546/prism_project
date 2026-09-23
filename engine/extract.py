"""Turn SIIS reference text (structured article or raw paste) into a Goal."""

from __future__ import annotations

import re
from typing import Optional

from engine.deeplink import DeeplinkMapper
from engine.schema import Action, ActionCategory, Goal, StepGroup
from engine.validate import (
    fit_description,
    infer_category,
    make_goal_line,
    sanitize_goal,
    sanitize_steps,
    sentence_case_title,
    title_case_action,
)

SCREEN_PATH_RE = re.compile(
    r"(Settings\s*>\s*[A-Za-z0-9 /&>]+|Tap on [A-Z][A-Za-z ]+)",
)


def _actions_from_plan(plan: dict, mapper: DeeplinkMapper) -> list[Action]:
    actions: list[Action] = []
    for raw in plan.get("actions") or []:
        groups = []
        for g in raw.get("stepGroups") or []:
            screen = g.get("screen_key")
            row = mapper.resolve_screen_key(screen)
            if row is None and screen:
                row = mapper.resolve_text(screen.replace("_", " "))
            if row is None:
                blob = " ".join(g.get("steps") or []) + " " + raw.get("actionName", "")
                row = mapper.resolve_text(blob)
            groups.append(
                StepGroup(
                    steps=sanitize_steps(g.get("steps") or []),
                    actionableDeeplink=mapper.to_model(row),
                )
            )
        if not groups:
            continue
        name = title_case_action(raw.get("actionName") or "Open Settings")
        steps_flat = [s for g in groups for s in g.steps]
        cat = infer_category(name, steps_flat, raw.get("category"))
        # Critical factory reset should stay last and may keep reset screen
        actions.append(
            Action(
                actionName=name,
                description=fit_description(raw.get("description") or "It will open the settings screen"),
                stepGroups=groups,
                category=cat,
            )
        )
    return actions


def _actions_from_raw_text(text: str, mapper: DeeplinkMapper) -> list[Action]:
    numbered = []
    for ln in text.splitlines():
        m = re.match(r"\s*\d+[.)]\s+(.*)", ln)
        if m:
            numbered.append(m.group(1).strip())
    steps = [s for s in numbered if s and not s.lower().startswith("do not")]
    steps = [s for s in steps if len(s.split()) >= 3][:12]
    if not steps:
        return []
    # Group by detected screen phrases
    row = mapper.resolve_text(text)
    cat = infer_category("Follow listed settings", steps, None)
    return [
        Action(
            actionName=title_case_action((row or {}).get("description") or "Open Matching Settings"),
            description=fit_description("It will open the matching settings screen"),
            stepGroups=[
                StepGroup(
                    steps=sanitize_steps(steps[:6]),
                    actionableDeeplink=mapper.to_model(row),
                )
            ],
            category=cat if cat != ActionCategory.critical else ActionCategory.auto,
        )
    ]


def extract_goal(
    query: str,
    article: Optional[dict],
    raw_siis: Optional[str],
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

    blob = raw_siis or (article or {}).get("body")
    if not blob or not blob.strip():
        return None
    actions = _actions_from_raw_text(blob, mapper)
    if not actions:
        return None
    title = sentence_case_title(query)
    goal = Goal(
        goal=make_goal_line(title, "Troubleshooting"),
        title=title,
        actions=actions,
        score=max(0.35, score * 0.7),
    )
    return sanitize_goal(goal, mapper.allowed, mapper.by_uri)
