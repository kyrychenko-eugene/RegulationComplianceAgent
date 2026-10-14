# Eval run — golden set through `agent.check()`

23 cases, 57 expectations, 112 (expectation, rule) pairs. Models: gpt-6-luna (checks); classifier threshold 0.2.

## 1. Headline metrics
- **False PASS rate** (expected fail, rule returned pass): **7/73 (9.6%)**
  - plus expected fail but rule not run (classifier did not select it): 0/73 (0.0%)
  - expectation level (no mapped rule failed): 0/34 (0.0%)
- False FAIL rate (expected pass, rule returned fail): 5/39 (12.8%)
- Unclear rate: 0/112 (0.0%)
  - by `unclear_reason` (all checked rules): model=3
- Overall-verdict agreement: 17/23 (73.9%)
- Known gaps (not counted as errors): 4 expectations
- Run errors: 0

## 2. Missed violations (false PASS / not run)
- `get-rich-tomorrow` / `PRIN2A.5.3-2-a` (pass) — promises fast, certain wealth; misleading about likely outcomes
- `up-to-12-percent` / `PRIN2A.5.3-2-a` (pass) — 'up to 12%' headline rate presented without conditions, implying it is typical or achievable
- `copy-top-trader-returns` / `PRIN2A.5.3-2-a` (pass) — single best-case past return presented as if repeatable
- `isa-vs-savings-comparison` / `PRIN2A.5.3-2-a` (pass) — comparison with savings accounts ignores the different risk; misleading
- `retiree-pension-crypto` / `PRIN2A.5.3-2-a` (pass) — 'the smart move at your age' presents a high-risk choice as sensible
- `wall-of-text-product-page` / `PRIN2A.5.7-5-a` (pass) — too much detail in one block makes it hard to make an effective decision
- `wall-of-text-product-page` / `PRIN2A.5.7-1-a` (pass) — information is not presented in a logical, structured way and key facts (total cost, risk) are not prominent

## 3. False FAIL
- `buried-disclaimer-email` / `PRIN2A.5.3-1c-b` — a risk statement is present
- `buried-disclaimer-email` / `PRIN2A.5.3-1c-c` — a risk statement is present
- `fomo-free-share` / `PRIN2A.5.3-1c-c` — basic risk statement is present
- `regret-and-inflation-fear` / `PRIN2A.5.3-1c-b` — risk of total loss is stated
- `regret-and-inflation-fear` / `PRIN2A.5.3-1c-c` — risk of total loss is stated

## 4. Per-rule agreement with expectations

