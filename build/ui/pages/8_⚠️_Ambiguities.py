"""Ambiguity register — full High-severity write-ups + Medium/Low log."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import BUILD, read_text, page_header, tutorial_intro, demo_prompt

st.set_page_config(page_title="Ambiguity register", layout="wide")

page_header("⚠️", "Ambiguity register",
            "Every place where static analysis could not decide between two "
            "valid interpretations of the SAS code, with the assumption "
            "made and what would change if it's wrong.")

tutorial_intro(
    why=(
        "A pure SAS-to-Python rewrite **silently encodes** whatever "
        "interpretation the implementer happened to pick. That's how "
        "modernization projects fail: not from missing functionality, but "
        "from undocumented decisions that propagate into production. The "
        "graph-driven pipeline forces every ambiguity into the open: **High** "
        "items pause for user resolution before Phase 5; **Medium/Low** are "
        "auto-logged with documented assumptions and a counterfactual "
        "(\"if this assumption is wrong, here's what breaks\")."
    ),
    what=(
        "- 6 ambiguity cards: 1 High, 3 Medium, 2 Low\n"
        "- Status: 1 resolved by user before Phase 5, 5 auto-logged\n"
        "- Below: full `build/reports/ambiguity_log.md` with detailed "
        "write-ups for the High item including counterfactual analysis"
    ),
    insight=(
        "Ambiguity #6 (AGE_DERIVED `//365` vs `floor(/365.25)`) is "
        "particularly instructive — it was **not** detected by static "
        "analysis. It surfaced as a Phase 5 test failure: 2 subjects out of "
        "20 had off-by-one ages because the SAS macro and the ground-truth "
        "generator disagreed. Per R4 (validation beats spec text), the spec "
        "was corrected and a new ambiguity was registered. **The register "
        "is a living document, not a one-shot static report.**"
    ),
    speaker=(
        "Walk through the cards. The **High** one (TRT_START_DT) is the "
        "marquee example: the system **paused**, asked the user to choose "
        "between two semantically valid interpretations, and recorded the "
        "decision with timestamp. **A traditional rewrite would have "
        "guessed.** Then point out **#6** at the bottom — *we discovered "
        "this during validation, not before*. The register grew "
        "organically. **This is what 'honest about uncertainty' looks like.**"
    ),
)

# ---------------------------------------------------------------------------
# Headline cards
# ---------------------------------------------------------------------------

cards = [
    ("#1 — `&TRT_START_DT` cross-program coupling", "High", "✅ Resolved 2026-05-07",
     "Phase 1 macro-globals scan flagged that `%is_treatment_emergent` reads a "
     "global written by an SQL `select … into :TRT_START_DT` in 03_derive_adsl. "
     "User confirmed the cohort-level scalar interpretation."),
    ("#2 — SP-184 vendor B `GRADE 1/2/3` codes", "Medium", "📝 Logged",
     "Spec §6.2 says deferred to v1.4. Phase 5 leaves `AESEV_STD` blank for "
     "those rows, reproducing the blank-severity rows in `ae_summary.csv`."),
    ("#3 — SITE_ID type mismatch (char vs num)", "Medium", "📝 Logged",
     "DM stores `SITEID` as char(2) with leading zeros; SITE_LOOKUP delivers "
     "`SITE_ID` as num. SAS does an implicit cast; pandas/duckdb don't. "
     "Phase 5 explicitly coerces to a zero-padded 2-char string."),
    ("#4 — DM duplicates from CRF amendment", "Low", "📝 Logged",
     "Spec §6.1 — dedup logic in `01_clean_dm.sas:41-49` resolves the issue. "
     "Synthetic data is already unique; the rule is preserved for "
     "production resilience."),
    ("#5 — `&PROJ_ROOT = %sysfunc(getoption(SASUSER))`", "Low", "📝 Logged",
     "Cosmetic — only feeds `libname` paths and `%include` resolution. "
     "Phase 5 ignores it; project root is computed at script start."),
    ("#6 — AGE_DERIVED `//365` vs `floor(/365.25)`", "Medium", "📝 Logged 2026-05-08",
     "Discovered during Phase 5 validation. SAS macro uses 365.25; ground truth "
     "uses 365. Spec corrected per R4 (validation contract beats spec text). "
     "Affects 2/20 subjects."),
]

cols = st.columns(3)
for i, (title, sev, status, body) in enumerate(cards):
    with cols[i % 3]:
        with st.container(border=True):
            color = {"High": "🔴", "Medium": "🟡", "Low": "⚪"}[sev]
            st.markdown(f"#### {title}")
            st.markdown(f"{color} **{sev}** · {status}")
            st.markdown(body)

# ---------------------------------------------------------------------------
# Full ambiguity log
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Full ambiguity log")
st.caption("`build/reports/ambiguity_log.md` — High-severity items have full "
            "write-ups including counterfactual analysis.")

st.markdown(read_text(BUILD / "reports" / "ambiguity_log.md"))
