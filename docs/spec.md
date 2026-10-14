# Regulation Compliance Agent — Technical Specification

Status: agreed design, pre-implementation. This document is the contract the implementation stages in `docs/stages/` are built against.

## 1. Goal and scope

An LLM-powered tool that acts as a compliance officer for **marketing materials**. It takes a real regulatory source (FCA PS22/9, the Consumer Duty) and a short marketing text, checks the text rule by rule, and returns an explicit verdict per rule with reasoning and evidence.

### 1.1 In scope

- Source: **FCA PS22/9**, specifically the made rules in Appendix 1 (Consumer Duty Instrument 2022, FCA 2022/31), i.e. the text of **PRIN 2A**.
- Input: marketing / promotional communications of a retail investment and trading platform (ads, landing pages, push notifications, emails, social posts). English only.
- Output: per-rule verdict, overall verdict computed by code, Markdown + JSON report, run history.

### 1.2 Deliberately out of scope (and why)

| Excluded | Reason |
|---|---|
| FG22/5 (non-Handbook guidance) | Homework scope. PRIN 2A already covers the target violations (see §3.3). |
| COBS 4 (financial promotions rules, prescribed risk warnings) | Separate regime. We detect missing risk balance through Consumer Duty, not the letter of COBS 4. |
| CySEC / other jurisdictions | Jurisdiction is defined by the source. Switching means swapping the source and one line of domain description. |
| Intent / input-type check | The task guarantees the input is marketing material. |
| Rewrite suggestions (`suggested_fix`) | The task is to check, not to rewrite. Listed under "with more time". |
| Human review of extracted rules | Replaced by an automated quality gate (§4.4). In a real deployment a compliance reviewer would approve rules. |
| Non-English input | Rules and quotes are English; mixing languages adds noise to verbatim quoting. |

## 2. Architecture

Three independent entry points sharing one `.env`. Dependencies point one way:

```
ingest ──► data/rules.json ──► agent ──► eval / ui
```

- `python -m ingest` — one-time preprocessing, builds `data/rules.json`. Uses `STRONG_MODEL`.
- `python -m agent "<text>"` — checks one text, prints the report, appends to `runs.jsonl`.
- `python -m eval coverage` — golden set ↔ rules mapping, no API calls.
- `python -m eval run` — runs the golden set through the agent and prints metrics.
- `streamlit run ui/app.py` — thin UI over the agent's public function and the files.

Rules of separation:
- The only contact point between ingest and agent is `rules.json` and its schema (`common/schemas.py`).
- The agent never imports ingest code. Ingest knows nothing about the agent.
- Eval and UI call the same public function as the CLI (`agent.check(text) -> RunResult`); they do not reach into agent internals.
- The UI contains no business logic. Deleting `ui/` must not affect anything else.

### 2.1 Runtime flow (agent)

```
input text
   │
   ▼
[1] classifier (Decisions API, gpt-6-luna) ──► P(tag) per tag        ┐ run concurrently
   │     code: tags = {t : P(t) ≥ CLASSIFIER_THRESHOLD}                │
   │     on failure / refusal: run ALL approved rules                  │
[3] cache prewarm: shared prefix (system prompt + input text)         ┘
   │     then `always` rule checks start at once (they do not need the classifier)
   ▼
[2] rule selection (code): scope=always ∪ conditional rules matching tags; conditional checks start
   │
   ▼
[4] per-rule checks in parallel (FAST_MODEL, semaphore = MAX_CONCURRENCY ≥ rules per run)
   │
   ▼
[5] validation (code): normalize each answer into pass / fail / unclear
   │
   ▼
[6] aggregation (code): PASS / FAIL / NEEDS_HUMAN_REVIEW + template summary
   │
   ▼
[8] report (Markdown + JSON) and one line appended to runs.jsonl  ──► agent.check() returns here
   │
   ▼ (background thread, same run_id)
[7] judge (STRONG_MODEL): monitoring only, never changes the verdict; appends a judge record to runs.jsonl
```

