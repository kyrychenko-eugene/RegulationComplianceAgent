# Regulation Compliance Agent

LLM compliance officer for retail investment marketing: checks a marketing text rule by rule against FCA PS22/9 (PRIN 2A) and returns per-rule verdicts with evidence. The design is settled in `docs/spec.md`; it is the single source of truth. Work is delivered in stages, one stage per session.

## Running a stage

1. Read `docs/spec.md` and your stage file `docs/stages/NN-*.md`.
2. Build only what the stage file lists under **Produces** and **Scope**; leave other stages' files untouched.
3. Meet every **Done when** criterion and run each check yourself; a criterion counts as met when its command has run and the output confirms it.
4. Fill the stage file's **Execution log** (executor model, review findings, fixes) and set its status.
5. Add findings to `NOTES.md`: measured numbers, surprises, places where generated output was wrong and how it was caught.
6. Stop and report. The human commits with the prefix `stage-NN:`.

When the spec and the code disagree, or the spec is silent on a decision that matters, stop and ask instead of choosing; record the answer in the spec.

## Invariants

- **Deterministic outcome.** LLMs make narrow judgments (tag probabilities, one rule's verdict). Code decides selection, validation, aggregation and the judge rating.
- **Never raise.** `agent.check(text)` always returns a `RunResult`; any failure becomes `unclear` (`technical`) plus an entry in `errors`, and a run with a technical problem is at most `NEEDS_HUMAN_REVIEW`.
- **One-way dependencies:** `ingest → data/rules.json → agent → eval / ui`. The agent imports only `common/`; eval and UI call the public `agent.check()` and read files.
- **Prompts are documents.** Every prompt lives in `prompts/` as its own `.md` file, loaded by code.
- **Verbatim evidence.** Quotes from the source and from the marketing text are checked by code with exact (whitespace-normalised) matching.
- **APIs:** classification uses the OpenAI Decisions API; every other LLM call uses the Responses API with Pydantic structured outputs. Raw `openai` SDK, no orchestration framework.
- **Secrets:** config comes from `.env` (see `.env.example`); keys stay out of code, logs and commits.

## Tests

Unit tests run offline with a mocked OpenAI client (`pytest`). Calls that need a real key are marked and skipped when `OPENAI_API_KEY` is unset.
