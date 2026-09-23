"""Exact output contract for the Smart Guided Troubleshooting Engine."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BaseDeeplink(BaseModel):
    deeplink: str


class Deeplink(BaseDeeplink):
    description: str
    message: Optional[str] = ""
    classes: Optional[Dict[str, str]] = None
    originalType: Optional[str] = None


class Condition(str, Enum):
    greater = "greater"
    equal = "equal"
    less = "less"


class ResultTypes(str, Enum):
    boolean = "boolean"
    intNum = "integer"
    string = "str"
    floatNum = "float"


class ActionCategory(str, Enum):
    auto = "auto"
    manual = "manual"
    critical = "critical"


class ValidationDeeplink(BaseDeeplink):
    key: str
    resultType: Optional[ResultTypes] = None
    condition: Optional[Condition] = None
    value: Optional[str] = None


class StepGroup(BaseModel):
    steps: List[str]
    validationDeeplink: Optional[ValidationDeeplink] = None
    actionableDeeplink: Optional[Deeplink] = None


class Action(BaseModel):
    actionName: str
    description: str
    stepGroups: List[StepGroup]
    category: Optional[ActionCategory] = ActionCategory.manual


class Goal(BaseModel):
    goal: str
    title: str
    actions: List[Action]
    score: float = Field(ge=0.0, le=1.0)


class ContextDeeplinkResponse(BaseModel):
    """RAG response containing a list of Goal objects."""

    contexts: List[Goal] = []


class TroubleshootRequest(BaseModel):
    query: str
    siis_response: Optional[str] = None


class ResponseMeta(BaseModel):
    latency_ms: float
    cache_hit: bool
    model: str
    cost_usd: float = 0.0
    fallback: Optional[str] = None


class TroubleshootResponse(BaseModel):
    query: str
    query_variations: List[str]
    response: ContextDeeplinkResponse
    meta: ResponseMeta
