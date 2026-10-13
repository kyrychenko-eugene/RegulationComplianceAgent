"""Offline tests for the judge: rating, id filtering, failure isolation (no API)."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import agent
from agent.judge import DisputedVerdict, JudgeResponse, MissedRule, rate, render_input, run_judge
from common.config import Config
from common.schemas import JudgeInfo, Rule, RuleResult, RunResult


def _rule(i, sev):
    return Rule(id=i, source_ref="PRIN 2A", source_quote="q", title=i, check="c?", applies_when="all",
                scope="always", scope_rationale="r", severity=sev, severity_basis="b", pass_example="p",
                fail_example="f", status="approved")


CFG = Config("k", "fast", "cls", 0.2, "strong", 3, True)
CATALOG = [_rule("b1", "blocking"), _rule("a1", "advisory"), _rule("a2", "advisory")]
RESULTS = [RuleResult(rule_id="b1", verdict="pass", reasoning="ok"), RuleResult(rule_id="a1", verdict="fail")]


def _resp(missed=(), disputed=()):
    return JudgeResponse(reasoning="r", missed_rules=[MissedRule(rule_id=i, reason="x") for i in missed],
                         disputed_verdicts=[DisputedVerdict(rule_id=i, agent_verdict="pass", judge_verdict=v, reason="x")
                                            for i, v in disputed])


def test_rating_agree():
    j = rate(_resp(), CATALOG, RESULTS)
    assert (j.status, j.rating, j.missed_rules, j.disputed_verdicts) == ("ok", "agree", [], [])


def test_rating_partial_only_advisory():
    assert rate(_resp(missed=["a2"]), CATALOG, RESULTS).rating == "partial"
    assert rate(_resp(disputed=[("a1", "pass")]), CATALOG, RESULTS).rating == "partial"


def test_rating_disagree_any_blocking():
    assert rate(_resp(disputed=[("b1", "fail")]), CATALOG + [], RESULTS).rating == "disagree"
    assert rate(_resp(missed=["a2"], disputed=[("b1", "fail")]), CATALOG, RESULTS).rating == "disagree"
    cat = [_rule("b2", "blocking")] + CATALOG
    assert rate(_resp(missed=["b2"]), cat, RESULTS).rating == "disagree"


def test_unknown_ids_filtered_before_rating():
    j = rate(_resp(missed=["ghost"], disputed=[("ghost2", "fail")]), CATALOG, RESULTS)
    assert j.rating == "agree" and j.missed_rules == [] and j.disputed_verdicts == []


def test_nonsense_entries_dropped():
    # "missed" rule that was run; dispute of a rule not run; dispute that equals the agent's verdict
    j = rate(_resp(missed=["b1"], disputed=[("a2", "fail"), ("b1", "pass")]), CATALOG, RESULTS)
    assert j.rating == "agree"


def test_disputed_agent_verdict_comes_from_run():
    j = rate(_resp(disputed=[("a1", "pass")]), CATALOG, RESULTS)
    assert j.disputed_verdicts[0]["agent_verdict"] == "fail"


def test_render_marks_not_run():
    out = render_input("hello", CATALOG, RESULTS)
    assert "a2 [advisory] a2 — c?  (NOT RUN)" in out and "b1: pass — ok" in out


class _Boom:
    config = CFG

    async def parse(self, **kw):
        raise RuntimeError("down")


def test_judge_failure_is_unavailable():
    info, ms = asyncio.run(run_judge(_Boom(), CFG, "t", CATALOG, RESULTS))
    assert info.status == "unavailable" and info.rating is None and ms is not None


def test_forced_judge_failure_leaves_run_unchanged(monkeypatch, tmp_path: Path):
    """Same checker outcome with a working and a failing judge: verdict, summary, errors identical."""
    from agent.checker import CheckOutcome

    async def fake_checks(text, **kw):
        return CheckOutcome(text=text, catalog=CATALOG, selected_rules=CATALOG[:2], results=[
            RuleResult(rule_id="b1", verdict="pass", reasoning="ok"),
            RuleResult(rule_id="a1", verdict="fail", reasoning="bad", violation_type="omission")])

    monkeypatch.setattr(agent, "run_checks", fake_checks)
    cfg = CFG
    llm = SimpleNamespace(config=cfg, total_usage={})

    async def good(*a, **k):
        return JudgeInfo(status="ok", rating="disagree", disputed_verdicts=[{"rule_id": "b1"}]), 5

    async def bad(*a, **k):
        return await run_judge(_Boom(), cfg, "t", CATALOG, RESULTS)

    runs = []
    for judge in (good, bad):
        monkeypatch.setattr(agent, "run_judge", judge)
        runs.append(asyncio.run(agent.acheck("t", config=cfg, llm=llm, log_path=tmp_path / "r.jsonl")))
    ok, down = runs
    assert ok.judge.status == "ok" and down.judge.status == "unavailable"
    assert (ok.verdict, ok.summary, ok.errors) == (down.verdict, down.summary, down.errors)
    assert down.errors == [] and down.verdict == "NEEDS_HUMAN_REVIEW"
    assert '"judge":{"status":"unavailable"' in (tmp_path / "r.jsonl").read_text().splitlines()[-1]
