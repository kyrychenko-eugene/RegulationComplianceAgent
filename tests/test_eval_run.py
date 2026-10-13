"""Offline tests for `python -m eval run` metrics (fake agent results)."""
from common.schemas import ClassifierInfo, RuleResult, RunResult
from eval.__main__ import eval_report


def _run(verdict, results, probs=None):
    return RunResult(run_id="x", started_at="", finished_at="", input_text="t", verdict=verdict, summary="",
                     results=[RuleResult(rule_id=i, verdict=v) for i, v in results],
                     classifier=ClassifierInfo(status="ok", probabilities=probs or {}, threshold=0.2))


def _rules():
    r = lambda i, scope, tags: {"id": i, "status": "approved", "severity": "blocking", "scope": scope, "tags": tags}  # noqa: E731
    return {"rules": [r("a", "always", []), r("c", "conditional", ["t"])]}


def test_false_pass_not_run_and_threshold():
    golden = {"cases": [
        {"id": "get-rich-tomorrow", "expected_overall": "FAIL", "text": "x", "expectations": [
            {"concept": "k", "provision": "P", "expected": "fail", "rule_ids": ["a", "c"], "known_gap": False}]},
        {"id": "ok", "expected_overall": "PASS", "text": "y", "expectations": [
            {"concept": "k2", "provision": "P", "expected": "pass", "rule_ids": ["a"], "known_gap": False}]}]}
    runs = {"get-rich-tomorrow": _run("PASS", [("a", "pass")], {"t": 0.3}),
            "ok": _run("PASS", [("a", "fail")], {"t": 0.0})}
    rep = eval_report(golden, _rules(), runs)
    assert "**False PASS rate** (expected fail, rule returned pass): **1/2 (50.0%)**" in rep
    assert "rule not run (classifier did not select it): 1/2" in rep
    assert "False FAIL rate (expected pass, rule returned fail): 1/1" in rep
    assert "| 0.3 | 0 | 0 |" in rep and "| 0.35 | 1 | 0 | get-rich-tomorrow |" in rep
    assert "Recommended `CLASSIFIER_THRESHOLD`: 0.3**" in rep
    assert "Reference case overall verdict: **PASS**" in rep
