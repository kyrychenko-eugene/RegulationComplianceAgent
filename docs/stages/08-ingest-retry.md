# Stage 8 — Ingest retry with critic feedback (optional)

Block: Optional (second iteration on data) · Status: postponed

## Goal
Recover rules that failed the quality gate by regenerating them with the critic's feedback, without letting them drift from the source.

## Depends on
Stage 1. Spec §4.2 step 7, §4.4.

## Produces
- Retry loop in `ingest/extract.py` / `ingest/gate.py`.
- `prompts/ingest/regenerate.md`.
- Regenerated `data/rules.json`; `eval coverage` re-run.

## Scope
- A rule failing deterministic checks or scoring < 2 on any critic criterion is regenerated with the failing checks and critic notes, max 2 extra attempts.
- The critic always judges against the **original** `source_quote` and provision text, never the previous version (anti-drift).
- After the final attempt: `status: rejected`, `rejection_reason`, `attempts` recorded.

## Out of scope
Human approval.

## Done when
- `rules.json` shows `attempts` per rule; rejected rules have a reason.
- `NOTES.md` compares approved counts before/after retry.
- `python -m eval coverage` still passes its checks.

## Postponed
Decision (2026-10-14): scope reduced; this stage was optional from the beginning and is postponed. Nothing in it was built. README lists it under "with more time".

## If cut
Keep this file with status "cut" and the reason; README lists it under "with more time".

## Execution log
_Executor model:_ — (not run, postponed)
_Review findings:_ —
_Fixes:_ —
