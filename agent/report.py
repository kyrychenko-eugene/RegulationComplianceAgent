"""One function builds both outputs of a run: Markdown and JSON (spec §5.9)."""
from __future__ import annotations

from typing import Tuple

from common.schemas import RunResult

_ORDER = {"fail": 0, "unclear": 1, "pass": 2}


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def build_report(run: RunResult) -> Tuple[str, str]:
    """Return `(markdown, json)`; the JSON is the full `RunResult`."""
    lines = [f"# Compliance report: {run.verdict}", "", run.summary.split("\n", 1)[0], ""]
    c = run.classifier
    lines.append(f"Classifier: {c.status}; tags: {', '.join(c.tags) or 'none'}"
                 + ("; fallback: all rules run" if c.fallback_all_rules else "")
                 + f". Rules checked: {len(run.results)}.")
    if run.errors:
        lines += ["", "## Errors", ""] + [f"- {_cell(e)}" for e in run.errors]

    lines += ["", "## All rules", "", "| Rule | Title | Source | Severity | Verdict |", "|---|---|---|---|---|"]
    for r in sorted(run.results, key=lambda r: _ORDER[r.verdict]):
        verdict = r.verdict if r.verdict != "unclear" else f"unclear ({r.unclear_reason})"
        lines.append(f"| {r.rule_id} | {_cell(r.title)} | {_cell(r.source_ref)} | {r.severity} | {verdict} |")

    flagged = [r for r in sorted(run.results, key=lambda r: _ORDER[r.verdict]) if r.verdict != "pass"]
    if flagged:
        lines += ["", "## Details: failed and unclear rules"]
    for r in flagged:
        lines += ["", f"### {r.rule_id}: {r.title} — {r.verdict.upper()}",
                  f"- Source: {r.source_ref} ({r.severity})", f"- Reasoning: {' '.join(r.reasoning.split())}"]
        if r.verdict == "fail" and r.violation_type == "content":
            lines.append(f'- Quote: "{r.evidence_quote}" (chars {r.span[0]}–{r.span[1]})' if r.span
                         else f'- Quote: "{r.evidence_quote}"')
        elif r.verdict == "fail":
            lines.append("- Omission: the text lacks what the reasoning names.")
        else:
            lines.append(f"- Unclear reason: {r.unclear_reason}")
    lines += ["", f"Run {run.run_id} · rules hash {run.rules_hash} · {run.timings.total_ms} ms · "
                  f"${run.usage.cost_usd:.4f}", ""]
    return "\n".join(lines), run.model_dump_json(indent=2)
