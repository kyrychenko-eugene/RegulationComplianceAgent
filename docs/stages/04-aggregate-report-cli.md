# Stage 4 — Aggregation, report, CLI, run log

Block: B. Agent · Status: done

## Goal
Turn per-rule results into a deterministic overall verdict and a readable report, expose the public `agent.check(text) -> RunResult`, and record every run with timings.

## Depends on
Stage 3. Spec §5.7–5.9, §7.

## Produces
- `agent/aggregate.py`, `agent/report.py`, `agent/runlog.py`, `agent/__main__.py`, public `agent.check()`.
- `common/schemas.py` extended: `RunResult`.
- `examples/` — a sample Markdown report and JSON for the reference case.
- `.gitignore` entry for `runs.jsonl`.

## Scope
1. **Aggregation** (code, spec §5.7): FAIL if any blocking rule failed; NEEDS_HUMAN_REVIEW if any fail or unclear; else PASS. Technical problems can never yield PASS.
2. **Summary**: code template, e.g. `FAIL: 3 of 18 rules failed (2 blocking, 1 advisory); 1 unclear.` + list of failed/unclear rules with `source_ref`, reasoning, quote or "omission: …".
3. **Report**: one function → Markdown (verdict, summary, table of all rules, details for fail/unclear) and JSON (full `RunResult`).
4. **CLI**: `python -m agent "<text>"` or `--file path`; prints Markdown, optional `--json out.json`.
5. **Run log**: one line per run appended to `runs.jsonl` with all fields in spec §7, including timings (`total_ms`, `classify_ms`, `prewarm_ms`, `checks_wall_ms`, `rule_latency_avg_ms`, `rule_latency_max_ms`), token usage, cost from the dated price table (add `PRICES` and `cost_usd` to `common/config.py` / `common/llm.py` here; deferred from stage 1), `rules_hash`.

## Out of scope
Judge block in the log (filled in stage 6; field present with `status: not_run`). UI.

## Done when
- `python -m agent "Install our app and get rich tomorrow 🚀🚀🚀"` prints a report with overall FAIL and citations to PRIN 2A provisions.
- A new line appears in `runs.jsonl` with all spec §7 fields.
- Unit tests (no API) for aggregation: all three outcomes, plus "only advisory fails" and "technical unclear only".
- Sample report committed in `examples/`.

## Execution log
_Executor model:_ Claude Sonnet 5.5 (claude-sonnet-5-5).
_Review findings:_ none yet (no separate reviewer run); self-checks: 59 offline tests pass; live run on the reference case: FAIL, 18 rules, 13 fail, 0 errors, one line in `runs.jsonl` with every spec §7 key.
_Fixes:_ none needed after the first live run. Additions beyond the file list: `RuleResult` gained `title`, `source_ref`, `severity`, `prompt`, `raw_response` (copied in by `agent.check` so a `RunResult` is self-contained and the log carries the full prompt/raw response required by §7); `agent/checker.py` records prompt and raw response per call.
