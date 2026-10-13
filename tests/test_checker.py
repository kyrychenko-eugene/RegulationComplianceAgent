"""Offline tests for stage 3: validation table, spans, classifier selection/fallback, error contract."""
import asyncio
from types import SimpleNamespace

import pytest

from agent.checker import load_rules, render_rule, run_checks, shared_prefix
from agent.classifier import classify, interpret_answers, select_rules, tag_vocabulary
from agent.validate import find_span, validate_answer
from common.config import RULES_PATH, Config
from common.llm import LLM
from common.schemas import CheckResponse, Rule

TEXT = "Install our app and\n get rich   tomorrow 🚀🚀🚀"


def cfg(cache=True):
    return Config("k", "fast", "cls", 0.2, "strong", 3, cache)


def resp(verdict, vt="none", quote=None, reasoning="because"):
    return CheckResponse(reasoning=reasoning, violation_type=vt, evidence_quote=quote, verdict=verdict)


def rule(id_, scope="always", tags=()):
    return Rule(id=id_, source_ref="PRIN 2A.1 R", source_quote="q", title="t", check="c?", applies_when="uses emojis.",
                scope=scope, scope_rationale="r", tags=list(tags), severity="blocking", severity_basis="b",
                pass_example="p", fail_example="f", status="approved")


# --- validation table (spec §5.6), one test per row ---

def test_pass_with_reasoning():
    r = validate_answer("r", resp("pass"), TEXT)
    assert (r.verdict, r.unclear_reason, r.downgraded) == ("pass", None, False)


def test_pass_without_reasoning_is_invalid():
    r = validate_answer("r", resp("pass", reasoning="  "), TEXT)
    assert (r.verdict, r.unclear_reason, r.downgraded) == ("unclear", "invalid_answer", True)


def test_fail_content_verbatim_gets_span():
    r = validate_answer("r", resp("fail", "content", "get rich tomorrow"), TEXT)
    assert r.verdict == "fail" and r.span is not None and not r.downgraded
    assert TEXT[r.span[0]:r.span[1]] == "get rich   tomorrow"


def test_fail_content_quote_not_in_text():
    r = validate_answer("r", resp("fail", "content", "get rich today"), TEXT)
    assert (r.verdict, r.unclear_reason, r.downgraded, r.span) == ("unclear", "invalid_answer", True, None)


def test_fail_content_without_quote():
    assert validate_answer("r", resp("fail", "content", None), TEXT).unclear_reason == "invalid_answer"


def test_fail_content_without_reasoning():
    assert validate_answer("r", resp("fail", "content", "get rich", reasoning=""), TEXT).unclear_reason == "invalid_answer"


def test_fail_omission_ignores_quote():
    r = validate_answer("r", resp("fail", "omission", "made up text"), TEXT)
    assert (r.verdict, r.evidence_quote, r.span) == ("fail", None, None)


def test_fail_omission_without_reasoning():
    assert validate_answer("r", resp("fail", "omission", reasoning=""), TEXT).unclear_reason == "invalid_answer"


def test_fail_with_violation_none():
    r = validate_answer("r", resp("fail", "none"), TEXT)
    assert (r.verdict, r.unclear_reason, r.downgraded) == ("unclear", "invalid_answer", True)


def test_unclear_is_model():
    r = validate_answer("r", resp("unclear"), TEXT)
    assert (r.verdict, r.unclear_reason, r.downgraded) == ("unclear", "model", False)


# --- spans ---

def test_span_whitespace_and_offsets():
    assert find_span("and get rich tomorrow", TEXT) == [TEXT.index("and"), TEXT.index("tomorrow") + 8]
    assert find_span("", TEXT) is None
    assert find_span("GET RICH", TEXT) is None  # exact, case-sensitive


# --- classifier ---

VOCAB = {"a": ["x"], "b": ["y"]}


def ans(name, p):
    return {"type": "predicate", "name": name, "probability": p}


def test_threshold_selection_and_unknown_names_ignored():
    r = interpret_answers([ans("a", 0.2), ans("b", 0.19), ans("zzz", 0.99)], VOCAB, 0.2)
    assert (r.status, r.tags, r.fallback_all_rules) == ("ok", ["a"], False)
    assert "zzz" not in r.probabilities


def test_refusal_falls_back():
    r = interpret_answers([ans("a", 0.9), {"type": "refusal", "name": "b"}], VOCAB, 0.2)
    assert r.fallback_all_rules and r.status == "fallback"


