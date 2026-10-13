# NOTES

Findings recorded while building. Numbers are measured, not estimated.

## Stage 1 — ingest

### Source structure (measured on the real PS22/9 PDF, 161 pages)
- PRIN 2A in Appendix 1 splits into **169 provisions**, all ids unique: **89 R, 78 G, 2 E** (2A.3.30, 2A.4.35). E does occur, contrary to the spec's "not observed in 2A.2 or 2A.5" (true for those sections only); the splitter handles it and maps it to `advisory`.
- Per section: 2A.1: 18 · 2A.2: 28 · 2A.3: 30 · 2A.4: 35 · 2A.5: 15 · 2A.6: 6 · 2A.7: 5 · 2A.8: 5 · 2A.9: 17 · 2A.10: 5 · 2A.11: 5.
- Located by heading search (`Appendix 1` cover page → `2A The Consumer Duty` → next `Amend/Insert/Annex` instruction), no page numbers.

### Surprises
- The FCA PDF is AES-encrypted: `pypdf` fails with `DependencyError` until `cryptography` is installed. Added to `requirements.txt`.
- Sub-headings ("Application", "Manufacturers: product approval process …") are not marked in the text. Long ones wrap onto a second line with no indent, and my first splitter glued that tail (e.g. "products", "distributors") onto the previous provision. Caught by a check that every provision text ends in sentence punctuation; fixed by dropping the wrapped line after a sub-heading. 169 provisions before and after, so only the text was wrong, not the count.
- Environment: Python 3.9 here, so schemas use `typing.Optional/List`, not `X | Y` (pydantic evaluates annotations). Installed `openai` is 2.48.0, not the ≥ 3.26.0 in spec §10; ingest only needs the Responses API, which 2.48.0 has. The Decisions API (stage 3) needs the newer SDK — bump `requirements.txt` then.

### Design choices the spec left open
- `id` is built by code: `PRIN<provision>-<sub>-<a,b,…>`, e.g. `PRIN2A.5.3-1c-a`; `source_ref` is built by code from the provision and the model's `sub_ref`. The model only proposes the sub-paragraph.
- `source_quote` is verified against **its own provision's** text, stricter than "anywhere in the source"; a final assert also checks all approved quotes against the whole chapter.
- The critic runs on every drafted rule, including ones that already failed a deterministic check, so rejected rules still carry scores.
- "Single question" is a heuristic: exactly one `?` at the end, no `;`, no `(a)` labels, no "x, y, and z" lists. It cannot see two conditions joined by a bare "and"; that is the critic's `atomic` job.
- Tag vocabulary: rules are extracted in parallel and cannot see each other's tags, so `prompts/ingest/extract.md` seeds a starting vocabulary and asks the model to reuse it. Review the resulting tag counts (printed by `python -m ingest`) before stage 3.

### Current `data/rules.json` — second full run (2026-10-13, after the `source_quote` prompt fix)

**Why a second run.** 2A.5.8 ("tailor communications to customer characteristics, complexity, channel, firm role") produced zero rules in the first run, and in a re-test its three drafts were rejected `faithful=1`. Cause: the extractor quoted only the list item, e.g. "(2) the complexity of the product;", which has no obligation in it; the critic then (rightly) said the check adds a requirement. Fix in `prompts/ingest/extract.md`: the quote must contain the whole requirement and, for a list item, the lead-in clause (or the whole provision). After the fix, 2A.5.8 alone gave 4 approved rules.

| Stage | Number |
|---|---|
| Provisions total / kept / dropped | 169 / 15 / 154 |
| Kept with zero rules | 6 |
| Rules drafted / approved / rejected | 34 / **27** / **7** (21% rejected) |
| Approved by severity | 14 blocking, 13 advisory |
| Approved by scope | 18 always, 9 conditional |
| Usage | 137k input, 28.7k output, ≈ $0.56 at the table price (the 5-provision sample extrapolated to $1–3; real cost is lower) |

**Rejected (7):** 2A.2.2-a (checkable=1), 2A.2.2-c (faithful=1), 2A.2.3(a) (checkable=1), 2A.2.10(1) (faithful=1: "likely to cause" is stricter than "foreseeable"), 2A.2.20(1) (checkable=1), 2A.5.7(2)-b jargon (faithful=1: dropped "where unavoidable"), 2A.5.8(1)-a (faithful=1: limited tailoring to characteristics "identified in the text"). All plausible critic calls, but note the pattern: 4 of 7 are `faithful=1`, i.e. the generated check narrowed or widened the source. This is what a retry with critic feedback (stage 8) is for.

