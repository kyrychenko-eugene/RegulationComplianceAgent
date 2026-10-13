"""Validation of one model answer into a normalised RuleResult (spec §5.6). Pure code, no LLM."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from common.schemas import CheckResponse, RuleResult, TokenUsage

_WS = re.compile(r"\s+")


def normalise_with_map(s: str) -> Tuple[str, List[int]]:
    """Collapse whitespace runs to one space; `idx[i]` is the original index of normalised char i."""
    out: List[str] = []
    idx: List[int] = []
    prev_space = True  # drops leading whitespace
    for i, ch in enumerate(s):
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(ch)
            idx.append(i)
            prev_space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def find_span(quote: str, text: str) -> Optional[List[int]]:
    """Exact (whitespace-normalised) match of `quote` in `text`; span is [start, end) in the original text."""
    q = _WS.sub(" ", quote).strip()
    if not q:
        return None
    norm, idx = normalise_with_map(text)
    start = norm.find(q)
    if start < 0:
        return None
    return [idx[start], idx[start + len(q) - 1] + 1]


def technical_result(rule_id: str, error: str, latency_ms: int = 0) -> RuleResult:
    return RuleResult(rule_id=rule_id, verdict="unclear", unclear_reason="technical",
                      reasoning=f"Technical failure: {error}", latency_ms=latency_ms)


def validate_answer(
    rule_id: str, resp: CheckResponse, text: str, *, latency_ms: int = 0, usage: Optional[TokenUsage] = None
) -> RuleResult:
    """Apply the §5.6 table. `downgraded` is set whenever code overrides the model's verdict."""
    base = dict(rule_id=rule_id, latency_ms=latency_ms, usage=usage or TokenUsage(),
                reasoning=resp.reasoning, violation_type=resp.violation_type)

    def invalid(why: str) -> RuleResult:
        return RuleResult(**{**base, "reasoning": f"{resp.reasoning}\n[invalid answer: {why}]".strip()},
                          verdict="unclear", unclear_reason="invalid_answer",
                          downgraded=resp.verdict != "unclear")

    if resp.verdict == "unclear":
        return RuleResult(**base, verdict="unclear", unclear_reason="model")
    if not resp.reasoning.strip():
        return invalid("empty reasoning")
    if resp.verdict == "pass":
        return RuleResult(**{**base, "violation_type": "none"}, verdict="pass")
    # verdict == fail
    if resp.violation_type == "omission":
        return RuleResult(**base, verdict="fail")  # quote ignored
    if resp.violation_type == "content":
        quote = resp.evidence_quote or ""
        span = find_span(quote, text)
        if span is None:
            return invalid("evidence_quote not found verbatim in the text")
        return RuleResult(**base, verdict="fail", evidence_quote=quote, span=span)
    return invalid("fail without violation_type content or omission")
