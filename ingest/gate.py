"""Quality gate (spec §4.4): deterministic checks, then the critic rubric."""
from __future__ import annotations

import asyncio
import re
from typing import Dict, List, Optional, Set

from common.llm import LLM
from common.prompts import load_prompt
from common.schemas import Critic, Rule
from ingest.split import Provision, normalise

PROMPT = "ingest/critic"
MIN_SCORE = 2

SOURCE_REF_RE = re.compile(r"^PRIN (2A\.\d+\.\d+)((?:\([0-9A-Za-z]+\))*) ([REG])$")
TAG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# Enumeration heuristics for "single question": "a, b, and c", "(a)", semicolons.
ENUMERATION_RE = re.compile(r",[^,?]*,\s*(and|or)\b|\([a-z0-9]\)|;", re.I)


def deterministic_failures(rule: Rule, provision: Provision, seen_ids: Set[str]) -> List[str]:
    """Return a list of failed-check descriptions; empty means all passed."""
    failures: List[str] = []

    # schema: Rule construction already validated types; check required text is not blank
    for name in ("source_quote", "title", "check", "applies_when", "scope_rationale",
                 "pass_example", "fail_example"):
        if not getattr(rule, name).strip():
            failures.append(f"schema: empty {name}")

    # verbatim quote (whitespace-normalised, against this rule's provision)
    quote = normalise(rule.source_quote)
    if not quote:
        failures.append("source_quote: empty")
    elif quote not in provision.text:
        failures.append("source_quote: not found verbatim in the source provision")

    # marker in source_ref matches the marker next to the provision in the source
    m = SOURCE_REF_RE.match(rule.source_ref)
    if not m:
        failures.append(f"source_ref: malformed '{rule.source_ref}'")
    elif m.group(1) != provision.provision_id or m.group(3) != provision.marker:
        failures.append(
            f"source_ref: '{rule.source_ref}' does not match source "
            f"PRIN {provision.provision_id} {provision.marker}"
        )

    # unique id
    if rule.id in seen_ids:
        failures.append(f"id: duplicate '{rule.id}'")

    # tags
    if rule.scope == "conditional" and not rule.tags:
        failures.append("tags: conditional rule has no tags")
    for t in rule.tags:
        if not TAG_RE.match(t):
            failures.append(f"tags: '{t}' is not lowercase snake_case")

    # single question
    if rule.check.count("?") != 1 or not rule.check.rstrip().endswith("?"):
        failures.append("check: must be exactly one question ending with '?'")
    elif ENUMERATION_RE.search(rule.check):
        failures.append("check: looks like an enumeration of several conditions")

    return failures


def render_for_critic(rule: Rule) -> str:
    return (
        f"Source reference: {rule.source_ref}\n"
        f'Source quote: "{rule.source_quote}"\n'
        f"Title: {rule.title}\n"
        f"Check: {rule.check}\n"
        f"Applies when: {rule.applies_when}\n"
        f"Pass example: {rule.pass_example}\n"
        f"Fail example: {rule.fail_example}"
    )


async def run_critic(llm: LLM, rule: Rule) -> Critic:
    r = await llm.parse(
        model=llm.config.strong_model,
        system=load_prompt(PROMPT),
        user=render_for_critic(rule),
        schema=Critic,
    )
    return r.parsed  # type: ignore[return-value]


def decide(
    rule: Rule, failures: List[str], critic: Optional[Critic], critic_error: str = ""
) -> Rule:
    """Approved only if every deterministic check passes and every critic score >= 2."""
    reasons = list(failures)
    if critic is None:
        reasons.append(f"critic: no score ({critic_error or 'not run'})")
    else:
        low = [
            f"{name}={score}"
            for name, score in (
                ("faithful", critic.faithful),
                ("atomic", critic.atomic),
                ("checkable_from_text", critic.checkable_from_text),
            )
            if score < MIN_SCORE
        ]
        if low:
            reasons.append(f"critic: {', '.join(low)} ({critic.notes.strip()})")
    update = {"critic": critic}
    if reasons:
        update.update(status="rejected", rejection_reason="; ".join(reasons))
    else:
        update.update(status="approved", rejection_reason=None)
    return rule.model_copy(update=update)


async def gate_rules(
    llm: LLM, per_provision: List[List[Rule]], provisions: List[Provision]
) -> List[Rule]:
    """Gate every drafted rule (single attempt; retry is stage 8)."""
    by_pid: Dict[str, Provision] = {p.provision_id: p for p in provisions}
    seen: Set[str] = set()
    drafts: List[tuple] = []
    for p, rules in zip(provisions, per_provision):
        for r in rules:
            drafts.append((r, deterministic_failures(r, by_pid[p.provision_id], seen)))
            seen.add(r.id)
    critics = await asyncio.gather(*(run_critic(llm, r) for r, _ in drafts), return_exceptions=True)
    out: List[Rule] = []
    for (r, f), c in zip(drafts, critics):
        if isinstance(c, BaseException):
            out.append(decide(r, f, None, f"{type(c).__name__}: {c}"))  # rejected, not lost
        else:
            out.append(decide(r, f, c))
    return out