Latency decision (stage 9, 2026-10-14, requested by the owner): the judge is off the critical path. `agent.check(text, judge=...)`: `background` (default) returns with `judge.status = pending` and appends the judge record later; `sync` waits (used by `eval run`, and automatically when there is no run log); `off` skips it. The CLI prints the verdict first, then waits for the judge and prints it.

LLMs make narrow judgments (which tags, does this one rule pass). Everything that decides the outcome — selection, validation, aggregation, judge rating — is deterministic code.

## 3. Source

### 3.1 Document

- PS22/9 PDF: https://www.fca.org.uk/publication/policy/ps22-9.pdf
- The default URL is the constant `SOURCE_PDF` in `common/config.py` (not an env var); `python -m ingest --source <path|url>` overrides it, so the source is not hard-coded.
- Ingest locates Appendix 1 and the PRIN 2A text by heading search, not by hard-coded page numbers.
- Note for README: the live FCA Handbook has later amendments to PRIN 2A (e.g. 2A.2.4 updated 26/06/2026). We work from the PS22/9 text as published; this is a known, accepted difference.

### 3.2 Unit of processing: the provision

PRIN 2A is numbered by provision (e.g. `PRIN 2A.5.3`), and each provision carries a status marker:
- **R** — rule, binding.
- **G** — guidance.
- (**E** — evidential provision; not observed in PRIN 2A.2 or 2A.5, ingest must still handle it.)

Ingest splits the text into provisions and groups them by section (2A.1 … 2A.11). The provision is the unit for filtering, extraction and `source_ref`.

### 3.3 Coverage of the reference test case

The task's example ("Install our app and get rich tomorrow 🚀🚀🚀") must flag three things. All three are expressible from PRIN 2A:

| Expected violation | Provision(s) | Marker |
|---|---|---|
| Misleading return promise | PRIN 2A.5.3(2) — clear, fair and not misleading | R |
| No risk information / not properly informed decision | PRIN 2A.5.3(1)(c) | R |
| Urgency / excitement signals | PRIN 2A.2.3(b) — exploiting emotions or behavioural biases to mislead or create demand; PRIN 2A.2.10(2) — unfairly exploiting behavioural biases | G |

So no `known_gap` is needed for this case. Consequence of the R/G severity mapping: the urgency check is `advisory`, while the overall verdict is still FAIL via the R provisions. This is a visible, documented design consequence, not a bug.

## 4. Ingest (one-time preprocessing)

### 4.1 Business domain statement (used in the relevance filter prompt)

> Marketing and promotional communications of a retail investment and trading platform to retail customers in the United Kingdom: advertising, landing pages, push notifications, emails, social media posts.

UK is included because the source defines the jurisdiction (FCA, UK retail customers). It also anchors the "average UK retail customer" standard in the check prompt.

### 4.2 Pipeline

1. **Load** PDF → text (`pypdf` or `pdfplumber`). Locate PRIN 2A in Appendix 1.
2. **Split** into provisions: `{provision_id, marker, section, text}`.
3. **Relevance filter** (STRONG_MODEL), per provision: `keep | drop` + `rationale`, against the domain statement. Governance, board reporting, fair value assessment, monitoring processes and similar firm-internal obligations are dropped. Dropped provisions are saved with their rationale (shown in the UI "Rules" tab — visible scoping).
4. **Extract** rules from kept provisions (STRONG_MODEL): one provision may yield 0..n atomic rules.
5. **Deterministic checks** (code), see §4.4.
6. **Critic** (STRONG_MODEL), see §4.4.
7. **Retry** (stage 8, optional): rules that fail 5 or 6 are regenerated with the critic's feedback, max 2 attempts, always judged against the **original** `source_quote` to prevent drift. After that: `status: rejected` with reason.
8. **Write** `data/rules.json`.

