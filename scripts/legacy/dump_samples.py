"""Dump five gold input/output samples from the live pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from engine.pipeline import TroubleshootingEngine
from engine.store import article_by_id

ROOT = Path(__file__).resolve().parents[1]
INDEX = json.loads((ROOT / "data" / "samples" / "index.json").read_text())


def main() -> None:
    engine = TroubleshootingEngine()
    for row in INDEX:
        article = article_by_id(row["article_id"])
        siis = article["body"] if article else None
        out = engine.troubleshoot(row["query"], siis)
        path = ROOT / "data" / "samples" / row["file"]
        path.write_text(json.dumps(out.model_dump(), indent=2) + "\n")
        print("wrote", path, "contexts", len(out.response.contexts))


if __name__ == "__main__":
    main()
