# Final review (stage 9)

Reviewer: Claude Opus 5.5, 2026-10-14. Inputs: `docs/spec.md`, every `docs/stages/*.md`, the whole code base, `NOTES.md`, the run log, and a new live eval run. The task PDF itself could not be read in this session (it is image-only and the extraction tool was not permitted), so the task checklist below uses the requirements as quoted in the stage 9 file and spec §14. Please spot-check it against the PDF.

The owner raised five concerns at the start of the review. Each has its own section (§3–§5), and they are also items in the issue list (§6).

## 1. Task requirement checklist

| Requirement | Status | Where |
|---|---|---|
| Real regulatory source | ✅ FCA PS22/9 PDF, located by heading search; `--source` overrides | `ingest/load.py`, `common/config.py` |
| Structured rule decomposition, choice visible | ✅ 169 provisions → 15 kept / 154 dropped with rationale → 34 drafts → 24 approved; schema + critic scores; all visible in the UI Rules tab | `data/rules.json`, `ui/rules_tab.py` |
| Per-rule verdict with reasoning | ✅ `pass/fail/unclear` + reasoning + verbatim quote or omission note + span | `agent/validate.py`, report |
| Clean, separable stages | ✅ `ingest → rules.json → agent → eval/ui`; agent imports only `common/`; UI is replaceable | spec §2 |
| Prompt design | ✅ 7 prompts as standalone `.md` files; design reasons in `technical-overview.md` §5 and README | `prompts/` |
| Framework justification | ✅ raw SDK + Pydantic, with what would change it | `technical-overview.md` §8, README |
| Scoped recall (what is in and out, and why) | ✅ spec §1.2, dropped provisions with rationale, known gaps listed by `eval coverage` | |
| Repo hygiene: no keys, `.env.example`, BYOK | ✅ `.env` never committed (checked across all history: no `sk-…` pattern, no `.env` path); `.env.example` complete | §7 |
| Two-command quickstart from a clean clone | ✅ verified (§7) | README, `technical-overview.md` §1 |
| Thinking doc: built/cut, prompt decisions, more time, a surprise, time spent, AI use | ✅ README thinking doc, in the author's own words: built/cut, prompt decisions, more time, surprises, AI use. Not covered: time spent (not among the task's four bullets) | README |

## 2. Spec conformance ("was everything built to the tech design?")

Yes, with the deviations below. Each one is either documented or fixed in this stage.