**Done-when coverage, now met:** 2A.5.3(1)(c) has three approved rules, 2A.5.3(2) three, 2A.2.3(b) and 2A.2.10(2) one or more each, 2A.5.8 two (complexity, firm role) of its four limbs.

**Run-to-run variance is large.** Same prompts, same model: the first run rejected 2A.5.3(1)(c) outright, the second approved three variants of it; 2A.2.3(b) flipped between `always` and `conditional`; 2A.5.3(2)-b "fair" was approved, then rejected in a single-provision test, then approved. The filter also differed on 2 provisions (2A.2.13 and 2A.5.5 dropped in the second run, kept in the first). Conclusion for the README: `rules.json` is a reviewed snapshot of one run, not a reproducible function of the source; `meta.generated_at` and prompt hashes identify it. A reviewer who wants stability should approve the file, not re-run ingest.

**Manual edits after the run (human-reviewed, 3 rules):** `PRIN2A.5.9-2-a`, `PRIN2A.5.9-2-b` and `PRIN2A.5.3-1c-a` were set to `rejected` with a "Manual review: …" reason instead of being deleted, so they stay visible in the UI Rules tab. The file now has **24 approved** (11 blocking, 13 advisory; 17 `always`, 7 `conditional`) and **10 rejected** (7 by the gate, 3 manual). Two limbs of 2A.5.9 are gone; 2A.5.3(1)(c) keeps `-b` (timely information) and `-c` (sufficiently complete basis for an informed decision). Re-running `python -m ingest` overwrites these edits.

**Remaining quality problems (as generated; the manual edits above resolve the 2A.5.3(1)(c) and 2A.5.9 items):**
- 2A.5.3(1)(c) variants are vague and overlap: "usable basis for deciding how to proceed", "sufficiently complete basis for an informed decision", "information needed to make any decision it presents in time"; all three are `blocking` and all `always`. They can disagree on the same text. Also a risk of false FAILs on short ads where nothing is expected to be complete.
- 2A.5.9(2)-a/b (ask the customer whether they understand / have questions) are still approved, `blocking`, tag `one_to_one_interactions`. They are one-to-one dialogue duties, not mass-marketing duties. Recommend removing by hand or tightening the filter prompt.
- 2A.5.7(3)-a/b are still the same requirement twice.
- 2A.5.8(3) (channel) produced no rule; 2A.5.8(1) (customer characteristics) was rejected.
- Tags: 9 distinct for 11 uses; seed vocabulary again mostly ignored (`vulnerable_customers`, `product_features`, `complex_products`, `disclaimers` only). The urgency/emotion check is tagged `emotional_or_behavioural_appeals`, which the golden "get rich tomorrow 🚀" case relies on the classifier to fire.

### First full run (superseded), kept for comparison
Counts: 169 provisions, 17 kept, 152 dropped; 26 drafts, 21 approved, 5 rejected. The detail below describes this first run.
| Stage | Number |
|---|---|
| Provisions total | 169 (89 R, 78 G, 2 E) |
| Kept by the filter | **17** (10%) |
| Dropped by the filter | **152** (90%), all with a rationale |
| Kept but zero rules extracted | 10 |
| Provisions that produced rules | 7 (2A.2.2, 2A.2.3, 2A.2.10, 2A.2.20, 2A.5.3, 2A.5.7, 2A.5.9) |
| Rules drafted | 26 |
| Rules approved | **21** (7 blocking, 14 advisory; 14 `always`, 7 `conditional`) |
| Rules rejected | **5** (19% of drafts) |

Dropped by section: 2A.1 18/18 · 2A.2 19/28 · 2A.3 30/30 · 2A.4 35/35 · 2A.5 8/15 · 2A.6 6/6 · 2A.7 4/5 · 2A.8 5/5 · 2A.9 17/17 · 2A.10 5/5 · 2A.11 5/5. Spot-checking the drops in 2A.2/2A.5/2A.6/2A.7: the rationales read as correct (scope, interpretation, firm processes, inter-firm duties, customer support, testing/monitoring). This matches the spec's expectation that most Consumer Duty text is not checkable from a marketing text.

