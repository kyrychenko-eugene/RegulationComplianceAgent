"""Extract 0..n atomic rules per kept provision."""
from __future__ import annotations

import asyncio
import re
from typing import List, Literal, Tuple

from pydantic import BaseModel

from common.llm import LLM
from common.prompts import load_prompt
from common.schemas import Rule
from ingest.filter import render_provision
from ingest.split import Provision

PROMPT = "ingest/extract"

SEVERITY = {"R": "blocking", "G": "advisory", "E": "advisory"}
MARKER_LABEL = {"R": "rule", "G": "guidance", "E": "evidential provision"}


class ExtractedRule(BaseModel):
    sub_ref: str
    source_quote: str
    title: str
    check: str
    applies_when: str
    scope: Literal["always", "conditional"]
    scope_rationale: str
    tags: List[str]
    pass_example: str
    fail_example: str


class Extraction(BaseModel):
    rules: List[ExtractedRule]


def severity_for(marker: str) -> str:
    """Severity is decided by code from the marker: R -> blocking, G/E -> advisory."""
    return SEVERITY[marker]


def _letter(n: int) -> str:
    return chr(ord("a") + n) if n < 26 else str(n)


def build_rules(p: Provision, extraction: Extraction) -> List[Rule]:
    """Turn the model's draft into `Rule`s; ids, source_ref and severity come from code."""
    rules: List[Rule] = []
    counters: dict = {}
    for er in extraction.rules:
        sub = re.sub(r"\s+", "", er.sub_ref)
        n = counters.get(sub, 0)
        counters[sub] = n + 1
        sub_id = sub.replace(")(", "").strip("()")
        rule_id = f"PRIN{p.provision_id}" + (f"-{sub_id}" if sub_id else "") + f"-{_letter(n)}"
        sev = severity_for(p.marker)
        rules.append(
            Rule(
                id=rule_id,
                source_ref=f"PRIN {p.provision_id}{sub} {p.marker}",
                source_quote=er.source_quote.strip(),
                title=er.title.strip(),
                check=er.check.strip(),
                applies_when=er.applies_when.strip(),
                scope=er.scope,
                scope_rationale=er.scope_rationale.strip(),
                tags=[t.strip() for t in er.tags if t.strip()],
                severity=sev,
                severity_basis=f"Marker {p.marker} on PRIN {p.provision_id}: {MARKER_LABEL[p.marker]} -> {sev}",
                pass_example=er.pass_example.strip(),
                fail_example=er.fail_example.strip(),
                status="rejected",  # draft: only the gate can approve
                rejection_reason="not gated",
            )
        )
    return rules


async def extract_rules(
    llm: LLM, provisions: List[Provision]
) -> Tuple[List[List[Rule]], List[str]]:
    """One list of draft rules per provision, in input order, plus failed provisions.

    A failed provision yields an empty list and is reported, never silently skipped.
    """
    system = load_prompt(PROMPT)
    results = await asyncio.gather(
        *(
            llm.parse(
                model=llm.config.strong_model,
                system=system,
                user=render_provision(p),
                schema=Extraction,
            )
            for p in provisions
        ),
        return_exceptions=True,
    )
    drafts: List[List[Rule]] = []
    failed: List[str] = []
    for p, r in zip(provisions, results):
        if isinstance(r, BaseException):
            drafts.append([])
            failed.append(f"{p.provision_id}: {type(r).__name__}: {r}")
        else:
            drafts.append(build_rules(p, r.parsed))  # type: ignore[arg-type]
    return drafts, failed
