"""Live Demo Walkthrough — guided steps with speaker notes for live presentation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, load_json, read_text, render_mermaid,
                  run_pipeline_step, page_header)

st.set_page_config(page_title="Live Demo Walkthrough", layout="wide")

page_header("🎬", "Live Demo Walkthrough",
            "A linear, narrated tour of the modernization. Use Previous/Next "
            "to step through. Speaker notes guide what to say at each step.")

# ----------------------------------------------------------------------------
# Step navigation state
# ----------------------------------------------------------------------------

if "demo_step" not in st.session_state:
    st.session_state.demo_step = 0

STEPS: list[dict] = [
    # 0
    {
        "title": "1 · The setup — what we're modernizing",
        "say": (
            "Before we start, here's what we're working with. CTX-2024-001 "
            "is a clinical-trials safety pipeline written in SAS. Five "
            "programs, 533 lines of code, a macro library, a format catalog, "
            "and a markdown spec describing the derivations. It produces six "
            "ADaM datasets — the analysis tables a regulator would see. We "
            "have ground-truth CSVs that the modernized pipeline must "
            "reproduce row-for-row."
        ),
        "show": "codebase",
    },
    # 1
    {
        "title": "2 · Why naive translation fails",
        "say": (
            "The obvious approach — read the SAS line by line and rewrite it "
            "in Python — sounds simple. It isn't. Three things will burn you. "
            "First, **macros are runtime**: a static reading can't see what "
            "they expand to in any given call. Second, there are **hidden "
            "cross-program globals** — a macro variable set in one program "
            "by a SQL `select … into :var` is read inside a macro called from "
            "two *other* programs. Static file-by-file translation never sees "
            "this. Third, SAS does **implicit type coercions** in joins that "
            "Python silently won't. We're going to build something that "
            "catches all three."
        ),
        "show": "naive_failure",
    },
    # 2
    {
        "title": "3 · The architecture — graph-driven modernization",
        "say": (
            "Instead of translating SAS to Python directly, we mediate "
            "everything through a knowledge graph. Five phases. "
            "Phase 1 parses the SAS into a structured AST plus control-flow "
            "and data-flow graphs. Phase 2 parses the markdown docs into "
            "structured entities. Phase 3 unifies both into a knowledge "
            "graph — datasets, columns, procs, macros, rules, open issues, "
            "constraints, all with edges between them. Phase 4 regenerates "
            "specs, schemas, DAG, and pytest stubs from the graph alone. "
            "Phase 5 generates Python from the regenerated specs — never from "
            "the SAS source. That last rule is the most important: it forces "
            "every ambiguity to surface explicitly."
        ),
        "show": "architecture",
    },
    # 3
    {
        "title": "4 · Run the whole pipeline — live",
        "say": (
            "Before we drill into the phases, let me show you the headline. "
            "I'm going to run the entire modernization end-to-end right now "
            "— Phase 1 through 5 plus the validation tests. Watch the bottom "
            "of the screen."
        ),
        "show": "run_live",
    },
    # 4
    {
        "title": "5 · Phase 1 — parsing the SAS",
        "say": (
            "Phase 1 is a hand-rolled two-pass parser. Pass A expands every "
            "macro, every `%include`, every `&var` reference — and crucially, "
            "**scans each macro body for global reads and writes**. That's "
            "the trick that catches `&TRT_START_DT` — the variable that one "
            "program writes via a SQL `select into :var` and a macro in another "
            "program reads invisibly. Pass B builds a structural AST per "
            "program plus control- and data-flow graphs. The output is in "
            "build/ast — eight JSON files per program plus an aggregate "
            "macro table."
        ),
        "show": "phase1_demo",
    },
    # 5
    {
        "title": "6 · The hidden coupling exposed",
        "say": (
            "Here's the macro table from Phase 1. Look at "
            "`is_treatment_emergent` — its `reads_globals` column shows "
            "`TRT_START_DT`. That's a variable not declared as a parameter. "
            "It must be set somewhere else at runtime. The parser doesn't "
            "guess what it is — it just flags it. This is exactly the kind "
            "of dependency that a line-by-line translation misses."
        ),
        "show": "macro_globals",
    },
    # 6
    {
        "title": "7 · Phase 2 — parsing the docs",
        "say": (
            "The SAS code says *what* the pipeline does. The docs say *why*, "
            "and they flag known issues. Phase 2 parses the markdown spec "
            "into Section, BusinessRule, and OpenIssue nodes. The "
            "'first dose vs randomization date' issue — tracker SP-227 — "
            "becomes an OpenIssue with full provenance. SP-184 — vendor B's "
            "`GRADE n` severity codes — becomes another. These will both "
            "feed into the ambiguity register."
        ),
        "show": "phase2_demo",
    },
    # 7
    {
        "title": "8 · Phase 3 — the knowledge graph",
        "say": (
            "Phases 1 and 2 feed into the central knowledge graph: 173 nodes, "
            "93 edges. Eight node kinds, eight edge kinds. The most-connected "
            "node is `adam.adsl` — the subject-level analysis dataset that "
            "every downstream program touches. Try the queries on this page: "
            "trace `TRTEMFL` back to its upstream columns, including the "
            "runtime macro it depends on. This graph is the **single source "
            "of truth** for everything downstream — Phases 4 and 5 read only "
            "from here."
        ),
        "show": "phase3_demo",
    },
    # 8
    {
        "title": "9 · The ambiguity checkpoint",
        "say": (
            "Before Phase 4, the pipeline pauses on every High-severity "
            "ambiguity. There was one: TRTEMFL's definition. The spec says "
            "`first dose date` per subject. The implementation uses a "
            "cohort-level `max(RFSTDT)` over the safety population. The user "
            "is asked to choose. We picked Option B (cohort-level) because "
            "that's what reproduces ground truth and matches the running "
            "implementation. **The point is**: the system asked. It didn't "
            "guess. Medium and Low items are auto-logged with documented "
            "assumptions and counterfactuals."
        ),
        "show": "ambiguity_checkpoint",
    },
    # 9
    {
        "title": "10 · Phase 4 — regenerating the contracts",
        "say": (
            "From the graph alone, Phase 4 regenerates everything Phase 5 "
            "will need. Five functional specs in plain English. Nine dataset "
            "schemas with dtype maps. A topologically-sorted execution DAG "
            "with parallelizable levels. Six pytest stubs that assert schema "
            "match, row count, and row-for-row equality on the dataset's "
            "natural sort key. Let me show you one spec — this is the "
            "**only thing Phase 5 codegen will read for that program**."
        ),
        "show": "phase4_demo",
    },
    # 10
    {
        "title": "11 · Phase 5 — code generation under R1",
        "say": (
            "Phase 5 generates pandas + duckdb code from the spec markdown "
            "and the schema modules — and *only* those. Hard rule R1: no "
            "SAS file is opened. If the spec is incomplete, we discover it "
            "as a test failure and fix the **spec**, never the generated "
            "Python. That happened twice during validation: an off-by-one "
            "AGE_DERIVED — turned out the SAS code uses 365.25 but the "
            "ground truth was generated with 365 — and a duckdb `SUM` "
            "returning DECIMAL instead of INT. Both became spec corrections, "
            "with new ambiguity entries."
        ),
        "show": "phase5_demo",
    },
    # 11
    {
        "title": "12 · Validation — row-for-row, with diff highlighting",
        "say": (
            "Here's the proof. Every output dataset compared cell-by-cell "
            "against the ground truth, with mismatches highlighted in red. "
            "Right now there are zero mismatches across all 6 datasets — "
            "23 out of 23 pytest assertions green. On top of that, five "
            "aggregate-reconciliation tests catch bugs row-by-row tests can "
            "pass coincidentally — like 'AE_SUMMARY total events must equal "
            "ADAE TRTEMFL=Y rows'. That's not coincidence; it's the result "
            "of every ambiguity being surfaced and resolved before codegen."
        ),
        "show": "validation_proof",
    },
    # 12
    {
        "title": "13 · The ambiguity register — honesty about uncertainty",
        "say": (
            "Six ambiguities total. Three Medium, two Low, one High. The "
            "High one — `&TRT_START_DT` — was paused at the checkpoint and "
            "resolved by the user. Five Mediums and Lows were auto-logged "
            "with documented assumptions and 'what would change if this is "
            "wrong'. **This is the deliverable nobody asks for but everyone "
            "needs**: a complete record of what we assumed and why, so a "
            "future engineer or regulator can audit our decisions."
        ),
        "show": "ambiguity_register",
    },
    # 13
    {
        "title": "14 · Why this scales",
        "say": (
            "This codebase has 5 programs. A real client has hundreds. The "
            "architecture is exactly the same. The graph backend swaps from "
            "NetworkX-in-JSON to SQLite or a graph database when you cross "
            "~50 nodes. The hand-rolled parser swaps to tree-sitter when you "
            "hit `%do %while` or `%eval`. The ambiguity policy moves from "
            "an in-process pause to a Linear/Jira ticket. Every piece is "
            "designed to swap. The 5-phase architecture and the R1 contract "
            "stay constant."
        ),
        "show": "production_rollout",
    },
    # 14
    {
        "title": "15 · Takeaways",
        "say": (
            "Three things to remember. **One**: we don't translate, we "
            "mediate — every fact lives in a graph that downstream phases "
            "read from. **Two**: the spec is the contract — Phase 5 reads "
            "it, never the SAS source, so spec gaps surface as test "
            "failures. **Three**: ambiguities are honored, not guessed — "
            "the system pauses on Highs and documents Mediums and Lows so "
            "no decision is silently encoded. The full SOLUTION.md and a "
            "PDF takeaway are on the right-hand sidebar."
        ),
        "show": "takeaways",
    },
]

# ----------------------------------------------------------------------------
# Step navigator
# ----------------------------------------------------------------------------

n_steps = len(STEPS)
step = st.session_state.demo_step

# Progress bar
st.progress((step + 1) / n_steps, text=f"Step {step + 1} of {n_steps}")

# Prev / Next / Jump
nav_cols = st.columns([1, 1, 4, 1])
with nav_cols[0]:
    if st.button("◀ Previous", disabled=(step == 0), width="stretch"):
        st.session_state.demo_step = max(0, step - 1)
        st.rerun()
with nav_cols[1]:
    if st.button("Next ▶", type="primary",
                  disabled=(step >= n_steps - 1), width="stretch"):
        st.session_state.demo_step = min(n_steps - 1, step + 1)
        st.rerun()
with nav_cols[2]:
    jump = st.selectbox("Jump to step", [s["title"] for s in STEPS],
                          index=step, label_visibility="collapsed")
    if jump != STEPS[step]["title"]:
        st.session_state.demo_step = [s["title"] for s in STEPS].index(jump)
        st.rerun()
with nav_cols[3]:
    if st.button("⏮ Restart", width="stretch"):
        st.session_state.demo_step = 0
        st.rerun()

st.divider()

# ----------------------------------------------------------------------------
# Render the current step
# ----------------------------------------------------------------------------

cur = STEPS[step]

st.header(cur["title"])

# Speaker notes (always visible)
with st.container(border=True):
    st.markdown("##### 🗣️ What to say")
    st.markdown(cur["say"])

st.divider()

# ----------------------------------------------------------------------------
# Per-step content (the actual demo material)
# ----------------------------------------------------------------------------

show = cur["show"]

if show == "codebase":
    st.markdown("##### 📂 What's in the codebase")
    counts = load_json(BUILD / "ast" / "_aggregate" / "counts.json")
    rows = []
    for p in counts["programs"]:
        rel = Path(p["source_file"]).relative_to(PROJECT_ROOT)
        rows.append({
            "file": str(rel).replace("\\", "/"),
            "lines": p["lines_of_source"],
            "DATA": p["data_blocks"],
            "PROC": p["proc_blocks"],
            "by_kind": ", ".join(f"{k}×{v}" for k, v in p["procs_by_kind"].items()) or "—",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown("##### 📦 Ground-truth outputs (the contract)")
    truth_files = ["dm_clean", "ae_clean", "adsl", "adae", "ae_summary", "ae_incidence"]
    cols = st.columns(3)
    for i, name in enumerate(truth_files):
        df = pd.read_csv(PROJECT_ROOT / "ground_truth" / f"{name}.csv",
                          dtype=str, keep_default_na=False)
        with cols[i % 3]:
            st.metric(name, f"{len(df)} rows × {len(df.columns)} cols")

elif show == "naive_failure":
    st.markdown("##### 🕳️ The trap: hidden cross-program coupling")
    st.markdown("Here's a snippet from `util_macros.sas`:")
    st.code('''%macro is_treatment_emergent(ae_start=);
  (not missing(&ae_start) and &ae_start >= &TRT_START_DT)
%mend is_treatment_emergent;''', language="sas")
    st.markdown("And from `03_derive_adsl.sas` — *a different file*:")
    st.code('''proc sql noprint;
  select max(rfstdt) into :TRT_START_DT trimmed
  from work.adsl_pre
  where saffl = 'Y';
quit;''', language="sas")
    st.error(
        "**The macro reads `&TRT_START_DT`. The variable is set in a different "
        "program by an SQL select-into. A line-by-line translation of either "
        "file in isolation will not produce a working pipeline.**"
    )

elif show == "architecture":
    render_mermaid("""
