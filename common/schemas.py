"""Shared contract between ingest and the agent: `rules.json` (spec §4.3)."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Marker = Literal["R", "G", "E"]
Score = Literal[1, 2, 3]


class Critic(BaseModel):
    """Critic rubric, 1 (poor) .. 3 (good). `notes` comes first so the model reasons before scoring."""

    notes: str
    faithful: Score
    atomic: Score
    checkable_from_text: Score


class Rule(BaseModel):
    id: str
    source_ref: str
    source_quote: str
    title: str
    check: str
    applies_when: str
    scope: Literal["always", "conditional"]
    scope_rationale: str
    tags: List[str] = Field(default_factory=list)
    severity: Literal["blocking", "advisory"]
    severity_basis: str
    pass_example: str
    fail_example: str
    critic: Optional[Critic] = None
    attempts: int = 1
    status: Literal["approved", "rejected"]
    rejection_reason: Optional[str] = None


class DroppedProvision(BaseModel):
    provision_id: str
    marker: Marker
    rationale: str


class Meta(BaseModel):
    source: str
    source_url: str
    generated_at: str
    strong_model: str
    prompt_versions: dict


class RulesFile(BaseModel):
    meta: Meta
    rules: List[Rule]
    dropped_provisions: List[DroppedProvision]


class CheckResponse(BaseModel):
    """Structured output of one rule check (spec §5.4). Field order is intentional: reason, then decide."""

    reasoning: str
    violation_type: Literal["none", "content", "omission"]
    evidence_quote: Optional[str] = None
    verdict: Literal["pass", "fail", "unclear"]


UnclearReason = Literal["model", "invalid_answer", "technical"]


class TokenUsage(BaseModel):
    input: int = 0
    cached: int = 0
    cache_write: int = 0
    output: int = 0


class RuleResult(BaseModel):
    """Normalised, code-validated result for one rule (spec §5.6)."""

    rule_id: str
    verdict: Literal["pass", "fail", "unclear"]
    unclear_reason: Optional[UnclearReason] = None
    reasoning: str = ""
    violation_type: Literal["none", "content", "omission"] = "none"
    evidence_quote: Optional[str] = None
    span: Optional[List[int]] = None
    downgraded: bool = False
    latency_ms: int = 0
    usage: TokenUsage = Field(default_factory=TokenUsage)
