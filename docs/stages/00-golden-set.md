# Stage 0 — Golden set (before ingest)

Block: A. Data · Status: done

## Goal
Write the evaluation cases and their expectations **before** any rule is generated, so the golden set tests both extraction and runtime instead of being fitted to the generated rules' wording.

## Depends on
Nothing. Spec §3.3 and §8.1.

## Produces
- `eval/golden.json` — 10–12 cases in the format of spec §8.1, `rule_ids` left empty.

## Scope
- Cases across formats: ad, landing page, push notification, email, social post, product description.
- Must include:
  - the reference case "Install our app and get rich tomorrow 🚀🚀🚀" (expected FAIL; misleading returns PRIN 2A.5.3(2) R, not properly informed PRIN 2A.5.3(1)(c) R, urgency/emotional exploitation PRIN 2A.2.3(b) G and 2A.2.10(2) G);
  - a compliant text (expected PASS);
  - borderline: risk disclaimer present but buried; "up to 12% p.a." with no risks; FOMO / social proof; jargon without explanation (PRIN 2A.5.7 G);
  - a case where conditional rules should not apply.
- Each expectation: plain-language concept + PRIN 2A provision + expected `fail`/`pass`.

## Out of scope
Mapping to `rule_id` (stage 2). Running anything.

## Done when
- `eval/golden.json` exists and validates against the schema in spec §8.1.
- Every case has `expected_overall` and at least one expectation.
- Committed before stage 1 starts (commit history shows the order).

## Execution log
_Executor model:_ written with Claude (Opus) from the spec, reviewed by the human; the log was not filled at the time and is reconstructed in stage 9 from git history.
_Review findings (stage 9):_ Done-when verified from history: commit `eabca8f` (2026-10-13 17:32) adds `eval/golden.json` with 23 cases and zero `rule_ids`, 15 minutes before the first ingest commit `c78e5d9` (17:47). 23 cases instead of the 10–12 targeted, covering push, email, landing page, social, ad and product page. Labels were not changed after any eval run.
_Fixes:_ none. Note: the early commits are labelled `stage 1: golden dataset` / `stage 2: ingest` / `stage 1: data rules`, not the `stage-NN:` prefix from `CLAUDE.md`; the order of work is still readable.
