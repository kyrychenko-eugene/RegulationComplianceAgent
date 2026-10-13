# Stage 5 — Eval run: false PASS rate and per-rule accuracy

Block: C. Agent verification · Status: done

## Goal
Measure how well the agent does on the golden set, with false PASS (missed violations) as the primary metric.

## Depends on
Stages 2 and 4. Spec §8.3.

## Produces
- `eval/__main__.py` `run` mode.
- `examples/eval_report.md` — committed results of a full run.

## Scope
- Runs each golden case through the public `agent.check()` (no access to internals).
- Prints:
  - **false PASS rate**: expected `fail` expectations where the mapped rule returned `pass`;
  - false FAIL rate (expected `pass` returned `fail`);
  - `unclear` rate, by `unclear_reason`;
  - per-rule agreement table;
  - overall-verdict agreement per case;
  - classifier threshold sweep (0.05…0.5): misses of required conditional rules vs extra checks; recommended threshold = highest with zero misses;
  - `known_gap` items on a separate line, not counted as errors.
- Reuses `MAX_CONCURRENCY`; cases may run sequentially.

## Out of scope
Judge calibration (stage 6). Tuning prompts beyond fixing clear bugs (record ideas in `NOTES.md`).

## Done when
- `python -m eval run` completes on all cases and prints the metrics above.
- The reference case's overall verdict is FAIL.
- Recommended `CLASSIFIER_THRESHOLD` written to `.env.example` and `NOTES.md`.
- Results committed as `examples/eval_report.md`; notable failures discussed in `NOTES.md`.

## Execution log
_Executor model:_ Claude Sonnet 5.5 (claude-sonnet-5-5).
_Review findings:_ none (no separate reviewer); 60 offline tests pass; live run of all 23 cases, reference case FAIL, results in `examples/eval_report.md`.
_Fixes:_ none needed. Recommended threshold 0.5 (sweep saturated, see NOTES.md); httpx teardown noise on stderr left as is.