**Rejected rules (5), all by the critic, none by the deterministic checks:**
| Rule | Why |
|---|---|
| PRIN2A.2.2-a "avoid misleading wording" (quote: "honesty") | checkable_from_text=1 |
| PRIN2A.2.2-b "avoid unfair pressure" (quote: "fair and open dealing") | faithful=1: adds a prohibition the three-word quote does not contain |
| PRIN2A.2.2-c "avoid obscuring material information" (same quote) | faithful=1, same reason |
| PRIN2A.2.3(a) "take account of customers' interests" | checkable_from_text=1: needs the firm's intent |
| **PRIN2A.5.3(1)(c)** "sufficient information for a properly informed decision" | checkable_from_text=1 |

**Gap against Done-when:** PRIN 2A.5.3(1)(c), the "no risk information / not properly informed" expectation of the reference case, has **no approved rule**. The same rule was approved in the 5-provision sample run earlier (checkable=2) and rejected here (checkable=1): the critic is not stable across runs on borderline rules. The other targets are covered: 2A.5.3(2) (clear / fair / not misleading, 3 rules), 2A.2.3(b) and 2A.2.10(2). Stage 2 will show which golden expectations lack a rule; 2A.5.3(1)(c) is the first candidate for the stage-8 retry (or a rule-level override), since the reference case depends on it.

**Quality of the 21 approved rules (my review):**
- Good: 2A.5.3(1)(a)(b), 2A.5.3(2)-a/b/c, 2A.2.3(b), 2A.2.10(2)-a/b, 2A.5.7(2)-a/b, 2A.5.7(3), 2A.5.7(4).
- Weak or redundant: 2A.5.7(3)-a/b are one requirement split in two ("prominent" / "easy to identify"); 2A.5.3(2)-a ("convey its meaning unambiguously") overlaps 2A.5.3(1)(b); 2A.5.7(5)-a ("provide relevant information") is vague; 2A.2.10(1)-a ("encouraging conduct that foreseeably harms") is broad.
- Misfit: **2A.5.9(2)-a/b** ask whether the communication asks the customer if they understand or have questions. These are one-to-one dialogue duties, tagged `one_to_one_dialogue`, severity `blocking` (marker R). A push notification would fail them if the tag fired. Candidates for removal; they are the strongest sign the filter let a non-marketing provision through.
- Severity consequence as predicted: the urgency/exploitation rules (2A.2.3(b), 2A.2.10) are `advisory` (G), so only the R rules in 2A.5.3 can make the reference case FAIL.
- Scope is inconsistent between similar rules: 2A.2.3(b) is `always`, 2A.2.3(c) `conditional`.
- Tags: 6 distinct, 7 uses: `vulnerable_customers` 2, `one_to_one_dialogue` 2, `customer_circumstances`, `calls_to_action`, `technical_terms`, `disclaimers`. Only 2 of the 10 seed tags were used (`vulnerable_customers`, `calls_to_action`), so the seed is largely ignored. The vocabulary is small enough to curate by hand if needed. A rule about urgency or emotional pressure has no tag, because 2A.2.3(b) became `always`.
- Kept-but-zero-rules: 2A.2.1 and 2A.2.8 (the headline good-faith and foreseeable-harm duties, covered instead by 2A.2.2/2A.2.3/2A.2.10), 2A.2.13, 2A.2.14, 2A.2.25, 2A.5.4, 2A.5.5, 2A.5.6, 2A.5.8, 2A.7.2. 2A.5.8 ("tailor communications to customer characteristics") may deserve a rule.

**Takeaway:** the 5 rejections are mostly correct, but the larger story is upstream: 90% of provisions are dropped and only 7 provisions yield rules. The set is small (21) and thin on investment-marketing specifics (no risk-warning, returns or performance rule beyond "not misleading"). That is a property of PRIN 2A, not a bug, and matches spec §1.2 (COBS 4 is out of scope), but it limits what the eval can show.

### Verification done without a key
- 18 offline tests (`pytest`): splitter, heading search, id/ref/severity by code, every deterministic check, critic thresholds, full pipeline with a mocked client, `--limit`, the verbatim assertion, empty-parse error, and the failure paths (filter/critic/extract call fails).
- The three Pydantic output schemas convert to OpenAI strict structured-output format.
- Not verified: real model behaviour, the live `responses.parse` call, usage field names (`cache_write_tokens` is read with a default of 0 in case the SDK does not expose it).

