"""Offline tests for stage 4: aggregation, cost, report, run log, public check()."""
import json
from types import SimpleNamespace

import agent
from agent.aggregate import aggregate, aggregate_verdict
from agent.report import build_report
from common.config import Config
from common.llm import LLM, Usage, cost_usd
from common.schemas import CheckResponse, RuleResult, RunResult
from tests.test_checker import FakeClient, TEXT, cfg


def res(id_, verdict, severity="blocking", **kw):
    return RuleResult(rule_id=id_, verdict=verdict, severity=severity, source_ref=f"PRIN 2A.{id_} R",
                      title=f"title {id_}", reasoning="because", **kw)


def test_all_pass():
    assert aggregate_verdict([res("a", "pass"), res("b", "pass")], []) == "PASS"


def test_blocking_fail_is_fail():
    assert aggregate_verdict([res("a", "fail"), res("b", "pass")], []) == "FAIL"


def test_blocking_fail_beats_unclear_and_advisory():
    rs = [res("a", "fail"), res("b", "unclear", unclear_reason="model"), res("c", "fail", "advisory")]
    assert aggregate_verdict(rs, []) == "FAIL"


def test_only_advisory_fails_needs_review():
    assert aggregate_verdict([res("a", "fail", "advisory"), res("b", "pass")], []) == "NEEDS_HUMAN_REVIEW"


def test_technical_unclear_only_needs_review():
    rs = [res("a", "pass"), res("b", "unclear", unclear_reason="technical")]
    assert aggregate_verdict(rs, ["check b: down"]) == "NEEDS_HUMAN_REVIEW"


def test_error_or_no_results_is_never_pass():
    assert aggregate_verdict([res("a", "pass")], ["classifier: down"]) == "NEEDS_HUMAN_REVIEW"
    assert aggregate_verdict([], []) == "NEEDS_HUMAN_REVIEW"


def test_summary_template():
    rs = [res("a", "fail", violation_type="content", evidence_quote="get rich"),
          res("b", "fail", "advisory", violation_type="omission"),
          res("c", "unclear", unclear_reason="model"), res("d", "pass")]
    verdict, summary = aggregate(rs, [])
    head, *items = summary.split("\n")
    assert head == "FAIL: 2 of 4 rules failed (1 blocking, 1 advisory); 1 unclear."
    assert '"get rich"' in items[0] and "omission: because" in items[1] and "unclear (model)" in items[2]


def test_cost_usd_cache_factors():
    # 1M input: 100k read from cache, 200k written, 700k plain; 1M output; luna = $0.10 / $0.50
    u = Usage(input=1_000_000, cached=100_000, cache_write=200_000, output=1_000_000)
    assert abs(cost_usd("gpt-6-luna", u) - (0.07 + 0.001 + 0.025 + 0.5)) < 1e-9
    assert cost_usd("unknown-model", u) == 0.0


def test_report_markdown_and_json():
    run = RunResult(run_id="r", started_at="s", finished_at="f", input_text=TEXT, verdict="FAIL",
                    summary="FAIL: 1 of 2 rules failed (1 blocking, 0 advisory); 0 unclear.",
                    results=[res("p", "pass"), res("a", "fail", violation_type="content",
                                                    evidence_quote="get rich", span=[1, 9])])
    md, js = build_report(run)
    assert md.index("| a |") < md.index("| p |")  # fails first
    assert "### a: title a — FAIL" in md and 'Quote: "get rich"' in md and "# Compliance report: FAIL" in md
    assert RunResult.model_validate_json(js) == run


def test_check_end_to_end_with_mock_and_log(tmp_path):
    good = CheckResponse(reasoning="because", violation_type="content", evidence_quote="get rich", verdict="fail")
    llm = LLM(cfg(), client=FakeClient(post={"answers": []}, parse=good))
    log = tmp_path / "runs.jsonl"
    run = agent.check(TEXT, llm=llm, log_path=log)
    assert run.verdict == "FAIL" and run.results and all(r.title and r.source_ref for r in run.results)
    assert run.selected_rules and run.rules_hash and run.judge.status == "not_run"
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    for key in ("run_id", "started_at", "finished_at", "input_text", "models", "rules_hash", "classifier",
                "selected_rules", "results", "verdict", "summary", "errors", "timings", "usage", "judge"):
        assert key in row
    for key in ("total_ms", "classify_ms", "prewarm_ms", "checks_wall_ms", "rule_latency_avg_ms",
                "rule_latency_max_ms", "judge_ms"):
        assert key in row["timings"]
    assert row["results"][0]["prompt"] and row["results"][0]["raw_response"]["verdict"] == "fail"
    assert "cost_usd" in row["usage"]


def test_check_never_raises_on_outage(tmp_path):
    llm = LLM(cfg(), client=FakeClient(post=RuntimeError("down"), parse=RuntimeError("down")))
    run = agent.check(TEXT, llm=llm, log_path=tmp_path / "runs.jsonl")
    assert run.verdict == "NEEDS_HUMAN_REVIEW" and run.errors


def test_check_with_missing_rules(tmp_path):
    run = agent.check(TEXT, llm=LLM(cfg(), client=FakeClient()), rules_path=tmp_path / "x.json", log_path=None)
    assert run.verdict == "NEEDS_HUMAN_REVIEW" and run.errors and not run.results
