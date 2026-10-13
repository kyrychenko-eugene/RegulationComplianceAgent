"""Offline tests for the ingest pipeline: mocked OpenAI client, synthetic source text."""
import asyncio
from types import SimpleNamespace

import pytest

from common.config import Config
from common.llm import LLM, LLMError
from common.schemas import Critic, Rule
from ingest.__main__ import IngestIncomplete, assert_quotes_verbatim, run_ingest
from ingest.extract import ExtractedRule, Extraction, build_rules
from ingest.filter import FilterDecision
from ingest.gate import decide, deterministic_failures
from ingest.load import SourceError, locate_prin2a
from ingest.split import Provision, split_provisions

PAGES = [
    "cover\nAppendix 1\nMade rules (legal instrument)",
    "FCA 2022/31\nInsert the following new chapter PRIN 2A, after PRIN 2.\n"
    "2A The Consumer Duty \n2A.1 Application and purpose\n Application \n"
    "Page 13 of 68 \n"
    "2A.1.1 R References in PRIN to the obligations on firms\nunder Principle 12 apply.\n"
    " Manufacturers: product approval process for products that are not closed\n"
    "products\n"
    "2A.5.3 R (1) A firm must support retail customer understanding so that its\n"
    "communications:\n   (c) equip retail customers to make decisions that are effective, \n"
    "timely and properly informed.\n  (2) A firm must communicate information to retail customers in a way\n"
    "which is clear, fair and not misleading.\n"
    "2A.2.3 G Examples include seeking to exploit emotions.\n"
    "Amend the following as shown.\n2A.9.9 R not part of the chapter\n",
]


def config():
    return Config("k", "fast", "cls", 0.2, "strong", 3, True)


def test_locate_and_split():
    text = locate_prin2a(PAGES)
    assert "Page 13" not in text and "FCA 2022/31" not in text
    assert "2A.9.9" not in text
    ps = split_provisions(text)
    assert [(p.provision_id, p.marker) for p in ps] == [("2A.1.1", "R"), ("2A.5.3", "R"), ("2A.2.3", "G")]
    assert ps[0].section == "2A.1 Application and purpose"
    assert ps[0].text == "References in PRIN to the obligations on firms under Principle 12 apply."
    assert "Manufacturers" not in ps[0].text and "products" not in ps[0].text.split("apply")[-1]
    assert "(c) equip retail customers to make decisions that are effective, timely" in ps[1].text


def test_locate_fails_loudly():
    with pytest.raises(SourceError):
        locate_prin2a(["nothing here"])


def provision():
    return split_provisions(locate_prin2a(PAGES))[1]  # 2A.5.3 R


def draft(**kw):
    base = dict(
        sub_ref="(2)",
        source_quote="A firm must communicate information to retail customers in a way which is clear, fair and not misleading.",
        title="Clear, fair, not misleading",
        check="Does the communication avoid presenting returns as certain?",
        applies_when="all marketing communications",
        scope="always",
        scope_rationale="Any communication.",
        tags=[],
        pass_example="Past performance is no guide.",
        fail_example="Guaranteed 20% returns.",
    )
    base.update(kw)
    return ExtractedRule(**base)


def rules_for(*drafts, p=None):
    return build_rules(p or provision(), Extraction(rules=list(drafts)))


def test_build_rules_ids_refs_severity():
    rs = rules_for(draft(), draft(sub_ref="(1)(c)"), draft())
    assert [r.id for r in rs] == ["PRIN2A.5.3-2-a", "PRIN2A.5.3-1c-a", "PRIN2A.5.3-2-b"]
    assert rs[0].source_ref == "PRIN 2A.5.3(2) R" and rs[1].source_ref == "PRIN 2A.5.3(1)(c) R"
    assert all(r.severity == "blocking" for r in rs)
    g = split_provisions(locate_prin2a(PAGES))[2]
    assert rules_for(draft(sub_ref=""), p=g)[0].severity == "advisory"
    assert rules_for(draft(sub_ref=""), p=g)[0].id == "PRIN2A.2.3-a"


def failures(rule, seen=()):
    return deterministic_failures(rule, provision(), set(seen))


def test_gate_accepts_good_rule():
    assert failures(rules_for(draft())[0]) == []


@pytest.mark.parametrize(
    "kw,needle",
    [
        (dict(source_quote="A firm must never mislead anyone."), "verbatim"),
        (dict(source_quote="  A firm must communicate   information to retail customers in a way which is clear, fair and not misleading."), None),
        (dict(scope="conditional", tags=[]), "no tags"),
        (dict(scope="conditional", tags=["Not Snake"]), "snake_case"),
        (dict(check="Is it clear? Is it fair?"), "one question"),
        (dict(check="Does it state this"), "one question"),
        (dict(check="Does it avoid hype, promises, and guarantees?"), "enumeration"),
        (dict(check="Does it avoid hype; and does it warn?"), "enumeration"),
        (dict(pass_example=" "), "empty pass_example"),
    ],
)
def test_gate_rejections(kw, needle):
    f = failures(rules_for(draft(**kw))[0])
    if needle is None:
        assert f == []
    else:
        assert any(needle in x for x in f), f


