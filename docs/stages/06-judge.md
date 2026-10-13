# Stage 6 — Judge and calibration

Block: C. Agent verification · Status: pending

## Goal
Add an LLM judge that monitors each run — missed rules (classifier recall) and disputed verdicts — with the rating computed by code and no influence on the agent's verdict. Measure how far the judge can be trusted.

## Depends on
Stages 4 and 5. Spec §6.

## Produces
- `agent/judge.py`, `prompts/judge/judge.md`.
- Judge block written into each `runs.jsonl` line.
- Judge calibration added to `eval run` output.

## Scope
1. Judge (STRONG_MODEL) input: system description, marketing text, catalog of **all** approved rules (id, title, check), agent's per-rule results.
2. Structured output, `reasoning` first: `missed_rules[{rule_id, reason}]`, `disputed_verdicts[{rule_id, agent_verdict, judge_verdict, reason}]`.
3. Code filters ids not in the catalog; computes rating: none → `agree`; only advisory → `partial`; any blocking → `disagree`.
4. Runs after aggregation; never changes `verdict`. Failure → `judge.status = unavailable`, run otherwise unaffected.
5. Timing `judge_ms` and usage logged.
6. `eval run`: share of cases where the judge's rating is consistent with golden labels.

## Out of scope
Multiple judge samples / averaging. Numeric scores.

## Done when
- Each new run line contains a judge block with `status`, `rating`, both lists.
- Unit tests (no API): rating computation for all three outcomes; unknown-id filtering.
- Forced judge failure leaves the agent verdict and report unchanged.
- `eval run` prints judge agreement; result noted in `NOTES.md`.

## Execution log
_Executor model:_ —
_Review findings:_ —
_Fixes:_ —