### First live samples (gpt-6.1-sol, not the full run)
- `--limit 20`: the first 20 provisions are 2A.1.1–2A.1.18 plus 2A.2.1/2A.2.2. The filter dropped all 18 of 2A.1 with sensible rationales (scope, definitions, purpose); the 2 kept gave zero rules. A prefix slice is a poor sample, so `--only 2A.2.3,2A.5.3,…` was added.
- `--only 2A.2.1,2A.2.3,2A.2.10,2A.5.3,2A.5.7`: 5 kept → 20 drafts → **17 approved, 3 rejected**; 6 blocking / 11 advisory. Usage 19.9k input, 8.4k output (≈ $0.12 at the table price). `cache_write_tokens` is exposed by the SDK (3,318).
- Targets covered: 2A.5.3(1)(c), 2A.5.3(2) (split into clear / fair / not misleading), 2A.2.3(b), 2A.2.10(2).
- Rejected, all plausibly right: 2A.2.3(a) and (c) (checkable_from_text=1: need the firm's intent / customer circumstances), 2A.5.7(2) jargon (faithful=1: the check dropped the "where unavoidable" condition). The jargon rule is a golden-set expectation, so it is a stage-8 retry candidate.
- Tag seed vocabulary was **not reused**: new tags `emotional_appeals`, `behavioural_biases`, `customer_circumstances`, `jargon_or_technical_terms`, `disclaimers`; none of the 10 seeds appeared. Expect fragmented tags in the full run; a normalisation step or a two-pass tag assignment may be needed before stage 3.
- Weak spots: near-duplicate rules (2A.5.7(3): "prominent" vs "easy to identify" from the same quote); vague checks ("provide information relevant to the decision"); 2A.2.3(b) is `conditional` while the equivalent 2A.2.10(2) is `always`.


## Stage 2 — coverage

Command: `python -m eval coverage` (offline). Result on 24 approved rules × 23 cases × 57 expectations: **0 unmapped, 4 known gaps, 3 approved rules never expected to fail.**

**Mapping choices (mine, to be reviewed).** `rule_ids` follow the provision cited in the expectation, plus rules that match the concept: `2.10-2-b` (vulnerability exploitation) added to the two `2A.2.3(c)` vulnerability cases; `2.20-2-a` (informed decision) added to the welcome-bonus and account-change omissions. Pass expectations list the rules that should pass. Golden texts and provisions were not touched.

**Known gaps (4):** 2A.2.1/2A.2.2 open dealing (2A.2.2-a/-c rejected by the critic; `2.2-b` covers only manipulative wording), 2A.5.8(1) tailoring to customer characteristics (all drafts rejected, faithful=1), 2A.2.3(d) and 2A.5.6(2) (dropped by the ingest filter). Three of the four are ingest losses on provisions the golden set targets; stage 8 (retry with critic feedback) is the natural fix, or a manual rule.

**Approved rules with no failing case (3), left as is:**
- `PRIN2A.2.2-b` (unfairly manipulative wording) and `PRIN2A.2.8-a` (foreseeable harm): general-standard rules; no golden expectation was written for them. Candidates for a new case, but cases written now would be fitted to rule wording (spec §8.1), so they are recorded, not added.
- `PRIN2A.5.8-4-a` (wording consistent with advisory/information-only role): no golden case on advice vs information.
Also, `2.2-b` and `2.8-a` are `always` rules that every `PASS` case implicitly exercises only if mapped; they are not, so their false-FAIL rate is unmeasured.

**Surprise:** the 5.3(1)(c) pair and 5.3(2) triple appear in nearly every case, so they dominate the matrix. A single bad rule there will swing most per-rule numbers in stage 5.


## Stage 3 — checker

**Reference case live run** ("Install our app and get rich tomorrow 🚀🚀🚀", gpt-6-luna, 2026-10-13): 18 rules selected, **8 fail / 4 pass / 0 unclear**, no errors. R-rule fails: 5.3(2)-a/b/c (quote "get rich tomorrow", span [20,37]) and 5.3(1)(c)-b/c (omission); advisory fails: 2.3(b), 2.10(2)-a. Also failed: 2.2-b, 2.8-a, 2.20-2-a, 5.3(1)(a), 5.7(3)-a, 5.7(5)-a/b. Passed: 5.3(1)(b), 5.7(1)-a, 5.7(2)-a, 5.7(3)-b. 5.7(3)-a fails but its twin 5.7(3)-b passes: the near-duplicate pair from stage 1 disagrees on the same text.

**Classifier probabilities (Decisions API, live):** `emotional_or_behavioural_appeals` **0.89**; all seven other tags **0.00** (`vulnerable_customers`, `customer_circumstances`, `switching_and_complaints`, `disclaimers`, `complex_products`, `product_features`, `advice_or_information`). One call, ~1.8 s. The probabilities are strongly bimodal here, so the 0.2 threshold is not stressed by this case; tuning needs the stage-5 sweep.

**Surprises**
- The installed SDK (openai 2.48.0) has no `client.decisions` and 3.26.0 is not on PyPI for this environment, but the endpoint is live: I call it with `client.post("/decisions", body=..., cast_to=object)`. Wire format used: request `{model, input, questions:[{type:"predicate", name, instructions}]}`, response `answers:[{type, name, probability}]`, refusal = `{type:"refusal", name}`. Source: third-party summaries plus the live response. No SDK bump needed; `requirements.txt` untouched.
- Cache breakpoint syntax is not in the spec and my first guess (`cache_control`) was wrong. The live API accepted `{"prompt_cache_breakpoint": {"mode": "explicit"}}` on an `input_text` part (found by probing the 400 messages).
- **Shared prefix = 691 tokens for this input (system prompt + 38-char text), under the 1,024 minimum.** Prewarm therefore wrote nothing (`cache_write_tokens=0`) and **no call had `cached_tokens > 0`**. Calls whose total input crossed 1,024 (rule block included) reported `cache_write_tokens` ≈ 1,050–1,160 for rule-specific content, which can never be reused by other rules. Per spec §5.5 this means caching is ineffective with the current system prompt; `PROMPT_CACHE=off` saves the prewarm call. Not changed: needs your call (pad the system prompt with useful guidance past ~1,024, or default the switch to off).
- The classifier only ever sees conditional tags, so only 1 of 7 conditional rules ran here; 17 always-rules + 1.

**Verification:** 47 offline tests (`python -m pytest`; bare `pytest` fails to import `common` in this venv, as before). New file `tests/test_checker.py` covers every row of the §5.6 table, spans with whitespace differences, threshold/fallback/refusal/missing/garbage answers, selection, Decisions request shape, API outage, missing and broken `rules.json`.


## Stage 4 — aggregation, report, CLI, run log

**Reference case via the CLI** (`python -m agent "Install our app and get rich tomorrow 🚀🚀🚀"`, 2026-10-13): **FAIL**, 13 of 18 rules failed (7 blocking, 6 advisory), 0 unclear, 0 errors. Timings: total 17.7 s, classify 1.7 s, prewarm 1.9 s, checks wall 14.1 s, rule latency avg 3.4 s / max 5.8 s. Usage 20.8k input, 7.6k cached, 4.1k output, **$0.0034**. Report and JSON in `examples/reference-case.{md,json}`.

**Surprises**
- Stage 3 recorded 8 fails on the same text; this run has 13 (5.3(2)-b/c, 2.2-b, 2.8-a, 5.3(1)(c), 5.7(5) and others flip between runs). The checker is not stable run to run at this size; stage 5 should repeat runs before trusting per-rule numbers.
- `cached` was 7,632 tokens this time although stage 3 saw none: the cache apparently kicked in without a write being reported (`cache_write` = 0). Cost counts `cached` at 0.1x; whether `input_tokens` includes cached tokens is assumed (OpenAI convention), not verified.
- The spec's "technical problem never PASS" is implemented strictly: any entry in `errors` (including a classifier fallback or failed prewarm, where all rules still ran) caps the verdict at NEEDS_HUMAN_REVIEW. An empty result list is also NEEDS_HUMAN_REVIEW, not PASS (the bare formula would give PASS).
- `agent.check()` also appends to `runs.jsonl` by default (`log_path=None` disables it, for eval); the `--no-log` CLI flag does the same. Classifier (Decisions API) tokens are added to usage/cost from its response `usage`; the price table has no separate Decisions rate, so it uses the input rate of the classifier model.