def test_gate_marker_mismatch_and_duplicate_id():
    r = rules_for(draft())[0].model_copy(update={"source_ref": "PRIN 2A.5.3(2) G"})
    assert any("does not match" in x for x in failures(r))
    assert any("malformed" in x for x in failures(r.model_copy(update={"source_ref": "bogus"})))
    assert any("duplicate" in x for x in failures(rules_for(draft())[0], seen={"PRIN2A.5.3-2-a"}))


def test_decide_thresholds():
    r = rules_for(draft())[0]
    ok = Critic(notes="fine", faithful=2, atomic=3, checkable_from_text=2)
    assert decide(r, [], ok).status == "approved"
    bad = Critic(notes="needs board report", faithful=3, atomic=3, checkable_from_text=1)
    out = decide(r, [], bad)
    assert out.status == "rejected" and "checkable_from_text=1" in out.rejection_reason
    out = decide(r, ["check: x"], ok)
    assert out.status == "rejected" and out.rejection_reason.startswith("check: x")


class FakeResponses:
    def __init__(self):
        self.calls = []

    async def parse(self, *, model, input, text_format):
        self.calls.append((model, text_format))
        if text_format is FilterDecision:
            pid = input[1]["content"].split("PRIN ")[1].split(" ")[0]
            parsed = FilterDecision(
                rationale="internal" if pid == "2A.1.1" else "about communications",
                decision="drop" if pid == "2A.1.1" else "keep",
            )
        elif text_format is Extraction:
            gm = "2A.5.3" in input[1]["content"]
            parsed = Extraction(
                rules=[draft(), draft(sub_ref="(1)(c)", source_quote="not in the source")]
                if gm
                else []
            )
        else:
            parsed = Critic(notes="ok", faithful=3, atomic=3, checkable_from_text=3)
        usage = SimpleNamespace(
            input_tokens=100, output_tokens=10,
            input_tokens_details=SimpleNamespace(cached_tokens=40),
        )
        return SimpleNamespace(output_parsed=parsed, usage=usage, status="completed")


def fake_llm():
    return LLM(config(), client=SimpleNamespace(responses=FakeResponses()))


def test_pipeline_end_to_end():
    llm = fake_llm()
    rf, stats = asyncio.run(run_ingest(config(), llm, PAGES, "x.pdf"))
    assert stats["provisions_total"] == 3
    assert stats["provisions_kept"] == 2 and stats["provisions_dropped"] == 1
    assert stats["kept_with_zero_rules"] == 1
    assert stats["rules_approved"] == 1 and stats["rules_rejected"] == 1
    rejected = [r for r in rf.rules if r.status == "rejected"][0]
    assert "verbatim" in rejected.rejection_reason
    assert rf.dropped_provisions[0].rationale
    assert set(rf.meta.prompt_versions) == {"ingest/filter", "ingest/extract", "ingest/critic"}
    assert llm.total_usage["strong"].cached > 0
    RulesFile = type(rf)
    RulesFile.model_validate_json(rf.model_dump_json())


def test_limit_and_verbatim_assertion():
    rf, stats = asyncio.run(run_ingest(config(), fake_llm(), PAGES, "x", limit=1))
    assert stats["provisions_processed"] == 1 and stats["provisions_total"] == 3
    rf.rules.append(rules_for(draft(source_quote="invented"))[0].model_copy(update={"status": "approved"}))
    with pytest.raises(AssertionError):
        assert_quotes_verbatim(rf, locate_prin2a(PAGES))


def test_llm_error_on_empty_parse():
    class Empty:
        async def parse(self, **kw):
            return SimpleNamespace(output_parsed=None, usage=None, status="incomplete")

    llm = LLM(config(), client=SimpleNamespace(responses=Empty()))
    with pytest.raises(LLMError):
        asyncio.run(llm.parse(model="m", system="s", user="u", schema=FilterDecision))


class FailingResponses(FakeResponses):
    """Fails calls for one schema; everything else behaves normally."""

    def __init__(self, fail_on):
        super().__init__()
        self.fail_on = fail_on

    async def parse(self, *, model, input, text_format):
        if text_format is self.fail_on:
            raise RuntimeError("boom")
        return await super().parse(model=model, input=input, text_format=text_format)


def failing_llm(fail_on):
    return LLM(config(), client=SimpleNamespace(responses=FailingResponses(fail_on)))


def test_filter_failure_keeps_provisions():
    rf, stats = asyncio.run(run_ingest(config(), failing_llm(FilterDecision), PAGES, "x"))
    assert stats["provisions_kept"] == 3 and stats["provisions_dropped"] == 0
    assert len(stats["filter_failed_kept"]) == 3


def test_critic_failure_rejects_rule_with_reason():
    rf, stats = asyncio.run(run_ingest(config(), failing_llm(Critic), PAGES, "x"))
    assert stats["rules_approved"] == 0 and stats["rules_rejected"] == 2
    assert all("critic: no score" in r.rejection_reason for r in rf.rules)


def test_extract_failure_aborts_without_output():
    with pytest.raises(IngestIncomplete, match="2A.5.3"):
        asyncio.run(run_ingest(config(), failing_llm(Extraction), PAGES, "x"))


def test_draft_rules_are_never_born_approved():
    assert rules_for(draft())[0].status == "rejected"
