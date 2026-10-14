"""`python -m eval coverage` — do the approved rules cover the golden expectations? No API calls.

`python -m eval run` — run the golden set through the public `agent.check()` and print metrics (spec §8.3).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import Counter
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


THRESHOLDS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else "n/a (0 cases)"


def run_golden(golden: dict, only: Optional[List[str]] = None, check=None) -> Dict[str, object]:
    """Run each case through `agent.check` (sequentially, no run log). Returns case id -> RunResult."""
    if check is None:
        import agent
        check = lambda text: agent.check(text, log_path=None, judge="sync")  # noqa: E731
    runs = {}
    for i, c in enumerate(golden["cases"], 1):
        if only and c["id"] not in only:
            continue
        run = check(c["text"])
        runs[c["id"]] = run
        print(f"[{i}/{len(golden['cases'])}] {c['id']}: {run.verdict} ({len(run.errors)} errors)", file=sys.stderr)
    return runs


def judge_calibration(cases: List[dict], rows: list, runs: Dict[str, object]) -> List[str]:
    """Judge rating vs golden labels (spec §6).

    A case is *agent-wrong* when any of its (expectation, rule) pairs is a false PASS, a rule that was
    expected to fail but was not run, or a false FAIL. The judge is *consistent* with the labels when it rates
    `agree` on an agent-right case, or `partial`/`disagree` on an agent-wrong one. Cases whose judge did not
    return (`status != ok`) are excluded.
    """
    out = ["## 8. Judge calibration", ""]
    wrong = {c["id"] for c, e, _, o in rows
             if (e["expected"] == "fail" and o in ("pass", "not_run")) or (e["expected"] == "pass" and o == "fail")}
    judged = [c for c in cases if runs[c["id"]].judge.status == "ok"]
    out.append(f"Judge returned for {len(judged)}/{len(cases)} cases (the rest: unavailable or not run).")
    if not judged:
        out.append("Judge agreement with golden labels: n/a (0 cases judged)")
        return out
    consistent = [c for c in judged if (runs[c["id"]].judge.rating == "agree") != (c["id"] in wrong)]
    out.append(f"- **Judge agreement with golden labels** (agent-right → `agree`, agent-wrong → `partial`/`disagree`): "
               f"**{_pct(len(consistent), len(judged))}**")
    right = [c for c in judged if c["id"] not in wrong]
    bad = [c for c in judged if c["id"] in wrong]
    flagged_right = [c for c in right if runs[c["id"]].judge.rating != "agree"]
    caught = [c for c in bad if runs[c["id"]].judge.rating != "agree"]
    out.append(f"  - agent-wrong cases the judge flagged (recall): {_pct(len(caught), len(bad))}")
    out.append(f"  - agent-right cases the judge flagged anyway (false alarms): {_pct(len(flagged_right), len(right))}")
    acc = lambda c: c.get("acceptable_overall") or [c["expected_overall"]]  # noqa: E731
    with_overall = [c for c in judged if runs[c["id"]].judge.overall_verdict]
    if with_overall:
        j_ok = [c for c in with_overall if runs[c["id"]].judge.overall_verdict in acc(c)]
        a_ok = [c for c in with_overall if runs[c["id"]].verdict in acc(c)]
        out.append(f"- **Overall-verdict agreement if the judge's rule verdicts were applied**: "
                   f"**{_pct(len(j_ok), len(with_overall))}** (agent on the same cases: {_pct(len(a_ok), len(with_overall))}). "
                   "Diagnostic only: the judge never changes the verdict.")
        same = [c for c in with_overall if runs[c["id"]].judge.verdict_agrees]
        out.append(f"  - judge reaches the same overall verdict as the agent: {_pct(len(same), len(with_overall))}")
    ratings = Counter(runs[c["id"]].judge.rating for c in judged)
    out.append("  - ratings: " + ", ".join(f"{k}={ratings.get(k, 0)}" for k in ("agree", "partial", "disagree")))
    missed = Counter(m["rule_id"] for c in judged for m in runs[c["id"]].judge.missed_rules)
    out.append(f"  - rules the judge reported as missed (classifier misses): "
               + (", ".join(f"`{k}`×{v}" for k, v in missed.most_common()) or "none"))
    out.append("")
    out.append("| case | expected | agent | judge overall | agent vs labels | judge rule rating | missed | disputed | consistent |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for c in judged:
        j = runs[c["id"]].judge
        out.append(f"| {c['id']} | {'/'.join(acc(c))} | {runs[c['id']].verdict} | {j.overall_verdict or '-'} | "
                   f"{'wrong' if c['id'] in wrong else 'right'} | {j.rating} | {len(j.missed_rules)} | "
                   f"{len(j.disputed_verdicts)} | {'yes' if c in consistent else '**NO**'} |")
    return out


def eval_report(golden: dict, rules_file: dict, runs: Dict[str, object]) -> str:
    """Build the metrics report; pure function of golden, rules and the runs."""
    rules = {r["id"]: r for r in rules_file["rules"] if r["status"] == "approved"}
    cases = [c for c in golden["cases"] if c["id"] in runs]
    out: List[str] = []

    # One row per (case, expectation, rule_id): the rule's outcome in that run.
    rows = []  # (case, expectation, rule_id, outcome) outcome: pass|fail|unclear|not_run
    for c in cases:
        by_id = {r.rule_id: r for r in runs[c["id"]].results}
        for e in c["expectations"]:
            for rid in e["rule_ids"]:
                res = by_id.get(rid)
                rows.append((c, e, rid, res.verdict if res else "not_run"))
    exp_fail = [r for r in rows if r[1]["expected"] == "fail"]
    exp_pass = [r for r in rows if r[1]["expected"] == "pass"]

    false_pass = [r for r in exp_fail if r[3] == "pass"]
    not_run = [r for r in exp_fail if r[3] == "not_run"]
    false_fail = [r for r in exp_pass if r[3] == "fail"]
    out.append("# Eval run — golden set through `agent.check()`")
    out.append("")
    out.append(f"{len(cases)} cases, {sum(len(c['expectations']) for c in cases)} expectations, "
               f"{len(rows)} (expectation, rule) pairs. Models: {next(iter(runs.values())).models.fast or '?'} "
               f"(checks); classifier threshold {next(iter(runs.values())).classifier.threshold}.")
    out.append("")
    out.append("## 1. Headline metrics")
    out.append(f"- **False PASS rate** (expected fail, rule returned pass): **{_pct(len(false_pass), len(exp_fail))}**")
    out.append(f"  - plus expected fail but rule not run (classifier did not select it): {_pct(len(not_run), len(exp_fail))}")
    missed_exp = [(c, e) for c in cases for e in c["expectations"]
                  if e["expected"] == "fail" and e["rule_ids"]
                  and not any(r[0] is c and r[1] is e and r[3] == "fail" for r in rows)]
    n_exp_fail = sum(1 for c in cases for e in c["expectations"] if e["expected"] == "fail" and e["rule_ids"])
    out.append(f"  - expectation level (no mapped rule failed): {_pct(len(missed_exp), n_exp_fail)}")
    out.append(f"- False FAIL rate (expected pass, rule returned fail): {_pct(len(false_fail), len(exp_pass))}")
    unclear = [r for r in rows if r[3] == "unclear"]
    out.append(f"- Unclear rate: {_pct(len(unclear), len(rows))}")
    reasons = Counter()
    for c in cases:
        for res in runs[c["id"]].results:
            if res.verdict == "unclear":
                reasons[res.unclear_reason or "?"] += 1
    out.append("  - by `unclear_reason` (all checked rules): " +
               (", ".join(f"{k}={v}" for k, v in sorted(reasons.items())) or "none"))
    agree = [c for c in cases if runs[c["id"]].verdict in (c.get("acceptable_overall") or [c["expected_overall"]])]
    out.append(f"- Overall-verdict agreement: {_pct(len(agree), len(cases))}")
    out.append(f"- Known gaps (not counted as errors): "
               f"{sum(1 for c in cases for e in c['expectations'] if e.get('known_gap'))} expectations")
    tech = [(c["id"], err) for c in cases for err in runs[c["id"]].errors]
    out.append(f"- Run errors: {len(tech)}" + ("".join(f"\n  - {i}: {e}" for i, e in tech[:10])))

    out.append("")
    out.append("## 2. Missed violations (false PASS / not run)")
    for c, e, rid, o in false_pass + not_run:
        out.append(f"- `{c['id']}` / `{rid}` ({o}) — {e['concept']}")
    if not (false_pass or not_run):
        out.append("- (none)")

    out.append("")
    out.append("## 3. False FAIL")
    for c, e, rid, o in false_fail:
        out.append(f"- `{c['id']}` / `{rid}` — {e['concept']}")
    if not false_fail:
        out.append("- (none)")

    out.append("")
    out.append("## 4. Per-rule agreement with expectations")
    out.append("")
    out.append("| rule | severity | pairs | agree | false PASS | false FAIL | unclear | not run |")
    out.append("|---|---|---|---|---|---|---|---|")
    by_rule: Dict[str, list] = {}
    for r in rows:
        by_rule.setdefault(r[2], []).append(r)
    for rid in sorted(by_rule):
        rr = by_rule[rid]
        agree_n = sum(1 for _, e, _, o in rr if o == e["expected"])
        fp = sum(1 for _, e, _, o in rr if e["expected"] == "fail" and o == "pass")
        ff = sum(1 for _, e, _, o in rr if e["expected"] == "pass" and o == "fail")
        un = sum(1 for r in rr if r[3] == "unclear")
        nr = sum(1 for r in rr if r[3] == "not_run")
        sev = rules[rid]["severity"] if rid in rules else "?"
        out.append(f"| `{rid}` | {sev} | {len(rr)} | {agree_n} | {fp} | {ff} | {un} | {nr} |")

    out.append("")
    out.append("## 5. Overall verdict per case")
    out.append("")
    out.append("| case | expected | acceptable | agent | ok | fail/unclear rules |")
    out.append("|---|---|---|---|---|---|")
    for c in cases:
        run = runs[c["id"]]
        acc = c.get("acceptable_overall") or [c["expected_overall"]]
        nf = sum(1 for r in run.results if r.verdict == "fail")
        nu = sum(1 for r in run.results if r.verdict == "unclear")
        out.append(f"| {c['id']} | {c['expected_overall']} | {'/'.join(acc)} | {run.verdict} | "
                   f"{'yes' if run.verdict in acc else '**NO**'} | {nf}/{nu} of {len(run.results)} |")

    out.append("")
    out.append("## 6. Classifier threshold sweep")
    out.append("")
    out.append("Miss = conditional rule mapped to an `expected: fail` expectation that the classifier did not select. "
               "Extra = conditional rules selected beyond those needed. Cases where the classifier fell back to "
               "all rules are excluded (no probabilities).")
    usable = [c for c in cases if runs[c["id"]].classifier.status == "ok"]
    fallbacks = [c["id"] for c in cases if runs[c["id"]].classifier.status != "ok"]
    out.append(f"Usable cases: {len(usable)}/{len(cases)}" + (f"; fallback in: {', '.join(fallbacks)}" if fallbacks else ""))
    out.append("")
    out.append("| threshold | misses | extra checks | cases with a miss |")
    out.append("|---|---|---|---|")
    cond = {rid: set(r["tags"]) for rid, r in rules.items() if r["scope"] == "conditional"}
    recommended = None
    for t in THRESHOLDS:
        misses, extra, bad = 0, 0, []
        for c in usable:
            probs = runs[c["id"]].classifier.probabilities
            tags = {k for k, p in probs.items() if p >= t}
            needed = {rid for e in c["expectations"] if e["expected"] == "fail"
                      for rid in e["rule_ids"] if rid in cond}
            selected = {rid for rid, tg in cond.items() if tg & tags}
            m = needed - selected
            misses += len(m)
            extra += len(selected - needed)
            if m:
                bad.append(c["id"])
        if misses == 0:
            recommended = t
        out.append(f"| {t} | {misses} | {extra} | {', '.join(bad) or '-'} |")
    out.append("")
    out.append(f"**Recommended `CLASSIFIER_THRESHOLD`: {recommended if recommended is not None else 'none (misses at every threshold)'}** "
               "(highest threshold with zero misses).")

    out.append("")
    out.append("## 7. Known gaps")
    gaps = [f"- `{c['id']}`: {e['provision']} — {e.get('gap_note', '')}" for c in cases
            for e in c["expectations"] if e.get("known_gap")]
    out += gaps or ["- (none)"]

    out.append("")
    out += judge_calibration(cases, rows, runs)

    ref = runs.get("get-rich-tomorrow")
    if ref is not None:
        out.append("")
        out.append(f"Reference case overall verdict: **{ref.verdict}** (must be FAIL).")
    tot = sum(r.usage.cost_usd for r in runs.values())
    out.append(f"Total cost of the run: ${tot:.4f}.")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m eval")
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("coverage", help="golden expectations x approved rules (no API calls)")
    r = sub.add_parser("run", help="run the golden set through agent.check() and print metrics (needs OPENAI_API_KEY)")
    r.add_argument("--out", metavar="PATH", help="also write the report (Markdown) to PATH")
    r.add_argument("--runs", metavar="PATH", help="also dump every RunResult (incl. classifier probabilities) as JSON")
    r.add_argument("--cases", nargs="+", metavar="ID", help="only these case ids")
    args = p.parse_args(argv)
    if args.mode == "coverage":
        print(coverage_report(load_json(GOLDEN_PATH), load_json(RULES_PATH)))
        return 0
    if args.mode == "run":
        golden, rules_file = load_json(GOLDEN_PATH), load_json(RULES_PATH)
        runs = run_golden(golden, args.cases)
        if args.runs:
            Path(args.runs).write_text(json.dumps({k: v.model_dump() for k, v in runs.items()}, ensure_ascii=False,
                                                  indent=1), encoding="utf-8")
        report = eval_report(golden, rules_file, runs)
        print(report)
        if args.out:
            Path(args.out).write_text(report + "\n", encoding="utf-8")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
