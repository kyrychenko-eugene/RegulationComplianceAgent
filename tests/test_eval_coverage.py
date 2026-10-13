"""Offline tests for `python -m eval coverage`."""
import json

from common.config import RULES_PATH
from eval.__main__ import GOLDEN_PATH, coverage_report, load_json


def _rule(rid, status="approved"):
    return {"id": rid, "status": status, "source_ref": "ref", "scope": "always"}


def _case(expectations):
    return {"id": "c1", "expectations": expectations}


def _exp(expected="fail", rule_ids=(), known_gap=False):
    return {"concept": "x", "provision": "P", "expected": expected,
            "rule_ids": list(rule_ids), "known_gap": known_gap}


def test_report_sections_and_counts():
    golden = {"cases": [_case([_exp("fail", ["a"]), _exp("pass", ["b"]), _exp("fail"),
                               _exp("fail", [], True), _exp("fail", ["gone"])])]}
    rules = {"rules": [_rule("a"), _rule("b"), _rule("gone", "rejected")]}
    report = coverage_report(golden, rules)
    assert "== 2." in report and "== 3." in report and "== 4." in report
    assert "  b  (" in report.split("== 2.")[1].split("== 3.")[0]
    assert "1 rules never expected to fail; 1 unmapped; 1 known gaps; 1 unknown rule_ids." in report


def test_real_golden_mapping_is_consistent():
    golden, rules = load_json(GOLDEN_PATH), load_json(RULES_PATH)
    approved = {r["id"] for r in rules["rules"] if r["status"] == "approved"}
    for c in golden["cases"]:
        for e in c["expectations"]:
            assert set(e["rule_ids"]) <= approved
            assert bool(e["rule_ids"]) != e["known_gap"], (c["id"], e["concept"])
            if e["known_gap"]:
                assert e.get("gap_note")
    json.dumps(golden)