### 4.3 Rule schema (`common/schemas.py`)

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable, e.g. `PRIN2A.5.3-2-a` |
| `source_ref` | str | Provision id with marker, e.g. `PRIN 2A.5.3(2) R` |
| `source_quote` | str | **Verbatim** excerpt from the source the rule derives from. Verified by code. |
| `title` | str | Short human label |
| `check` | str | One atomic yes/no question answerable from the marketing text alone. Generated, not copied: the source states obligations ("a firm must…"), not questions. |
| `applies_when` | str | When the rule is relevant. For `always` rules: "all marketing communications". |
| `scope` | `always` \| `conditional` | Proposed by LLM with `scope_rationale`. Heuristic: applies to any customer communication → `always`; depends on content (prices, vulnerability, a product type) → `conditional`. |
| `scope_rationale` | str | |
| `tags` | list[str] | Required for `conditional`. Tag vocabulary is derived from the rules file. |
| `severity` | `blocking` \| `advisory` | Derived from the marker: R → blocking, G (and E) → advisory. |
| `severity_basis` | str | The marker and provision it was derived from. |
| `pass_example` | str | Short example text that passes. Used as few-shot. |
| `fail_example` | str | Short example text that fails. Used as few-shot. |
| `critic` | object | `{faithful, atomic, checkable_from_text: 1..3, notes}` |
| `attempts` | int | Number of generation attempts |
| `status` | `approved` \| `rejected` | Only `approved` rules are loaded at runtime |
| `rejection_reason` | str \| null | |

`rules.json` top level: `{meta: {source, source_url, generated_at, strong_model, prompt_versions}, rules: [...], dropped_provisions: [{provision_id, marker, rationale}]}`. The agent logs a hash of this file with every run.

### 4.4 Quality gate (replaces human review)

**Deterministic checks (code):**
- `source_quote` appears verbatim in the source text (after whitespace normalization).
- The marker in `source_ref` matches the marker next to that provision in the source.
- Schema valid; unique `id`; `conditional` rules have at least one tag.
- `check` is a single question (one `?`, no enumerations of several conditions).

**Critic (STRONG_MODEL), rubric per rule, each scored 1–3 with a note:**
- **faithful** — does the `check` add anything not present in `source_quote`?
- **atomic** — does it test exactly one thing?
- **checkable_from_text** — can it be answered with only the marketing text? This is the key criterion: much of the Consumer Duty concerns firm processes (value assessments, board reports, outcome monitoring) that can never be verified from a marketing text. Such rules must be rejected, and the README says so.

A rule is `approved` only if all deterministic checks pass and every critic score is ≥ 2.

## 5. Agent runtime

### 5.1 Classifier — OpenAI Decisions API

Classification and judgment are different jobs, so they use different APIs:
- **Classification** (which tags apply) → **Decisions API** (`POST /v1/decisions`): returns typed answers with probabilities, no free text.
- **Judgment with evidence** (does this rule pass, why, which quote) → Responses API with structured output (§5.3–5.4). Decisions cannot return reasoning or quotes, which the validation in §5.6 depends on.

Design:
- One `predicate` question per tag in the vocabulary of approved conditional rules. `name` = tag, `instructions` = what the tag means, built from the `applies_when` texts of the rules carrying that tag (`prompts/agent/classify_tags.md` holds the shared wording).
- The API returns `P(tag)` in 0..1 for each tag. **Code** selects `tags = {t : P(t) ≥ CLASSIFIER_THRESHOLD}`. The threshold is deliberately low (default 0.2): over-inclusion costs one extra check, omission costs a missed violation.
- The model cannot invent tags: each tag is a separate named question. Code still ignores any answer whose name is not in the vocabulary.
- Fail-safe: API error, `refusal` answer, or missing answers → **all** approved rules run (not only `always`).
- The threshold is tuned on the golden set (§8.3): the lowest-cost threshold with zero classifier misses on golden cases.
- Facts (OpenAI docs, Oct 2026): public beta; only `gpt-6-luna` supported; billed for input tokens only ($0.10 / 1M); vendor claims ~10× faster than the Responses API; how `probability`/`confidence` are computed and whether they are calibrated is not documented — hence empirical threshold tuning; requires a recent SDK (Python ≥ 3.26.0).

### 5.2 Rule selection (code)

`selected = {r : r.scope == always} ∪ {r : r.scope == conditional and r.tags ∩ tags ≠ ∅}`

### 5.3 Check prompt structure

Order matters for caching: everything shared across rules comes first, the rule comes last.

