"""Validation — pytest results and aggregate reconciliation."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, read_text, run_pipeline_step,
                  page_header, tutorial_intro, demo_prompt)

st.set_page_config(page_title="Validation", layout="wide")

page_header("✅", "Validation",
            "Pytest stubs that compare every generated CSV against ground truth, "
            "plus aggregate reconciliations across datasets.")

tutorial_intro(
    why=(
        "R4 says validation is **row-for-row equality vs ground truth**. "
        "Not 'looks right', not 'row count matches', not 'aggregates close "
        "enough' — every cell in every row, in a stable order, equal. "
        "Three tests per output dataset (schema, row count, row equality) "
        "plus 5 cross-dataset reconciliations catch the kind of problem a "
        "row-by-row test can pass coincidentally."
    ),
    what=(
        "- A **▶️ Run pytest now** button that re-runs the full test suite "
        "and streams the output\n"
        "- The full validation report (`build/reports/validation_report.md`) "
        "rendered inline\n"
        "- **Live aggregate reconciliation** computed against the current "
        "outputs — numbers visible, no hidden state"
    ),
    insight=(
        "**Aggregate reconciliation catches what row-by-row misses.** "
        "Example: if your TRTEMFL filter is wrong but happens to keep the "
        "same number of rows, row counts match. But "
        "`sum(AE_SUMMARY.N_EVENTS)` won't equal `count(ADAE where TRTEMFL='Y')` "
        "anymore. The aggregate test fails immediately. This kind of "
        "internal consistency is **how you trust a pipeline** — not by "
        "spot-checking a few rows."
    ),
    speaker=(
        "Click **▶️ Run pytest now**. Watch the 23 tests stream by — "
        "18 row-equality + 5 aggregate. All green in under a second. Then "
        "scroll to **Live aggregate reconciliation** and read the numbers: "
        "39 ADAE rows where TRTEMFL='Y', sum of AE_SUMMARY N_EVENTS = 39. "
        "**That match isn't a coincidence — it's the contract.**"
    ),
)

if st.button("▶️ Run pytest now", type="primary"):
    with st.status("running pytest…", expanded=True) as status:
        ok, out = run_pipeline_step("pytest", [
            "python", "-m", "pytest", "build/tests/", "-v",
            "--tb=short", "--no-header", "--color=no",
        ])
        st.code(out or "(no output)", language="text")
        status.update(label=f"pytest — {'✅' if ok else '❌'}",
                        state="complete" if ok else "error")

# ---------------------------------------------------------------------------
# Validation report rendering
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Validation report")

report = read_text(BUILD / "reports" / "validation_report.md")
if report:
    st.markdown(report)
else:
    st.warning("`build/reports/validation_report.md` not found.")

# ---------------------------------------------------------------------------
# Live aggregate checks (computed inline so user can see numbers)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Live aggregate reconciliation")
st.caption("Computed against `build/target/output/` and `ground_truth/`. "
            "These are the same checks `build/tests/test_aggregates.py` runs.")

try:
    adsl = pd.read_csv(BUILD / "target" / "output" / "adsl.csv",
                        dtype=str, keep_default_na=False, na_values=[""])
    adae = pd.read_csv(BUILD / "target" / "output" / "adae.csv",
                        dtype=str, keep_default_na=False, na_values=[""])
    ae_summary = pd.read_csv(BUILD / "target" / "output" / "ae_summary.csv",
                              dtype=str, keep_default_na=False, na_values=[""])
    ae_incidence = pd.read_csv(BUILD / "target" / "output" / "ae_incidence.csv",
                                dtype=str, keep_default_na=False, na_values=[""])
except FileNotFoundError as e:
    st.error(f"missing output file: {e}")
    st.stop()

c1, c2 = st.columns(2)
with c1:
    te_rows = (adae["TRTEMFL"] == "Y").sum()
    summary_total = ae_summary["N_EVENTS"].astype(int).sum()
    st.markdown(f"**ADAE TRTEMFL='Y' rows** = {te_rows}")
    st.markdown(f"**SUM(AE_SUMMARY.N_EVENTS)** = {summary_total}")
    st.markdown(f"### {'✅ match' if te_rows == summary_total else '❌ mismatch'}")
with c2:
    serious_te = ((adae["TRTEMFL"] == "Y") & (adae["AESER"] == "Y")).sum()
    summary_serious = ae_summary["N_SERIOUS"].astype(int).sum()
    st.markdown(f"**ADAE TRTEMFL='Y' & AESER='Y' rows** = {serious_te}")
    st.markdown(f"**SUM(AE_SUMMARY.N_SERIOUS)** = {summary_serious}")
    st.markdown(f"### {'✅ match' if serious_te == summary_serious else '❌ mismatch'}")

st.markdown("**Per-arm denominator reconciliation (ADSL.SAFFL='Y' ↔ AE_INCIDENCE.N_SUBJ_TOTAL)**")
saffl = adsl[adsl["SAFFL"] == "Y"]
expected = saffl.groupby("ARM")["USUBJID"].nunique().to_dict()
actual = (ae_incidence.drop_duplicates("ARM")
            .set_index("ARM")["N_SUBJ_TOTAL"].astype(int).to_dict())
recon_rows = []
for arm in sorted(set(expected) | set(actual)):
    e = expected.get(arm)
    a = actual.get(arm)
    recon_rows.append({
        "arm": arm,
        "ADSL distinct USUBJID where SAFFL='Y'": e,
        "AE_INCIDENCE.N_SUBJ_TOTAL": a,
        "match": "✅" if e == a else "❌",
    })
st.dataframe(pd.DataFrame(recon_rows), hide_index=True, width="stretch")
