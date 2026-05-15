"""Render the final SOLUTION.md deliverable in full."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import BUILD, read_text, page_header

st.set_page_config(page_title="Final SOLUTION.md", layout="wide")

page_header("📑", "Final solution document",
            "The full `build/SOLUTION.md` deliverable: 9 sections covering "
            "everything from the executive summary to the production-rollout "
            "recommendations.")

content = read_text(BUILD / "SOLUTION.md")

with st.sidebar:
    st.markdown("### Section quick-jump")
    for line in content.splitlines():
        if line.startswith("## "):
            anchor = line[3:].strip().split()[0]
            st.markdown(f"- {line[3:].strip()}")
        elif line.startswith("### "):
            st.markdown(f"&nbsp;&nbsp;• {line[4:].strip()}")

st.markdown(content)