1. **Developer message — shared, stable across rules** (`prompts/agent/check_system.md`):
   - Role: compliance officer reviewing UK retail marketing under the Consumer Duty.
   - Standard of judgment: how an average UK retail customer would understand the text.
   - Verdict definitions, `content` vs `omission` violations, with examples of each.
   - Quoting rule: `evidence_quote` must be copied character for character, contiguous, no ellipses, no paraphrase, taken **only** from the marketing text; never invent text.
   - Prefer `unclear` over guessing when the text does not contain enough information.
   - Proportionality (stage 5): judge the message, not a full disclosure document; fail an omission only when this message makes the missing item necessary.
   - Materiality (stage 9): fail only what a compliance reviewer would raise; language rules are judged on the message as a whole in its app context, so everyday platform vocabulary is not jargon. Its examples are deliberately not taken from golden texts.
   - Reasoning must be written before the verdict.
2. **The marketing text**, in the same shared block.
   → explicit cache breakpoint here (§5.5).
3. **The rule**, rendered as readable text (not JSON):

```
Rule PRIN2A.5.3-2-a — Clear, fair and not misleading (PRIN 2A.5.3(2) R)
Check: Does the communication avoid presenting returns as certain or guaranteed?
Applies when: all marketing communications
Source: "A firm must communicate information to retail customers in a way which is clear, fair and not misleading."
Example that fails: "..."
Example that passes: "..."
```

### 5.4 Check response schema (structured output)

Field order is intentional: the model generates fields in order, so it reasons before deciding.

| Field | Type |
|---|---|
| `reasoning` | str |
| `violation_type` | `none` \| `content` \| `omission` |
| `evidence_quote` | str \| null |
| `verdict` | `pass` \| `fail` \| `unclear` |

### 5.5 Prompt caching strategy

Facts (OpenAI docs, checked Oct 2026, current model generation):
- Minimum cacheable prefix: 1,024 visible tokens.
- Cache write costs 1.25× the uncached input rate; reads cost 0.1×.
- The implicit breakpoint is placed at the end of the latest eligible message, i.e. after the rule, which differs per call → no reuse by default.
- Parallel calls fired at once can all miss, because none has finished writing the cache.

Design:
- Explicit caching mode with one breakpoint after the shared prefix (system prompt + marketing text).
- One **prewarm** request for the shared prefix before the parallel fan-out.
- The shared system prompt carries rule-agnostic guidance and examples that are useful anyway; whether it crosses 1,024 tokens is measured, not assumed.
- `PROMPT_CACHE=on|off` switch. If the prefix stays under the threshold, caching is off and README reports it.
- `cached_tokens` and `cache_write_tokens` are logged per call; the history tab shows the hit rate.

This is expected to be one of the "surprises" for the README.

### 5.6 Validation (code)

| Model verdict | `violation_type` | Required | Otherwise |
|---|---|---|---|
| `pass` | — | non-empty `reasoning` | `unclear` (`invalid_answer`) |
| `fail` | `content` | non-empty `reasoning` + `evidence_quote` found verbatim in the input | `unclear` (`invalid_answer`) |
| `fail` | `omission` | non-empty `reasoning` naming what is missing; quote ignored | `unclear` (`invalid_answer`) |
| `fail` | `none` / missing | — | `unclear` (`invalid_answer`) |
| `unclear` | — | — | `unclear` (`model`) |
| API error after retries / unparseable | — | — | `unclear` (`technical`) |

For valid `content` failures, code computes `span = [start, end]` of the quote in the input (`str.find` after normalization). The LLM never returns offsets. The UI uses the span for highlighting.

Normalized `RuleResult`: `rule_id, verdict, unclear_reason, reasoning, violation_type, evidence_quote, span, downgraded (bool), latency_ms, usage {input, cached, cache_write, output}`.

### 5.7 Aggregation (code)

```
if any(r.verdict == fail and rule.severity == blocking):  FAIL
elif any(r.verdict == fail) or any(r.verdict == unclear):  NEEDS_HUMAN_REVIEW
else:                                                      PASS
```

A run where something technical broke can never be PASS.

