"""`python -m eval coverage` — do the approved rules cover the golden expectations? No API calls."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from common.config import RULES_PATH

GOLDEN_PATH = Path(__file__).resolve().parent / "golden.json"
CELL = {"fail": "F", "pass": "P"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_report(golden: dict, rules_file: dict) -> str:
    """Build the text report; pure function of the two files."""
    rules = [r for r in rules_file["rules"] if r["status"] == "approved"]
    approved = {r["id"] for r in rules}
    cases = golden["cases"]
    out: List[str] = []

    # Cell value per (rule, case): F or P if an expectation maps it, FP if both, "." otherwise.
    cell: Dict[tuple, set] = {}
    failing: Dict[str, List[str]] = {r["id"]: [] for r in rules}
    unknown: List[str] = []
    unmapped: List[str] = []
    gaps: List[str] = []
    for c in cases:
        for e in c["expectations"]:
            label = f"{c['id']}: {e['provision']} ({e['expected']}) — {e['concept']}"
            if e.get("known_gap"):
                gaps.append(f"{label}\n      note: {e.get('gap_note', '(missing)')}")
            elif not e["rule_ids"]:
                unmapped.append(label)
            for rid in e["rule_ids"]:
                if rid not in approved:
                    unknown.append(f"{c['id']}: {rid}")
                    continue
                cell.setdefault((rid, c["id"]), set()).add(CELL[e["expected"]])
                if e["expected"] == "fail" and c["id"] not in failing[rid]:
                    failing[rid].append(c["id"])

    out.append("== 1. Matrix: approved rules x cases (F = expected fail, P = expected pass, . = not targeted) ==")
    idw = max(len(r["id"]) for r in rules)
    out.append(" " * idw + "  " + " ".join(f"{i + 1:>2}" for i in range(len(cases))))
    for r in rules:
        row = []
        for c in cases:
            v = cell.get((r["id"], c["id"]), set())
            row.append("FP" if len(v) == 2 else (next(iter(v)) if v else ".").rjust(2))
        out.append(f"{r['id']:<{idw}}  " + " ".join(row))
    out.append("(FP = expected fail by one expectation and pass by another in the same case)")
    out.append("Cases: " + "; ".join(f"{i + 1}={c['id']}" for i, c in enumerate(cases)))

    out.append("")
    out.append("== 2. Approved rules with no case expecting fail ==")
    none_failing = [r for r in rules if not failing[r["id"]]]
    out += [f"  {r['id']}  ({r['source_ref']}, {r['scope']})" for r in none_failing] or ["  (none)"]

    out.append("")
    out.append("== 3. Expectations mapped to no rule (not known_gap) ==")
    out += [f"  {u}" for u in unmapped] or ["  (none)"]
    if unknown:
        out.append("  rule_ids that are not approved rules:")
        out += [f"  {u}" for u in unknown]

    out.append("")
    out.append("== 4. Known gaps ==")
    out += [f"  {g}" for g in gaps] or ["  (none)"]

    out.append("")
    n_exp = sum(len(c["expectations"]) for c in cases)
    out.append(
        f"{len(rules)} approved rules, {len(cases)} cases, {n_exp} expectations; "
        f"{len(none_failing)} rules never expected to fail; {len(unmapped)} unmapped; "
        f"{len(gaps)} known gaps; {len(unknown)} unknown rule_ids."
    )
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m eval")
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("coverage", help="golden expectations x approved rules (no API calls)")
    args = p.parse_args(argv)
    if args.mode == "coverage":
        print(coverage_report(load_json(GOLDEN_PATH), load_json(RULES_PATH)))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