| Spec | Finding | Resolution |
|---|---|---|
| §2.1 runtime flow | Built as specified, but every step was serial, including the judge (≈ 7–16 s). | **Changed with the owner's agreement** (§3): concurrent classifier/prewarm, background judge. Spec §2.1 updated. |
| §4.2 step 7 (retry) | Not built. | Stage 8 **cut** (first in the cut order). The rule-set weaknesses it would address remain (§6, #11). |
| §4.3 `attempts` | Always 1, since there is no retry. | Consistent with the cut. |
| §5.1 classifier | SDK ≥ 3.26.0 was not installable; the classifier POSTs to `/v1/decisions` via `client.post`. Threshold 0.2 as specified. | Documented (`technical-overview.md` §8, NOTES stage 3). |
| §5.5 caching | The first prefix was 691 tokens, under the 1,024 minimum, so it had no effect. After the stage 5 proportionality text, 16–17 of 18 checks per run read from the cache. | Works now; prewarm kept, but it now overlaps the classifier. |
| §5.7 aggregation | Implemented strictly: any error, or an empty result list, gives NEEDS_HUMAN_REVIEW. | Conforms (stricter than the bare formula, documented in NOTES stage 4). |
| §5.8 never raise | Verified live: a wrong key gives exit 0, NEEDS_HUMAN_REVIEW, 26 technical errors. | Conforms. |
| §6 judge | The rating conformed, but the UI presented the rule-level rating as verdict disagreement (owner's concern #4). | **Fixed**: added `overall_verdict` / `verdict_agrees`, computed by code. Spec §6 updated. |
| §7 run log | Conformed. With a background judge, the judge arrives as a second line. | `agent.read_runs()` merges by `run_id`. Spec §7 updated. |
| §8.1 golden before ingest | ✅ `eabca8f` 17:32 (23 cases, 0 `rule_ids`) before `c78e5d9` 17:47. | — |
| §8.3 threshold recommendation | NOTES claimed 0.5 was written to `.env.example`; it was not. | NOTES corrected; 0.2 kept on purpose (spec §5.1 argument). |
| §9 UI | Conforms; the History judge label was misleading. | Fixed (#4). |
| §10 `MAX_CONCURRENCY=5` | With 17–22 rules per run, checks went out in 4 waves. | Default raised to **20**; spec §10 and `.env.example` updated; no 429s observed. |
| §13 workflow evidence | Stage 0 log empty, status `pending`; stage 6 calibration never run; commit prefixes do not follow `stage-NN:`. | Stage 0 log reconstructed from git; calibration run (§5); the prefix inconsistency is noted, not rewritten. |

## 3. Latency (owner's concern #2)

**Measured before:** 17.7–33.0 s per run (6 logged runs). Every step was serial: classifier 0.7–2.4 s, prewarm 1.3–2.4 s, checks 12.5–20.7 s (18 rules at concurrency 5 = 4 waves), judge 6.7–9.7 s.

**Changes:**
1. `MAX_CONCURRENCY` 5 → 20, so all checks go out in one wave. Checked with `OPENAI_LOG=info`: 21/21 requests returned `200`, no retries.
2. The classifier (Decisions API) and the cache prewarm run concurrently. `always` rules (17 of 24) do not depend on the classifier, so their checks start as soon as the prefix is warm; conditional checks start when the classifier answers. Selection logic is unchanged.
3. **The judge runs in the background.** `agent.check()` returns with `judge.status = "pending"`. A thread runs the judge on its own event loop and appends `{"record": "judge", "run_id", "judge", "judge_ms", "usage"}` to `runs.jsonl`. The run already had a unique id (`run_id`, a UUID4), which is the join key. `agent.read_runs()` merges the record into its run (judge block, `judge_ms`, cost). The CLI prints the verdict first, then waits and prints the judge. The UI shows "Judge still running" until the record lands. The eval uses `judge="sync"`; `judge="off"` skips it.
4. The HTTP client is now closed inside the run, with a 5 s bound. This also removes the "Event loop is closed" stderr noise noted in stage 5.

**Measured after:** 5.7 / 6.5 / 8.5 s to verdict on three CLI runs; 11.9 s median, 15.9 s max across the 23 eval cases. The floor is now the slowest single rule call (median 10.4 s in the eval), i.e. the fast model's tail latency. Further options, none implemented: a per-call deadline with one hedged retry for stragglers; fewer, merged rules (§6, #11); a faster model for the checks.

**Caveat:** a script that calls `agent.check()` and exits immediately may not leave the background judge enough time; it should call `agent.wait_for_judges()` before exiting (the CLI does). In that case the verdict is unaffected; only the monitor record is lost.

## 4. Strictness and the ~75% agreement (owner's concerns #3 and #5)

**The quoted case.** "Subject: New in the app … set price alerts on any instrument … dark mode" failed `5.3-1b-a` (blocking) and `5.7-2-a` because "instrument" was called jargon. Three causes stack up:
- *Run-to-run noise:* the same text was PASS in the stage 5 eval.
- *A doubled rule:* two rules test the same thing (5.3(1)(b) "likely to be understood", R; 5.7(2) "plain language", G), so one borderline word fails twice, once as blocking.
- *A lost nuance:* the rule that carried "where jargon is **unavoidable**, explain it" (`5.7-2-b`) was rejected at ingest, so the remaining rules read as "no technical words".

**Fix:** a *Materiality* section in the shared check prompt. Fail only what a compliance reviewer would raise, and judge language rules on the whole message in its app context. Examples were chosen *outside* the golden texts to avoid teaching to the test. Results: the case passed 3/3 runs with the judge agreeing; an out-of-sample leveraged-oil promo ("roll yield", "margin calls") still fails both language rules; the reference case is still FAIL.

**Is 74–78% too low?** The number is honest, but it is not a good measure of quality on its own:
- **Safety is intact:** 34/34 expected violations were caught, and **0/23** cases got a more lenient verdict than labelled. Every miss is the agent being stricter.
- **4 of the 6 misses are a label/severity conflict.** These cases are labelled NEEDS_HUMAN_REVIEW, which under §5.7 means only advisory rules may fail. Each text also trips an R-marked rule (misleading, understandable, foreseeable harm). The stronger judge model reaches **FAIL on all four** too. Applying the judge's rule verdicts gives only 18/23, so even a model ~20× pricier does not get past ~78% against these labels.
- **The verdict is an OR over ~18 noisy rules.** If each compliant rule has a few percent chance of a false fail, a clean text fails *somewhere* surprisingly often. The leverage is in fewer, sharper rules and in confirming blocking fails, not in a better prompt alone.
- **Rule-level false PASSes are mostly a mapping artefact:** 5 of the 7 are `5.3-2-a` ("expressed clearly") mapped to "misleading" concepts. On all 5 texts, `5.3-2-c` (misleading) and `5.3-2-b` (fair) did fail.
- The overall number moves by about ±1–2 cases between identical runs.

What would move it (not done, decisions for the owner): see §8.

## 5. Judge display (owner's concern #4)

Before, the History tab mapped the rule-level rating straight to a banner: `disagree` became "Judge disagrees with the verdict". But `disagree` only means "disputes at least one blocking rule". On the eval, the rating was `disagree` on 10/23 cases, while the judge's rule verdicts led to the **same overall verdict on 21/23**.

Now code applies the judge's verdicts (disputed rules replaced; missed rules added with the verdict the judge expects for them, a new `judge_verdict` field) to the agent's own `aggregate_verdict`, with the same errors. This gives `overall_verdict` and `verdict_agrees`. The UI and the Markdown report show two separate lines:
- **"Same overall verdict: Fail"** (green) or **"Different overall verdict: judge → Pass, agent → Fail"** (red);
- **"Rule level: judge disputes at least one blocking rule (2 disputed)"**, with the per-rule disputes expanded below.

History analytics now report "judge reaches the same overall verdict in N%" next to the rule-level split. Older runs without the field show "not compared (older run)".

## 6. Issues found and resolutions

| # | Issue | Sev. | Resolution |
|---|---|---|---|
| 1 | Judge on the critical path (+7–16 s) | high | **Fixed**: background judge, `run_id` join, `read_runs()` |
| 2 | Checks in 4 waves (`MAX_CONCURRENCY=5`) | high | **Fixed**: 20 |
| 3 | Classifier and prewarm serial before any check | med | **Fixed**: concurrent; `always` checks don't wait for the classifier |
| 4 | History "Judge disagrees with the verdict" for rule-level disputes | high | **Fixed**: verdict-level comparison computed by code |
| 5 | Over-strict language rules ("instrument") | high | **Fixed in the prompt** (Materiality); verified on the case, out-of-sample texts and the eval |
| 6 | Unclosed HTTP clients: stderr noise; one 2-minute stall after a run | low | **Fixed**: `LLM.aclose()` bounded to 5 s |
| 7 | NOTES claimed threshold 0.5 was written to `.env.example` | low | **Fixed**: NOTES corrected, 0.2 kept |
| 8 | Stage 0 log empty and `pending`; stage 6 calibration not run; stage 8 not marked cut | low | **Fixed**: logs and statuses filled, calibration run |
| 9 | No README | high | **Fixed**: README (author's thinking doc) + `docs/technical-overview.md` (how to run, architecture, results) |
| 10 | Offline tests could have started a background judge with a real client | med | **Fixed**: tests pin `judge="sync"` / monkeypatch; rule recorded in `CLAUDE.md` |
| 11 | Rule set: duplicates (5.7(3)-a/-b; 5.3(1)(b) ≈ 5.7(2)), broad `5.3-1c-c`, lost jargon nuance (`5.7-2-b` rejected) | med | **Open**: needs stage 8 or a manual edit of `rules.json` (owner's call, since it changes the reviewed rule set) |
| 12 | NEEDS_HUMAN_REVIEW labels vs R → blocking severity on 4 golden cases | med | **Open**: decision for the owner (§8) |
| 13 | Golden mapping puts `5.3-2-a` (clarity) under "misleading" concepts, inflating false PASS | low | **Open**: a stage 2 mapping fix; not done here, so as not to touch golden data without the owner |
| 14 | Judge calibration metric (stage 6 definition) is harsh: 12/23 "consistent"; it counts the judge disputing unmapped rules as a false alarm | low | Kept; the verdict-level comparison added next to it is the more useful number |
| 15 | Errors carry OpenAI's masked key (last 3 chars) into `runs.jsonl` | low | Accepted: masked by OpenAI, file is git-ignored |
| 16 | Commit prefixes not `stage-NN:` | low | Noted only (history not rewritten) |

## 7. Verification run in this stage

- `python -m pytest`: **75 passed** offline (5 new: verdict-level judge, background judge record merge, sync fallback without a log, `read_runs` robustness, always-checks start before the classifier answers).
- Clean copy of exactly the files to be committed (no `.env`, no `runs.jsonl`): fresh venv, `pip install -r requirements.txt`, 75 tests pass, `OPENAI_API_KEY=… python -m agent "Install our app and get rich tomorrow 🚀🚀🚀"` prints **FAIL** (14/18, 7 blocking), then the judge section; stderr empty.
- Secrets: `git log -p --all` has no `sk-…` key pattern, and `.env` was never in any commit.
- Live: dark-mode case ×3 (PASS, judge agrees), reference case (FAIL, judge agrees), 2 out-of-sample texts, full eval (`examples/eval_report.md`, $0.38).
- UI: Streamlit `AppTest` renders all tabs without exceptions; History shows the new two-line judge panel on new runs.

## 8. Open decisions for the owner

1. **Golden labels vs severity (#12).** Either add `FAIL` to `acceptable_overall` for `fomo-free-share`, `unexplained-jargon`, `disclaimer-overload` and `wall-of-text-product-page` (with a note that the strong judge agrees), or keep the labels and accept that R → blocking is too coarse for those cases. Changing the labels after seeing results must be recorded as such (spec §8.1).
2. **Rule-set cleanup (#11).** Merge 5.7(3)-a/-b and 5.3(1)(b)/5.7(2); restore the "unavoidable jargon" nuance; tighten `5.3-1c-c`. Each duplicate is one more chance of a false FAIL. This needs stage 8 or a hand edit of `rules.json`.
3. **Confirm blocking fails** (not built): re-ask a blocking `fail` once more with the strong model, or two more times with the fast one, and keep the majority. Cost is proportional to the few blocking fails per run. This would change the spec's "one call per rule" design, so it needs your go-ahead.
4. **Fix the `5.3-2-a` mapping in golden (#13).**
