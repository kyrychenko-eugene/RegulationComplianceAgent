"""One function builds both outputs of a run: Markdown and JSON (spec §5.9)."""
from __future__ import annotations

from typing import Tuple

from common.schemas import JudgeInfo, RunResult

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
    lines += [""] + judge_section(run.judge, run.verdict)
    lines += ["", f"Run {run.run_id} · rules hash {run.rules_hash} · {run.timings.total_ms} ms · "
                  f"${run.usage.cost_usd:.4f}", ""]
    return "\n".join(lines), run.model_dump_json(indent=2)


def judge_section(j: JudgeInfo, agent_verdict: str) -> list:
    """Markdown lines for the judge block. Verdict level and rule level are reported separately: the judge can
    dispute single rules and still reach the same overall verdict."""
    head = "## Judge (monitoring only, never changes the verdict)"
    if j.status == "pending":
        return [head, "", "Running in the background; its record is appended to the run log under this run id."]
    if j.status != "ok":
        return [head, "", f"Judge {j.status.replace('_', ' ')}."]
    if j.overall_verdict is None:
        overall = "not computed (older record)"
    elif j.verdict_agrees:
        overall = f"same as the agent ({j.overall_verdict})"
    else:
        overall = f"**{j.overall_verdict}** instead of the agent's {agent_verdict}"
    lines = [head, "", f"- Overall verdict implied by the judge's rule verdicts: {overall}",
             f"- Rule level: {j.rating} — {len(j.disputed_verdicts)} disputed, {len(j.missed_rules)} missed",
             f"- Reasoning: {' '.join(j.reasoning.split())}"]
    for d in j.disputed_verdicts:
        lines.append(f"- Disputed {d.get('rule_id')}: agent {d.get('agent_verdict')} → judge {d.get('judge_verdict')}. "
                     f"{' '.join(str(d.get('reason', '')).split())}")
    for m in j.missed_rules:
        lines.append(f"- Missed {m.get('rule_id')} (judge expects {m.get('judge_verdict', 'fail')}): "
                     f"{' '.join(str(m.get('reason', '')).split())}")
    return lines
