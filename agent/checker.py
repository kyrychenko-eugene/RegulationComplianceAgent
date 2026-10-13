"""Per-rule checks: shared prefix + rule last, prewarm, bounded fan-out, validation (spec §5.3–5.8).

`run_checks` never raises: every failure becomes `unclear` / `technical` plus an `errors` entry.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from agent.classifier import ClassifierResult, classify, select_rules
from agent.validate import technical_result, validate_answer
from common.config import RULES_PATH, Config, load_config
from common.llm import LLM, Usage
from common.prompts import load_prompt
from common.schemas import CheckResponse, Rule, RulesFile, RuleResult, TokenUsage

log = logging.getLogger("agent.checker")

SYSTEM_PROMPT = "agent/check_system"
RULE_PROMPT = "agent/check_rule"
CALL_TIMEOUT_S = 90
# Explicit-caching marker attached to the last shared content part (spec §5.5).
CACHE_BREAKPOINT = {"prompt_cache_breakpoint": {"mode": "explicit"}}


@dataclass
class CheckOutcome:
    """Everything stage 4 needs to aggregate, report and log a run."""

    text: str
    rules_hash: str = ""
    classifier: Optional[ClassifierResult] = None
    selected_rules: List[Rule] = field(default_factory=list)
    results: List[RuleResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    prewarm_ms: int = 0
    prewarm_usage: TokenUsage = field(default_factory=TokenUsage)
    checks_wall_ms: int = 0


def load_rules(path=RULES_PATH) -> Tuple[List[Rule], str]:
    """Approved rules and the file hash. Raises on a missing or broken file (caller catches)."""
    raw = path.read_bytes()
    rules_file = RulesFile.model_validate_json(raw)
    return [r for r in rules_file.rules if r.status == "approved"], hashlib.sha256(raw).hexdigest()[:12]


def render_rule(rule: Rule) -> str:
    out = load_prompt(RULE_PROMPT)
    values = {
        "id": rule.id, "title": rule.title, "source_ref": rule.source_ref, "check": rule.check,
        "applies_when": rule.applies_when, "source_quote": rule.source_quote,
        "fail_example": rule.fail_example, "pass_example": rule.pass_example,
    }
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


def shared_prefix(text: str, cache: bool) -> list:
    """Developer message: shared system prompt + marketing text, breakpoint on the last part."""
    text_part = {"type": "input_text", "text": f"## Marketing text under review\n\n{text}"}
    if cache:
        text_part = {**text_part, **CACHE_BREAKPOINT}
    return [{
        "role": "developer",
        "content": [{"type": "input_text", "text": load_prompt(SYSTEM_PROMPT)}, text_part],
    }]


def _usage(u: Usage) -> TokenUsage:
    return TokenUsage(input=u.input, cached=u.cached, cache_write=u.cache_write, output=u.output)


async def _check_one(llm: LLM, prefix: list, rule: Rule, text: str) -> RuleResult:
    t0 = time.perf_counter()
    try:
        rule_text = render_rule(rule)
        res = await asyncio.wait_for(
            llm.parse_input(
                model=llm.config.fast_model,
                input=prefix + [{"role": "user", "content": rule_text}],
                schema=CheckResponse,
            ),
            CALL_TIMEOUT_S,
        )
        usage = _usage(res.usage)
        log.info("rule=%s cached_tokens=%d cache_write_tokens=%d input=%d",
                 rule.id, usage.cached, usage.cache_write, usage.input)
        result = validate_answer(rule.id, res.parsed, text, latency_ms=res.latency_ms, usage=usage)  # type: ignore[arg-type]
        result.prompt = "\n\n".join(part["text"] for part in prefix[0]["content"]) + "\n\n" + rule_text
        result.raw_response = res.parsed.model_dump()
        return result
    except Exception as e:  # noqa: BLE001 - error contract: nothing escapes
        return technical_result(rule.id, f"{type(e).__name__}: {e}" or type(e).__name__,
                                int((time.perf_counter() - t0) * 1000))


async def run_checks(
    text: str, *, config: Optional[Config] = None, llm: Optional[LLM] = None, rules_path=RULES_PATH
) -> CheckOutcome:
    """Classify, select, check in parallel, validate. Never raises."""
    outcome = CheckOutcome(text=text)
    try:
        config = config or (llm.config if llm else load_config())
        llm = llm or LLM(config)
        try:
            rules, outcome.rules_hash = load_rules(rules_path)
        except Exception as e:  # noqa: BLE001
            outcome.errors.append(f"rules: cannot load {rules_path}: {type(e).__name__}: {e}")
            return outcome
        if not rules:
            outcome.errors.append("rules: no approved rules in rules file")
            return outcome

        outcome.classifier = await classify(llm, text, rules)
        if outcome.classifier.error:
            outcome.errors.append(f"classifier: {outcome.classifier.error} (running all approved rules)")
        outcome.selected_rules = select_rules(rules, outcome.classifier.tags, outcome.classifier.fallback_all_rules)

        prefix = shared_prefix(text, config.prompt_cache)
        if config.prompt_cache:
            t0 = time.perf_counter()
            try:
                u = await asyncio.wait_for(llm.prewarm(model=config.fast_model, input=prefix), CALL_TIMEOUT_S)
                outcome.prewarm_usage = _usage(u)
                log.info("prewarm cached_tokens=%d cache_write_tokens=%d input=%d", u.cached, u.cache_write, u.input)
            except Exception as e:  # noqa: BLE001 - prewarm is an optimisation only
                outcome.errors.append(f"prewarm: {type(e).__name__}: {e}")
            outcome.prewarm_ms = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        outcome.results = list(await asyncio.gather(
            *(_check_one(llm, prefix, r, text) for r in outcome.selected_rules)
        ))
        outcome.checks_wall_ms = int((time.perf_counter() - t0) * 1000)
        for r in outcome.results:
            if r.unclear_reason == "technical":
                outcome.errors.append(f"check {r.rule_id}: {r.reasoning}")
    except Exception as e:  # noqa: BLE001
        outcome.errors.append(f"agent: {type(e).__name__}: {e}")
        done = {r.rule_id for r in outcome.results}
        if not outcome.results:
            outcome.results = [technical_result(r.id, f"{type(e).__name__}: {e}")
                               for r in outcome.selected_rules if r.id not in done]
    return outcome
