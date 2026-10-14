"""Rules tab: what the agent checks, what was rejected, and what was left out of scope. Read-only."""
import json
from pathlib import Path

import streamlit as st

RULES = Path(__file__).resolve().parent.parent / "data" / "rules.json"


def render() -> None:
    try:
        data = json.loads(RULES.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        st.error(f"Cannot read {RULES.name}: {e}")
        return
    rules = data.get("rules", [])
    approved = [r for r in rules if r.get("status") == "approved"]
    rejected = [r for r in rules if r.get("status") == "rejected"]
    dropped = data.get("dropped_provisions", [])

    st.caption(f"{len(approved)} approved · {len(rejected)} rejected · {len(dropped)} provisions out of scope")
    for r in approved:
        c = r.get("critic") or {}
        level = ":red-badge[Mandatory]" if r["severity"] == "blocking" else ":gray-badge[Optional]"
        with st.expander(f"{r['source_ref']} : {r['title']}  {level}"):
            st.markdown(f"**Check:** {r['check']}")
            st.markdown(f"> {r['source_quote']}")
            tags = ", ".join(r.get("tags", [])) or "—"
            st.caption(f"scope: {r['scope']} · tags: {tags} · attempts: {r.get('attempts', 1)}"
                       + (f" · critic: faithful {c.get('faithful')}, atomic {c.get('atomic')}, checkable {c.get('checkable_from_text')}" if c else ""))
    if rejected:
        with st.expander(f"Rejected rules ({len(rejected)})"):
            for r in rejected:
                st.markdown(f"**{r['source_ref']} : {r['title']}**  \n{r.get('rejection_reason') or 'no reason recorded'}")
    if dropped:
        with st.expander(f"Provisions out of scope ({len(dropped)})"):
            for d in dropped:
                st.markdown(f"**{d['provision_id']} ({d['marker']})**: {d['rationale']}")
