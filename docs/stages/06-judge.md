# Stage 6 — Judge and calibration

Block: C. Agent verification · Status: done (calibration measured in stage 9)

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
_Executor model:_ Sonnet 5.5
_Review findings:_ none yet (no separate review pass).
_Fixes:_ existing end-to-end test expected `judge.status == not_run`; its fake client answers the judge call with a `CheckResponse`, so the judge now degrades to `unavailable` there. Test updated; it doubles as a forced-failure check.
_Not done:_ the 23-case `eval run` was stopped by the user to save cost; only the reference case was run live. Judge agreement over the full golden set is therefore not yet measured.
_Stage 9 follow-up:_ full calibration run on 23 cases: rule-level consistency with labels 12/23; judge's implied overall verdict matches labels 18/23 (agent 17/23) and the agent's verdict 21/23. The judge now runs in the background by default, and a verdict-level comparison (`overall_verdict`, `verdict_agrees`) was added. See `docs/final-review.md` §5.
