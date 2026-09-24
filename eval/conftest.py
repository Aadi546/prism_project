"""Keep pytest on the deterministic path even if `.env` has GROQ_API_KEY."""

from __future__ import annotations

import os

os.environ["ENGINE_DISABLE_LLM"] = "1"
