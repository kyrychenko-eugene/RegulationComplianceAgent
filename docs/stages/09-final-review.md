# Stage 9 — Final review, README, NOTES

Block: Optional / closing · Status: pending

## Goal
Check the result against this spec and the original task with a strong model (Opus), fix what it finds, and write the thinking doc.

## Depends on
All completed stages. Spec §1, §13, §14. Task PDF (deliverables and "what we care about").

## Produces
- `docs/final-review.md` — review report: spec conformance, task-requirement checklist, issues found, what was fixed.
- `README.md` per spec §14.
- `NOTES.md` cleaned up (findings, surprises, AI mistakes caught).
- `CLAUDE.md` — context file used by the coding agents.
- Status and execution log filled in every `docs/stages/*.md`; cut stages marked "cut" with reason.

## Scope
- Review against the task's requirements: real source; structured rule decomposition with visible choice; per-rule verdict with reasoning; clean separable stages; prompt design; framework justification; scoped recall; repo hygiene (no keys, `.env.example`, BYOK).
- Verify BYOK from a clean clone: two-command quickstart works, `rules.json` committed, sample history present.
- README covers: what was built and cut, key prompt design decisions, what to do differently with more time, one surprise, time spent vs the 2–3 h box, how AI was used.

## Done when
- `docs/final-review.md` committed with an issue list and resolutions.
- Clean-clone check passes: `pip install -r requirements.txt`, set key, `python -m agent "…"` prints a report.
- No secrets in git history.
- README answers every "Thinking Doc" bullet from the task.

## Execution log
_Executor model:_ —
_Review findings:_ —
_Fixes:_ —