Summary is a code template, no LLM:
`FAIL: 3 of 18 rules failed (2 blocking, 1 advisory); 1 unclear.` followed by the list of failed and unclear rules with `source_ref`, reasoning, and quote or "omission: <what is missing>".

### 5.8 Error contract

The public function never raises. Every path (OpenAI outage, missing or broken `rules.json`, invalid model output, timeout) returns a structured `RunResult` with `errors[]` and a verdict that is at most NEEDS_HUMAN_REVIEW. Retries with exponential backoff come from the SDK (`max_retries`); concurrency is bounded by an `asyncio.Semaphore(MAX_CONCURRENCY)`.

### 5.9 Report

One function builds both outputs:
- **Markdown**: overall verdict and summary; table of all rules (id, title, `source_ref`, severity, verdict); for each `fail` and `unclear`: reasoning, quote or omission note, `unclear_reason`.
- **JSON**: the full `RunResult`.

## 6. Judge (monitoring only)

- Model: STRONG_MODEL (stronger than the checker, otherwise it repeats the same mistakes).
- Input: shared system description, the marketing text, the **catalog of all approved rules** (id, title, check — so it can see what was not run), and the agent's per-rule results.
- Output (structured, `reasoning` first):
  - `missed_rules: [{rule_id, reason}]` — rules that should have been checked but were not run.
  - `disputed_verdicts: [{rule_id, agent_verdict, judge_verdict, reason}]` — only disagreements, agreements are not listed.
- Code filters ids not present in the catalog, then computes the rating:
  - both lists empty → `agree`
  - only advisory rules involved → `partial`
  - any blocking rule missed or disputed → `disagree`
- **Verdict level** (added in stage 9, 2026-10-14): code applies the judge's rule verdicts (disputes replace the agent's verdict; missed rules count with the verdict the judge expects for them, `fail` or `unclear`) and runs the same aggregation (§5.7), giving `overall_verdict` and `verdict_agrees`. The UI and the report show this first and the rule-level rating second, because a judge can dispute single rules and still reach the same overall verdict; showing only the rule-level rating read as "the judge disagrees with the verdict".
- `missed_rules` entries carry `judge_verdict: fail | unclear`.
- The judge never changes the agent's verdict. If the judge call fails, `judge.status = unavailable`. While it runs in the background, `judge.status = pending`.
- Calibration: `eval run` reports how often the judge's rating agrees with the golden labels.

## 7. Run log (`runs.jsonl`)

One JSON object per line, appended. Git-ignored. A sample is committed as `examples/runs.sample.jsonl`; the UI falls back to it (labelled "example") when no own runs exist.

```
run_id, started_at, finished_at,
input_text,
models {fast, strong}, rules_hash,
classifier {status, probabilities {tag: p}, threshold, tags, fallback_all_rules},
selected_rules [ids],
results [RuleResult + full prompt + raw response],
verdict, summary, errors [],
timings {total_ms, classify_ms, prewarm_ms, checks_wall_ms,
         rule_latency_avg_ms, rule_latency_max_ms, judge_ms},
usage {input, cached, cache_write, output, cost_usd},
judge {status, rating, overall_verdict, verdict_agrees, missed_rules, disputed_verdicts, reasoning}
```

With the background judge (§2.1), the run line is written with `judge.status = pending`, and a second line follows when the judge finishes: `{record: "judge", run_id, finished_at, judge {...}, judge_ms, usage {..., cost_usd}}`. `agent.read_runs()` merges it into the run with the same `run_id` (judge block, `timings.judge_ms`, usage and cost added). Readers (UI) go through `agent.read_runs()` rather than parsing lines themselves.

`rule_latency_max_ms` is logged because the parallel stage waits for the slowest call; it explains `checks_wall_ms` better than the average. Cost is computed from a dated price table in `common/config.py`.

## 8. Evaluation

### 8.1 Golden set (`eval/golden.json`), written **before** ingest

Writing cases after seeing the rules would fit them to the rules' wording. So:
1. Before ingest: case texts and expected violations in plain language, each referencing a PRIN 2A provision.
2. After rules are approved: map each expectation to `rule_id`s.
3. An expectation that maps to no rule is a finding about extraction gaps.