| rule | severity | pairs | agree | false PASS | false FAIL | unclear | not run |
|---|---|---|---|---|---|---|---|
| `PRIN2A.2.10-2-a` | advisory | 4 | 4 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.10-2-b` | advisory | 2 | 2 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.10-5iii-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.20-2-a` | advisory | 2 | 2 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.3-b-a` | advisory | 7 | 5 | 0 | 0 | 0 | 2 |
| `PRIN2A.2.3-c-a` | advisory | 2 | 2 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-1a-a` | blocking | 3 | 3 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-1b-a` | blocking | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-1c-b` | blocking | 18 | 16 | 0 | 2 | 0 | 0 |
| `PRIN2A.5.3-1c-c` | blocking | 18 | 15 | 0 | 3 | 0 | 0 |
| `PRIN2A.5.3-2-a` | blocking | 14 | 9 | 5 | 0 | 0 | 0 |
| `PRIN2A.5.3-2-b` | blocking | 14 | 14 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-2-c` | blocking | 14 | 14 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-1-a` | advisory | 1 | 0 | 1 | 0 | 0 | 0 |
| `PRIN2A.5.7-2-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-3-a` | advisory | 3 | 3 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-3-b` | advisory | 3 | 3 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-4-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-5-a` | advisory | 1 | 0 | 1 | 0 | 0 | 0 |
| `PRIN2A.5.7-5-b` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.8-2-a` | blocking | 1 | 1 | 0 | 0 | 0 | 0 |

## 5. Overall verdict per case

| case | expected | acceptable | agent | ok | fail/unclear rules |
|---|---|---|---|---|---|
| get-rich-tomorrow | FAIL | FAIL | FAIL | yes | 14/0 of 18 |
| compliant-balanced-landing | PASS | PASS | NEEDS_HUMAN_REVIEW | **NO** | 1/0 of 18 |
| up-to-12-percent | FAIL | FAIL | FAIL | yes | 13/0 of 18 |
| buried-disclaimer-email | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW/FAIL | FAIL | yes | 12/0 of 19 |
| fomo-free-share | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 9/1 of 19 |
| unexplained-jargon | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 8/0 of 19 |
| targets-financial-hardship | FAIL | FAIL | FAIL | yes | 20/0 of 21 |
| guaranteed-staking | FAIL | FAIL | FAIL | yes | 16/0 of 18 |
| copy-top-trader-returns | FAIL | FAIL | FAIL | yes | 14/0 of 18 |
| past-performance-with-caveat | PASS | PASS/NEEDS_HUMAN_REVIEW | FAIL | **NO** | 1/0 of 18 |
| service-update-no-promotion | PASS | PASS | PASS | yes | 0/0 of 17 |
| neutral-market-reminder | PASS | PASS | PASS | yes | 0/0 of 18 |
| free-headline-fee-footnote | FAIL | FAIL | FAIL | yes | 14/0 of 18 |
| isa-vs-savings-comparison | FAIL | FAIL | FAIL | yes | 13/0 of 18 |
| leveraged-product-for-beginners | FAIL | FAIL | FAIL | yes | 19/0 of 22 |
| retiree-pension-crypto | FAIL | FAIL | FAIL | yes | 17/0 of 21 |
| welcome-bonus-no-conditions | FAIL | FAIL | FAIL | yes | 8/2 of 18 |
| regret-and-inflation-fear | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW/FAIL | FAIL | yes | 10/0 of 19 |
| disclaimer-overload | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 3/0 of 18 |
| wall-of-text-product-page | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 10/0 of 19 |
| exit-barrier-retention | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW/FAIL | NEEDS_HUMAN_REVIEW | yes | 2/0 of 19 |
| compliant-crypto-explained | PASS | PASS | PASS | yes | 0/0 of 18 |
| account-change-accept-now | FAIL | FAIL/NEEDS_HUMAN_REVIEW | FAIL | yes | 10/0 of 17 |

## 6. Classifier threshold sweep

Miss = conditional rule mapped to an `expected: fail` expectation that the classifier did not select. Extra = conditional rules selected beyond those needed. Cases where the classifier fell back to all rules are excluded (no probabilities).
Usable cases: 23/23

| threshold | misses | extra checks | cases with a miss |
|---|---|---|---|
| 0.05 | 0 | 40 | - |
| 0.1 | 0 | 30 | - |
| 0.15 | 0 | 27 | - |
| 0.2 | 0 | 26 | - |
| 0.25 | 0 | 26 | - |
| 0.3 | 0 | 25 | - |
| 0.35 | 0 | 25 | - |
| 0.4 | 0 | 25 | - |
| 0.45 | 0 | 25 | - |
| 0.5 | 0 | 24 | - |

**Recommended `CLASSIFIER_THRESHOLD`: 0.5** (highest threshold with zero misses).

## 7. Known gaps
- `free-headline-fee-footnote`: PRIN 2A.2.1; PRIN 2A.2.2 — PRIN 2A.2.1/2A.2.2 (open dealing) has no approved rule: 2A.2.2-a/-c were rejected by the ingest critic; 2A.2.2-b covers only manipulative wording.
- `retiree-pension-crypto`: PRIN 2A.5.8(1) — PRIN 2A.5.8(1) (tailoring to customer characteristics): all drafts rejected by the ingest critic (faithful=1).
- `exit-barrier-retention`: PRIN 2A.2.3(d) — PRIN 2A.2.3(d) was dropped by the ingest filter; no rule.
- `account-change-accept-now`: PRIN 2A.5.6(2) — PRIN 2A.5.6(2) (opportunity to review information) was dropped by the ingest filter; no rule.

## 8. Judge calibration

Judge returned for 23/23 cases (the rest: unavailable or not run).
- **Judge agreement with golden labels** (agent-right → `agree`, agent-wrong → `partial`/`disagree`): **12/23 (52.2%)**
  - agent-wrong cases the judge flagged (recall): 6/9 (66.7%)
  - agent-right cases the judge flagged anyway (false alarms): 8/14 (57.1%)
- **Overall-verdict agreement if the judge's rule verdicts were applied**: **18/23 (78.3%)** (agent on the same cases: 17/23 (73.9%)). Diagnostic only: the judge never changes the verdict.
  - judge reaches the same overall verdict as the agent: 21/23 (91.3%)
  - ratings: agree=9, partial=4, disagree=10
  - rules the judge reported as missed (classifier misses): `PRIN2A.5.8-2-a`×3, `PRIN2A.2.3-b-a`×1

| case | expected | agent | judge overall | agent vs labels | judge rule rating | missed | disputed | consistent |
|---|---|---|---|---|---|---|---|---|
| get-rich-tomorrow | FAIL | FAIL | FAIL | wrong | agree | 0 | 0 | **NO** |
| compliant-balanced-landing | PASS | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | right | agree | 0 | 0 | yes |
| up-to-12-percent | FAIL | FAIL | FAIL | wrong | partial | 0 | 2 | yes |
| buried-disclaimer-email | NEEDS_HUMAN_REVIEW/FAIL | FAIL | FAIL | wrong | disagree | 1 | 1 | yes |
| fomo-free-share | NEEDS_HUMAN_REVIEW | FAIL | FAIL | wrong | disagree | 0 | 2 | yes |
| unexplained-jargon | NEEDS_HUMAN_REVIEW | FAIL | FAIL | right | disagree | 0 | 3 | **NO** |
| targets-financial-hardship | FAIL | FAIL | FAIL | right | agree | 0 | 0 | yes |
| guaranteed-staking | FAIL | FAIL | FAIL | right | disagree | 1 | 0 | **NO** |
| copy-top-trader-returns | FAIL | FAIL | FAIL | wrong | agree | 0 | 0 | **NO** |
| past-performance-with-caveat | PASS/NEEDS_HUMAN_REVIEW | FAIL | PASS | right | disagree | 0 | 1 | **NO** |
| service-update-no-promotion | PASS | PASS | PASS | right | agree | 0 | 0 | yes |
| neutral-market-reminder | PASS | PASS | PASS | right | agree | 0 | 0 | yes |
| free-headline-fee-footnote | FAIL | FAIL | FAIL | right | partial | 0 | 2 | **NO** |
| isa-vs-savings-comparison | FAIL | FAIL | FAIL | wrong | agree | 0 | 0 | **NO** |
| leveraged-product-for-beginners | FAIL | FAIL | FAIL | right | agree | 0 | 0 | yes |
| retiree-pension-crypto | FAIL | FAIL | FAIL | wrong | partial | 0 | 1 | yes |
| welcome-bonus-no-conditions | FAIL | FAIL | FAIL | right | disagree | 0 | 4 | **NO** |
| regret-and-inflation-fear | NEEDS_HUMAN_REVIEW/FAIL | FAIL | FAIL | wrong | partial | 0 | 1 | yes |
| disclaimer-overload | NEEDS_HUMAN_REVIEW | FAIL | FAIL | right | disagree | 1 | 0 | **NO** |
| wall-of-text-product-page | NEEDS_HUMAN_REVIEW | FAIL | FAIL | wrong | disagree | 0 | 1 | yes |
| exit-barrier-retention | NEEDS_HUMAN_REVIEW/FAIL | NEEDS_HUMAN_REVIEW | FAIL | right | disagree | 0 | 1 | **NO** |
| compliant-crypto-explained | PASS | PASS | PASS | right | agree | 0 | 0 | yes |
| account-change-accept-now | FAIL/NEEDS_HUMAN_REVIEW | FAIL | FAIL | right | disagree | 1 | 1 | **NO** |

Reference case overall verdict: **FAIL** (must be FAIL).
Total cost of the run: $0.3807.
