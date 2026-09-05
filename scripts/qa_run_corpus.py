"""Run QA corpus through Contract Reader pipeline, produce compact summary.

For each sample: run Stage 1 → 2 → 3, then print a one-block summary
comparing what actually happened to what the manifest expects.

Usage:
    python -m scripts.qa_run_corpus data/qa_contracts/stress/*.txt
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from app.contracts.stage1 import analyse
from app.contracts.stage2 import annotate
from app.contracts.stage3 import synthesise


def run_one(path: Path) -> None:
    text = path.read_text()
    print(f"\n{'=' * 78}")
    try:
        rel = path.relative_to(Path.cwd())
    except ValueError:
        rel = path
    print(f"SAMPLE: {rel}  ({len(text)} chars)")
    print("=" * 78)

    if not text.strip():
        print("  input is empty — skipping LLM calls")
        s1 = {"contract_type": "unknown", "confidence": 0, "clauses": [], "metadata": {}}
    else:
        t0 = time.time()
        s1 = analyse(text, language="en")
        s1_ms = int((time.time() - t0) * 1000)
        print(f"\n[Stage 1]  {s1_ms} ms")
        print(f"  contract_type: {s1.get('contract_type')}")
        print(f"  confidence:    {s1.get('confidence')}")
        print(f"  clauses:       {len(s1.get('clauses') or [])}")
        meta = s1.get("metadata") or {}
        print(f"  parties:       {[p.get('name') for p in (meta.get('parties') or [])[:3]]}")
        print(f"  jurisdiction:  {meta.get('jurisdiction')}")
        print(f"  gov_language:  {meta.get('governing_language')}")
        fallback = s1.get("_fallback")
        if fallback:
            print(f"  ⚠  fallback:  {fallback}")

    if not (s1.get("clauses") or []):
        print("\n[Stage 2] skipped (no clauses)")
        print("[Stage 3] skipped (no clauses)")
        return

    t0 = time.time()
    s2 = annotate(s1)
    s2_ms = int((time.time() - t0) * 1000)
    risk_counts = Counter(a.get("risk", "amber") for a in s2["annotations"])
    citations_present = sum(1 for a in s2["annotations"] if (a.get("citation") or {}).get("name"))
    print(f"\n[Stage 2]  {s2_ms} ms")
    print(f"  annotations:   {len(s2['annotations'])} "
          f"(red={risk_counts['red']} amber={risk_counts['amber']} green={risk_counts['green']})")
    print(f"  citations:     {citations_present} of {len(s2['annotations'])} carry a statute reference")
    # Show unique statutes cited
    statutes = set()
    for a in s2["annotations"]:
        cit = a.get("citation") or {}
        if cit.get("name"):
            statutes.add(cit["name"])
    for s in sorted(statutes):
        print(f"    · {s[:70]}")

    t0 = time.time()
    s3 = synthesise(s1, s2)
    s3_ms = int((time.time() - t0) * 1000)
    source_counts = Counter(r.get("source", "novel-llm") for r in s3["rendered"])
    print(f"\n[Stage 3]  {s3_ms} ms")
    print(f"  rendered:      {len(s3['rendered'])}")
    print(f"  source breakdown: "
          f"library-rule={source_counts['library-rule']} "
          f"novel-llm={source_counts['novel-llm']} "
          f"fallback={source_counts['fallback']}")
    overview = s3.get("overview") or {}
    ts = overview.get("top_summary") or ""
    ta = overview.get("top_actions") or []
    print(f"  top_summary:   {ts[:100]}{'…' if len(ts) > 100 else ''}")
    print(f"  top_actions:   {len(ta)} listed")
    for i, a in enumerate(ta[:3], 1):
        print(f"    {i}. {a[:80]}{'…' if len(a) > 80 else ''}")

    # Bugs: red-tier with null action, idiom leaks, forbidden phrases
    issues = []
    for r in s3["rendered"]:
        cid = r["clause_id"]
        # find matching risk
        risk = next((a.get("risk") for a in s2["annotations"] if a["clause_id"] == cid), "amber")
        if risk == "red" and not r.get("action"):
            issues.append(f"clause {cid} is RED but action is null")
        expl = (r.get("explanation") or "") + " " + (r.get("implication") or "") + " " + (r.get("action") or "")
        for bad in ("illegal", "you should sue", "grounds for a lawsuit", "is void"):
            if bad in expl.lower():
                issues.append(f"clause {cid} contains forbidden phrase '{bad}'")
    if issues:
        print("\n  ⚠  ISSUES:")
        for i in issues:
            print(f"    · {i}")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.qa_run_corpus <path> [...paths]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        path = Path(arg)
        if path.is_dir():
            for p in sorted(path.rglob("*.txt")):
                run_one(p)
        else:
            run_one(path)


if __name__ == "__main__":
    main()
