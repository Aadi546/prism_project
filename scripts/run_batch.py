"""Produce results.jsonl (Appendix B format) for every complaint in data/input.txt.

    python scripts/run_batch.py                 # query + its paired SIIS article (cold pipeline)
    python scripts/run_batch.py --no-siis       # query only: retrieval + semantic cache path
    python scripts/run_batch.py --samples       # also refresh data/samples/ with 5 reference pairs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.pipeline import TroubleshootingEngine  # noqa: E402

SAMPLES = [
    ("01_cracked_screen.json", "row_14"),
    ("02_touchscreen_lag.json", "row_21"),
    ("03_black_screen.json", "row_22"),
    ("04_email_flash.json", "row_1"),
    ("05_multi_intent_no_siis.json", "row_19"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-siis", action="store_true")
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results.jsonl"))
    args = ap.parse_args()

    articles = json.loads((ROOT / "data" / "siis_responses.json").read_text(encoding="utf-8"))["responses"]
    by_query = {a["original_query"].strip(): a for a in articles}
    queries = [l.strip() for l in (ROOT / "data" / "input.txt").read_text(encoding="utf-8").splitlines() if l.strip()]

    engine = TroubleshootingEngine(prewarm=args.no_siis)
    lines = []
    for q in queries:
        art = by_query.get(q)
        siis = None if args.no_siis or art is None else art["siis_response"]
        resp = engine.troubleshoot(q, siis).model_dump(mode="json")
        lines.append(json.dumps(resp, ensure_ascii=False))
        ctx = resp["response"]["contexts"]
        print(f"{resp['meta']['latency_ms']:>8.2f} ms  {len(ctx)} goal(s)  {(ctx[0]['title'] if ctx else resp['meta']['fallback']):<28} {q[:60]}")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} lines → {args.out}")

    if args.samples:
        fresh = TroubleshootingEngine(prewarm=False)
        index = []
        by_id = {a["id"]: a for a in articles}
        for name, rid in SAMPLES:
            art = by_id[rid]
            siis = None if "no_siis" in name else art["siis_response"]
            resp = fresh.troubleshoot(art["original_query"], siis).model_dump(mode="json")
            path = ROOT / "data" / "samples" / name
            path.write_text(json.dumps({"request": {"query": art["original_query"], "siis_response": siis}, **resp}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            index.append({"file": name, "query": art["original_query"], "article_id": rid, "siis_provided": siis is not None})
        (ROOT / "data" / "samples" / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("refreshed data/samples/")


if __name__ == "__main__":
    main()
