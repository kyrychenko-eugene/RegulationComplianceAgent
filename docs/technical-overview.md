# Technical overview

> Written by Claude Opus 5.5 during the final review (stage 9, 2026-10-14) as a read-only reference: how to run the project, how it is built, and the measured results. The author's own reflections are in [`README.md`](../README.md). Design source of truth: [`spec.md`](spec.md); review report: [`final-review.md`](final-review.md).

The agent checks a short marketing text (ad, push notification, email, landing page, social post) **rule by rule** against the FCA Consumer Duty, PS22/9 → **PRIN 2A**. For every rule it returns a verdict (`pass` / `fail` / `unclear`) with reasoning and evidence. Code then derives the overall verdict: `PASS`, `FAIL` or `NEEDS_HUMAN_REVIEW`.

## 1. Running it

Step-by-step setup (Python 3.9+, virtual environment, `.env` with your key) is in the [README quick start](../README.md#quick-start). In short, from the repository root with the virtual environment active:

```bash
pip install -r requirements.txt
cp .env.example .env              # put your key after OPENAI_API_KEY=
python -m agent "Install our app and get rich tomorrow 🚀🚀🚀"
```

`data/rules.json` is committed, so no ingest run is needed. A key set in the shell environment wins over `.env`. All settings (models, classifier threshold, concurrency, prompt caching) are in `.env.example` with comments. Entry points:

| Command | What it does | API calls |
|---|---|---|
| `python -m agent "<text>"` / `--file f.txt` / `--json out.json` | Check one text: Markdown report, one line in `runs.jsonl` | yes |
| `streamlit run ui/app.py` | Check, History (falls back to `examples/runs.sample.jsonl`), Rules | yes (Check tab) |
| `python -m eval coverage` | Golden set × rules matrix | no |
| `python -m eval run [--out f.md]` | Golden set through `agent.check()`, metrics, judge calibration | yes, ≈ $0.30 |
| `python -m ingest [--source pdf\|url] [--only 2A.5.3,…]` | Rebuild `data/rules.json` from the PDF | yes, ≈ $0.60 |
| `python -m pytest` | 75 offline tests (mocked OpenAI client); needs `pip install -r requirements-dev.txt` | no |

Example output for the reference case: [`examples/reference-case.md`](../examples/reference-case.md). It is **FAIL**, with "get rich tomorrow" quoted as a misleading return promise, plus omission failures for missing risk information and advisory failures for the urgency and emoji appeal.

## 2. Architecture

```
ingest ──► data/rules.json ──► agent ──► eval / ui
(one-off)   (reviewed snapshot)   (runtime)  (consumers of agent.check())
```

Runtime, per text:

```
classifier (Decisions API: P(tag) per tag) ┐ concurrent   code: tags = {t : P ≥ threshold}
cache prewarm (shared prefix)              ┘              always-rule checks start right away
rule selection (code) ─► per-rule checks in parallel (FAST_MODEL, structured output)
  ─► validation (code: verbatim quote, span, pass/fail/unclear) ─► aggregation (code)
  ─► report + runs.jsonl  ──── agent.check() returns here (~6–9 s)
  ─► judge (STRONG_MODEL, background thread, same run_id): appends its record to runs.jsonl
```

- **Three entry points, one-way dependencies.** Ingest and agent share only `rules.json` and its Pydantic schema (`common/schemas.py`). Eval and UI call only the public `agent.check()` / `agent.read_runs()`; deleting `ui/` breaks nothing.
- **Why ingest is a separate script:** decomposition is the expensive, strong-model, *reviewable* step. Its output is a file a human can approve (three rules were rejected by hand), and the runtime never re-derives rules.
- **Why eval is a separate script:** it uses the same public function as the CLI, so the metrics measure exactly what a user runs.
- **Never raises.** Any failure (outage, broken rules file, invalid model output) becomes `unclear (technical)` plus an `errors` entry, and a run with an error can never be `PASS`.

## 3. Source and scope

- Source: FCA **PS22/9**, Appendix 1 (Consumer Duty Instrument 2022), the made text of **PRIN 2A**. Ingest finds it by heading search, not page numbers. The live Handbook has later amendments; we use the text as published in PS22/9.
- Domain statement used for scoping: *marketing and promotional communications of a retail investment and trading platform to UK retail customers*.
- PRIN 2A has 169 provisions (89 R, 78 G, 2 E). The relevance filter keeps **15** and drops **154**, each with a rationale, which you can browse in the UI Rules tab. Most of the Consumer Duty governs firm processes (product approval, fair-value assessments, outcome monitoring, board reports) that can never be verified from a marketing text.
- Deliberately excluded: FG22/5 guidance, COBS 4 (the financial-promotions regime and its prescribed risk warnings), other jurisdictions, rewrite suggestions, non-English input. Reasons are in [`docs/spec.md` §1.2](spec.md).

## 4. Rule decomposition

The 15 kept provisions yield 34 drafted rules. **24 are approved** (11 blocking, 13 advisory; 17 `always`, 7 `conditional`); 7 were rejected by the quality gate and 3 by hand. Each rule has:

- `source_quote`, **verbatim** from its provision (checked by code), and a `source_ref` with the R/G/E marker.
- `check`: one atomic yes/no question answerable from the text alone. It is generated, because the source states obligations ("a firm must…"), not questions.
- `scope` (`always` / `conditional` + tags), with a rationale; `pass_example` / `fail_example` used as illustrations.
- `severity` derived by code from the marker: **R → blocking, G/E → advisory**. One consequence: the urgency rules (2A.2.3(b), 2A.2.10(2)) are guidance, so they only make a text `NEEDS_HUMAN_REVIEW` on their own; the reference case is FAIL through the R rules in 2A.5.3.

**Quality gate instead of human review.** Code checks: quote verbatim in its own provision, marker matches, schema valid, unique id, conditional rules have tags, `check` is a single question. A critic (strong model) scores `faithful`, `atomic` and `checkable_from_text` from 1 to 3; a rule is approved only with every score ≥ 2. `checkable_from_text` is the key criterion: it is why "take account of customers' interests" (2A.2.3(a)) is rejected, since it needs the firm's intent, which no text shows.

## 5. Key prompt design decisions

All prompts are standalone documents in [`prompts/`](../prompts/).

1. **Classification and judgment use different APIs.** Which conditional rules apply is a classification, done with the OpenAI **Decisions API**: one named `predicate` question per tag, which returns `P(tag)`. **Code** applies the threshold, so the model cannot invent a tag, and any failure falls back to running all rules. Whether a rule passes is a judgment that needs reasoning and a quote, done with the Responses API and a Pydantic schema.
2. **Shared prefix first, rule last.** The system prompt and the marketing text are identical for every rule, so they form a cached prefix (explicit breakpoint plus one prewarm call), and only the rule block differs.
3. **Reasoning before verdict.** The schema field order is `reasoning → violation_type → evidence_quote → verdict`, so the model decides after it has argued.
4. **Verbatim evidence, checked by code.** A `content` failure must quote the text exactly (whitespace-normalised). If the quote is not found, the answer becomes `unclear (invalid_answer)`, never a fail. Code computes the span; the LLM never returns offsets.
5. **Content vs omission.** "Guaranteed 20%" is quotable; a missing risk warning is not. Omissions must name what is missing instead of a quote.
6. **`unclear` over guessing**, but not as an escape from a clear call.
7. **Proportionality and materiality** (added after eval): judge the message, not a full disclosure document; fail only what a compliance reviewer would raise; language rules are judged on the whole message in its app context. This fixed most false FAILs (see §7).
8. **Judge with a code-computed rating.** A stronger model lists only missed rules and disputed verdicts. Code filters unknown ids, rates rule-level agreement (`agree` / `partial` / `disagree` by severity), and re-runs the agent's own aggregation on the judge's rule verdicts to say whether the **overall verdict** would change. The judge never changes the verdict.

## 6. Determinism: what code decides vs what the LLM decides

| LLM (narrow judgments) | Code (the outcome) |
|---|---|
| P(tag) per tag | Tag threshold, rule selection, fallback to all rules |
| One rule: reasoning, violation type, quote, verdict | Validation table (spec §5.6), quote matching, spans, downgrades to `unclear` |
| Judge: missed / disputed rules | Id filtering, rule-level rating, verdict-level comparison |
| Ingest: keep/drop, rule drafts, critic scores | Ids, `source_ref`, severity from marker, verbatim checks, approval threshold |
| — | Overall verdict: any blocking fail → FAIL; any fail/unclear/error → NEEDS_HUMAN_REVIEW; else PASS; and the summary text |

## 7. Evaluation

The golden set (`eval/golden.json`, 23 cases over push, email, ad, landing page, social and product page) was **committed before ingest** (git history: 17:32 vs 17:47), with expectations in plain language plus a provision. Each expectation was mapped to `rule_id`s only after the rules existed, so the cases are not fitted to the rule wording.

Latest run ([`examples/eval_report.md`](../examples/eval_report.md), gpt-6-luna checks, gpt-6.1-sol judge, $0.38 for 23 cases):

| Metric | Value | Comment |
|---|---|---|
| **Expected violations caught** (≥ 1 mapped rule fails) | **34/34** | the primary safety number |
| Overall verdict more lenient than the label | **0/23** | no case got a softer verdict than expected |
| False PASS, rule level | 7/73 (9.6%) | 5 of the 7 are `5.3-2-a` "expressed clearly", which golden maps to "misleading" concepts that `5.3-2-c` catches: a mapping issue |
| False FAIL, rule level | 5/39 (12.8%) | all `5.3-1c-b/c` on texts with a risk line present |
| Overall-verdict agreement | 17/23 (73.9%) | all 6 misses are *stricter* than the label |
| …if the strong judge's rule verdicts were applied | 18/23 (78.3%) | the judge also says FAIL on 4 of the 6 misses |
| Classifier misses (threshold sweep 0.05–0.5) | 0 | |

**Why ~75% is the ceiling here, not a model problem.** 4 of the 6 misses are cases labelled `NEEDS_HUMAN_REVIEW` (FOMO, jargon, disclaimer overload, wall of text). Under the spec's aggregation that label means only *advisory* rules may fail, but each text also trips an R-marked (blocking) rule such as "not misleading" or "understandable". The stronger judge model reaches FAIL on all four too. So either those labels should accept FAIL, or the R → blocking mapping is too coarse for them. That is a labelling/spec decision, left open (see [`docs/final-review.md`](final-review.md)). The other two misses are single advisory or blocking fails on otherwise clean texts (an "unnecessary disclaimer" call, and "doesn't say what the Growth portfolio is"), which the judge disputes.

The overall number also moves by a case or two between identical runs (the fast model is not deterministic, and a verdict is an OR over ~18 rules). Read it as about 75 ± 5%.

**Latency** (stage 9): time to verdict was ~25 s (classifier → prewarm → 4 waves of 5 checks → judge, all serial). It is now ~6–9 s from the CLI and 11.9 s median in the eval: the classifier and prewarm run concurrently, `always` rules start without waiting for the classifier, all checks go out in one wave (`MAX_CONCURRENCY=20`), and the judge (≈ 10 s median) runs in the background and appends its result to the history under the same `run_id`. The remaining floor is the slowest single rule call (the long tail of the fast model).

## 8. Framework choice

Raw `openai` SDK + Pydantic, no LangChain or agent framework. The runtime is three explicit steps (classify, fan-out checks, judge) with no tool use, memory or loops. A framework would hide exactly what a reviewer needs to see (the prompts, the message layout for caching, the validation). It would be worth it with multi-step tool use, several model providers, or long-lived conversational state.

Deviation: spec §10 names SDK ≥ 3.26.0 for `client.decisions`. That version was not installable here, so the classifier POSTs to `/v1/decisions` through the 2.x SDK's generic `client.post`; `requirements.txt` therefore says `openai>=2.0`.