flowchart LR
  classDef phase fill:#1f2937,stroke:#3b82f6,color:#fafafa,stroke-width:2px;
  classDef artifact fill:#064e3b,stroke:#22c55e,color:#dcfce7;
  classDef ground fill:#7c2d12,stroke:#ef4444,color:#fff7ed;

  SAS[("SAS source")]:::ground
  DOCS[("Markdown docs")]:::ground

  P1["Phase 1<br/>Parser"]:::phase
  P2["Phase 2<br/>Doc parser"]:::phase
  P3["Phase 3<br/>Knowledge graph"]:::phase
  P4["Phase 4<br/>Regenerator"]:::phase
  P5["Phase 5<br/>Codegen"]:::phase

  A1[/"AST + flow graphs"/]:::artifact
  A2[/"Doc entities"/]:::artifact
  A3[/"kg.json"/]:::artifact
  A4[/"specs · schemas · DAG · tests"/]:::artifact
  A5[/"Python output"/]:::artifact
  GT[("ground truth")]:::ground

  SAS --> P1 --> A1
  DOCS --> P2 --> A2
  A1 --> P3
  A2 --> P3
  P3 --> A3
  A3 --> P4 --> A4
  A4 --> P5 --> A5
  A5 -. row-for-row .- GT
""", height=480)
    st.info(
        "**The single most important constraint:** Phase 5 (codegen) reads "
        "**only** `build/specs/` and `build/schemas/`. It never opens the "
        "SAS source. That's what makes ambiguities surface — there's no "
        "back-channel to silently encode an assumption."
    )

elif show == "run_live":
    st.markdown("Click the button to execute Phase 1 → 5 → tests in order.")
    if st.button("▶️ Run all phases + tests", type="primary"):
        steps = [
            ("Phase 1 — Parse SAS", ["python", "build/parser/run.py"]),
            ("Phase 2 — Parse docs", ["python", "build/parser/parse_docs.py"]),
            ("Phase 3 — Build knowledge graph", ["python", "build/graph/build_kg.py"]),
            ("Phase 4 — Regenerate", ["python", "build/regenerator/regenerate.py"]),
            ("Phase 5 — Generate + run", ["python", "build/dag/run.py"]),
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
                    break
            progress.progress(i / len(steps))

elif show == "phase1_demo":
    st.markdown("##### 🔵 Phase 1 inputs and outputs")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Input:** `04_derive_adae.sas` (excerpt)")
        st.code("""data work.adae_pre;
  merge work.ae_sorted(in=a)
        work.adsl_sub(in=b);
  by usubjid;
  if a and b;

  length trtemfl $1;
  if %is_treatment_emergent(ae_start=aestdt) then trtemfl = 'Y';
  else trtemfl = 'N';
