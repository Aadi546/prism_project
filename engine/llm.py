"""Optional Groq Cloud path (OpenAI-compatible API).

Enabled only when GROQ_API_KEY is set. The model drafts the structure (which sections
become actions, names, categories, which catalog candidate fits a step group); every
draft is then re-grounded and re-validated by the same code as the deterministic path:

* a step survives only if it can be found in the SIIS text (token overlap ≥ 0.6),
* a deeplink survives only if its id was one of the candidates we offered,
* names / descriptions / categories go through engine.validate.

Any error, timeout or empty result falls back to the deterministic extractor.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    _env_file = Path(__file__).resolve().parents[1] / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
# USD per 1M tokens (input, output) — public Groq price list; override with GROQ_PRICE_IN/OUT.
PRICES = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.10, 0.50),
}

EXTRACT_PROMPT = """You convert Samsung customer-care reference text into a troubleshooting plan.
Rules:
- Use ONLY instructions that appear in REFERENCE. Copy step wording closely; one physical interaction per step.
- Skip explanations, notes, glossary, marketing and anything about PCs, TVs or iPhones.
- One action = one screen/feature. Group the steps for that screen.
- category: "auto" = a phone Settings screen or toggle; "manual" = physical/human step (inspect, charge, cable, service centre, contact support); "critical" = restart, force restart, safe mode, software update, factory reset, clearing app data.
- For each step group that opens a Settings screen, choose catalog_id from CANDIDATES only if it is the exact screen/toggle, else null.
- Keep only actions relevant to the COMPLAINT. Order does not matter (the engine orders them).
Return JSON: {"title": "2-3 word topic", "actions": [{"actionName": "...", "category": "auto|manual|critical", "stepGroups": [{"steps": ["..."], "catalog_id": "DL-xxxx" or null}]}]}"""

PARAPHRASE_PROMPT = """Rewrite the customer complaint as 10 distinct paraphrases across registers:
formal, casual, keyword-only, frustrated, one with a realistic typo, a question, a support-ticket style.
Keep the same problem. Return JSON: {"paraphrases": ["..."]}"""


@dataclass
class LLMResult:
    data: dict | None
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    error: str | None = None
    cost_usd: float = 0.0
    calls: list[dict] = field(default_factory=list)


class GroqClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 6.0):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL") or DEFAULT_MODEL
        self.timeout = float(os.environ.get("GROQ_TIMEOUT", timeout))
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key, base_url=os.environ.get("GROQ_BASE_URL", GROQ_BASE_URL), timeout=self.timeout, max_retries=0)
            except Exception:  # pragma: no cover - dependency missing
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def price(self, prompt_tokens: int, completion_tokens: int) -> float:
        pin, pout = PRICES.get(self.model, (0.59, 0.79))
        pin = float(os.environ.get("GROQ_PRICE_IN", pin))
        pout = float(os.environ.get("GROQ_PRICE_OUT", pout))
        return round((prompt_tokens * pin + completion_tokens * pout) / 1_000_000, 6)

    def _chat(self, system: str, user: str, max_tokens: int = 1800) -> LLMResult:
        started = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            content = resp.choices[0].message.content or "{}"
            content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
            data = json.loads(content)
            usage = resp.usage
            pt, ct = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
            return LLMResult(data, self.model, pt, ct, round((time.perf_counter() - started) * 1000, 1), cost_usd=self.price(pt, ct))
        except Exception as exc:  # network, timeout, bad JSON → caller falls back
            return LLMResult(None, self.model, latency_ms=round((time.perf_counter() - started) * 1000, 1), error=f"{type(exc).__name__}: {str(exc)[:160]}")

    def extract(self, complaint: str, reference: str, candidates: list[dict]) -> LLMResult:
        cand = "\n".join(f"{c['id']} | {c['message']} | {c['description']}" for c in candidates[:30])
        user = f"COMPLAINT:\n{complaint}\n\nREFERENCE:\n{reference[:9000]}\n\nCANDIDATES:\n{cand}"
        return self._chat(EXTRACT_PROMPT, user)

    def paraphrase(self, complaint: str) -> LLMResult:
        return self._chat(PARAPHRASE_PROMPT, complaint, max_tokens=700)


def grounded(step: str, reference: str, threshold: float = 0.6) -> bool:
    """A step is grounded when most of its content words occur in the reference text."""
    words = [w for w in re.findall(r"[a-z0-9]+", step.lower()) if len(w) > 2]
    if not words:
        return False
    ref = set(re.findall(r"[a-z0-9]+", reference.lower()))
    return sum(w in ref for w in words) / len(words) >= threshold