```
{ "id": "get-rich-tomorrow",
  "channel": "push notification",
  "text": "Install our app and get rich tomorrow 🚀🚀🚀",
  "expected_overall": "FAIL",
  "acceptable_overall": ["FAIL"],          // optional, for borderline cases
  "notes": "...",                           // optional
  "expectations": [
    { "concept": "misleading promise of returns", "provision": "PRIN 2A.5.3(2)",
      "marker": "R", "kind": "content",     // kind: content | omission
      "expected": "fail", "rule_ids": [], "known_gap": false } ] }
```

Overall-verdict agreement counts a case as correct if the agent's verdict is in `acceptable_overall` (or equals `expected_overall` when the list is absent).

Target: 10–12 cases across formats (ad, landing page, push, email, social, product description): the reference case, a compliant text, borderline cases (disclaimer present but buried; "up to 12% p.a." without risks; social proof / FOMO), and one where conditional rules should not apply. Every approved rule should be expected to `fail` in at least one case.

### 8.2 `eval coverage` (no API)

Coverage matrix rules × cases; lists rules with no failing case, expectations with no mapped rule, and `known_gap` items separately.

### 8.3 `eval run`

- **False PASS rate** (missed violations) — the primary metric; in compliance this is the most expensive error.
- Per-rule agreement with expectations; overall-verdict agreement.
- Judge calibration (§6).
- Classifier threshold sweep: for thresholds 0.05…0.5, the number of conditional rules the golden expectations needed but the classifier did not select, and the number of extra checks run. Recommended threshold = the highest one with zero misses; recorded in `NOTES.md` and `.env.example`.
- `known_gap` items are reported on their own line, not counted as agent errors.

## 9. UI (`ui/`)

Streamlit, minimal but informative. No business logic.
- **Run**: text input → overall verdict, summary, input with highlighted spans, one card per rule (verdict, severity, `source_ref`, reasoning, quote).
- **History**: list of runs from `runs.jsonl` (fallback to sample), drill-down to a run; analytics: verdict distribution, unclear rate by `unclear_reason`, average and max latency, tokens, cost, cache hit rate, judge `agree/partial/disagree` share, rules most often reported as missed by the judge.
- **Rules**: approved rules (source_ref, quote, check, scope, severity, tags, critic scores, attempts), rejected rules with reasons, dropped provisions with rationale.

Files: `ui/app.py`, `ui/run_tab.py`, `ui/history_tab.py`, `ui/rules_tab.py`.

## 10. Configuration

`.env.example`:

```
OPENAI_API_KEY=              # your OpenAI key (BYOK)
FAST_MODEL=gpt-6-luna        # cheap model: parallel rule checks
CLASSIFIER_MODEL=gpt-6-luna  # Decisions API classifier (only gpt-6-luna is supported in beta)
CLASSIFIER_THRESHOLD=0.2     # select a tag when P(tag) >= threshold; tuned on the golden set
STRONG_MODEL=gpt-6.1-sol     # strong model: ingest, critic, judge
MAX_CONCURRENCY=20           # max simultaneous OpenAI requests (≥ rules per run, so checks go out in one wave)
PROMPT_CACHE=on              # explicit prompt caching for rule checks
```

Model IDs and prices from OpenAI developer docs (Oct 2026): `gpt-6-luna` $0.10 / $0.50 per 1M input/output tokens; `gpt-6.1-sol` $2 / $10; `gpt-6-astra` $10 / $50 (alternative STRONG_MODEL). Reviewers can substitute any model they have access to.

Stack: Python, official `openai` SDK ≥ 3.26.0 (Decisions API for classification; Responses API with structured outputs via Pydantic for checks, ingest and judge), `pydantic`, `pypdf`/`pdfplumber`, `streamlit`, `python-dotenv`. No LangChain: three explicit steps with no agent loops, memory or tools; a framework would hide exactly the prompts reviewers want to see. What would change this: multi-step tool use, many providers, or long-lived conversational state.

## 11. Repository structure

