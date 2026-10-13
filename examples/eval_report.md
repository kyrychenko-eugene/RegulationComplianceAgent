# Eval run — golden set through `agent.check()`

23 cases, 57 expectations, 112 (expectation, rule) pairs. Models: gpt-6-luna (checks); classifier threshold 0.2.

## 1. Headline metrics
- **False PASS rate** (expected fail, rule returned pass): **7/73 (9.6%)**
  - plus expected fail but rule not run (classifier did not select it): 0/73 (0.0%)
  - expectation level (no mapped rule failed): 1/34 (2.9%)
- False FAIL rate (expected pass, rule returned fail): 4/39 (10.3%)
- Unclear rate: 1/112 (0.9%)
  - by `unclear_reason` (all checked rules): model=4
- Overall-verdict agreement: 17/23 (73.9%)
- Known gaps (not counted as errors): 4 expectations
- Run errors: 0

## 2. Missed violations (false PASS / not run)
- `up-to-12-percent` / `PRIN2A.5.3-2-a` (pass) — 'up to 12%' headline rate presented without conditions, implying it is typical or achievable
- `guaranteed-staking` / `PRIN2A.5.3-2-a` (pass) — 'guaranteed' income and 'zero risk' are false certainty claims
- `guaranteed-staking` / `PRIN2A.5.3-1c-b` (pass) — risks are denied rather than explained
- `retiree-pension-crypto` / `PRIN2A.5.3-2-a` (pass) — 'the smart move at your age' presents a high-risk choice as sensible
- `welcome-bonus-no-conditions` / `PRIN2A.5.3-1a-a` (pass) — conditions of the bonus (minimum deposit, holding period, eligibility) are missing; information needs not met
- `welcome-bonus-no-conditions` / `PRIN2A.2.3-b-a` (pass) — 'today' adds time pressure to an account-opening decision
- `wall-of-text-product-page` / `PRIN2A.5.7-1-a` (pass) — information is not presented in a logical, structured way and key facts (total cost, risk) are not prominent

## 3. False FAIL
- `buried-disclaimer-email` / `PRIN2A.5.3-1c-c` — a risk statement is present
- `fomo-free-share` / `PRIN2A.5.3-1c-c` — basic risk statement is present
- `regret-and-inflation-fear` / `PRIN2A.5.3-1c-c` — risk of total loss is stated
- `wall-of-text-product-page` / `PRIN2A.5.3-1c-c` — risk of loss is stated

## 4. Per-rule agreement with expectations

| rule | severity | pairs | agree | false PASS | false FAIL | unclear | not run |
|---|---|---|---|---|---|---|---|
| `PRIN2A.2.10-2-a` | advisory | 4 | 4 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.10-2-b` | advisory | 2 | 2 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.10-5iii-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.20-2-a` | advisory | 2 | 2 | 0 | 0 | 0 | 0 |
| `PRIN2A.2.3-b-a` | advisory | 7 | 4 | 1 | 0 | 0 | 2 |
| `PRIN2A.2.3-c-a` | advisory | 2 | 2 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-1a-a` | blocking | 3 | 2 | 1 | 0 | 0 | 0 |
| `PRIN2A.5.3-1b-a` | blocking | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-1c-b` | blocking | 18 | 17 | 1 | 0 | 0 | 0 |
| `PRIN2A.5.3-1c-c` | blocking | 18 | 14 | 0 | 4 | 0 | 0 |
| `PRIN2A.5.3-2-a` | blocking | 14 | 11 | 3 | 0 | 0 | 0 |
| `PRIN2A.5.3-2-b` | blocking | 14 | 14 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.3-2-c` | blocking | 14 | 13 | 0 | 0 | 1 | 0 |
| `PRIN2A.5.7-1-a` | advisory | 1 | 0 | 1 | 0 | 0 | 0 |
| `PRIN2A.5.7-2-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-3-a` | advisory | 3 | 3 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-3-b` | advisory | 3 | 3 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-4-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-5-a` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.7-5-b` | advisory | 1 | 1 | 0 | 0 | 0 | 0 |
| `PRIN2A.5.8-2-a` | blocking | 1 | 1 | 0 | 0 | 0 | 0 |

## 5. Overall verdict per case

| case | expected | acceptable | agent | ok | fail/unclear rules |
|---|---|---|---|---|---|
| get-rich-tomorrow | FAIL | FAIL | FAIL | yes | 15/0 of 18 |
| compliant-balanced-landing | PASS | PASS | FAIL | **NO** | 3/0 of 18 |
| up-to-12-percent | FAIL | FAIL | FAIL | yes | 13/0 of 18 |
| buried-disclaimer-email | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW/FAIL | FAIL | yes | 11/0 of 19 |
| fomo-free-share | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 8/1 of 19 |
| unexplained-jargon | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 5/0 of 19 |
| targets-financial-hardship | FAIL | FAIL | FAIL | yes | 19/0 of 21 |
| guaranteed-staking | FAIL | FAIL | FAIL | yes | 12/0 of 18 |
| copy-top-trader-returns | FAIL | FAIL | FAIL | yes | 15/0 of 18 |
| past-performance-with-caveat | PASS | PASS/NEEDS_HUMAN_REVIEW | FAIL | **NO** | 1/0 of 18 |
| service-update-no-promotion | PASS | PASS | PASS | yes | 0/0 of 17 |
| neutral-market-reminder | PASS | PASS | NEEDS_HUMAN_REVIEW | **NO** | 0/1 of 18 |
| free-headline-fee-footnote | FAIL | FAIL | FAIL | yes | 14/0 of 18 |
| isa-vs-savings-comparison | FAIL | FAIL | FAIL | yes | 15/0 of 18 |
| leveraged-product-for-beginners | FAIL | FAIL | FAIL | yes | 18/0 of 22 |
| retiree-pension-crypto | FAIL | FAIL | FAIL | yes | 17/0 of 21 |
| welcome-bonus-no-conditions | FAIL | FAIL | FAIL | yes | 3/1 of 18 |
| regret-and-inflation-fear | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW/FAIL | FAIL | yes | 8/0 of 19 |
| disclaimer-overload | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | yes | 2/0 of 18 |
| wall-of-text-product-page | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW | FAIL | **NO** | 12/0 of 19 |
| exit-barrier-retention | NEEDS_HUMAN_REVIEW | NEEDS_HUMAN_REVIEW/FAIL | NEEDS_HUMAN_REVIEW | yes | 3/0 of 19 |
| compliant-crypto-explained | PASS | PASS | PASS | yes | 0/0 of 18 |
| account-change-accept-now | FAIL | FAIL/NEEDS_HUMAN_REVIEW | FAIL | yes | 10/1 of 17 |

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

Reference case overall verdict: **FAIL** (must be FAIL).
Total cost of the run: $0.0920.
