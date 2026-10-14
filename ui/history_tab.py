"""History tab: past runs from runs.jsonl (fallback: the committed sample), a drill-down and a few numbers."""
import html
from collections import Counter
from pathlib import Path

import streamlit as st

import agent
from ui.run_tab import STYLE, _banner, render_run

ROOT = Path(__file__).resolve().parent.parent
RUNS, SAMPLE = ROOT / "runs.jsonl", ROOT / "examples" / "runs.sample.jsonl"


def _load(path: Path) -> list:
    """Runs with background judge records merged in (the agent owns the log format)."""
    return agent.read_runs(path)


def _analytics(runs: list) -> None:
    n = len(runs)
    verdicts = Counter(r.get("verdict") for r in runs)
    results = [x for r in runs for x in r.get("results", [])]
    unclear = Counter(x.get("unclear_reason") or "unspecified" for x in results if x["verdict"] == "unclear")
    inp = sum(r.get("usage", {}).get("input", 0) for r in runs)
    cached = sum(r.get("usage", {}).get("cached", 0) for r in runs)
    out = sum(r.get("usage", {}).get("output", 0) for r in runs)
    judged = Counter(r["judge"]["rating"] for r in runs if r.get("judge", {}).get("rating"))
    same = [r["judge"]["verdict_agrees"] for r in runs if r.get("judge", {}).get("verdict_agrees") is not None]
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
    if same:
        st.caption(f"Judge reaches the same overall verdict in {sum(same) / len(same):.0%} of {len(same)} judged runs")
    if judged:
        st.caption("Judge, rule level: " + ", ".join(f"{k} {v / sum(judged.values()):.0%}" for k, v in judged.items()))
    if missed:
        st.caption("Most-missed rules (per judge): " + ", ".join(f"{k} ×{v}" for k, v in missed.most_common(5)))


RULE_LEVEL = {"agree": "agrees with every rule verdict", "partial": "disputes advisory rules only",
              "disagree": "disputes at least one blocking rule"}
GREEN, AMBER, RED, GREY = "#1a7f37", "#bf8700", "#cf222e", "#6e7781"


def _judge(run: dict) -> None:
    """Second opinion, in two separate lines: does the judge reach the same overall verdict, and which single
    rule verdicts does it dispute. A judge can dispute rules and still land on the same overall verdict."""
    j = run.get("judge") or {}
    st.markdown("**Judge** (monitoring only, never changes the verdict)")
    status = j.get("status")
    if status == "pending":
        _banner(GREY, "Judge still running", "Its result is added to the history when it finishes; refresh to see it.")
        return
    if status != "ok" or j.get("rating") not in RULE_LEVEL:
        _banner(GREY, "Judge unavailable" if status == "unavailable" else "Judge not run")
        return
    disputed, missed = j.get("disputed_verdicts", []), j.get("missed_rules", [])
    agent_verdict, judge_verdict = run.get("verdict"), j.get("overall_verdict")
    if judge_verdict is None:  # record from before the verdict-level comparison existed
        title, color = "Overall verdict: not compared (older run)", GREY
    elif j.get("verdict_agrees"):
        title, color = f"Same overall verdict: {STYLE[judge_verdict][1]}", GREEN
    else:
        title = f"Different overall verdict: judge → {STYLE[judge_verdict][1]}, agent → {STYLE[agent_verdict][1]}"
        color = RED
    rule_color = {"agree": GREEN, "partial": AMBER, "disagree": RED}[j["rating"]]
    notes = [f"{len(disputed)} disputed"] if disputed else []
    notes += [f"{len(missed)} missed"] if missed else []
    _banner(color, title, f"Rule level: judge {RULE_LEVEL[j['rating']]}" + (f" ({', '.join(notes)})" if notes else ""))
    if rule_color != color and disputed:
        st.caption("The judge disputes single rule verdicts; see below whether they change the outcome.")
    with st.expander("Judge reasoning and disputed rules", expanded=bool(disputed or missed)):
        st.markdown(j.get("reasoning", ""))
        for d in disputed:
            st.markdown(f"**Disputed {d.get('rule_id')}:** agent _{d.get('agent_verdict')}_ → judge _{d.get('judge_verdict')}_  \n{d.get('reason', '')}")
        for m in missed:
            st.markdown(f"**Not run {m.get('rule_id')}:** judge expects _{m.get('judge_verdict', 'fail')}_  \n{m.get('reason', '')}")


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
