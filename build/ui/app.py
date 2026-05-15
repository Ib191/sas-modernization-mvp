"""SAS Modernization Explorer — landing page (Overview & Story).

Run with:  streamlit run build/ui/app.py
"""
from __future__ import annotations

import streamlit as st

from lib import (
    BUILD, PROJECT_ROOT, load_json, read_text, render_mermaid,
    run_pipeline_step, page_header,
)

st.set_page_config(
    page_title="SAS → Python Modernization Explorer",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Hero
# ============================================================================

st.title("🛠️ SAS → Python Modernization Explorer")
st.markdown(
    """
##### Turning a 533-line SAS clinical-trials pipeline into Python — auditable, repeatable, and honest about what it doesn't know.

This explorer walks through every phase of the modernization, lets you run
the whole pipeline live, and proves the result against a row-for-row
ground truth.

**Use the sidebar** to jump into any phase, or follow the narrative below.
For a guided walkthrough designed for live presentation, open
**🎬 Live Demo Walkthrough**.
"""
)

# ============================================================================
# Headline metrics (the "result first" pattern)
# ============================================================================

counts = load_json(BUILD / "ast" / "_aggregate" / "counts.json")
kg_stats = load_json(BUILD / "graph" / "kg_stats.json")

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("SAS lines modernized", "533",
                help="Across 5 programs + 2 config + 1 macro file")
with c2:
    st.metric("DATA + PROC blocks", f"{counts['totals']['data_blocks']} + {counts['totals']['proc_blocks']}",
                help="11 DATA steps, 15 PROC blocks")
with c3:
    st.metric("Knowledge-graph nodes", f"{kg_stats['total_nodes']}",
                help=f"{kg_stats['total_edges']} edges across 8 node kinds")
with c4:
    st.metric("Output datasets", "6 / 6 ✅",
                help="dm_clean, ae_clean, adsl, adae, ae_summary, ae_incidence — all match ground truth row-for-row")
with c5:
    st.metric("Tests passing", "23 / 23 ✅",
                help="18 row-equality + 5 cross-dataset aggregate reconciliation")

st.divider()

# ============================================================================
# The story
# ============================================================================

st.header("📖 The Story")

# ----------------------------------------------------------------------------
# 1. The problem
# ----------------------------------------------------------------------------

st.subheader("1️⃣ The problem we're solving")
c1, c2 = st.columns([2, 1])
with c1:
    st.markdown(
        """
Pharmaceutical companies have **decades of SAS code** running their
clinical trials. The CTX-2024-001 codebase in front of us is a tiny
synthetic example — 5 programs, 533 lines, producing 6 ADaM datasets — but
the patterns are real:

- **Macros** that read runtime-set globals
- **Cross-program coupling** via shared symbol tables
- **Implicit type coercions** in PROC SQL joins
- **Vendor-specific quirks** in the raw inputs
- **Documented "known issues"** that are accepted, not fixed

Modernizing this onto a cloud-native stack (pandas, Spark, dbt) is
**existential** for new analytical platforms — but the standard
"line-by-line translation" approach silently encodes wrong assumptions
and breaks in ways nobody notices until it's in production.
"""
    )
with c2:
    st.info(
        """
**This codebase, in numbers**

- 5 programs · 1 macro file · 1 format catalog
- 11 DATA steps · 15 PROC blocks (sort×7, sql×6, summary×1, format×1)
- 5 macros · 1 with cross-program global side-effect
- 3 raw CSVs · 6 ground-truth output CSVs
- 4 documented open issues / deferred work items
"""
    )

# ----------------------------------------------------------------------------
# 2. The naive approach (and why it fails)
# ----------------------------------------------------------------------------

st.subheader("2️⃣ The naive approach (and why it fails)")

c1, c2 = st.columns(2)
with c1:
    st.error(
        """
**❌ Line-by-line SAS → Python translation**

> "Just have a developer (or an LLM) read the SAS programs and rewrite
> them in Python."

Sounds simple, but:

- **Macros are runtime-evaluated.** Static reading can't see what a macro
  expands to in any given call site.
- **Hidden cross-program globals.** `&TRT_START_DT` is set in one program
  via `SELECT … INTO :var`, then read implicitly by a macro called in two
  *other* programs. No file-by-file translation can see this.
- **Implicit casts.** SAS quietly coerces char↔num in joins. pandas/duckdb
  won't, and the bug only manifests when one site is missing.
- **"Looks plausible" output.** A row count match and "looks right"
  spot-check can hide subtle aggregation bugs. We had two such bugs
  (AGE_DERIVED, N_SERIOUS) that only surfaced under row-for-row diff.
"""
    )
with c2:
    st.success(
        """
**✅ Graph-driven modernization (this project)**

> "Don't translate — **mediate**. Every fact about the SAS code lives in
> a knowledge graph. The Python is generated from specs that the graph
> regenerates."

What that buys us:

- **Auditable.** Every output cell traces back through specs → graph → SAS
  source.
- **Honest about uncertainty.** Static-analysis ambiguities pause for
  human resolution instead of being silently guessed.
- **Repeatable.** Re-run the 5 phases on a different SAS estate; the
  architecture is target-agnostic.
- **Validated against ground truth.** Row-for-row equality on every cell,
  not just "looks right."
"""
    )

# ----------------------------------------------------------------------------
# 3. The architecture
# ----------------------------------------------------------------------------

st.subheader("3️⃣ The architecture — a 5-phase pipeline")

st.markdown(
    """
The modernization runs in five strictly-ordered phases. The **most
important architectural decision** is that **Phase 5 codegen reads only
the regenerated specs — never the SAS source again.** That's the rule
that makes ambiguities surface instead of leaking into the Python.
"""
)

render_mermaid(
    """
flowchart LR
  classDef phase fill:#1f2937,stroke:#3b82f6,color:#fafafa,stroke-width:2px;
  classDef artifact fill:#064e3b,stroke:#22c55e,color:#dcfce7;
  classDef ground fill:#7c2d12,stroke:#ef4444,color:#fff7ed;

  SAS[("SAS source<br/>5 programs<br/>+ macros + formats")]:::ground
  DOCS[("Markdown docs<br/>functional_spec<br/>data_dictionary")]:::ground

  P1["Phase 1<br/>Hand-rolled parser<br/>AST + CFG + DFG"]:::phase
  P2["Phase 2<br/>Doc parser<br/>BusinessRule, OpenIssue"]:::phase
  P3["Phase 3<br/>Knowledge graph<br/>173 nodes / 93 edges"]:::phase
  P4["Phase 4<br/>Regenerator<br/>specs · schemas · DAG · tests"]:::phase
  P5["Phase 5<br/>Codegen<br/>Python (pandas + duckdb)"]:::phase

  A1[/"build/ast/*"/]:::artifact
  A2[/"build/graph/doc_entities.json"/]:::artifact
  A3[/"build/graph/kg.json"/]:::artifact
  A4[/"build/specs · schemas · dag · tests"/]:::artifact
  A5[/"build/target/output/*.csv +.parquet"/]:::artifact
  GT[("ground_truth/*.csv")]:::ground

  SAS --> P1 --> A1
  DOCS --> P2 --> A2
  A1 --> P3
  A2 --> P3
  P3 --> A3
  A3 --> P4 --> A4
  A4 --> P5 --> A5
  A5 -. "row-for-row equality" .- GT
""",
    height=520,
)

# ----------------------------------------------------------------------------
# 4. Each phase in one paragraph
# ----------------------------------------------------------------------------

st.subheader("4️⃣ The 5 phases — one paragraph each")

phases = [
    ("📜 Phase 1 — Parse SAS into AST + flow graphs",
     "🔵",
     "A two-pass hand-rolled parser. **Pass A** expands macros (`%include`, "
     "`%let`, `%macro`/`%mend`, `&var`, macro calls), tracking which "
     "globals each macro reads and writes. **Pass B** builds a structural "
     "AST — DATA steps, PROC blocks (SORT, SQL, SUMMARY, FORMAT), and per "
     "program a Control Flow Graph and Data Flow Graph. The output is "
     "8 JSON files per program plus an aggregate macro table and "
     "program-level dependency DAG. **Why this matters:** the macro-globals "
     "scan is what surfaces the cross-program `&TRT_START_DT` coupling — "
     "no file-by-file translation could see this.",
     "🔍 Phase 1 Parser"),
    ("📚 Phase 2 — Parse documentation into structured entities",
     "🟣",
     "Markdown docs (`functional_spec.md`, `data_dictionary.md`) parsed "
     "into `Section`, `BusinessRule`, and `OpenIssue` nodes. Every bullet "
     "in a §4.x derivation section becomes a rule; every section under "
     "'Known issues' or referencing a tracker (SP-184, SP-227) becomes an "
     "OpenIssue. **Why this matters:** the SAS code says *what*; the docs "
     "say *why*. The graph needs both. The §6.3 'first dose vs "
     "randomization' note feeds directly into the High-severity ambiguity.",
     "📚 Phase 2 Docs"),
    ("🕸️ Phase 3 — Build the knowledge graph",
     "🟢",
     "Phase 1 + Phase 2 outputs unified into a 173-node, 93-edge "
     "`networkx.MultiDiGraph`. Eight node kinds (Dataset, Column, Proc, "
     "Macro, Program, BusinessRule, OpenIssue, Constraint) and eight "
     "edge kinds (reads, writes, contributes_to, calls, depends_on, "
     "applies_to, flagged_by, validates). A small CLI (`query.py`) "
     "answers `lineage_for_column TRTEMFL`, `dependencies_of_program 04…`, "
     "and four other queries. **Why this matters:** this is the single "
     "source of truth Phases 4 and 5 read from. No re-parsing of SAS "
     "ever happens past this point.",
     "🕸️ Phase 3 Knowledge Graph"),
    ("🛠️ Phase 4 — Regenerate specs, schemas, DAG, tests",
     "🟠",
     "From the graph alone, emit: 5 functional specs (`build/specs/*.md` — "
     "the *only* Phase 5 input), 9 dataset schema modules with dtype maps, "
     "1 topologically-sorted execution DAG with parallelizable levels, "
     "6 pytest stubs (schema match + row count + row-for-row equality on "
     "natural sort keys), and an aggregate-reconciliation test file. "
     "**Why this matters:** this is the contract between graph and "
     "codegen. If the spec is incomplete, Phase 5 catches it as a test "
     "failure — the fix goes in the spec, never in the generated Python.",
     "🛠️ Phase 4 Regenerated"),
    ("🐍 Phase 5 — Generate target Python from specs only",
     "🔴",
     "5 Python modules + a shared utilities file. Each module reads the "
     "raw / upstream CSVs, executes the spec's transformations using "
     "pandas + duckdb, writes both CSV (validated) and Parquet alongside. "
     "Cross-program state (the `&TRT_START_DT` cohort scalar) is persisted "
     "to `build/target/state/` between programs. **Hard rule R1**: this "
     "code is generated *exclusively* from `build/specs/` and "
     "`build/schemas/` — no SAS file is opened. Two test failures during "
     "validation (AGE_DERIVED divisor, duckdb SUM dtype) were fixed by "
     "amending the spec, never by peeking at SAS.",
     "🐍 Phase 5 Codegen"),
]

for title, emoji, body, page in phases:
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.markdown(body)
        st.caption(f"📂 Open the **{page}** page in the sidebar for the full drill-down.")

# ----------------------------------------------------------------------------
# 5. The result
# ----------------------------------------------------------------------------

st.subheader("5️⃣ The result — auditable correctness")

c1, c2, c3 = st.columns(3)
with c1:
    st.success(
        """
**Row-for-row match against ground truth**

All 6 datasets pass schema, row-count, and full-cell-equality tests.
A stable sort key per dataset makes the comparison deterministic.
"""
    )
with c2:
    st.success(
        """
**Aggregate reconciliation**

`AE_SUMMARY` totals reconcile to `ADAE` event counts.
`AE_INCIDENCE` denominators match `ADSL.SAFFL='Y'` cohorts per arm.
Catches bugs that row-by-row tests pass coincidentally.
"""
    )
with c3:
    st.success(
        """
**Honest ambiguity register**

6 ambiguities surfaced (1 High, 3 Medium, 2 Low).
1 paused for user resolution before Phase 5; 5 auto-logged with
documented assumptions and counterfactuals.
"""
    )

# ============================================================================
# Run live
# ============================================================================

st.divider()
st.header("▶️ Run the whole pipeline live")

st.markdown(
    """
The button below runs the 5 phases end-to-end (`build/parser/run.py` →
`parse_docs.py` → `build/graph/build_kg.py` → `build/regenerator/regenerate.py`
→ `build/dag/run.py`) and finishes with a pytest validation. Each step's
stdout streams below.

This is the demo headline: **the entire modernization, regenerable from
scratch, in under 5 seconds**.
"""
)

if st.button("▶️ Run all phases + tests", type="primary"):
    steps = [
        ("Phase 1 — Parse SAS", ["python", "build/parser/run.py"]),
        ("Phase 2 — Parse docs", ["python", "build/parser/parse_docs.py"]),
        ("Phase 3 — Build knowledge graph", ["python", "build/graph/build_kg.py"]),
        ("Phase 4 — Regenerate specs/schemas/DAG/tests", ["python", "build/regenerator/regenerate.py"]),
        ("Phase 5 — Generate target code + run pipeline", ["python", "build/dag/run.py"]),
        ("Validation — pytest", ["python", "-m", "pytest", "build/tests/", "-v"]),
    ]
    progress = st.progress(0.0)
    for i, (label, cmd) in enumerate(steps, start=1):
        with st.status(label, expanded=False) as status:
            ok, out = run_pipeline_step(label, cmd)
            st.code(out or "(no output)", language="text")
            status.update(label=f"{label} — {'✅' if ok else '❌'}",
                            state="complete" if ok else "error")
            if not ok:
                st.error(f"step failed: {label}")
                break
        progress.progress(i / len(steps))

# ============================================================================
# Sidebar
# ============================================================================

with st.sidebar:
    st.markdown("### 🧭 Navigation")
    st.markdown(
        """
**Start here:**
- 🎬 **Live Demo Walkthrough** — guided steps with speaker notes
- 📁 **Codebase Inventory** — what we're modernizing

**The 5 phases:**
- 🔍 **Phase 1** — SAS parser & AST
- 📚 **Phase 2** — Doc parser & rules
- 🕸️ **Phase 3** — Knowledge graph (interactive)
- 🛠️ **Phase 4** — Regenerated artifacts
- 🐍 **Phase 5** — Generated code + diff

**Validation:**
- ✅ **Validation** — Tests + reconciliation
- ⚠️ **Ambiguities** — Full register

**Takeaways:**
- 📑 **Final SOLUTION.md** — the deliverable
- 📥 **Export PDF** — printable handout
"""
    )
    st.divider()
    st.caption("Project root:")
    st.code(str(PROJECT_ROOT), language="text")
