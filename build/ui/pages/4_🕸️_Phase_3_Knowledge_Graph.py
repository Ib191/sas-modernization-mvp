"""Phase 3 — Knowledge graph (interactive)."""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import (BUILD, PROJECT_ROOT, load_json, page_header, render_mermaid,
                  tutorial_intro, demo_prompt)

st.set_page_config(page_title="Phase 3 — Knowledge Graph", layout="wide")

page_header("🕸️", "Phase 3 — Knowledge graph (interactive)",
            "173-node, 93-edge MultiDiGraph unifying SAS structure, "
            "documentation, and validation rules into a single source of truth.")

tutorial_intro(
    why=(
        "Phases 4 and 5 must read from a **single, queryable representation** "
        "— never from the SAS source again. The graph is that representation. "
        "It is the **single source of truth** for everything downstream. If "
        "an answer isn't in the graph, the fix is to enrich Phase 3, not to "
        "peek at SAS."
    ),
    what=(
        "- Headline counts: 8 node kinds (Dataset, Column, Proc, Macro, "
        "Program, BusinessRule, OpenIssue, Constraint), 8 edge kinds\n"
        "- Top-10 most-connected hubs (`adam.adsl` is #1 — the data-flow "
        "linchpin)\n"
        "- An **interactive force-directed graph** you can drag/zoom/click\n"
        "- A query interface for column lineage and program dependencies\n"
        "- Mermaid diagrams of dataset and column lineage"
    ),
    insight=(
        "The **most-connected node is `adam.adsl`** with degree 12. It's "
        "the central hub: every downstream dataset depends on it, *and* it's "
        "where the runtime side-effect (`&TRT_START_DT`) is computed. The "
        "graph naturally reveals which datasets are load-bearing — exactly "
        "the ones a real engineering team should monitor most carefully."
    ),
    speaker=(
        "Use the **Focus around** dropdown to focus on `adam.adsl`. Watch "
        "how the graph re-centers and shows the 2-hop neighborhood. Then "
        "use the **Lineage for a column** query and pick `TRTEMFL`. Notice "
        "the writer (PROC sql in 04_derive_adae) and the upstream datasets "
        "(adsl, ae_clean) — and the `flagged_by` issues. **This is the same "
        "thing you'd run from the command line via "
        "`python build/graph/query.py lineage_for_column TRTEMFL`** — but "
        "with a click."
    ),
)

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

stats = load_json(BUILD / "graph" / "kg_stats.json")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Node counts**")
    st.dataframe(pd.DataFrame([
        {"kind": k, "count": v}
        for k, v in stats["node_counts_by_kind"].items()
    ]), hide_index=True, width="stretch")
with c2:
    st.markdown("**Edge counts**")
    st.dataframe(pd.DataFrame([
        {"kind": k, "count": v}
        for k, v in stats["edge_counts_by_kind"].items()
    ]), hide_index=True, width="stretch")

st.markdown("**Most-connected nodes** (the 'hubs')")
st.dataframe(pd.DataFrame(stats["most_connected"]), hide_index=True,
              width="stretch")

# ---------------------------------------------------------------------------
# Interactive pyvis network
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Interactive graph")

st.caption("Drag to pan, scroll to zoom, click nodes to inspect. "
            "Filter by node kind to declutter.")

@st.cache_data(show_spinner=False)
def _load_graph_data() -> dict:
    return load_json(BUILD / "graph" / "kg.json")


@st.cache_resource(show_spinner=False)
def _load_graph() -> nx.MultiDiGraph:
    return nx.node_link_graph(_load_graph_data(), edges="edges",
                                directed=True, multigraph=True)


g = _load_graph()

KIND_COLORS = {
    "Dataset":      "#3b82f6",  # blue
    "Column":       "#0ea5e9",  # cyan
    "Proc":         "#a855f7",  # purple
    "Macro":        "#f59e0b",  # amber
    "Program":      "#ef4444",  # red
    "BusinessRule": "#22c55e",  # green
    "OpenIssue":    "#dc2626",  # dark red
    "Constraint":   "#94a3b8",  # slate
}

available_kinds = sorted(stats["node_counts_by_kind"].keys())
default = ["Dataset", "Program", "Macro", "OpenIssue"]
sel_kinds = st.multiselect("Show node kinds", available_kinds,
                              default=[k for k in default if k in available_kinds])

# Optional: focus on a single dataset and its neighborhood
focus = st.selectbox("Focus around (optional)",
                       ["(whole graph)"]
                       + sorted(n for n, a in g.nodes(data=True)
                                if a.get("kind") == "Dataset"))


