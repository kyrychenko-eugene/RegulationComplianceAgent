# Stage 1 — Ingest with shared foundation → `rules.json`

Block: A. Data · Status: pending

## Goal
Turn PS22/9 (PRIN 2A text in Appendix 1) into a reviewed set of atomic, checkable rules in `data/rules.json`, through a one-time script. Build the minimal shared foundation that ingest and the agent will both use.

## Depends on
Stage 0 committed. Spec §3, §4, §10.

## Produces
- `common/config.py` — loads `.env` (`OPENAI_API_KEY`, `FAST_MODEL`, `STRONG_MODEL`, `MAX_CONCURRENCY`, `PROMPT_CACHE`, `SOURCE_PDF`), dated price table.
- `common/llm.py` — OpenAI client (Responses API, structured outputs via Pydantic), `asyncio.Semaphore(MAX_CONCURRENCY)`, SDK `max_retries`, usage capture (`input`, `cached`, `cache_write`, `output`).
- `common/schemas.py` — `Rule`, `DroppedProvision`, `RulesFile` (spec §4.3).
- `ingest/` — `load.py`, `split.py`, `filter.py`, `extract.py`, `gate.py`, `__main__.py`.
- `prompts/ingest/filter.md`, `extract.md`, `critic.md`.
- `data/rules.json` (committed).
- `.env.example`, `requirements.txt` (or `pyproject.toml`).

## Scope
1. Load the PDF (`SOURCE_PDF`, path or URL); locate PRIN 2A in Appendix 1 by heading search.
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
_Executor model:_ —
_Review findings:_ —
_Fixes:_ —
