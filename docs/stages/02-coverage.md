# Stage 2 — Coverage: golden set ↔ rules

Block: A. Data · Status: done

## Goal
Before any agent code exists, answer: do the extracted rules cover what we want to catch? Map golden expectations to approved `rule_id`s and report gaps — a data check with no API calls.

## Depends on
Stage 0 (`eval/golden.json`), stage 1 (`data/rules.json`). Spec §8.1–8.2.

## Produces
- `eval/golden.json` updated: `rule_ids` filled for each expectation; `known_gap: true` (with a note) where no rule fits.
- `eval/__main__.py` with the `coverage` mode.

## Scope
- `python -m eval coverage` prints:
  - matrix rules × cases (expected fail / pass / not targeted);
  - approved rules with no case expecting `fail`;
  - expectations mapped to no rule;
  - `known_gap` items listed separately.
- No OpenAI calls; runs without an API key.

## Out of scope
Running the agent on cases (stage 5).

## Done when
- `python -m eval coverage` runs offline and prints all four sections.
- Every approved rule is expected to `fail` in at least one case, or the exception is explained in `NOTES.md`.
- Any expectation without a rule is either a `known_gap` (documented) or triggers a fix in stage 1.

## Execution log
_Executor model:_ Claude Sonnet 5.5
_Review findings:_ No separate reviewer run. Self-check: `python -m eval coverage` prints all four sections offline (run with `OPENAI_API_KEY` unset); 24 tests pass. Mapping is my judgement, so it needs a human read of `eval/golden.json` (`rule_ids` per expectation).
_Fixes:_ Matrix-cell formatting simplified after a first awkward version. Added optional `gap_note` field to expectations (not in spec §8.1 example) to hold the known-gap note.
