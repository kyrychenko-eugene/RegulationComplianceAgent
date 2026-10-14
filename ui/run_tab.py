"""Check tab: text in, colour-coded verdict out. Failed/unclear rules get cards; passed rules a collapsed short list."""
import html

import streamlit as st

import agent

# verdict -> (colour, label)
STYLE = {
    "PASS": ("#1a7f37", "Pass"),
    "FAIL": ("#cf222e", "Fail"),
    "NEEDS_HUMAN_REVIEW": ("#bf8700", "Needs human review"),
}
RED, AMBER = "#cf222e", "#bf8700"


def _banner(color: str, title: str, subtitle: str = "") -> None:
    sub = f'<div style="font-weight:400;font-size:0.95rem;margin-top:2px">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div style="border-left:6px solid {color};background:{color}1a;padding:12px 16px;'
        f'border-radius:6px;font-size:1.25rem;font-weight:600;color:{color}">{html.escape(title)}{sub}</div>',
        unsafe_allow_html=True)


def _highlighted(text: str, spans: list) -> str:
    """Escape `text` and wrap the (merged) spans in <mark>."""
    merged: list = []
    for s, e in sorted((s, e) for s, e in spans if 0 <= s < e <= len(text)):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out, pos = [], 0
    for s, e in merged:
        out.append(html.escape(text[pos:s]))
        out.append(f'<mark style="background:#ffd8d8;color:#111;border-radius:3px;padding:0 2px">{html.escape(text[s:e])}</mark>')
        pos = e
    out.append(html.escape(text[pos:]))
    return "".join(out)


LEVEL = {"blocking": "Mandatory", "advisory": "Optional"}


def _card(res: dict) -> None:
    """One expandable item per failed / unclear rule: 'PRIN 2A.2.2 R : Title' + status badge."""
    failed = res["verdict"] == "fail"
    badge = ":red-badge[Fail]" if failed else ":orange-badge[Unclear]"
    label = f"{res.get('source_ref') or res['rule_id']} : {res.get('title') or res['rule_id']}  {badge}"
    with st.expander(label, expanded=failed):
        st.markdown(res.get("reasoning", ""))
        if res.get("evidence_quote"):
            st.markdown(f"**{'Missing' if res.get('violation_type') == 'omission' else 'Quote'}:** _“{res['evidence_quote']}”_")
        elif res.get("violation_type") == "omission":
            st.markdown("**Omission:** required information is missing from the text.")
        meta = [LEVEL.get(res.get("severity"), ""), f"unclear: {res['unclear_reason']}" if res.get("unclear_reason") else ""]
        st.caption(" · ".join(m for m in meta if m))


def render_run(run: dict) -> None:
    """Render one run (a RunResult as a dict). Shared with the History tab."""
    results = run.get("results", [])
    total = len(results)
    failed = [r for r in results if r["verdict"] == "fail"]
    unclear = [r for r in results if r["verdict"] == "unclear"]
    verdict = run.get("verdict", "NEEDS_HUMAN_REVIEW")
    color, label = STYLE.get(verdict, STYLE["NEEDS_HUMAN_REVIEW"])

    if verdict == "PASS":
        _banner(color, f"✓ Pass: {total} rules checked")
    else:
        blocking = sum(r.get("severity") == "blocking" for r in failed)
        parts = []
        if failed:
            parts.append(f"{len(failed)} of {total} rules failed ({blocking} blocking)")
        if unclear:
            parts.append(f"{len(unclear)} unclear")
        if not parts:
            parts.append("the run could not be completed")
        _banner(color, f"{'✕' if verdict == 'FAIL' else '!'} {label}", "; ".join(parts))

    for err in run.get("errors", []):
        st.warning(err)

    if verdict != "PASS":
        _flagged(run, failed, unclear)
    _passed_list([r for r in results if r["verdict"] == "pass"])


def _passed_list(passed: list) -> None:
    """Collapsed short list of the rules that were checked and passed: one line each, no reasoning."""
    if not passed:
        return
    with st.expander(f"✓ {len(passed)} rules passed"):
        st.markdown("\n".join(
            f"- {r.get('source_ref') or r['rule_id']} : {r.get('title') or r['rule_id']}"
            + (f" · {LEVEL[r['severity']]}" if r.get("severity") in LEVEL else "")
            for r in passed))


def _flagged(run: dict, failed: list, unclear: list) -> None:
    spans = [r["span"] for r in failed if r.get("span")]
    if spans and run.get("input_text"):
        st.markdown("**Flagged text**")
        st.markdown(
            f'<div style="white-space:pre-wrap;border:1px solid #8884;border-radius:6px;padding:10px 14px">'
            f'{_highlighted(run["input_text"], spans)}</div>', unsafe_allow_html=True)
    for res in failed + unclear:
        _card(res)


def render() -> None:
    # A form sends the text area's current value with the click. A plain button disabled on `not text` only saw
    # the value after the text area lost focus, so the first click after typing or pasting did nothing.
    with st.form("check_form", border=False):
        text = st.text_area("Marketing text", height=160, placeholder="Paste the marketing text to check…")
        submitted = st.form_submit_button("Check", type="primary")
    if submitted:
        if not text.strip():
            st.warning("Paste or type a marketing text first.")
        else:
            with st.spinner("Checking against the rules…"):
                st.session_state["last_run"] = agent.check(text).model_dump()
    if "last_run" in st.session_state:
        render_run(st.session_state["last_run"])
        if st.session_state["last_run"].get("judge", {}).get("status") == "pending":
            st.caption("A second-opinion judge is reviewing this run in the background; "
                       "its result appears in the History tab.")
