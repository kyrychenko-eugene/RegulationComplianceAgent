"""Judge: monitoring only (spec §6). An LLM flags missed rules and disputed verdicts; code filters and rates.

The judge never changes the agent's verdict. `run_judge` never raises: any failure is `status = unavailable`.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel

from common.config import Config
from common.llm import LLM
from common.prompts import load_prompt
from common.schemas import JudgeInfo, Rule, RuleResult

log = logging.getLogger("agent.judge")

JUDGE_PROMPT = "judge/judge"
CALL_TIMEOUT_S = 120


class MissedRule(BaseModel):
    rule_id: str
    reason: str


class DisputedVerdict(BaseModel):
    rule_id: str
    agent_verdict: Literal["pass", "fail", "unclear"]
    judge_verdict: Literal["pass", "fail", "unclear"]
    reason: str


class JudgeResponse(BaseModel):
    """Structured output of the judge. `reasoning` first, so the model thinks before listing."""

    reasoning: str
    missed_rules: List[MissedRule]
    disputed_verdicts: List[DisputedVerdict]


def render_input(text: str, catalog: List[Rule], results: List[RuleResult]) -> str:
    run_ids = {r.rule_id for r in results}
    lines = ["## Marketing text", "", text, "", "## Catalog of all approved rules", ""]
    for r in catalog:
        lines.append(f"- {r.id} [{r.severity}] {r.title} — {r.check}" + ("" if r.id in run_ids else "  (NOT RUN)"))
    lines += ["", "## Agent results (rules that were run)", ""]
    for res in results:
        reasoning = " ".join(res.reasoning.split())
        lines.append(f"- {res.rule_id}: {res.verdict} — {reasoning}")
    if not results:
        lines.append("(no rules were run)")
    return "\n".join(lines)


def rate(response: JudgeResponse, catalog: List[Rule], results: List[RuleResult]) -> JudgeInfo:
    """Code filters ids and computes the rating (none → agree; only advisory → partial; any blocking → disagree).

    Beyond unknown ids (spec), two nonsensical entries are dropped: a "missed" rule that was in fact run, and a
    dispute of a rule that was not run or where the judge's verdict equals the agent's. Duplicates are merged.
    """
    severity = {r.id: r.severity for r in catalog}
    run_verdicts = {r.rule_id: r.verdict for r in results}
    missed, seen = [], set()
    for m in response.missed_rules:
        if m.rule_id in severity and m.rule_id not in run_verdicts and m.rule_id not in seen:
            seen.add(m.rule_id)
            missed.append(m.model_dump())
    disputed, seen = [], set()
    for d in response.disputed_verdicts:
        if d.rule_id in severity and d.rule_id in run_verdicts and d.judge_verdict != run_verdicts[d.rule_id] \
                and d.rule_id not in seen:
            seen.add(d.rule_id)
            # The agent's verdict is taken from the run, not from the judge's echo of it.
            disputed.append({**d.model_dump(), "agent_verdict": run_verdicts[d.rule_id]})
    involved = [m["rule_id"] for m in missed] + [d["rule_id"] for d in disputed]
    if not involved:
        rating = "agree"
    elif any(severity[i] == "blocking" for i in involved):
        rating = "disagree"
    else:
        rating = "partial"
    return JudgeInfo(status="ok", rating=rating, missed_rules=missed, disputed_verdicts=disputed,
                     reasoning=response.reasoning)


async def run_judge(llm: LLM, config: Config, text: str, catalog: List[Rule],
                    results: List[RuleResult]) -> Tuple[JudgeInfo, Optional[int]]:
    """Returns (judge block, judge_ms). Never raises."""
    t0 = time.perf_counter()
    try:
        if not catalog:
            raise ValueError("no rule catalog")
        res = await asyncio.wait_for(
            llm.parse(model=config.strong_model, system=load_prompt(JUDGE_PROMPT),
                      user=render_input(text, catalog, results), schema=JudgeResponse),
            CALL_TIMEOUT_S)
        info = rate(res.parsed, catalog, results)  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001 - the judge must never affect the run
        log.warning("judge unavailable: %s: %s", type(e).__name__, e)
        info = JudgeInfo(status="unavailable", reasoning=f"{type(e).__name__}: {e}")
    return info, int((time.perf_counter() - t0) * 1000)
