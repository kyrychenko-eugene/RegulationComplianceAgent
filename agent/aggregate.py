"""Overall verdict and summary (spec §5.7). Pure code, no LLM."""
from __future__ import annotations

import re
from typing import List, Tuple

from common.schemas import RuleResult, Verdict

_WS = re.compile(r"\s+")


def aggregate_verdict(results: List[RuleResult], errors: List[str]) -> Verdict:
    """FAIL on a blocking fail; NEEDS_HUMAN_REVIEW on any other fail or unclear; else PASS.

    A run with a technical problem (any entry in `errors`) or without a single result can never be PASS.
    """
    if any(r.verdict == "fail" and r.severity == "blocking" for r in results):
        return "FAIL"
    if any(r.verdict in ("fail", "unclear") for r in results) or errors or not results:
        return "NEEDS_HUMAN_REVIEW"
    return "PASS"


def _one_line(s: str) -> str:
    return _WS.sub(" ", s).strip()


def _detail(r: RuleResult) -> str:
    ref = r.source_ref or r.rule_id
    if r.verdict == "fail":
        what = f'"{r.evidence_quote}"' if r.violation_type == "content" and r.evidence_quote else "omission: " + _one_line(r.reasoning)
        reasoning = _one_line(r.reasoning) if r.violation_type == "content" else ""
        return f"- {ref} [{r.severity}] {r.rule_id}: " + (f"{reasoning} — quote: {what}" if reasoning else what)
    return f"- {ref} [{r.severity}] {r.rule_id}: unclear ({r.unclear_reason}): {_one_line(r.reasoning)}"


def build_summary(verdict: Verdict, results: List[RuleResult], errors: List[str]) -> str:
    failed = [r for r in results if r.verdict == "fail"]
    unclear = [r for r in results if r.verdict == "unclear"]
    blocking = sum(r.severity == "blocking" for r in failed)
    head = (f"{verdict}: {len(failed)} of {len(results)} rules failed "
            f"({blocking} blocking, {len(failed) - blocking} advisory); {len(unclear)} unclear.")
    if errors:
        head += f" {len(errors)} technical error(s)."
    return "\n".join([head] + [_detail(r) for r in failed + unclear])


def aggregate(results: List[RuleResult], errors: List[str]) -> Tuple[Verdict, str]:
    verdict = aggregate_verdict(results, errors)
    return verdict, build_summary(verdict, results, errors)
