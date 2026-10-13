"""Public entry point: `agent.check(text) -> RunResult`. Never raises (spec §5.8)."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.aggregate import aggregate
from agent.judge import run_judge
from agent.checker import CheckOutcome, run_checks
from agent.runlog import RUNS_PATH, append_run
from common.config import RULES_PATH, Config, load_config
from common.llm import LLM, Usage, cost_usd
from common.schemas import (ClassifierInfo, JudgeInfo, ModelsUsed, RunResult, RunUsage, Timings)

log = logging.getLogger("agent")

__all__ = ["check", "acheck"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_run(text: str, outcome: CheckOutcome, llm: Optional[LLM], config: Optional[Config],
               run_id: str, started_at: str, total_ms: int, judge: Optional[JudgeInfo] = None,
               judge_ms: Optional[int] = None) -> RunResult:
    by_id = {r.id: r for r in outcome.selected_rules}
    for res in outcome.results:
        rule = by_id.get(res.rule_id)
        if rule:
            res.title, res.source_ref, res.severity = rule.title, rule.source_ref, rule.severity
    verdict, summary = aggregate(outcome.results, outcome.errors)

    c = outcome.classifier
    classifier = (ClassifierInfo(status=c.status, probabilities=c.probabilities, threshold=c.threshold,
                                 tags=c.tags, fallback_all_rules=c.fallback_all_rules) if c else ClassifierInfo())
    latencies = [r.latency_ms for r in outcome.results]

    usage = Usage()
    cost = 0.0
    if llm:
        for model, u in llm.total_usage.items():
            usage += u
            cost += cost_usd(model, u)
    if c and config:  # the Decisions API call is not tracked by the LLM wrapper
        usage.input += c.input_tokens
        cost += cost_usd(config.classifier_model, Usage(input=c.input_tokens))

    return RunResult(
        run_id=run_id, started_at=started_at, finished_at=_now(), input_text=text,
        models=ModelsUsed(fast=config.fast_model, strong=config.strong_model) if config else ModelsUsed(),
        rules_hash=outcome.rules_hash, classifier=classifier,
        selected_rules=[r.id for r in outcome.selected_rules], results=outcome.results,
        verdict=verdict, summary=summary, errors=outcome.errors,
        timings=Timings(
            total_ms=total_ms, classify_ms=c.latency_ms if c else 0, prewarm_ms=outcome.prewarm_ms,
            checks_wall_ms=outcome.checks_wall_ms,
            rule_latency_avg_ms=int(sum(latencies) / len(latencies)) if latencies else 0,
            rule_latency_max_ms=max(latencies, default=0), judge_ms=judge_ms),
        usage=RunUsage(input=usage.input, cached=usage.cached, cache_write=usage.cache_write,
                       output=usage.output, cost_usd=round(cost, 6)),
        judge=judge or JudgeInfo(),
    )


async def acheck(text: str, *, config: Optional[Config] = None, llm: Optional[LLM] = None,
                 rules_path: Path = RULES_PATH, log_path: Optional[Path] = RUNS_PATH) -> RunResult:
    """Async twin of `check`. `log_path=None` skips the run log (used by eval)."""
    run_id, started_at, t0 = str(uuid.uuid4()), _now(), time.perf_counter()
    outcome = CheckOutcome(text=text if isinstance(text, str) else "")
    try:
        config = config or (llm.config if llm else load_config())
        llm = llm or LLM(config)
        outcome = await run_checks(text, config=config, llm=llm, rules_path=rules_path)
    except Exception as e:  # noqa: BLE001 - error contract
        outcome.errors.append(f"agent: {type(e).__name__}: {e}")
    judge, judge_ms = JudgeInfo(), None
    if llm and config and outcome.catalog and outcome.results:  # monitoring only; never touches the verdict
        judge, judge_ms = await run_judge(llm, config, outcome.text, outcome.catalog, outcome.results)
    try:
        run = _build_run(outcome.text, outcome, llm, config, run_id, started_at,
                         int((time.perf_counter() - t0) * 1000), judge, judge_ms)
    except Exception as e:  # noqa: BLE001
        outcome.errors.append(f"report: {type(e).__name__}: {e}")
        run = RunResult(run_id=run_id, started_at=started_at, finished_at=_now(), input_text=outcome.text,
                        verdict="NEEDS_HUMAN_REVIEW", errors=outcome.errors,
                        summary="NEEDS_HUMAN_REVIEW: the run failed before a result could be built.")
    if log_path is not None:
        try:
            append_run(run, log_path)
        except Exception as e:  # noqa: BLE001 - a log failure must not lose the result
            log.warning("cannot append to %s: %s", log_path, e)
            run.errors.append(f"runlog: {type(e).__name__}: {e}")
    return run


def check(text: str, **kwargs) -> RunResult:
    """Check one marketing text against the approved rules. Never raises."""
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(acheck(text, **kwargs))
        # Called from inside a running loop: run on a private loop in a worker thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, acheck(text, **kwargs)).result()
    except Exception as e:  # noqa: BLE001
        now = _now()
        return RunResult(run_id=str(uuid.uuid4()), started_at=now, finished_at=now,
                         input_text=text if isinstance(text, str) else "",
                         verdict="NEEDS_HUMAN_REVIEW", errors=[f"agent: {type(e).__name__}: {e}"],
                         summary="NEEDS_HUMAN_REVIEW: the run failed before a result could be built.")
