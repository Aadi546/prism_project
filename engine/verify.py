"""Closed-loop verification.

The contract has a `validationDeeplink` (key / resultType / condition / value) but the
brief never says how to fill it. We derive it from the catalog row we tapped:

    onURL      → boolean  equal  "True"
    offURL     → boolean  equal  "False"
    updateURL  → integer  greater|less (direction of the step)
    onClickURL → key only (opening a page changes nothing we can read back)

`DeviceSimulator` stands in for the on-device agent that would resolve a `bixby://…/val/…`
URI to the live setting value. It lets the console show a plan being executed and
verified step by step, and lets eval measure "resolved before the critical tier".
"""

from __future__ import annotations

import random
import re
import secrets
import time
from dataclasses import dataclass, field

from engine.schema import Condition, ResultTypes, ValidationDeeplink


def build_validation(row: dict, kind: str, direction: str, step_text: str) -> ValidationDeeplink | None:
    raw = row.get("validation") or {}
    uri = raw.get("deeplink")
    key = raw.get("key")
    if not uri or not key or key.lower() in {"onurl", "offurl"}:
        # twin rows with a placeholder key still carry a usable URI
        if not uri:
            return None
        key = (row.get("qna_description") or row.get("description") or "setting").split(".")[0][:60]
    if kind == "on":
        return ValidationDeeplink(deeplink=uri, key=key, resultType=ResultTypes.boolean, condition=Condition.equal, value="True")
    if kind == "off":
        return ValidationDeeplink(deeplink=uri, key=key, resultType=ResultTypes.boolean, condition=Condition.equal, value="False")
    if kind == "update":
        m = re.search(r"\b(\d{1,4})\b", step_text or "")
        cond = Condition.less if direction == "decrease" else Condition.greater
        return ValidationDeeplink(deeplink=uri, key=key, resultType=ResultTypes.intNum, condition=cond, value=m.group(1) if m else None)
    return ValidationDeeplink(deeplink=uri, key=key)


def is_verifiable(v: ValidationDeeplink | dict | None) -> bool:
    if v is None:
        return False
    d = v if isinstance(v, dict) else v.model_dump()
    return bool(d.get("resultType") and d.get("condition"))


def _coerce(value, result_type: str | None):
    if result_type == "boolean":
        return str(value).lower() in {"true", "1", "on", "yes"}
    if result_type in {"integer", "float"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return value


def evaluate(observed, validation: dict, baseline=None) -> bool:
    rt = validation.get("resultType")
    cond = validation.get("condition")
    expected = validation.get("value")
    if not rt or not cond:
        return observed is not None
    a = _coerce(observed, rt)
    if expected is None:
        # "greater"/"less" with no explicit target: must have moved past the starting value
        if baseline is None or a is None:
            return False
        expected = baseline
    b = _coerce(expected, rt)
    if a is None or b is None:
        return False
    if cond == "equal":
        return a == b
    if cond == "greater":
        return a > b
    if cond == "less":
        return a < b
    return False


@dataclass
class SimSession:
    id: str
    state: dict[str, object] = field(default_factory=dict)  # validation URI → value
    labels: dict[str, str] = field(default_factory=dict)
    baseline: dict[str, object] = field(default_factory=dict)
    screens: list[str] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    created: float = field(default_factory=time.time)


class DeviceSimulator:
    """In-memory mock Galaxy settings store, one session per troubleshooting run."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.sessions: dict[str, SimSession] = {}

    def _gc(self) -> None:
        cutoff = time.time() - 3600
        for sid in [s for s, v in self.sessions.items() if v.created < cutoff]:
            self.sessions.pop(sid, None)

    def start(self, plan: dict, seed: int | None = None) -> SimSession:
        """Seed every setting the plan touches in its *faulty* state, so the loop is visible."""
        self._gc()
        rng = random.Random(seed)
        sess = SimSession(id=secrets.token_hex(6))
        for ctx in plan.get("contexts") or []:
            for action in ctx.get("actions") or []:
                for g in action.get("stepGroups") or []:
                    v = g.get("validationDeeplink")
                    if not v or not v.get("deeplink"):
                        continue
                    uri = v["deeplink"]
                    sess.labels[uri] = v.get("key") or uri
                    rt, val = v.get("resultType"), v.get("value")
                    if rt == "boolean":
                        sess.state[uri] = "False" if str(val).lower() == "true" else "True"
                    elif rt in {"integer", "float"}:
                        base = float(val) if val not in (None, "") else 30.0
                        sess.state[uri] = str(int(base - rng.randint(5, 15)) if v.get("condition") == "greater" else int(base + rng.randint(5, 15)))
                    else:
                        sess.state[uri] = "closed"
        sess.baseline = dict(sess.state)
        self.sessions[sess.id] = sess
        return sess

    def tap(self, session_id: str, deeplink: str, validation: dict | None) -> dict:
        """Simulate the one-tap deeplink: the target screen opens and the switch moves."""
        sess = self.sessions[session_id]
        row = self.catalog.by_uri.get(deeplink)
        screen = (row or {}).get("message") or ("Settings" if deeplink.endswith("dummy_positive") else deeplink)
        sess.screens.append(screen)
        if validation and validation.get("deeplink"):
            uri = validation["deeplink"]
            rt, cond, val = validation.get("resultType"), validation.get("condition"), validation.get("value")
            if rt == "boolean":
                sess.state[uri] = "True" if str(val).lower() == "true" else "False"
            elif rt in {"integer", "float"}:
                cur = float(sess.state.get(uri) or 0)
                target = float(val) if val not in (None, "") else cur
                sess.state[uri] = str(int(max(cur, target) + 10) if cond == "greater" else int(min(cur, target) - 10))
            else:
                sess.state[uri] = "opened"
        entry = {"t": round(time.time(), 3), "event": "tap", "deeplink": deeplink, "screen": screen}
        sess.log.append(entry)
        return {"screen": screen, "row": _screen_card(row), "state": dict(sess.state)}

    def verify(self, session_id: str, validation: dict) -> dict:
        sess = self.sessions[session_id]
        uri = validation.get("deeplink")
        row = self.catalog.by_validation_uri(uri) if uri else None
        observed = sess.state.get(uri)
        passed = evaluate(observed, validation, sess.baseline.get(uri))
        result = {
            "deeplink": uri,
            "key": validation.get("key") or (row or {}).get("validation", {}).get("key"),
            "observed": observed,
            "expected": validation.get("value") if validation.get("value") is not None else sess.baseline.get(uri),
            "condition": validation.get("condition"),
            "resultType": validation.get("resultType"),
            "verifiable": is_verifiable(validation),
            "passed": bool(passed),
        }
        sess.log.append({"t": round(time.time(), 3), "event": "verify", **result})
        return result

    def snapshot(self, session_id: str) -> dict:
        sess = self.sessions[session_id]
        return {"id": sess.id, "state": dict(sess.state), "labels": dict(sess.labels), "screens": sess.screens, "log": sess.log}


def _screen_card(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "message": row.get("message"),
        "description": row.get("description"),
        "qna_description": row.get("qna_description"),
        "originalType": row.get("originalType"),
        "key": (row.get("validation") or {}).get("key"),
    }
