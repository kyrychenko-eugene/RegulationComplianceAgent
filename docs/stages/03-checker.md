# Stage 3 — Checker: classifier, parallel checks, validation, error contract

Block: B. Agent · Status: pending

## Goal
Given a marketing text, select the relevant approved rules and get a validated per-rule verdict for each, without ever raising an exception.

## Depends on
Stage 1 (`common/`, `data/rules.json`). Spec §5.1–5.6, §5.8.

## Produces
- `agent/classifier.py`, `agent/checker.py`, `agent/validate.py`.
- `prompts/agent/classify_tags.md`, `prompts/agent/check_system.md`, `prompts/agent/check_rule.md` (rule template rendered as readable text).
- `common/schemas.py` extended: `CheckResponse`, `RuleResult`.

## Scope
1. **Classifier via OpenAI Decisions API** (`CLASSIFIER_MODEL`, `POST /v1/decisions`, spec §5.1): one `predicate` question per tag, `instructions` built from the `applies_when` of rules carrying the tag. Code selects tags with `P(tag) ≥ CLASSIFIER_THRESHOLD`, ignores answer names outside the vocabulary. Error, `refusal` or missing answers → run all approved rules (`fallback_all_rules: true`).
2. **Selection** (code): `always` ∪ `conditional` matching tags.
3. **Prompt**: developer message = shared system prompt + marketing text → explicit cache breakpoint → rule block last. `CheckResponse` field order: `reasoning`, `violation_type`, `evidence_quote`, `verdict`.
4. **Caching**: if `PROMPT_CACHE=on`, one prewarm request for the shared prefix before fan-out; log `cached_tokens` and `cache_write_tokens` per call.
5. **Parallel checks** bounded by the semaphore; SDK retries with backoff.
6. **Validation** exactly per the table in spec §5.6; `span` computed by code for `content` fails; `downgraded` flag when code overrides the model.
7. **Error contract**: missing/broken `rules.json`, API outage, invalid JSON, timeout → structured result, `unclear` with `unclear_reason: technical`, error recorded. No exception escapes.

## Out of scope
Aggregation, report, run log (stage 4). Judge (stage 6).

## Done when
- A function returns a `RuleResult` per selected rule for the reference case, with at least two `fail` verdicts from R provisions.
- Unit tests (no API): validation table — each row of spec §5.6 has a test; span computation; threshold selection and fallback logic on mocked Decisions responses (including `refusal`).
- Test with a forced API failure (e.g. invalid key or mocked client): results are `unclear` / `technical`, no exception.
- `NOTES.md`: classifier probabilities for the reference case; measured shared-prefix size in tokens and whether prewarm produced `cached_tokens > 0`.

## Execution log
_Executor model:_ —
_Review findings:_ —
_Fixes:_ —