def _build_pyvis_html(g: nx.MultiDiGraph, sel_kinds: list[str],
                       focus: str | None, max_nodes: int = 250) -> str:
    from pyvis.network import Network
    sub = nx.MultiDiGraph()
    nodes_to_keep: set[str] = set()
    for n, a in g.nodes(data=True):
        if a.get("kind") in sel_kinds:
            nodes_to_keep.add(n)
    if focus and focus != "(whole graph)" and focus in g:
        # 2-hop neighborhood of focus
        nbhd = {focus}
        for u, v in list(g.in_edges(focus)) + list(g.out_edges(focus)):
            nbhd.add(u); nbhd.add(v)
        # 2-hop expand
        more = set()
        for n in list(nbhd):
            for u, v in list(g.in_edges(n)) + list(g.out_edges(n)):
                more.add(u); more.add(v)
        nbhd |= more
        nodes_to_keep &= nbhd
        nodes_to_keep |= {focus}  # always include focus

    if len(nodes_to_keep) > max_nodes:
        # prefer high-degree nodes
        ranked = sorted(nodes_to_keep,
                          key=lambda n: g.degree(n), reverse=True)[:max_nodes]
        nodes_to_keep = set(ranked)

    for n in nodes_to_keep:
        a = g.nodes[n]
        sub.add_node(n, **a)
    for u, v, k, a in g.edges(keys=True, data=True):
        if u in nodes_to_keep and v in nodes_to_keep:
            sub.add_edge(u, v, key=k, **a)

    net = Network(height="700px", width="100%", bgcolor="#0e1117",
                    font_color="#fafafa", directed=True, notebook=False,
                    cdn_resources="remote")
    net.barnes_hut(gravity=-8000, spring_length=180, spring_strength=0.04)
    for n, a in sub.nodes(data=True):
        kind = a.get("kind", "?")
        title_parts = [f"<b>{kind}</b>: {n}"]
        for k, v in a.items():
            if k == "kind":
                continue
            sval = str(v)
            if len(sval) > 80:
                sval = sval[:80] + "…"
            title_parts.append(f"{k}: {sval}")
        net.add_node(n, label=n.split("::")[-1].split(":")[-1][-30:],
                      title="<br/>".join(title_parts),
                      color=KIND_COLORS.get(kind, "#9ca3af"),
                      shape="dot",
                      size=8 + min(20, sub.degree(n)))
    for u, v, _, a in sub.edges(keys=True, data=True):
        net.add_edge(u, v, title=a.get("kind", ""),
                      label="" if a.get("kind") in ("validates", "applies_to")
                      else a.get("kind", ""),
                      arrows="to", color="#475569")
    # Save to a temp file under build/ui/static so we can read it back
    out_path = Path(__file__).resolve().parent.parent / "static" / "network.html"
    net.save_graph(str(out_path))
    return out_path.read_text(encoding="utf-8")


focus_arg = None if focus == "(whole graph)" else focus
html = _build_pyvis_html(g, sel_kinds, focus_arg)
components.html(html, height=720, scrolling=True)

# ---------------------------------------------------------------------------
# Query interface
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Query the graph")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Lineage for a column**")
    col_name = st.selectbox("Column", [
        "TRTEMFL", "MAX_AESEV", "ITTFL", "TRTDURD", "INCIDENCE_RATE",
        "AGE_DERIVED", "AESEVN", "SAFFL", "ASTDY", "USUBJID",
    ])
    col_l = col_name.lower()
    matches = [
        n for n, a in g.nodes(data=True)
        if a.get("kind") == "Column" and a.get("name", "").lower() == col_l
    ]
    if not matches:
        st.warning(f"No Column node named {col_name}")
    for cid in matches:
        attr = g.nodes[cid]
        with st.container(border=True):
            st.markdown(f"**`{cid}`** · {attr.get('dtype')} · "
                        f"nullable={attr.get('nullable')}")
            writers = [u for u, _, _, a in g.in_edges(cid, keys=True, data=True)
                        if a.get("kind") == "writes"]
            if writers:
                st.markdown("**Written by:**")
                for w in writers:
                    wattr = g.nodes[w]
                    if wattr.get("kind") == "Proc":
                        st.markdown(
                            f"- {wattr.get('label')} · "
                            f"`{wattr.get('program')}.sas:{wattr.get('line_start')}`"
                        )
            ds = attr["dataset"]
            upstream = [u for u, _, _, a in g.in_edges(ds, keys=True, data=True)
                         if a.get("kind") == "contributes_to"]
            if upstream:
                st.markdown(f"**Upstream datasets:** "
                            f"{', '.join(sorted(set(upstream)))}")
            flags = [v for _, v, _, a in g.out_edges(cid, keys=True, data=True)
                      if a.get("kind") == "flagged_by"]
            flags += [v for _, v, _, a in g.out_edges(ds, keys=True, data=True)
                       if a.get("kind") == "flagged_by"]
            if flags:
                st.markdown("**Flagged by issues:**")
                for f in sorted(set(flags)):
                    fa = g.nodes[f]
                    st.markdown(f"- `{fa.get('id')}`: "
                                f"{(fa.get('text') or '')[:120]}")

