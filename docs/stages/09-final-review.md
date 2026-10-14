# Stage 9 — Final review, README, NOTES

Block: Optional / closing · Status: done

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
_Executor model:_ Claude Opus 5.5 (claude-opus-5-5).
_Review findings:_ 16 issues, listed in `docs/final-review.md` §6. Main ones: serial pipeline plus a synchronous judge (≈ 25 s per run); concurrency 5 for ~18 rules; the History judge banner presented rule-level disputes as verdict disagreement; over-strict language rules (the "instrument" case); no README; NOTES wrongly claimed the threshold had been changed; stage logs incomplete. The task PDF could not be read (image-only, extraction not permitted), so the checklist uses the requirements quoted in this file and spec §14.
_Fixes:_ concurrent classifier/prewarm with early `always` checks; `MAX_CONCURRENCY=20`; background judge keyed by `run_id`, with `agent.read_runs()` merging the record; verdict-level judge comparison (code) in the UI and report; Materiality section in the check prompt; bounded client close; README; NOTES correction and stage 9 section; stage 0/6/8 logs; spec §2.1/§5.3/§6/§7/§10 and `CLAUDE.md` updated. 75 offline tests; clean-copy quickstart verified; full eval re-run (`examples/eval_report.md`).
_Open (owner's decisions):_ golden NEEDS_HUMAN_REVIEW labels vs blocking R rules; rule-set cleanup (stage 8 or a manual edit); confirming blocking fails with a second call; the `5.3-2-a` golden mapping.