```
common/      config.py · llm.py (client, semaphore, retries) · schemas.py
ingest/      __main__.py · load.py · split.py · filter.py · extract.py · gate.py
agent/       __main__.py (CLI) · checker.py · classifier.py · validate.py
             aggregate.py · judge.py · report.py · runlog.py
eval/        __main__.py (coverage | run) · golden.json
ui/          app.py · run_tab.py · history_tab.py · rules_tab.py
prompts/     ingest/ · agent/ · judge/   (one .md file per prompt)
data/        rules.json  (committed)
docs/        spec.md · stages/
examples/    runs.sample.jsonl · sample reports
.env.example · README.md · NOTES.md · CLAUDE.md
```

Prompts live in `prompts/` as standalone files so they can be read as documents; the "Prompt design" criterion is assessed there.

## 12. Implementation stages and cut order

| Block | # | Stage | File |
|---|---|---|---|
| A. Data | 0 | Golden set (before ingest) | `stages/00-golden-set.md` |
| | 1 | Ingest with shared foundation → `rules.json` | `stages/01-ingest.md` |
| | 2 | Coverage: golden ↔ rules | `stages/02-coverage.md` |
| B. Agent | 3 | Checker: classifier, parallel checks, validation, error contract | `stages/03-checker.md` |
| | 4 | Aggregation, report, CLI, run log | `stages/04-aggregate-report-cli.md` |
| C. Agent verification | 5 | Eval run: false PASS rate, per-rule accuracy | `stages/05-eval-run.md` |
| | 6 | Judge + calibration | `stages/06-judge.md` |
| D. UI | 7 | Run, History, Rules tabs | `stages/07-ui.md` |
| Optional | 8 | Ingest retry with critic feedback | `stages/08-ingest-retry.md` |
| | 9 | Final review, README, NOTES | `stages/09-final-review.md` |

Cut order if time runs out: 8 → 7 → 6. A cut stage keeps its file with status "cut" and the reason. The CLI report (stage 4) satisfies the output requirement without the UI.

## 13. AI-assisted workflow (how this was built)

- **Spec-driven development**: the design was settled first (this document), through a structured interview with a strong model.
- **Planner–executor**: a strong model (Opus) produced the spec and the stage breakdown; each stage was implemented by a cheaper model (Sonnet) against its stage file; a final review by Opus checked the result against the spec and the task.
- Evidence in the repo: this spec, `docs/stages/` with per-stage execution logs, commits prefixed by stage, the final review report, `CLAUDE.md`, and `NOTES.md` including the places where AI output was wrong and was corrected.

## 14. README plan

1. What it is, two-command quickstart (BYOK), example output.
2. Architecture: diagram, three entry points, why ingest and eval are separate scripts.
3. Source and scope: PS22/9 → PRIN 2A, domain statement, what was excluded and why (§1.2), dropped provisions.
4. Rule decomposition: schema, `check` as an atomic question, quality gate, why many Consumer Duty provisions are not checkable from text.
5. Key prompt design decisions: classification via Decisions API (probabilities, threshold in code) vs judgment via structured output (reasoning + evidence), shared prefix then rule, reasoning before verdict, verbatim quoting, content vs omission, unclear over guessing, one named predicate per tag, judge with code-computed rating.
6. Determinism: what code decides vs what the LLM decides; R/G → severity.
7. Evaluation: golden set written before ingest, metrics, results.
8. Framework choice: raw SDK + Pydantic, and what would change it.
9. What I built and what I cut (with the cut order), time actually spent vs the 2–3 h box.
10. What I'd do differently with more time: human approval of rules, FG22/5 and COBS 4, rewrite suggestions, online judge sampling, multilingual input, CySEC source.
11. One thing that surprised me (from `NOTES.md`; caching behaviour is a strong candidate).
12. How AI was used (§13).

## 15. Risks to measure during the build

- Whether the shared prefix crosses the caching threshold and whether prewarm produces hits.
- Share of PRIN 2A provisions dropped or rejected as not checkable from text.
- `unclear` rate on borderline golden cases with FAST_MODEL.
- Classifier misses reported by the judge.
- Decisions API is in public beta: behaviour or SDK surface may change; the fail-safe (run all rules) must cover any breakage.