with col2:
    st.markdown("**Dependencies of a program**")
    prog = st.selectbox("Program", [
        "01_clean_dm", "02_clean_ae", "03_derive_adsl",
        "04_derive_adae", "05_summary_safety",
    ])
    pid = f"PROGRAM:{prog}"
    if g.has_node(pid):
        with st.container(border=True):
            ups = [(v, a) for _, v, _, a in g.out_edges(pid, keys=True, data=True)
                   if a.get("kind") == "depends_on"]
            if ups:
                st.markdown("**Depends on:**")
                for v, a in ups:
                    st.markdown(f"- {v.replace('PROGRAM:', '')} via "
                                f"`{a.get('via_dataset')}`")
            else:
                st.markdown("No upstream dependencies.")
            downs = [u for u, _, _, a in g.in_edges(pid, keys=True, data=True)
                      if a.get("kind") == "depends_on"]
            if downs:
                st.markdown(f"**Depended on by:** "
                            f"{', '.join(sorted(set(d.replace('PROGRAM:','') for d in downs)))}")
            macros = [v for _, v, _, a in g.out_edges(pid, keys=True, data=True)
                       if a.get("kind") == "calls"]
            if macros:
                st.markdown(f"**Calls macros:** "
                            f"{', '.join(sorted(set(m.replace('macro::','') for m in macros)))}")

# ---------------------------------------------------------------------------
# Dataset & column lineage diagrams
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Dataset-level lineage")
render_mermaid("""
graph LR
  raw_dm["raw.dm"]
  raw_ae["raw.ae"]
  raw_sl["raw.site_lookup"]
  dm_c["adam.dm_clean"]
  ae_c["adam.ae_clean"]
  adsl["adam.adsl"]
  adae["adam.adae"]
  ae_sum["adam.ae_summary"]
  ae_inc["adam.ae_incidence"]

  raw_dm -- "01_clean_dm" --> dm_c
  raw_ae -- "02_clean_ae" --> ae_c
  dm_c -- "03_derive_adsl" --> adsl
  raw_sl -- "03_derive_adsl" --> adsl
  ae_c -- "04_derive_adae" --> adae
  adsl -- "04_derive_adae" --> adae
  adae -- "05_summary_safety" --> ae_sum
  adae -- "05_summary_safety" --> ae_inc
  adsl -- "05_summary_safety" --> ae_sum
  adsl -- "05_summary_safety" --> ae_inc
""", height=460)

st.subheader("Column-level lineage (5 critical columns)")
render_mermaid("""
graph LR
  classDef in fill:#1e3a8a,color:#dbeafe;
  classDef out fill:#7c2d12,color:#fed7aa;
  classDef rt fill:#581c87,color:#f3e8ff;

  RFSTDT[adam.dm_clean.RFSTDT]:::in
  RFENDT[adam.dm_clean.RFENDT]:::in
  TRTDURD[adam.adsl.TRTDURD]:::out
  RFSTDT --> TRTDURD
  RFENDT --> TRTDURD

  SAFFL[adam.adsl.SAFFL]:::in
  ARM[adam.adsl.ARM]:::in
  ITTFL[adam.adsl.ITTFL]:::out
  SAFFL --> ITTFL
  ARM --> ITTFL

  AESTDT[adam.adae.AESTDT]:::in
  TRTSDT["&TRT_START_DT (cohort scalar)"]:::rt
  TRTEMFL[adam.adae.TRTEMFL]:::out
  AESTDT --> TRTEMFL
  TRTSDT --> TRTEMFL

  N_W[adam.ae_incidence.N_SUBJ_WITH_AE]:::in
  N_T[adam.ae_incidence.N_SUBJ_TOTAL]:::in
  IR[adam.ae_incidence.INCIDENCE_RATE]:::out
  N_W --> IR
  N_T --> IR
""", height=520)
