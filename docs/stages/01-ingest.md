# Stage 1 — Ingest with shared foundation → `rules.json`

Block: A. Data · Status: done, awaiting human review of the rule set

## Goal
Turn PS22/9 (PRIN 2A text in Appendix 1) into a reviewed set of atomic, checkable rules in `data/rules.json`, through a one-time script. Build the minimal shared foundation that ingest and the agent will both use.

## Depends on
Stage 0 committed. Spec §3, §4, §10.

## Produces
- `common/config.py` — loads `.env` (`OPENAI_API_KEY`, `FAST_MODEL`, `STRONG_MODEL`, `MAX_CONCURRENCY`, `PROMPT_CACHE`) and the `SOURCE_PDF` default constant. The dated price table moved to stage 4 (first needed for run-log cost).
- `common/llm.py` — OpenAI client (Responses API, structured outputs via Pydantic), `asyncio.Semaphore(MAX_CONCURRENCY)`, SDK `max_retries`, usage capture (`input`, `cached`, `cache_write`, `output`).
- `common/schemas.py` — `Rule`, `DroppedProvision`, `RulesFile` (spec §4.3).
- `ingest/` — `load.py`, `split.py`, `filter.py`, `extract.py`, `gate.py`, `__main__.py`.
- `prompts/ingest/filter.md`, `extract.md`, `critic.md`.
- `data/rules.json` (committed).
- `.env.example`, `requirements.txt` (or `pyproject.toml`).

## Scope
1. Load the PDF (`SOURCE_PDF` default, `--source` path or URL); locate PRIN 2A in Appendix 1 by heading search.
2. Split into provisions `{provision_id, marker R|G|E, section, text}`.
3. Relevance filter per provision against the domain statement (spec §4.1); keep `dropped_provisions` with rationale.
4. Extract 0..n rules per kept provision; `check` is one atomic yes/no question; propose `scope` + `scope_rationale`, `tags`, pass/fail examples.
5. Severity by code from the marker: R → `blocking`, G/E → `advisory`.
6. Deterministic checks (spec §4.4): verbatim `source_quote`, marker matches source, schema, unique ids, tags on conditional rules, single question.
7. Critic rubric (faithful / atomic / checkable_from_text, 1–3). Approved only if all checks pass and all scores ≥ 2; otherwise `rejected` with reason (single attempt — retry is stage 8).
8. Write `rules.json` with `meta` (source, url, generated_at, strong_model, prompt_versions).

## Out of scope
Retry loop (stage 8). Agent runtime code. UI.

## Done when
- `python -m ingest` produces `data/rules.json` from a clean checkout with only `OPENAI_API_KEY` set.
- Every approved rule's `source_quote` is found verbatim in the source (assert in code).
- `dropped_provisions` and rejected rules each have a non-empty reason.
- Rules exist that cover PRIN 2A.5.3(1)(c), 2A.5.3(2), and 2A.2.3(b) or 2A.2.10(2) — or the gap is recorded in `NOTES.md`.
- `NOTES.md` records counts: provisions total / kept / dropped; rules approved / rejected.

## Execution log
_Executor model:_ Claude Sonnet 5.5.
_Review findings:_ Second full run is the committed `data/rules.json`: 169 provisions → 15 kept / 154 dropped; 34 rules drafted, 27 approved, 7 rejected (details and per-rule review in `NOTES.md`). Done-when met: `python -m ingest` runs; every approved quote is asserted verbatim; dropped/rejected all carry reasons; coverage for 2A.5.3(1)(c), 2A.5.3(2), 2A.2.3(b), 2A.2.10(2) present. First run had missed 2A.5.3(1)(c) and 2A.5.8; the cause was the extractor quoting bare list items (see below). Open quality issues for the human: vague/overlapping 2A.5.3(1)(c) rules, 2A.5.9(2) one-to-one-dialogue rules (blocking), duplicate 2A.5.7(3), fragmented tags, large run-to-run variance.
_Fixes:_ Splitter sub-heading wrap; failure handling in filter/extract/critic; `--only` flag; `extract.md` now requires the quote to include the lead-in clause for list items.