def test_missing_answer_and_garbage_fall_back():
    assert interpret_answers([ans("a", 0.9)], VOCAB, 0.2).fallback_all_rules
    assert interpret_answers(None, VOCAB, 0.2).fallback_all_rules
    assert interpret_answers([ans("a", "high"), ans("b", 0.1)], VOCAB, 0.2).fallback_all_rules


def test_select_rules():
    rs = [rule("al"), rule("c1", "conditional", ["a"]), rule("c2", "conditional", ["b"])]
    assert [r.id for r in select_rules(rs, ["a"], False)] == ["al", "c1"]
    assert [r.id for r in select_rules(rs, [], False)] == ["al"]
    assert [r.id for r in select_rules(rs, [], True)] == ["al", "c1", "c2"]


def test_tag_vocabulary_only_conditional():
    rs = [rule("al", tags=["ignored"]), rule("c1", "conditional", ["a"])]
    assert list(tag_vocabulary(rs)) == ["a"]


class FakeClient:
    def __init__(self, post=None, parse=None):
        self._post, self._parse = post, parse
        self.responses = SimpleNamespace(parse=self._rparse, create=self._rcreate)
        self.posted = []

    async def post(self, path, body=None, cast_to=None):
        self.posted.append((path, body))
        if isinstance(self._post, Exception):
            raise self._post
        return self._post

    async def _rparse(self, **kw):
        if isinstance(self._parse, Exception):
            raise self._parse
        return SimpleNamespace(output_parsed=self._parse, usage=None, status="completed")

    async def _rcreate(self, **kw):
        if isinstance(self._parse, Exception):
            raise self._parse
        return SimpleNamespace(usage=None)


def test_classify_uses_decisions_endpoint():
    rs = [rule("c1", "conditional", ["a"])]
    c = FakeClient(post={"answers": [ans("a", 0.5)], "usage": {"input_tokens": 7}})
    out = asyncio.run(classify(LLM(cfg(), client=c), TEXT, rs))
    assert out.tags == ["a"] and out.input_tokens == 7
    path, body = c.posted[0]
    assert path == "/decisions" and body["model"] == "cls"
    assert body["questions"][0]["type"] == "predicate" and body["questions"][0]["name"] == "a"


def test_classify_api_error_falls_back():
    rs = [rule("c1", "conditional", ["a"])]
    out = asyncio.run(classify(LLM(cfg(), client=FakeClient(post=RuntimeError("down"))), TEXT, rs))
    assert out.fallback_all_rules and "down" in out.error


# --- error contract ---

def test_api_failure_gives_technical_unclear_no_exception():
    llm = LLM(cfg(), client=FakeClient(post=RuntimeError("down"), parse=RuntimeError("down")))
    out = asyncio.run(run_checks(TEXT, llm=llm))
    assert out.results and all(r.verdict == "unclear" and r.unclear_reason == "technical" for r in out.results)
    assert len(out.results) == len(load_rules()[0])  # classifier fallback -> all approved rules
    assert out.errors


def test_missing_rules_file(tmp_path):
    out = asyncio.run(run_checks(TEXT, llm=LLM(cfg(), client=FakeClient()), rules_path=tmp_path / "nope.json"))
    assert out.errors and not out.results


def test_broken_rules_file(tmp_path):
    p = tmp_path / "rules.json"
    p.write_text("{not json")
    out = asyncio.run(run_checks(TEXT, llm=LLM(cfg(), client=FakeClient()), rules_path=p))
    assert out.errors and not out.results


def test_happy_path_validates_with_mock():
    good = resp("fail", "content", "get rich")
    llm = LLM(cfg(), client=FakeClient(post={"answers": []}, parse=good))
    out = asyncio.run(run_checks(TEXT, llm=llm))
    assert out.results and all(r.verdict == "fail" and r.span for r in out.results)
    assert not [e for e in out.errors if not e.startswith("classifier")]


# --- prompt assembly ---

def test_prefix_and_rule_rendering():
    p = shared_prefix(TEXT, True)
    assert "prompt_cache_breakpoint" in p[0]["content"][-1] and TEXT in p[0]["content"][-1]["text"]
    assert "prompt_cache_breakpoint" not in shared_prefix(TEXT, False)[0]["content"][-1]
    rules, _ = load_rules(RULES_PATH)
    text = render_rule(rules[0])
    assert rules[0].id in text and "{" not in text.replace("{}", "")
