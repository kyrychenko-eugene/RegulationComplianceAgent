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
    # Rule metadata copied in by `agent.check` so a RunResult is self-contained (report, log, UI).
    title: str = ""
    source_ref: str = ""
    severity: Literal["blocking", "advisory"] = "blocking"  # unknown severity is treated conservatively
    # Run log material (spec §7): the full prompt sent and the model's raw structured answer.
    prompt: str = ""
    raw_response: Optional[dict] = None


Verdict = Literal["PASS", "FAIL", "NEEDS_HUMAN_REVIEW"]


class ModelsUsed(BaseModel):
    fast: str = ""
    strong: str = ""


class ClassifierInfo(BaseModel):
    status: str = "not_run"  # ok | fallback | not_run
    probabilities: dict = Field(default_factory=dict)
    threshold: float = 0.0
    tags: List[str] = Field(default_factory=list)
    fallback_all_rules: bool = False


class Timings(BaseModel):
    total_ms: int = 0
    classify_ms: int = 0
    prewarm_ms: int = 0
    checks_wall_ms: int = 0
    rule_latency_avg_ms: int = 0
    rule_latency_max_ms: int = 0
    judge_ms: Optional[int] = None


class RunUsage(TokenUsage):
    cost_usd: float = 0.0


class JudgeInfo(BaseModel):
    """Monitoring block (spec §6). `pending` while the judge runs in the background."""

    status: Literal["not_run", "pending", "ok", "unavailable"] = "not_run"
    # Rule level: none involved → agree; only advisory → partial; any blocking → disagree.
    rating: Optional[Literal["agree", "partial", "disagree"]] = None
    # Verdict level: the overall verdict code computes from the judge's per-rule verdicts, and whether it
    # equals the agent's. Rule-level disputes can leave the overall verdict unchanged.
    overall_verdict: Optional[Verdict] = None
    verdict_agrees: Optional[bool] = None
    missed_rules: List[dict] = Field(default_factory=list)
    disputed_verdicts: List[dict] = Field(default_factory=list)
    reasoning: str = ""


class RunResult(BaseModel):
    """What `agent.check(text)` always returns (spec §7)."""

    run_id: str
    started_at: str
    finished_at: str
    input_text: str
    models: ModelsUsed = Field(default_factory=ModelsUsed)
    rules_hash: str = ""
    classifier: ClassifierInfo = Field(default_factory=ClassifierInfo)
    selected_rules: List[str] = Field(default_factory=list)
    results: List[RuleResult] = Field(default_factory=list)
    verdict: Verdict
    summary: str
    errors: List[str] = Field(default_factory=list)
    timings: Timings = Field(default_factory=Timings)
    usage: RunUsage = Field(default_factory=RunUsage)
    judge: JudgeInfo = Field(default_factory=JudgeInfo)
