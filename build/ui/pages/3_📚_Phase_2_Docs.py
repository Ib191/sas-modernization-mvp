"""Phase 2 — Parse documentation into structured entities."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, load_json, read_text, page_header,
                  tutorial_intro, demo_prompt)

st.set_page_config(page_title="Phase 2 — Documentation", layout="wide")

page_header("📚", "Phase 2 — Parse documentation into structured entities",
            "Markdown specs broken into sections, business rules, and "
            "open-issue nodes that the knowledge graph can reason about.")

tutorial_intro(
    why=(
        "The SAS code says **what** the pipeline does. The docs say **why** "
        "and surface **known issues** — deferred work, vendor-specific "
        "quirks, decisions the medical monitor accepted but flagged. Both "
        "feed the knowledge graph. Without docs, you don't know that the "
        "TRTEMFL definition is contested or that vendor B's GRADE codes are "
        "deferred — and those become silent bugs."
    ),
    what=(
        "- A section index for each markdown doc\n"
        "- Every business rule extracted from §4.x derivation sections\n"
        "- Every open issue with its tracker (SP-184, SP-227) and provenance"
    ),
    insight=(
        "**Tracker IDs become anchors.** When the parser sees `SP-227` in §6.3, "
        "it creates an `OpenIssue` node with that ID. That node will then be "
        "wired in Phase 3 to the affected dataset and column. Result: the "
        "ambiguity register in SOLUTION.md §1.5 isn't hand-curated — it's a "
        "natural by-product of the graph having `flagged_by` edges."
    ),
    speaker=(
        "Open the **Open issues** section below. Notice that **SP-227** "
        "('first dose vs randomization' for TRTEMFL) and **SP-184** "
        "(vendor B GRADE codes) are extracted with their tracker IDs and "
        "datasets. These two will become Medium- and High-severity items "
        "in the ambiguity register, with full counterfactual write-ups. "
        "The functional spec was a regular markdown file — no annotations, "
        "no special schema — and yet the parser surfaces all the issues "
        "that matter."
    ),
)

docs = load_json(BUILD / "graph" / "doc_entities.json")

# ---------------------------------------------------------------------------
# Source documents (toggleable preview)
# ---------------------------------------------------------------------------

st.subheader("Source documents")

doc_paths = [d["file"] for d in docs["documents"]]
sel = st.selectbox("Document", doc_paths)
md = read_text(sel)
with st.expander("Show full source", expanded=False):
    st.code(md, language="markdown", line_numbers=True)

# ---------------------------------------------------------------------------
# Sections per document
# ---------------------------------------------------------------------------

st.subheader("Section index")

for doc in docs["documents"]:
    if doc["file"] != sel:
        continue
    rows = []
    for s in doc["sections"]:
        rows.append({
            "level": "#" * s["level"],
            "title": s["title"],
            "line": s["line_start"],
            "datasets": ", ".join(s["datasets"]) or "—",
            "columns": ", ".join(s["columns"][:6])
                + ("…" if len(s["columns"]) > 6 else "") or "—",
            "bullets": len(s["bullets"]),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
# Business rules
# ---------------------------------------------------------------------------

st.divider()
st.subheader(f"Business rules ({len(docs['business_rules'])})")
st.caption("Bullets inside §4.x derivation/cleaning sections.")

br_rows = [{
    "section": r["source_section"],
    "line": r["source_line"],
    "datasets": ", ".join(r["datasets"]) or "—",
    "columns": ", ".join(r["columns"][:5])
        + ("…" if len(r["columns"]) > 5 else "") or "—",
    "text": r["text"][:200] + ("…" if len(r["text"]) > 200 else ""),
} for r in docs["business_rules"]]
st.dataframe(pd.DataFrame(br_rows), hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
# Open issues
# ---------------------------------------------------------------------------

st.divider()
st.subheader(f"Open issues ({len(docs['open_issues'])})")
st.caption("Each open issue becomes an `OpenIssue` node in the graph, "
            "linked to the affected datasets and columns.")

for o in docs["open_issues"]:
    with st.expander(f"**{o['id']}** — {o['source_section']}",
                       expanded=("SP-227" in o["id"]) or ("SP-184" in o["id"])):
        st.markdown(f"**Source:** `{o['source_file']}` line {o['source_line']}")
        if o["tickers"]:
            st.markdown(f"**Tickers:** {', '.join(o['tickers'])}")
        if o["datasets"]:
            st.markdown(f"**Datasets:** {', '.join(o['datasets'])}")
        if o["columns"]:
            st.markdown(f"**Columns:** {', '.join(o['columns'])}")
        st.markdown(f"**Text:**\n\n{o['text']}")
