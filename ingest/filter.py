"""Relevance filter: keep | drop per provision against the domain statement."""
from __future__ import annotations

import asyncio
from typing import List, Literal, Tuple

from pydantic import BaseModel

from common.llm import LLM
from common.prompts import load_prompt
from common.schemas import DroppedProvision
from ingest.split import Provision

PROMPT = "ingest/filter"


class FilterDecision(BaseModel):
    rationale: str  # first: the model reasons before deciding
    decision: Literal["keep", "drop"]


def render_provision(p: Provision) -> str:
    return (
        f"Provision: PRIN {p.provision_id} ({p.marker})\n"
        f"Section: {p.section}\n"
        f"Text: {p.text}"
    )


async def filter_provisions(
    llm: LLM, provisions: List[Provision]
) -> Tuple[List[Provision], List[DroppedProvision], List[str]]:
    system = load_prompt(PROMPT)
    results = await asyncio.gather(
        *(
            llm.parse(
                model=llm.config.strong_model,
                system=system,
                user=render_provision(p),
                schema=FilterDecision,
            )
            for p in provisions
        ),
        return_exceptions=True,
    )
    kept: List[Provision] = []
    dropped: List[DroppedProvision] = []
    failed: List[str] = []
    for p, r in zip(provisions, results):
        if isinstance(r, BaseException):
            # A provision must never be lost to a failed call: keep it, later stages decide.
            kept.append(p)
            failed.append(f"{p.provision_id}: {type(r).__name__}: {r}")
            continue
        d: FilterDecision = r.parsed  # type: ignore[assignment]
        if d.decision == "keep":
            kept.append(p)
        else:
            rationale = d.rationale.strip() or "dropped by the relevance filter (no rationale given)"
            dropped.append(
                DroppedProvision(
                    provision_id=p.provision_id, marker=p.marker, rationale=rationale
                )
            )
    return kept, dropped, failed
