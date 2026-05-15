"""Phase 5 — Generated Python code + side-by-side gen vs ground-truth diff."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, read_text, page_header,
                  tutorial_intro, demo_prompt)

st.set_page_config(page_title="Phase 5 — Codegen", layout="wide")

page_header("🐍", "Phase 5 — Generated Python code",
            "pandas + duckdb code emitted from the regenerated specs only. "
            "No SAS file is read here.")

tutorial_intro(
    why=(
        "This is the modernization payoff: **Python code that runs the "
        "pipeline on real data and produces the ADaM datasets**. The R1 "
        "contract is strict — Phase 5 reads the spec markdown and the "
        "schema modules, nothing else. That constraint is what forces "
        "every assumption to be encoded *in the spec*, where it can be "
        "audited, instead of buried in the generated code."
    ),
    what=(
        "- A **side-by-side** view of each program's spec ↔ generated Python\n"
        "- A **side-by-side** view of each generated CSV ↔ ground-truth CSV "
        "with **cell-level diff highlighting**\n"
        "- Diff metrics: schema match, row count, cells different, sort key"
    ),
    insight=(
        "On test failure, the rule is **fix the spec, regenerate, re-test** "
        "— never patch the Python by reading SAS. Two such corrections "
        "happened during this project's validation: (1) AGE_DERIVED uses "
        "`//365` not `floor(/365.25)` because ground truth used a different "
        "divisor than the SAS macro; (2) duckdb's `SUM` returns DECIMAL, "
        "which cast to float in pandas — fixed with explicit `::INTEGER`. "
        "Both became new entries in the ambiguity register."
    ),
    speaker=(
        "Pick `04_derive_adae` from the program dropdown. Show the spec on "
        "the left and the generated Python on the right — notice how the "
        "TRTEMFL line in the spec maps directly to a 3-line Python block. "
        "Then scroll down to the **Generated output ↔ ground truth** "
        "comparison and pick `adae`. The 'Cells different' metric should "
        "show **0** with the result chip showing **✅ row-for-row match**. "
        "Mention that **a green diff is the validation contract**, not "
        "'looks right'."
    ),
)

# ---------------------------------------------------------------------------
# Side-by-side spec ↔ generated code viewer
# ---------------------------------------------------------------------------

st.subheader("Spec ↔ Generated code")

PROGRAMS = ["01_clean_dm", "02_clean_ae", "03_derive_adsl",
            "04_derive_adae", "05_summary_safety"]
sel = st.selectbox("Program", PROGRAMS)

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**Spec** — `build/specs/{sel}.md`")
    st.markdown(read_text(BUILD / "specs" / f"{sel}.md"))
with c2:
    st.markdown(f"**Generated code** — `build/target/{sel}.py`")
    st.code(read_text(BUILD / "target" / f"{sel}.py"),
              language="python", line_numbers=True)

with st.expander("Shared utilities — `build/target/common.py`"):
    st.code(read_text(BUILD / "target" / "common.py"),
              language="python", line_numbers=True)

# ---------------------------------------------------------------------------
# Generated outputs vs ground truth
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Generated output ↔ ground truth (row-for-row)")

OUTPUTS = ["dm_clean", "ae_clean", "adsl", "adae",
           "ae_summary", "ae_incidence"]
ds = st.selectbox("Dataset", OUTPUTS)

gen_csv = BUILD / "target" / "output" / f"{ds}.csv"
truth_csv = PROJECT_ROOT / "ground_truth" / f"{ds}.csv"

if not gen_csv.exists():
    st.error(f"Generated CSV not found: {gen_csv}. Run the pipeline first.")
    st.stop()

gen = pd.read_csv(gen_csv, dtype=str, keep_default_na=False)
truth = pd.read_csv(truth_csv, dtype=str, keep_default_na=False)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Generated rows", len(gen))
with c2:
    st.metric("Ground-truth rows", len(truth))
with c3:
    schema_match = list(gen.columns) == list(truth.columns)
    st.metric("Schema match", "✅" if schema_match else "❌")

# Try to sort both by a stable key for visual comparison
SORT_KEYS = {
    "dm_clean": ["USUBJID"],
    "ae_clean": ["USUBJID", "AESEQ"],
    "adsl": ["USUBJID"],
    "adae": ["USUBJID", "AESEQ"],
    "ae_summary": ["ARM", "SEVERITY"],
    "ae_incidence": ["ARM", "WORST_SEVERITY_RANK"],
}
key = SORT_KEYS.get(ds, list(gen.columns)[:1])
key = [c for c in key if c in gen.columns and c in truth.columns]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if "INCIDENCE_RATE" in df.columns:
        def _r(v):
            v = (v or "").strip()
            if v == "":
                return ""
            try:
                return f"{round(float(v), 4):g}"
            except ValueError:
                return v
        df = df.copy()
        df["INCIDENCE_RATE"] = df["INCIDENCE_RATE"].map(_r)
    return df

gen_n = _normalize(gen)
truth_n = _normalize(truth)
if key:
    gen_n = gen_n.sort_values(by=key, kind="mergesort").reset_index(drop=True)
    truth_n = truth_n.sort_values(by=key, kind="mergesort").reset_index(drop=True)

# Cell-level diff
diff_count = 0
diff_mask = pd.DataFrame(False, index=gen_n.index, columns=gen_n.columns)
if len(gen_n) == len(truth_n) and list(gen_n.columns) == list(truth_n.columns):
    for c in gen_n.columns:
        diff_mask[c] = gen_n[c] != truth_n[c]
    diff_count = int(diff_mask.values.sum())

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Sorted by", ", ".join(key) or "(no key)")
with c2:
    st.metric("Cells different", diff_count,
                delta_color="inverse")
with c3:
    st.metric("Result", "✅ row-for-row match" if diff_count == 0
                                                  and len(gen_n) == len(truth_n)
                                                  and schema_match
                          else "❌ mismatch")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**Generated** — `build/target/output/{ds}.csv`")
    st.dataframe(gen_n, hide_index=True, width="stretch")
with c2:
    st.markdown(f"**Ground truth** — `ground_truth/{ds}.csv`")

    # Highlight diffs
    def _style(row):
        return ['background-color: #7f1d1d; color: #fee2e2'
                 if diff_mask.loc[row.name, c] else ''
                 for c in row.index]

    if diff_count:
        st.dataframe(truth_n.style.apply(_style, axis=1),
                      hide_index=True, width="stretch")
    else:
        st.dataframe(truth_n, hide_index=True, width="stretch")

if diff_count:
    st.markdown("**Differing rows**")
    diff_rows = diff_mask.any(axis=1)
    st.dataframe(
        pd.concat([gen_n[diff_rows].add_prefix("gen_"),
                   truth_n[diff_rows].add_prefix("truth_")], axis=1),
        hide_index=True, width="stretch"
    )
