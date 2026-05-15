"""Phase 4 — Regenerated specs, schemas, DAG, and tests."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, load_json, read_text, render_mermaid,
                  page_header, tutorial_intro, demo_prompt)

st.set_page_config(page_title="Phase 4 — Regenerated", layout="wide")

page_header("🛠️", "Phase 4 — Regenerated artifacts (graph-only inputs)",
            "From the knowledge graph (and only the graph), regenerate functional "
            "specs, dataset schemas, the execution DAG, and pytest stubs.")

tutorial_intro(
    why=(
        "Phase 5 codegen reads **only** the regenerated specs and schemas — "
        "never the SAS source. That means **everything** Phase 5 needs has "
        "to be expressible from the graph. Phase 4 is the contract layer: it "
        "translates graph facts into human-readable specs, machine-readable "
        "schemas, an executable DAG, and runnable pytest stubs."
    ),
    what=(
        "- **📝 Specs** — 5 markdown files, plain-English transformations. "
        "**The only Phase 5 input.**\n"
        "- **📐 Schemas** — 9 Python modules with dtype maps and column "
        "ordering pinned to ground-truth CSV headers\n"
        "- **🗺️ DAG** — topologically-sorted, with parallelizable levels\n"
        "- **🧪 Test stubs** — 6 pytest files (schema match + row count + "
        "row-for-row equality)"
    ),
    insight=(
        "If a Phase 5 test fails, the rule is **fix the spec, regenerate, "
        "re-test** — never patch the generated Python by reading SAS. This "
        "is what enforces R1 in practice. During this project's validation, "
        "two such failures occurred (AGE_DERIVED divisor, duckdb SUM dtype). "
        "Both were fixed by amending the spec, not the code."
    ),
    speaker=(
        "Open the **📝 Functional specs** tab and pick `04_derive_adae.md`. "
        "Read the Transformations section out loud — notice it's plain "
        "English, with explicit references to ambiguity #1 (TRTEMFL "
        "semantics). **This is the only thing Phase 5 codegen will read for "
        "this program.** Then switch to the **📐 Schemas** tab and pick "
        "`adam_adae.py` — point at the column order and dtype map. **None "
        "of this was hand-written; all of it came from the graph.**"
    ),
)

# ---------------------------------------------------------------------------
# Tabs for each artifact category
# ---------------------------------------------------------------------------

t_specs, t_schemas, t_dag, t_tests = st.tabs(
    ["📝 Functional specs", "📐 Schemas", "🗺️ DAG", "🧪 Test stubs"]
)

# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

with t_specs:
    st.caption("These are the **only** input to Phase 5. Read them like a "
                "design doc, then read the generated Python alongside.")
    spec_files = sorted([p.name for p in (BUILD / "specs").glob("*.md")])
    sel = st.selectbox("Spec", spec_files)
    st.markdown(read_text(BUILD / "specs" / sel))

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

with t_schemas:
    st.caption("Per-dataset Python schema modules. dtype hints are derived "
                "from a CSV scan; nullability from any-blank-in-data; column "
                "order pinned from the ground-truth CSV header.")
    schema_files = sorted([p.name for p in (BUILD / "schemas").glob("*.py")
                            if p.name != "__init__.py"])
    sel = st.selectbox("Schema", schema_files,
                        index=schema_files.index("adam_dm_clean.py")
                        if "adam_dm_clean.py" in schema_files else 0)
    st.code(read_text(BUILD / "schemas" / sel), language="python",
              line_numbers=True)

# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

with t_dag:
    pipeline = load_json(BUILD / "dag" / "pipeline.json")
    st.markdown("**Topological order**")
    st.json(pipeline["topological_order"])

    st.markdown("**Parallelizable levels**")
    for i, lvl in enumerate(pipeline["levels"], start=1):
        st.markdown(f"- Level {i}: `{', '.join(lvl)}`")

    st.markdown("**Outputs per program**")
    rows = [{"program": p, "outputs": ", ".join(outs)}
            for p, outs in pipeline["outputs_per_program"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.markdown("**Dependency edges**")
    render_mermaid("\n".join([
        "flowchart LR",
        '  P01["01_clean_dm"]', '  P02["02_clean_ae"]',
        '  P03["03_derive_adsl"]', '  P04["04_derive_adae"]',
        '  P05["05_summary_safety"]',
        *(f'  P{e["from"][:2]} -->|{e["via_dataset"]}| P{e["to"][:2]}'
          for e in pipeline["edges"]),
    ]), height=380)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

with t_tests:
    st.caption("Auto-generated pytest stubs. Each output dataset gets three "
                "tests: schema match, row count, row-for-row equality.")
    test_files = sorted([p.name for p in (BUILD / "tests").glob("*.py")
                          if p.name != "__init__.py"])
    sel = st.selectbox("Test file", test_files,
                        index=test_files.index("test_adam_adae.py")
                        if "test_adam_adae.py" in test_files else 0)
    st.code(read_text(BUILD / "tests" / sel), language="python",
              line_numbers=True)
