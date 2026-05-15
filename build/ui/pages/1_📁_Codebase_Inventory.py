"""Codebase inventory — what we started with."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, load_json, read_text, page_header,
                  tutorial_intro, demo_prompt)

st.set_page_config(page_title="Codebase Inventory", layout="wide")

page_header("📁", "Codebase Inventory",
            "What the SAS estate looks like before any modernization happens.")

tutorial_intro(
    why=(
        "Modernization starts with **inventory**. You can't translate what "
        "you can't see. This page shows every SAS file, every raw input, "
        "and every ground-truth output — the contract the new pipeline must "
        "honor. The numbers here also feed §1.2 of the final SOLUTION.md."
    ),
    what=(
        "- A table of all 8 SAS files with line counts and DATA/PROC counts\n"
        "- A source viewer for each file\n"
        "- The 3 raw input CSVs (`dm.csv`, `ae.csv`, `site_lookup.csv`)\n"
        "- The 6 ground-truth output CSVs we must reproduce row-for-row"
    ),
    insight=(
        "This is a **synthetic** codebase (533 lines), but the patterns are "
        "real: cross-program coupling via macro globals, char↔num implicit "
        "casts, vendor-specific raw-data quirks, and explicit 'known issues' "
        "in the documentation. A real client estate has hundreds of "
        "programs but the same five categories of structural problem."
    ),
    speaker=(
        "Open the file viewer and pick `04_derive_adae.sas`. Notice on line "
        "38 the call `%is_treatment_emergent(ae_start=aestdt)`. That macro "
        "is defined in `util_macros.sas` and reads a global "
        "(`&TRT_START_DT`) that is set by SQL inside `03_derive_adsl.sas`. "
        "**Three files, one runtime variable, no static cross-reference.** "
        "This is exactly what the parser will catch in Phase 1."
    ),
)

demo_prompt("Switch the file viewer to `programs/04_derive_adae.sas` and "
             "scroll to line 38 — the `%is_treatment_emergent` call. Then "
             "switch to `macros/util_macros.sas` line 46 to see the macro "
             "body. That cross-file dependency is what makes naive "
             "translation fail.")

counts = load_json(BUILD / "ast" / "_aggregate" / "counts.json")

# ---------------------------------------------------------------------------
# File table
# ---------------------------------------------------------------------------

st.subheader("SAS files")

rows = []
for p in counts["programs"]:
    rel = Path(p["source_file"]).relative_to(PROJECT_ROOT)
    rows.append({
        "file": str(rel).replace("\\", "/"),
        "lines": p["lines_of_source"],
        "DATA": p["data_blocks"],
        "PROC": p["proc_blocks"],
        "by_kind": ", ".join(f"{k}×{v}" for k, v in p["procs_by_kind"].items())
                    or "—",
        "long_inputs": ", ".join(d for d in p["input_datasets"]
                                  if not d.startswith("work.")) or "—",
        "long_outputs": ", ".join(d for d in p["output_datasets"]
                                   if not d.startswith("work.")) or "—",
    })
df = pd.DataFrame(rows)
st.dataframe(df, hide_index=True, width="stretch",
             column_config={
                 "file": st.column_config.TextColumn("file", width="large"),
                 "lines": st.column_config.NumberColumn("lines", format="%d"),
             })

# ---------------------------------------------------------------------------
# SAS source viewer
# ---------------------------------------------------------------------------

st.subheader("Browse the SAS source")
sas_files = [r["file"] for r in rows]
sel = st.selectbox("File", sas_files,
                    index=sas_files.index("sas_codebase/programs/01_clean_dm.sas")
                    if "sas_codebase/programs/01_clean_dm.sas" in sas_files else 0)
src = read_text(sel)
st.code(src, language="sas", line_numbers=True)

# ---------------------------------------------------------------------------
# Input data preview
# ---------------------------------------------------------------------------

st.subheader("Raw input data")

inputs = ["input_data/dm.csv", "input_data/ae.csv", "input_data/site_lookup.csv"]
tabs = st.tabs(["dm.csv", "ae.csv", "site_lookup.csv"])
for tab, path in zip(tabs, inputs):
    with tab:
        full = PROJECT_ROOT / path
        if full.exists():
            df = pd.read_csv(full, dtype=str, keep_default_na=False)
            st.caption(f"`{path}` — {len(df)} rows, {len(df.columns)} cols")
            st.dataframe(df, hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
# Ground truth preview
# ---------------------------------------------------------------------------

st.subheader("Ground-truth outputs (the contract)")
st.caption("The 6 CSVs the modernized pipeline must reproduce row-for-row.")

truth_files = ["dm_clean", "ae_clean", "adsl", "adae",
               "ae_summary", "ae_incidence"]
tabs = st.tabs(truth_files)
for tab, name in zip(tabs, truth_files):
    with tab:
        full = PROJECT_ROOT / "ground_truth" / f"{name}.csv"
        df = pd.read_csv(full, dtype=str, keep_default_na=False)
        st.caption(f"`ground_truth/{name}.csv` — {len(df)} rows, "
                    f"{len(df.columns)} cols")
        st.dataframe(df, hide_index=True, width="stretch")
