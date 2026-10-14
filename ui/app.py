"""Streamlit entry point: `streamlit run ui/app.py`. Thin layer over agent.check(), runs.jsonl and rules.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from ui import history_tab, rules_tab, run_tab  # noqa: E402

st.set_page_config(page_title="Marketing compliance check", page_icon="✅", layout="centered")
st.title("Marketing compliance check")
st.caption("Checks a marketing text against FCA PS22/9 (PRIN 2A).")

tab_run, tab_history, tab_rules = st.tabs(["Check", "History", "Rules"])
with tab_run:
    run_tab.render()
with tab_history:
    history_tab.render()
with tab_rules:
    rules_tab.render()
