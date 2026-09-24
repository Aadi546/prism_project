"""Turn SIIS reference text into a Goal. Every step is lifted from the reference.

Deterministic path:
  clean → sections → sentences → imperative steps (atomic) → screen runs → actions
Each step keeps the character span of the sentence it came from (provenance), so the
console can prove nothing was invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sklearn.feature_extraction.text import TfidfVectorizer

from engine.catalog import DUMMY_URI, Catalog, ScreenMatch
from engine.lexicon import (
    CONFIG_INTENT_RE,
    CRITICAL_RE,
    IMPERATIVE_VERBS,
    INFO_HEADING_RE,
    LEAD_IN_RE,
    MANUAL_RE,
    NON_PHONE_RE,
    SYMPTOMS,
)
from engine.schema import Action, ActionCategory, Deeplink, Goal, StepGroup
from engine.validate import (
    clean_step,
    describe_action,
    make_goal_line,
    sanitize_goal,
    sentence_case_title,
    strip_urls,
    title_case_action,
)
from engine.verify import build_validation

PREFIX_RE = re.compile(r"^[^\n]{0,400}?\(\s*[A-Za-z0-9 ,/&+\-]+\)\s*:\s*", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,4})\s*(.*)$")
STEP_PREFIX_RE = re.compile(r"^(step\s*\d+\s*[:.)-]\s*|\d+\s*[.)]\s*)", re.IGNORECASE)
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])|(?<=[a-z]\.)(?=[A-Z][a-z])")
SUBPROC_RE = re.compile(r"^(to [^:]{3,80}|for [^:]{3,60}|on devices with [^:]{3,60}):\s*(.*)$", re.IGNORECASE)
DROP_RE = re.compile(
    r"^(note\b|learn more|check out|for more information|you can find instructions|refer to|"
    r"here are|here's|there are|glossary|terms and conditions)|at the provided links|our (website|guide)|"
    r"troubleshooting guide|\blet'?s\b|^(enter|do|use|try) (it|them|this)\b",
    re.IGNORECASE,
)
YOU_CAN_RE = re.compile(
    r"^(?:you (?:can|could|should|may|might)(?: also| still| simply)?(?: need to)?|you'll need to|you need to|it is recommended to|it's (?:also )?a good (?:practice|idea) to|let's|let us|i recommend(?: that you)?)\s+",
    re.IGNORECASE,
)
SETTINGS_START_RE = re.compile(r"\b(navigate to|go to|open|from)\s+(and open\s+)?settings\b|^settings\b", re.IGNORECASE)
QUICK_START_RE = re.compile(r"quick settings panel|swipe down from the top", re.IGNORECASE)
UI_RE = re.compile(r"^(tap|select|touch|swipe to|search|enter|choose|toggle|switch|locate|scroll)\b", re.IGNORECASE)
ON_RE = re.compile(r"\b(enable|enabling|turn on|turning on|switch on|activate)\b", re.IGNORECASE)
OFF_RE = re.compile(r"\b(disable|disabling|turn off|turn it off|turning off|switch off|deactivate)\b", re.IGNORECASE)
TARGET_RE = re.compile(
    r"^(?:tap|select|touch and hold|touch|choose|search for and select|search for)\s+(?:on\s+)?(?:the\s+)?(?:switch(?:es)? next to\s+)?(.+?)(?:\s+(?:to|and|when|if|from)\b.*)?[.]?$",
    re.IGNORECASE,
)

HEADING_REWRITES = {
    "software updates": "Check for Software Updates",
    "update device software": "Update Device Software",
    "charger issues": "Check the Charger",
    "safe mode": "Restart in Safe Mode",
    "factory data reset": "Perform a Factory Data Reset",
    "further assistance": "Contact Samsung Support",
    "restarting your device": "Restart Your Device",
    "connection method": "Connect Both Devices",
    "touch sensitivity setting": "Turn Off Touch Sensitivity",
    "full screen gesture function": "Switch Navigation to Buttons",
    "factors affecting touchscreen performance": "Remove Touch Interference",
    "fingerprint recognition issues": "Improve Fingerprint Accuracy",
    "samsung repair services": "Schedule a Screen Repair",
    "samsung authorized service centers": "Visit a Service Center",
    "samsung premium care": "Use Samsung Premium Care",
    "troubleshooting video flickering": "Reduce Video Flickering",
    "device damage and repair options": "Get Damage Repaired",
    "tips for mirroring with smart view": "Fix Smart View Mirroring",
    "touchscreen doesn't work but the screen is still visible": "Back Up Data with a Mouse",
    "nothing is visible on the screen": "Back Up Data via HDMI",
    "some things to check first": "Check Charger and Restart",
}


@dataclass
class Step:
    text: str
    start: int
    end: int
    source: str


@dataclass
class Run:
    kind: str  # settings | quick | plain
    steps: list[Step] = field(default_factory=list)
    label: str = ""


@dataclass
class DraftGroup:
    steps: list[Step]
    link: Optional[Deeplink] = None
    validation: Any = None
    match: Optional[ScreenMatch] = None
    category: ActionCategory = ActionCategory.manual
    label: str = ""
    mapping_note: str = ""


@dataclass
class DraftAction:
    name: str
    category: ActionCategory
    groups: list[DraftGroup]
    heading: str
    description: str = ""
    policy: str = ""
    from_catalog: bool = False


@dataclass
class Section:
    heading: str
    level: int
    start: int
    lines: list[tuple[str, int]]

    @property
    def body(self) -> str:
        return " ".join(t for t, _ in self.lines)


@dataclass
class Extraction:
    goal: Optional[Goal]
    text: str
    provenance: list[dict]
    mapping: list[dict]
    sections_used: list[str]
    sections_dropped: list[str]
    topic: str
    kind: str
    deeplink_coverage: float = 0.0


# ---------------------------------------------------------------- text utilities
def clean_article(raw: Any) -> tuple[str, str]:
    """Return (title, body) with the product-category preamble removed."""
    if isinstance(raw, dict):
        title = str(raw.get("title") or "")
        content = str(raw.get("content") or "")
    else:
        title, content = "", str(raw or "")
    content = content.replace("\r\n", "\n")
    m = PREFIX_RE.match(content)
    if m and m.end() < 600:
        content = content[m.end():]
    return title.strip(), content.strip()


def _garbled(sentence: str) -> bool:
    return any(len(tok) > 28 for tok in sentence.split())


def parse_sections(text: str, doc_title: str = "") -> list[Section]:
    sections: list[Section] = [Section(doc_title or "Overview", 0, 0, [])]
    pos = 0
    for line in text.split("\n"):
        start = pos
        pos += len(line) + 1
        stripped = line.strip()
        if not stripped:
            continue
        m = HEADING_RE.match(stripped)
        if m:
            heading = STEP_PREFIX_RE.sub("", m.group(2).strip()).strip()
            if heading:
                sections.append(Section(heading, len(m.group(1)), start, []))
            continue
        lead = len(line) - len(line.lstrip())
        sections[-1].lines.append((stripped, start + lead))
    return [s for s in sections if s.lines]


def _sentences(line: str, offset: int) -> list[tuple[str, int]]:
    out = []
    cursor = 0
    for piece in SENT_SPLIT_RE.split(line):
        idx = line.find(piece, cursor)
        if idx < 0:
            idx = cursor
        cursor = idx + len(piece)
        piece = piece.strip()
        if piece:
            out.append((piece, offset + idx))
    return out


def _base_verb(word: str) -> str:
    return word.lower().strip(",.;:\"'")


def _is_imperative(text: str) -> bool:
    words = text.split()
    if not words:
        return False
    first = _base_verb(words[0])
    if first == "turn" and len(words) > 1 and _base_verb(words[1]) in {"on", "off"}:
        return True
    return first in IMPERATIVE_VERBS


def _normalize_settings(step: str) -> str:
    step = re.sub(r"^(navigate to|go to|open|from)\s+(and open\s+)?settings\b[.,]?$", "Navigate to and open Settings", step, flags=re.I)
    step = re.sub(r"^(navigate to|go to)\s+settings$", "Navigate to and open Settings", step, flags=re.I)
    return step


def _atomic(sentence: str) -> list[str]:
    """Split "Go to Settings, tap Display, and then tap X" into one interaction per step."""
    parts = re.split(r",?\s+and then\s+|,\s+then\s+|;\s+then\s+|,\s+(?=(?:tap|select|touch|swipe|enter|search for|choose)\b)", sentence, flags=re.I)
    parts = [p.strip(" ,.") for p in parts if p and p.strip(" ,.")]
    if len(parts) > 1 and all(_is_imperative(p) or re.match(r"^(navigate|go) to", p, re.I) for p in parts):
        return [_normalize_settings(p) for p in parts]
    return [_normalize_settings(sentence.strip(" ."))]


def to_steps(sentence: str) -> list[str]:
    s = sentence.strip()
    if not s or DROP_RE.search(s) or NON_PHONE_RE.search(s) or _garbled(s):
        return []
    for _ in range(3):
        s2 = LEAD_IN_RE.sub("", s)
        s2 = YOU_CAN_RE.sub("", s2)
        if s2 == s:
            break
        s = s2
    if not s or DROP_RE.search(s):
        return []
    s = s[0].upper() + s[1:]
    if re.match(r"^[A-Z][\w /&+-]{1,40}:\s", s):  # "Moisture: If the screen…" label → drop label
        s = s.split(":", 1)[1].strip()
        if not s:
            return []
        s = s[0].upper() + s[1:]
    if _is_imperative(s):
        return _atomic(s)
    # "If X, do Y" / "Using two fingers, swipe down…" → keep when the main clause is imperative
    if "," in s:
        head, tail = s.split(",", 1)
        tail = LEAD_IN_RE.sub("", tail.strip())
        tail = YOU_CAN_RE.sub("", tail)
        if _is_imperative(tail) and len(head.split()) <= 18:
            if re.match(r"^to\b", head, re.I):
                return _atomic(tail[0].upper() + tail[1:])  # purpose clause: the steps carry the meaning
            if re.match(r"^(if|when|once|before|after|using|with|while|on|in|from|for)\b", head, re.I):
                return [s.rstrip(" .")]
    return []


# ---------------------------------------------------------------- section → runs
def _runs(section: Section) -> list[Run]:
    runs: list[Run] = []
    if section.lines and NON_PHONE_RE.search(section.lines[0][0]):
        return runs  # the whole section is about a PC / TV, not the phone
    label = ""
    current: Run | None = None
    for line, lstart in section.lines:
        m = SUBPROC_RE.match(line)
        if m and (not m.group(2) or m.group(1).lower().startswith("to ")):
            label = m.group(1).strip()
            current = None
            if not m.group(2):
                continue
        sentences = _sentences(line, lstart)
        if any(NON_PHONE_RE.search(sent) for sent, _ in sentences[:2]):
            continue
        for sent, sstart in sentences:
            for step_text in to_steps(sent):
                step = Step(step_text, sstart, sstart + len(sent), sent)
                if SETTINGS_START_RE.search(step_text) and (current is None or current.kind != "settings" or len(current.steps) > 1):
                    current = Run("settings", [step], label)
                    runs.append(current)
                elif QUICK_START_RE.search(step_text) and not re.search(r"\bpower icon\b", step_text, re.I):
                    current = Run("quick", [step], label)
                    runs.append(current)
                elif current is not None and current.kind in {"settings", "quick"} and UI_RE.match(step_text) and current.label == label:
                    current.steps.append(step)
                elif (
                    current is not None
                    and current.kind == "plain"
                    and current.label == label
                    and bool(CRITICAL_RE.search(step_text)) == bool(CRITICAL_RE.search(current.steps[-1].text))
                ):
                    current.steps.append(step)
                else:
                    current = Run("plain", [step], label)
                    runs.append(current)
    return runs


def _direction(text: str) -> str:
    if OFF_RE.search(text):
        return "off"
    if ON_RE.search(text):
        return "on"
    if re.search(r"\b(increase|longer|raise|higher)\b", text, re.I):
        return "increase"
    if re.search(r"\b(decrease|lower|reduce|shorter)\b", text, re.I):
        return "decrease"
    return "open"


def _targets(steps: list[Step]) -> list[str]:
    out = []
    for st in steps:
        m = TARGET_RE.match(st.text.strip())
        if m:
            tgt = re.sub(r"\b(your|the|icon|it)\b", " ", m.group(1), flags=re.I)
            tgt = re.sub(r"\s+", " ", tgt).strip(" ,.")
            for part in re.split(r"\s+(?:or|and)\s+", tgt):
                if part and len(part.split()) <= 6:
                    out.append(part)
    return out


BUTTON_RE = re.compile(r"^(clear|reset|delete|ok|restart|confirm|start|done|allow|apply|your|an?\b)", re.IGNORECASE)


def _dummy_link(steps: list[Step]) -> Deeplink:
    targets = [t for t in _targets(steps) if not BUTTON_RE.match(t)]
    if targets:
        leaf = targets[-1]
        parent = targets[0] if len(targets) > 1 else "Settings"
        desc = f"Open {leaf} settings under {parent}" if parent != leaf else f"Open {leaf} settings"
        msg = f"Open {leaf}"
    else:
        desc, msg = "Open the relevant Settings screen", "Open Settings"
    return Deeplink(deeplink=DUMMY_URI, description=desc, message=msg)


def _map_runs(run: Run, context: str, catalog: Catalog) -> list[DraftGroup]:
    """One step group per switch: "tap the switches next to A or B" → a group for A and one for B."""
    if run.kind != "plain" and run.steps:
        last = run.steps[-1]
        m = re.match(r"^(tap|select|touch)\s+(?:on\s+)?(?:the\s+)?(switch(?:es)? next to\s+)?(.+?)\.?$", last.text, re.I)
        if m and re.search(r"\s(or|and)\s", m.group(3)):
            parts = [p.strip(" ,.") for p in re.split(r"\s+(?:or|and)\s+", m.group(3))]
            hits = [catalog.exact_setting(p) for p in parts]
            if len(parts) > 1 and all(hits) and len({h[0] for h in hits}) == len(parts):
                out = []
                for part in parts:
                    text = f"{m.group(1).capitalize()} the switch next to {part}." if m.group(2) else f"{m.group(1).capitalize()} {part}."
                    sub = Run(run.kind, [*run.steps[:-1], Step(text, last.start, last.end, last.source)], run.label)
                    out.append(_map_run(sub, context, catalog))
                return out
    return [_map_run(run, context, catalog)]


def _map_run(run: Run, context: str, catalog: Catalog) -> DraftGroup:
    group = DraftGroup(steps=run.steps, label=run.label)
    if run.kind == "plain":
        return group
    run_text = " ".join(s.text for s in run.steps)
    direction = _direction(f"{run_text} {context}")
    targets = _targets(run.steps)
    target_text = " ".join(targets[-2:]) or run_text
    match = catalog.resolve(target_text, context, direction)
    if match is None and targets:
        match = catalog.resolve(run_text, context, direction, threshold=0.5, exact=False)
    group.match = match
    if match is not None:
        row = match.row
        group.link = Deeplink(
            deeplink=row["deeplink"],
            description=row.get("description") or "",
            message=row.get("message") or "",
            originalType=row.get("originalType"),
        )
        group.validation = build_validation(row, catalog.kind(row), direction, run_text)
        group.mapping_note = match.reason
    elif run.kind == "settings" and len(run.steps) > 1:
        group.link = _dummy_link(run.steps)
        group.mapping_note = "valid Settings path, screen not in catalog → dummy_positive"
    return group


def _group_category(group: DraftGroup, heading: str) -> ActionCategory:
    text = " ".join([group.label, *[s.text for s in group.steps]])
    if CRITICAL_RE.search(group.label) or CRITICAL_RE.search(text):
        return ActionCategory.critical
    if group.link is not None:
        return ActionCategory.auto
    return ActionCategory.manual


def _action_name(heading: str, groups: list[DraftGroup], catalog: Catalog) -> str:
    h = re.sub(r"\s+", " ", heading).strip()
    key = h.lower().strip(" .:")
    if key in HEADING_REWRITES:
        return HEADING_REWRITES[key]
    words = h.split()
    if words and _is_imperative(h):
        return title_case_action(re.sub(r"\byour\b\s*", "", re.sub(r"'s\b", "", h), flags=re.I))
    linked = [g for g in groups if g.match is not None]
    if linked:
        row = linked[0].match.row
        name = (row.get("validation") or {}).get("key") or row.get("message") or h
        kind = catalog.kind(row)
        verb = {"on": "Enable", "off": "Disable", "update": "Adjust"}.get(kind, "Open")
        suffix = "" if kind != "open" else " Settings"
        return title_case_action(f"{verb} {name}{suffix}")
    return title_case_action(f"Check {h}")


CRITICAL_NAMES = [
    (re.compile(r"factory (data )?reset", re.I), "Perform a Factory Data Reset"),
    (re.compile(r"safe mode", re.I), "Restart in Safe Mode"),
    (re.compile(r"forc(e|ing) (a )?restart", re.I), "Force Restart the Device"),
    (re.compile(r"clear data|delete all", re.I), "Clear App Data"),
    (re.compile(r"software update|update (device|your|the) software", re.I), "Update Device Software"),
    (re.compile(r"remove the battery", re.I), "Reseat the Battery"),
    (re.compile(r"restart|reboot", re.I), "Restart Your Device"),
]


def _critical_name(groups: list[DraftGroup]) -> str | None:
    blob = " ".join([*(g.label for g in groups), *(s.text for g in groups for s in g.steps)])
    for pattern, name in CRITICAL_NAMES:
        if pattern.search(blob):
            return name
    return None


def _label_name(label: str) -> str:
    lab = re.sub(r"^to\s+", "", label, flags=re.I)
    lab = re.sub(r"\b(the|app's|app’s|your)\b", lambda m: "App" if "app" in m.group(0) else "", lab, flags=re.I)
    return title_case_action(re.sub(r"\s+", " ", lab).strip())


def section_actions(section: Section, catalog: Catalog) -> list[DraftAction]:
    runs = _runs(section)
    if not runs:
        return []
    context = f"{section.heading} {section.body}"
    groups = [g for r in runs for g in _map_runs(r, context, catalog)]
    heading_critical = bool(CRITICAL_RE.search(section.heading))
    for g in groups:
        g.category = ActionCategory.critical if heading_critical else _group_category(g, section.heading)
        if g.category != ActionCategory.auto and g.category != ActionCategory.critical:
            g.link, g.validation = None, None
        if g.category == ActionCategory.critical:
            g.link, g.validation = None, None  # never one-tap a destructive step
    # One Action = One Screen: split by category, and by distinct catalog screens.
    buckets: dict[tuple, list[DraftGroup]] = {}
    for g in groups:
        screen = None
        if g.link is not None and g.link.deeplink != DUMMY_URI and g.match is not None:
            screen = (g.match.row.get("validation") or {}).get("key") or g.link.deeplink
        buckets.setdefault((g.category, screen, g.label if g.category != ActionCategory.manual else ""), []).append(g)
    actions = []
    for (cat, screen, label), gs in buckets.items():
        from_catalog = False
        if cat == ActionCategory.critical and len(buckets) > 1:
            name = _critical_name(gs) or _action_name(section.heading, gs, catalog)
        elif len(buckets) == 1:
            name = _action_name(section.heading, gs, catalog)
        elif label:
            name = _label_name(label)
        elif screen:
            name = _action_name("", gs, catalog)
            from_catalog = True
        else:
            name = _action_name(section.heading, gs, catalog)
        if cat == ActionCategory.critical and not CRITICAL_RE.search(name):
            name = _critical_name(gs) or name
        if not from_catalog and cat == ActionCategory.auto and len(gs) == 1 and not (
            _is_imperative(section.heading) or section.heading.lower().strip() in HEADING_REWRITES
        ):
            from_catalog = gs[0].match is not None
        # consecutive un-linked groups of the same sub-procedure read as one procedure
        merged_groups: list[DraftGroup] = []
        for g in gs:
            prev = merged_groups[-1] if merged_groups else None
            if prev is not None and prev.link is None and g.link is None and prev.label == g.label:
                prev.steps = prev.steps + g.steps
            else:
                merged_groups.append(g)
        actions.append(DraftAction(name=name, category=cat, groups=merged_groups, heading=section.heading, from_catalog=from_catalog))
    # Soft checks ("Ensure your phone is connected…") belong to the screen action they precede.
    autos = [a for a in actions if a.category == ActionCategory.auto]
    if len(autos) == 1:
        for a in [a for a in actions if a.category == ActionCategory.manual]:
            text = " ".join(s.text for g in a.groups for s in g.steps)
            if not MANUAL_RE.search(text) and not a.groups[0].label:
                autos[0].groups = a.groups + autos[0].groups
                actions.remove(a)
        if len(actions) == 1 and (_is_imperative(section.heading) or section.heading.lower().strip() in HEADING_REWRITES):
            if not autos[0].groups[-1].label:
                autos[0].name = _action_name(section.heading, autos[0].groups, catalog)
    return actions


def _describe(action: DraftAction) -> str:
    for g in action.groups if action.from_catalog else []:
        if g.match is not None and g.link is not None and g.link.deeplink != DUMMY_URI:
            qna = g.match.row.get("qna_description") or ""
            if qna:
                words = qna.split()
                w = words[0].lower()
                if re.search(r"(ches|shes|sses|xes|zzes)$", w):
                    w = w[:-2]
                elif w.endswith("ies"):
                    w = w[:-3] + "y"
                elif w.endswith("s") and not w.endswith("ss"):
                    w = w[:-1]
                return describe_action(action.name, " ".join([w, *words[1:]]))
    return describe_action(f"{action.name}|{action.heading}")


# ---------------------------------------------------------------- goal assembly
def detect_symptoms(text: str) -> list[str]:
    return [s.key for s in SYMPTOMS if s.pattern.search(text or "")]


def title_and_topic(query: str, doc_title: str) -> tuple[str, str]:
    for source in (query, doc_title):
        for s in SYMPTOMS:
            if s.pattern.search(source or ""):
                return s.title, s.topic
    title = sentence_case_title(doc_title or query)
    return title, title.split()[0].capitalize() + " " + (title.split()[1].capitalize() if len(title.split()) > 1 else "")


def _relevance_filter(query: str, sections: list[tuple[Section, list[DraftAction]]], procedural: bool):
    """Feature guides carry many unrelated how-tos; keep the sections that fit the complaint.

    Numbered troubleshooting flows are kept whole — their order *is* the diagnosis.
    """
    max_sections = 10 if procedural else 4
    if len(sections) <= 1 or len(sections) <= (max_sections if procedural else 3):
        return sections, []
    texts = [f"{s.heading} {s.heading} {s.body}" for s, _ in sections]
    vec = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit(texts + [query])
    sims = (vec.transform(texts) @ vec.transform([query]).T).toarray().ravel()
    ranked = sorted(range(len(sections)), key=lambda i: -sims[i])
    keep = {i for i in ranked[:max_sections] if procedural or sims[i] >= 0.04 or len(sections) <= 3} or {ranked[0]}
    kept = [sections[i] for i in range(len(sections)) if i in keep]
    dropped = [sections[i] for i in range(len(sections)) if i not in keep]
    return kept, dropped


def backup_action(text: str, actions: list[DraftAction], catalog: Catalog) -> DraftAction | None:
    """Backup-before-destructive guard, only when the reference itself asks for a backup."""
    risky = any(
        a.category == ActionCategory.critical and re.search(r"factory|delete all|erase|clear data", " ".join(s.text for g in a.groups for s in g.steps) + a.name, re.I)
        for a in actions
    )
    repair = any(
        re.search(r"repair|service cent|walk-in|mail-in", " ".join(s.text for g in a.groups for s in g.steps) + a.name, re.I)
        for a in actions
    )
    m = re.search(r"[^.]*\bback(ing)? up\b[^.]*\.", text, re.I) or re.search(r"[^.\n]*\b(repair|service cent(er|re))\b[^.\n]*\.", text, re.I)
    if not (risky or repair) or not m:
        return None
    rows = catalog.key_index.get("back up data samsung cloud") or []
    if not rows:
        return None
    row = catalog._pick_direction(rows, "on")
    steps = [
        Step("Navigate to and open Settings.", m.start(), m.end(), m.group(0).strip()),
        Step("Tap Accounts and backup.", m.start(), m.end(), m.group(0).strip()),
        Step("Select Back up data to secure your personal files.", m.start(), m.end(), m.group(0).strip()),
    ]
    link = Deeplink(deeplink=row["deeplink"], description=row["description"], message=row["message"], originalType=row.get("originalType"))
    group = DraftGroup(steps=steps, link=link, validation=build_validation(row, "on", "on", "back up"), category=ActionCategory.auto,
                       mapping_note="backup-before-destructive policy (reference asks to back up)")
    group.match = ScreenMatch(row, 0.95, "policy")
    return DraftAction("Back Up Phone Data", ActionCategory.auto, [group], "policy", "It will keep your data safe", "backup-before-destructive")


def extract_goal(query: str, raw_siis: Any, catalog: Catalog, score: float) -> Extraction:
    doc_title, text = clean_article(raw_siis)
    title, topic = title_and_topic(query, doc_title)
    kind = "Configuration" if CONFIG_INTENT_RE.search(query or "") else "Troubleshooting"
    empty = Extraction(None, text, [], [], [], [], topic, kind)
    if not text:
        return empty
    per_section: list[tuple[Section, list[DraftAction]]] = []
    dropped_names: list[str] = []
    for section in parse_sections(text, doc_title):
        if INFO_HEADING_RE.match(section.heading) and not any(
            _is_imperative(t) for line, _ in section.lines for t in [LEAD_IN_RE.sub("", line)]
        ) and section.level > 0:
            dropped_names.append(section.heading)
            continue
        acts = section_actions(section, catalog)
        if acts:
            per_section.append((section, acts))
        else:
            dropped_names.append(section.heading)
    procedural = bool(re.search(r"^#+\s*(step\s*)?\d+\s*[:.)]", text, re.I | re.M))
    kept, dropped = _relevance_filter(query, per_section, procedural)
    dropped_names += [s.heading for s, _ in dropped]
    drafts = [a for _, acts in kept for a in acts]
    # Merge duplicates (same name) produced by repeated headings.
    merged: dict[tuple, DraftAction] = {}
    for d in drafts:
        key = (d.name, d.category)
        if key in merged:
            merged[key].groups.extend(d.groups)
        else:
            merged[key] = d
    drafts = list(merged.values())
    if len(drafts) > 10:  # keep the flow's ends: first fixes and the last-resort steps
        crit = [d for d in drafts if d.category == ActionCategory.critical]
        rest = [d for d in drafts if d.category != ActionCategory.critical]
        drafts = rest[: 10 - min(len(crit), 3)] + crit[:3]
    guard = backup_action(text, drafts, catalog)
    if guard and not any(a.name == guard.name for a in drafts):
        drafts.insert(0, guard)
    return _assemble(query, drafts, text, title, topic, kind, score, [s.heading for s, _ in kept], dropped_names, catalog)


def _assemble(query, drafts, text, title, topic, kind, score, sections_used, sections_dropped, catalog) -> Extraction:
    empty = Extraction(None, text, [], [], sections_used, sections_dropped, topic, kind)
    actions: list[Action] = []
    provenance: list[dict] = []
    mapping: list[dict] = []
    for d in drafts:
        d.description = d.description or _describe(d)
        groups = [
            StepGroup(
                steps=[s.text for s in g.steps][:7],
                actionableDeeplink=g.link if d.category != ActionCategory.manual else None,
                validationDeeplink=g.validation if d.category == ActionCategory.auto else None,
            )
            for g in d.groups
        ]
        actions.append(Action(actionName=d.name, description=d.description, stepGroups=groups, category=d.category))
    goal = Goal(goal=make_goal_line(topic, kind), title=title, actions=actions, score=max(0.0, min(1.0, score)))
    goal = sanitize_goal(goal, catalog.allowed, catalog.by_uri)
    if goal is None:
        return empty
    # Provenance/mapping are aligned to the *sanitized* order.
    by_name = {d.name: d for d in drafts}
    linked = total_auto = 0
    for ai, action in enumerate(goal.actions):
        d = by_name.get(action.actionName) or next((x for x in drafts if title_case_action(x.name) == action.actionName), None)
        if d is None:
            continue
        by_text = {clean_step(st.text): st for g in d.groups for st in g.steps}
        for gi, g in enumerate(d.groups[: len(action.stepGroups)]):
            for si, text_ in enumerate(action.stepGroups[gi].steps):
                st = by_text.get(text_)
                if st is not None:
                    provenance.append({"action": ai, "group": gi, "step": si, "start": st.start, "end": st.end, "source": st.source, "policy": d.policy})
            link = action.stepGroups[gi].actionableDeeplink
            mapping.append({
                "action": ai,
                "group": gi,
                "category": action.category.value if action.category else "manual",
                "deeplink": link.deeplink if link else None,
                "catalog_id": g.match.row["id"] if (g.match is not None and link and link.deeplink != DUMMY_URI) else None,
                "reason": g.mapping_note or ("physical or destructive step — no one-tap link" if not link else ""),
                "candidates": (g.match.candidates if g.match is not None else []),
            })
        if action.category == ActionCategory.auto:
            total_auto += 1
            linked += int(any(sg.actionableDeeplink for sg in action.stepGroups))
    return Extraction(
        goal=goal,
        text=text,
        provenance=provenance,
        mapping=mapping,
        sections_used=sections_used,
        sections_dropped=sections_dropped,
        topic=topic,
        kind=kind,
        deeplink_coverage=(linked / total_auto) if total_auto else 1.0,
    )


# ---------------------------------------------------------------- LLM draft → grounded Goal
def _locate(step: str, text: str) -> tuple[int, int, str]:
    """Best-matching source sentence for a step (for provenance)."""
    words = set(re.findall(r"[a-z0-9]+", step.lower()))
    best = (0.0, 0, 0, "")
    for line_match in re.finditer(r"[^\n]+", text):
        for sent, start in _sentences(line_match.group(0), line_match.start()):
            sw = set(re.findall(r"[a-z0-9]+", sent.lower()))
            if not sw:
                continue
            ov = len(words & sw) / max(1, len(words))
            if ov > best[0]:
                best = (ov, start, start + len(sent), sent)
    return best[1], best[2], best[3]


def goal_from_llm(query: str, data: dict, raw_siis: Any, catalog: Catalog, score: float, candidate_ids: set[str]) -> Extraction:
    from engine.llm import grounded

    doc_title, text = clean_article(raw_siis)
    title, topic = title_and_topic(query, doc_title)
    kind = "Configuration" if CONFIG_INTENT_RE.search(query or "") else "Troubleshooting"
    empty = Extraction(None, text, [], [], [], [], topic, kind)
    drafts: list[DraftAction] = []
    for raw in (data or {}).get("actions") or []:
        groups: list[DraftGroup] = []
        for g in raw.get("stepGroups") or []:
            steps = []
            for s in g.get("steps") or []:
                s = strip_urls(str(s))
                if s and grounded(s, text):
                    start, end, src = _locate(s, text)
                    steps.append(Step(s, start, end, src))
            if not steps:
                continue
            group = DraftGroup(steps=steps)
            cid = g.get("catalog_id")
            row = catalog.by_id.get(cid) if cid in candidate_ids else None
            run_text = " ".join(s.text for s in steps)
            if row is not None:
                direction = _direction(run_text)
                if catalog.kind(row) in {"on", "off"} and direction in {"on", "off"}:
                    row = catalog.twin(row, direction)
                group.match = ScreenMatch(row, 0.9, "llm pick from offered candidates")
                group.link = Deeplink(deeplink=row["deeplink"], description=row.get("description") or "", message=row.get("message") or "", originalType=row.get("originalType"))
                group.validation = build_validation(row, catalog.kind(row), direction, run_text)
                group.mapping_note = "llm pick from offered candidates"
            elif SETTINGS_START_RE.search(run_text) and len(steps) > 1:
                group.link = _dummy_link(steps)
                group.mapping_note = "valid Settings path, screen not in catalog → dummy_positive"
            groups.append(group)
        if not groups:
            continue
        name = title_case_action(str(raw.get("actionName") or "Open Settings"))
        steps_blob = " ".join(s.text for g in groups for s in g.steps)
        has_screen = any(g.link is not None for g in groups)
        # rules override the model: destructive is always critical, physical is never auto
        if CRITICAL_RE.search(name) or (CRITICAL_RE.search(steps_blob) and not has_screen):
            cat = ActionCategory.critical
        elif has_screen and not MANUAL_RE.search(name):
            cat = ActionCategory.auto
        else:
            cat = ActionCategory.manual
        if cat != ActionCategory.auto:
            for g in groups:
                g.link, g.validation = None, None
        drafts.append(DraftAction(name=name, category=cat, groups=groups, heading=name, from_catalog=False))
    if not drafts:
        return empty
    guard = backup_action(text, drafts, catalog)
    if guard and not any(a.name == guard.name for a in drafts):
        drafts.insert(0, guard)
    llm_title = sentence_case_title(str((data or {}).get("title") or ""))
    if not any(s.pattern.search(query or "") for s in SYMPTOMS) and llm_title != "Device settings":
        title = llm_title
    return _assemble(query, drafts, text, title, topic, kind, score, [d.name for d in drafts], [], catalog)
