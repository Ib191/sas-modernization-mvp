"""Phase 1 — Parse SAS into AST + CFG + DFG."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, load_json, read_text, render_mermaid,
                  page_header, tutorial_intro, demo_prompt)

st.set_page_config(page_title="Phase 1 — Parser", layout="wide")

page_header("🔍", "Phase 1 — Parse SAS into AST + CFG + DFG",
            "Two-pass hand-rolled parser. Pass A expands macros (%include, %let, %macro, &var). "
            "Pass B builds a structural AST + control/data flow graphs.")

tutorial_intro(
    why=(
        "Before we can build a knowledge graph, we need **structured "
        "representations** of every SAS file: which datasets are read/written, "
        "which columns are assigned, which macros call which globals, how "
        "programs depend on each other. Static representations let us reason "
        "about cross-program coupling that no file-by-file reading can see."
    ),
    what=(
        "- **Per program**: original SAS, post-macro-expansion source, "
        "structural AST, control-flow graph (CFG), data-flow graph (DFG)\n"
        "- **Aggregate**: macro table (with reads/writes-globals scan), "
        "program-level dependency DAG, counts feeding SOLUTION.md §1.2"
    ),
    insight=(
        "**Pass A's macro-globals scan is the hero.** When `%is_treatment_emergent` "
        "is registered, the parser scans its body and finds `&TRT_START_DT` — "
        "a reference that is *not* a parameter and *not* a `%let` symbol. It "
        "gets recorded as `reads_globals=['TRT_START_DT']`. That single fact "
        "is what surfaces the cross-program coupling. **No regex over the SAS "
        "files would ever discover this.**"
    ),
    speaker=(
        "Pick `04_derive_adae.sas` from the dropdown. Click the **🪄 Expanded "
        "(post-macro)** tab. Notice that line 38's `%is_treatment_emergent(...)` "
        "has been textually replaced with the macro body — including the "
        "literal `&TRT_START_DT` token (still unresolved, because it's set at "
        "runtime). Then click **🔗 CFG** to see the linear flow of DATA and "
        "PROC blocks. Finally scroll to the **Macro table** at the bottom and "
        "point at `is_treatment_emergent` — its `reads_globals` column shows "
        "`TRT_START_DT`. **That's the smoking gun.**"
    ),
)

# ---------------------------------------------------------------------------
# Per-program explorer
# ---------------------------------------------------------------------------

st.subheader("Program-by-program explorer")

PROGRAMS = ["setup", "formats", "util_macros", "01_clean_dm", "02_clean_ae",
            "03_derive_adsl", "04_derive_adae", "05_summary_safety"]
sel = st.selectbox("Program", PROGRAMS, index=3)

ast_path = BUILD / "ast" / f"{sel}.json"
if not ast_path.exists():
    st.warning(f"AST not found for `{sel}` — run Phase 1 first.")
    st.stop()

ast = load_json(ast_path)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Blocks", len(ast["blocks"]))
with c2:
    st.metric("DATA steps",
                sum(1 for b in ast["blocks"] if b["kind"] == "data"))
with c3:
    st.metric("PROC blocks",
                sum(1 for b in ast["blocks"] if b["kind"] == "proc"))

t1, t2, t3, t4, t5 = st.tabs([
    "📄 Original SAS", "🪄 Expanded (post-macro)",
    "🌳 AST (blocks)", "🔗 CFG", "📊 DFG",
])

with t1:
    st.caption(f"`{ast['source_file']}`")
    src = read_text(ast["source_file"])
    st.code(src, language="sas", line_numbers=True)

with t2:
    st.caption("After Pass A: %include inlined, %macro bodies registered, "
                "&var resolved, macro calls textually substituted.")
    expanded = read_text(BUILD / "ast" / f"{sel}.expanded.sas")
    st.code(expanded, language="sas", line_numbers=True)

with t3:
    st.caption("Each block is a top-level construct (DATA step, PROC, or "
                "miscellaneous). Click rows to inspect.")
    blocks_df = pd.DataFrame([{
        "i": i,
        "kind": b["kind"],
        "proc_name": b.get("proc_name") or "—",
        "lines": f"{b['line_start']}-{b['line_end']}",
        "inputs": ", ".join(b["input_datasets"]) or "—",
        "outputs": ", ".join(b["output_datasets"]) or "—",
        "stmts": len(b["statements"]),
    } for i, b in enumerate(ast["blocks"])])
    st.dataframe(blocks_df, hide_index=True, width="stretch")

    if ast["blocks"]:
        idx = st.number_input("Inspect block #", min_value=0,
                                max_value=len(ast["blocks"]) - 1, value=0)
        b = ast["blocks"][idx]
        st.markdown(f"**Block {idx} — {b['kind']}**  "
                    f"(`{b.get('proc_name') or '—'}`, lines {b['line_start']}-{b['line_end']})")
        st.code(b.get("raw_text_head") or "", language="sas")
        if b["statements"]:
            st.markdown("**Statements**")
            stmt_rows = []
            for s in b["statements"]:
                row = {"kind": s.get("kind"), "line": s.get("line", "—")}
                for k in ("col", "expr", "raw"):
                    if k in s:
                        row[k] = str(s[k])[:120]
                stmt_rows.append(row)
            st.dataframe(pd.DataFrame(stmt_rows), hide_index=True,
                          width="stretch")

with t4:
    cfg_path = BUILD / "ast" / f"{sel}.cfg.json"
    cfg = load_json(cfg_path)
    if not cfg["nodes"]:
        st.info("No control-flow nodes for this program.")
    else:
        # Render CFG as Mermaid. Use '\\n' (a literal backslash-n) for line
        # breaks inside quoted labels — portable across Mermaid versions and
        # not affected by the security-level HTML stripping that breaks <br/>.
        lines = ["flowchart TD"]
        for n in cfg["nodes"]:
            label = n['label'].replace('"', "'")
            lines.append(
                f'  {n["id"]}["{label}\\nL{n["line_start"]}-{n["line_end"]}"]'
            )
        for e in cfg["edges"]:
            arrow = "-->" if e["kind"] == "sequential" else "-.->"
            lines.append(f'  {e["from"]} {arrow}|{e["kind"]}| {e["to"]}')
        render_mermaid("\n".join(lines), height=620)

with t5:
    dfg_path = BUILD / "ast" / f"{sel}.dfg.json"
    dfg = load_json(dfg_path)
    if not dfg["edges"]:
        st.info("No data-flow edges for this program.")
    else:
        st.caption("Datasets and columns referenced; `produces`/"
                    "`reads_dataset`/`writes_dataset` edges show flow.")
        st.dataframe(pd.DataFrame(dfg["nodes"]), hide_index=True,
                      width="stretch")
        st.dataframe(pd.DataFrame(dfg["edges"]), hide_index=True,
                      width="stretch")

# ---------------------------------------------------------------------------
# Macro table
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Macro table — registered definitions")

st.markdown("Pass A registers every `%macro` definition. The "
            "**reads_globals** / **writes_globals** scan is what surfaces "
            "cross-program coupling like `&TRT_START_DT`.")

macro_table = load_json(BUILD / "ast" / "_aggregate" / "macro_table.json")
mrows = []
for m in macro_table["macros"]:
    mrows.append({
        "name": m["name"],
        "params": ", ".join(p["name"] for p in m["params"]),
        "reads_globals": ", ".join(m["reads_globals"]) or "—",
        "writes_globals": ", ".join(m["writes_globals"]) or "—",
        "source": Path(m["source_file"]).name + f":{m['source_line']}",
    })
st.dataframe(pd.DataFrame(mrows), hide_index=True, width="stretch")

# ---------------------------------------------------------------------------
# Program-level DAG
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Program-level DAG")
st.caption("Edges are derived purely from cross-program output→input dataset "
            "relationships. The macro-globals coupling (`&TRT_START_DT`) is *not* "
            "in this graph — that's why it had to be raised at the ambiguity "
            "checkpoint.")

prog_dag = load_json(BUILD / "ast" / "_aggregate" / "program_dag.json")
mlines = ["flowchart TD"]
for p in ["01_clean_dm", "02_clean_ae", "03_derive_adsl",
          "04_derive_adae", "05_summary_safety"]:
    mlines.append(f'  {p.replace("_", "")}["{p}"]')
for e in prog_dag["edges"]:
    a = e["from"].replace("_", "")
    b = e["to"].replace("_", "")
    mlines.append(f'  {a} -->|{e["via_dataset"]}| {b}')
render_mermaid("\n".join(mlines), height=420)