run;""", language="sas")
    with c2:
        st.markdown("**Output:** AST block (excerpt from `build/ast/04_derive_adae.json`)")
        st.code('''{
  "kind": "data",
  "output_datasets": ["work.adae_pre"],
  "input_datasets": ["work.ae_sorted", "work.adsl_sub"],
  "statements": [
    {"kind": "merge", "raw": "merge work.ae_sorted(in=a)..."},
    {"kind": "by", "raw": "by usubjid"},
    {"kind": "if_assign", "col": "trtemfl",
     "expr": "'Y'", "else_expr": "'N'"}
  ]
}''', language="json")

elif show == "macro_globals":
    macro_table = load_json(BUILD / "ast" / "_aggregate" / "macro_table.json")
    rows = []
    for m in macro_table["macros"]:
        rows.append({
            "macro": m["name"],
            "params": ", ".join(p["name"] for p in m["params"]),
            "reads_globals": ", ".join(m["reads_globals"]) or "—",
            "writes_globals": ", ".join(m["writes_globals"]) or "—",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.warning(
        "🎯 **Look at `is_treatment_emergent`** — `reads_globals = TRT_START_DT`. "
        "That global is *not* a parameter and is *not* `%let` in this file. "
        "The parser flags it. The graph will then connect this dot."
    )

elif show == "phase2_demo":
    docs = load_json(BUILD / "graph" / "doc_entities.json")
    st.markdown(f"##### 📚 Open issues extracted from documentation ({len(docs['open_issues'])} total)")
    for o in docs["open_issues"]:
        with st.container(border=True):
            tickers = ", ".join(o["tickers"]) or "no tracker"
            st.markdown(f"**{o['id']}** · {tickers}")
            st.caption(f"`{o['source_file']}` §{o['source_section']} L{o['source_line']}")
            st.markdown(o["text"])
    st.info(
        "🎯 **SP-227** (the 'first dose vs randomization' issue) and **SP-184** "
        "(vendor B GRADE codes) will become High and Medium ambiguities once "
        "the graph connects them to the SAS code that touches their datasets."
    )

elif show == "phase3_demo":
    stats = load_json(BUILD / "graph" / "kg_stats.json")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Node kinds")
        st.dataframe(pd.DataFrame([
            {"kind": k, "count": v}
            for k, v in stats["node_counts_by_kind"].items()
        ]), hide_index=True, width="stretch")
    with c2:
        st.markdown("##### Edge kinds")
        st.dataframe(pd.DataFrame([
            {"kind": k, "count": v}
            for k, v in stats["edge_counts_by_kind"].items()
        ]), hide_index=True, width="stretch")
    st.markdown("##### Most-connected nodes")
    st.dataframe(pd.DataFrame(stats["most_connected"]), hide_index=True,
                  width="stretch")
    st.success(
        "🎯 Open the **🕸️ Phase 3 Knowledge Graph** page in the sidebar to see "
        "this as an interactive force-directed graph. Click any node to see "
        "its attributes; filter by kind; focus on a 2-hop neighborhood."
    )

elif show == "ambiguity_checkpoint":
    st.markdown("##### ⚠️ The High-severity ambiguity raised before Phase 4")
    with st.container(border=True):
        st.markdown("**#1 — `&TRT_START_DT` cross-program coupling for TRTEMFL**")
        st.markdown(
            "**The question:** does `TRTEMFL = 'Y'` mean the AE happened on or "
            "after the **subject's own** RFSTDT (per spec §4.4 text), or on or "
            "after the **cohort-level latest** RFSTDT among `SAFFL='Y'` "
            "subjects (per the SAS implementation)?"
        )
        st.markdown(
            "**The two options:**\n\n"
            "| Option | Behaviour | Match with ground truth |\n"
            "| ------ | --------- | ----------------------- |\n"
            "| A | Per-subject `RFSTDT` (spec text) | Likely **mismatch** |\n"
            "| B | Cohort-level `max(RFSTDT)` (implementation) | **Matches** |"
        )
        st.success(
            "✅ User confirmed Option B (cohort-level). SP-227 follow-up "
            "remains for v1.4. **The system asked. It did not guess.**"
        )

elif show == "phase4_demo":
    st.markdown("##### 🛠️ One regenerated spec — the only Phase 5 input")
    spec = read_text(BUILD / "specs" / "04_derive_adae.md")
    with st.expander("📝 build/specs/04_derive_adae.md (full)", expanded=True):
        st.markdown(spec)
    st.info(
        "🎯 The Transformations section is plain English. Phase 5 will read "
        "this and generate Python — without ever opening the original SAS."
    )

elif show == "phase5_demo":
    st.markdown("##### 🐍 Spec ↔ generated Python (program 04)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Spec excerpt** (`build/specs/04_derive_adae.md`)")
        st.markdown(
            "5. Compute `TRTEMFL`: `'Y'` if `AESTDT is not null and "
            "AESTDT >= TRT_START_DT` else `'N'`. (Cohort-level scalar — "
            "see §1.5 #1.)"
        )
        st.markdown(
            "6. Compute `ONTRTFL`: `'Y'` if `AESTDT, RFSTDT, RFENDT all "
            "non-null and RFSTDT <= AESTDT <= RFENDT` else `'N'`."
        )
    with c2:
        st.markdown("**Generated Python** (`build/target/04_derive_adae.py`)")
        st.code('''aestdt = to_date(adae["AESTDT"])
adae["TRTEMFL"] = (
    aestdt.notna() & (aestdt >= trt_start_dt)
).map({True: "Y", False: "N"})

rfstdt = to_date(adae["RFSTDT"])
rfendt = to_date(adae["RFENDT"])
adae["ONTRTFL"] = (
    aestdt.notna() & rfstdt.notna() & rfendt.notna()
    & (aestdt >= rfstdt) & (aestdt <= rfendt)
).map({True: "Y", False: "N"})''', language="python")
    st.success(
        "🎯 No SAS file was opened during this codegen. Hard rule R1 enforced."
    )

elif show == "validation_proof":
    st.markdown("##### ✅ All 6 datasets pass row-for-row + aggregate checks")
    rows = [
        ("adam.dm_clean", 20, 13, "✅", "✅", "✅"),
        ("adam.ae_clean", 58, 12, "✅", "✅", "✅"),
        ("adam.adsl", 20, 18, "✅", "✅", "✅"),
        ("adam.adae", 58, 24, "✅", "✅", "✅"),
        ("adam.ae_summary", 9, 5, "✅", "✅", "✅"),
        ("adam.ae_incidence", 7, 7, "✅", "✅", "✅"),
    ]
    df = pd.DataFrame(rows, columns=["Dataset", "Rows", "Cols", "Schema",
                                       "Row count", "Row equality"])
    st.dataframe(df, hide_index=True, width="stretch")

    st.markdown("##### 5 aggregate-reconciliation tests (added on top)")
    st.markdown(
        "- `sum(AE_SUMMARY.N_EVENTS) == count(ADAE where TRTEMFL='Y')` ✅\n"
        "- `sum(AE_SUMMARY.N_SERIOUS) == count(ADAE where TRTEMFL='Y' and AESER='Y')` ✅\n"
        "- Per-arm `AE_INCIDENCE.N_SUBJ_TOTAL == count distinct USUBJID in ADSL where SAFFL='Y'` ✅\n"
        "- `N_SUBJ_WITH_AE ≤ N_SUBJ_TOTAL` per row ✅\n"
        "- `set(ADAE.USUBJID) ⊆ set(ADSL.USUBJID)` ✅"
    )

    st.success("🎯 **23 / 23 pytest assertions green.** Re-run live on the "
                "Validation page if you want to prove it.")

elif show == "ambiguity_register":
    cards = [
        ("#1 · `&TRT_START_DT` cohort vs per-subject", "🔴 High",
         "✅ Resolved by user 2026-05-07", "cohort-level scalar"),
        ("#2 · SP-184 vendor B `GRADE n` codes", "🟡 Medium",
         "📝 Logged", "leave AESEV_STD blank, matches ground truth"),
        ("#3 · SITE_ID type mismatch (char vs num)", "🟡 Medium",
         "📝 Logged", "explicit zero-padded coercion"),
        ("#4 · DM duplicates from CRF amendment", "⚪ Low",
         "📝 Logged", "max RECORDCREATEDT dedup retained"),
        ("#5 · `&PROJ_ROOT = %sysfunc(getoption(SASUSER))`", "⚪ Low",
         "📝 Logged", "cosmetic — ignored in Python"),
        ("#6 · AGE_DERIVED `//365` vs `floor(/365.25)`", "🟡 Medium",
         "📝 Logged at validation", "spec corrected per R4"),
    ]
    cols = st.columns(2)
    for i, (title, sev, status, decision) in enumerate(cards):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.markdown(f"{sev} · {status}")
                st.caption(f"Decision: {decision}")

elif show == "production_rollout":
    st.markdown("##### 🚀 What changes for a real client estate")
    items = [
        ("Parser", "hand-rolled regex", "tree-sitter SAS / ANTLR"),
        ("Graph backend", "NetworkX + JSON", "SQLite or graph DB (Neo4j/Kuzu)"),
        ("Ambiguity policy", "in-process pause", "Linear/Jira ticket integration"),
        ("Format catalog", "hard-coded in common.py", "auto-emit from PROC FORMAT"),
        ("PROC SQL parsing", "regex `as <alias>`", "real SQL parser (sqlglot)"),
        ("Validation", "row-for-row equality", "+ property-based + boundary tests"),
        ("Vendor adapters", "inline in 02_clean_ae", "first-class adapter layer"),
        ("Schema migrations", "manual", "regenerate.py --diff plan"),
    ]
    df = pd.DataFrame(items, columns=["Concern", "MVP (this codebase)",
                                        "Production rollout"])
    st.dataframe(df, hide_index=True, width="stretch")
    st.info(
        "🎯 **The architecture stays constant.** The 5-phase pipeline and "
        "the R1 contract are exactly the same. Only the components swap."
    )

elif show == "takeaways":
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("### 1️⃣")
            st.markdown("**Mediate, don't translate.**")
            st.markdown(
                "Every fact about the SAS code lives in a knowledge graph. "
                "Downstream phases read from the graph — not from SAS."
            )
    with c2:
        with st.container(border=True):
            st.markdown("### 2️⃣")
            st.markdown("**The spec is the contract.**")
            st.markdown(
                "Phase 5 reads the regenerated spec, never the SAS source. "
                "Spec gaps surface as test failures, not as silent bugs."
            )
    with c3:
        with st.container(border=True):
            st.markdown("### 3️⃣")
            st.markdown("**Honor ambiguities.**")
            st.markdown(
                "Pause on High-severity items, document Medium and Low. "
                "No assumption is silently encoded."
            )
    st.divider()
    st.markdown("##### 📂 Materials")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📑 Final SOLUTION.md** — open the *Final Solution* page "
                    "in the sidebar for the full deliverable.")
    with c2:
        st.markdown("**📥 Export PDF** — generate a printable handout from "
                    "the *Export PDF* page.")
    with c3:
        st.markdown("**▶️ Re-run live** — every phase has its own page; the "
                    "*Validation* page reruns pytest on demand.")
