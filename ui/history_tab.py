"""History tab: past runs from runs.jsonl (fallback: the committed sample), a drill-down and a few numbers."""
import html
import json
from collections import Counter
from pathlib import Path

import streamlit as st

from ui.run_tab import STYLE, _banner, render_run

ROOT = Path(__file__).resolve().parent.parent
RUNS, SAMPLE = ROOT / "runs.jsonl", ROOT / "examples" / "runs.sample.jsonl"


def _load(path: Path) -> list:
    runs = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue  # skip a corrupt line, keep the rest
    return runs


def _analytics(runs: list) -> None:
    n = len(runs)
    verdicts = Counter(r.get("verdict") for r in runs)
    results = [x for r in runs for x in r.get("results", [])]
    unclear = Counter(x.get("unclear_reason") or "unspecified" for x in results if x["verdict"] == "unclear")
    inp = sum(r.get("usage", {}).get("input", 0) for r in runs)
    cached = sum(r.get("usage", {}).get("cached", 0) for r in runs)
    out = sum(r.get("usage", {}).get("output", 0) for r in runs)
    judged = Counter(r["judge"]["rating"] for r in runs if r.get("judge", {}).get("rating"))
    missed = Counter(m.get("rule_id") for r in runs for m in r.get("judge", {}).get("missed_rules", []))

    c = st.columns(3)
    for col, v in zip(c, ("PASS", "FAIL", "NEEDS_HUMAN_REVIEW")):
        col.metric(STYLE[v][1], verdicts.get(v, 0))
    total_ms = [r.get("timings", {}).get("total_ms", 0) for r in runs]
    c = st.columns(3)
    c[0].metric("Latency avg / max", f"{sum(total_ms) / n / 1000:.1f}s / {max(total_ms) / 1000:.1f}s")
    c[1].metric("Cost", f"${sum(r.get('usage', {}).get('cost_usd', 0) for r in runs):.3f}")
    c[2].metric("Cache hit rate", f"{cached / inp:.0%}" if inp else "n/a")
    st.caption(f"Tokens: {inp:,} in · {out:,} out")
    if unclear:
        st.caption("Unclear by reason: " + ", ".join(f"{k} {v}" for k, v in unclear.items()))
    if judged:
        st.caption("Judge: " + ", ".join(f"{k} {v / sum(judged.values()):.0%}" for k, v in judged.items()))
    if missed:
        st.caption("Most-missed rules (per judge): " + ", ".join(f"{k} ×{v}" for k, v in missed.most_common(5)))


JUDGE = {  # rating -> (colour, headline)
    "agree": ("#1a7f37", "Judge agrees with the verdict"),
    "partial": ("#bf8700", "Judge partly disagrees"),
    "disagree": ("#cf222e", "Judge disagrees with the verdict"),
}


def _judge(run: dict) -> None:
    """Second-opinion section shown above the run: colour + status at a glance, details expandable."""
    j = run.get("judge") or {}
    st.markdown("**Judge**")
    if j.get("status") != "ok" or j.get("rating") not in JUDGE:
        text = "Judge unavailable" if j.get("status") == "unavailable" else "Judge not run"
        _banner("#6e7781", text)
        return
    color, text = JUDGE[j["rating"]]
    disputed, missed = j.get("disputed_verdicts", []), j.get("missed_rules", [])
    notes = [f"{len(disputed)} disputed verdict(s)"] if disputed else []
    notes += [f"{len(missed)} missed rule(s)"] if missed else []
    _banner(color, text, "; ".join(notes))
    with st.expander("Judge reasoning"):
        st.markdown(j.get("reasoning", ""))
        for d in disputed:
            st.markdown(f"**Disputed {d.get('rule_id')}:** agent said _{d.get('agent_verdict')}_, judge says _{d.get('judge_verdict')}_  \n{d.get('reason', '')}")
        for m in missed:
            st.markdown(f"**Missed {m.get('rule_id')}:** {m.get('reason', '')}")


def render() -> None:
    runs, example = _load(RUNS), False
    if not runs:
        runs, example = _load(SAMPLE), True
    if not runs:
        st.info("No runs yet.")
        return
    if example:
        st.info("No runs of your own yet: showing **example** runs.")
    runs = runs[::-1]  # newest first
    _analytics(runs)
    st.divider()
    icon = {"PASS": "🟢", "FAIL": "🔴", "NEEDS_HUMAN_REVIEW": "🟡"}
    idx = st.selectbox(
        "Run", range(len(runs)),
        format_func=lambda i: f"{icon.get(runs[i].get('verdict'), '⚪')} {runs[i].get('started_at', '')[:16].replace('T', ' ')} · "
                              f"{(runs[i].get('input_text') or '').strip()[:60]}")
    st.markdown("**Input text**")
    st.markdown(
        f'<div style="white-space:pre-wrap;border:1px solid #8884;border-radius:6px;padding:10px 14px">'
        f'{html.escape(runs[idx].get("input_text") or "")}</div>', unsafe_allow_html=True)
    _judge(runs[idx])
    st.markdown("**Agent verdict**")
    render_run(runs[idx])
    with st.expander("Run details"):
        r = runs[idx]
        st.json({k: r.get(k) for k in ("run_id", "models", "classifier", "timings", "usage", "judge")}, expanded=False)
