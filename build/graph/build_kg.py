"""Phase 3 — build the knowledge graph.

Inputs:
  build/ast/<program>.json
  build/ast/<program>.dfg.json
  build/ast/_aggregate/macro_table.json
  build/ast/_aggregate/program_dag.json
  build/graph/doc_entities.json
  input_data/*.csv          (for raw column inference)
  ground_truth/*.csv        (for adam column inference + nullability)

Output:
  build/graph/kg.json       (NetworkX node-link format)
  build/graph/kg_stats.json (counts and most-connected nodes)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _scan_csv_columns(path: Path) -> tuple[list[str], dict[str, dict]]:
    """Return (column_order, {col: {nullable: bool, dtype: str}}) for a CSV."""
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        info: dict[str, dict] = {c: {"nullable": False, "samples": [],
                                        "all_int": True, "all_float": True,
                                        "all_iso_date": True, "any": False}
                                 for c in cols}
        for row in reader:
            for c in cols:
                v = (row.get(c) or "").strip()
                if v == "":
                    info[c]["nullable"] = True
                    continue
                info[c]["any"] = True
                if len(info[c]["samples"]) < 3:
                    info[c]["samples"].append(v)
                # int test
                try:
                    int(v)
                except ValueError:
                    info[c]["all_int"] = False
                # float test
                try:
                    float(v)
                except ValueError:
                    info[c]["all_float"] = False
                # iso date test
                if not (len(v) == 10 and v[4] == "-" and v[7] == "-"
                        and v[:4].isdigit() and v[5:7].isdigit()
                        and v[8:10].isdigit()):
                    info[c]["all_iso_date"] = False

    out: dict[str, dict] = {}
    for c, i in info.items():
        # leading-zero detection: if any sample is an int that would lose
        # information when re-rendered (e.g. "02" -> 2), force string.
        leading_zero = any(
            len(s) > 1 and s.startswith("0") and s[0:].isdigit()
            for s in i["samples"]
        )
        if not i["any"]:
            dtype = "string"
        elif leading_zero:
            dtype = "string"
        elif i["all_int"]:
            dtype = "int"
        elif i["all_float"]:
            dtype = "float"
        elif i["all_iso_date"]:
            dtype = "date"
        else:
            dtype = "string"
        out[c] = {"dtype": dtype, "nullable": i["nullable"],
                   "samples": i["samples"]}
    return cols, out


# --------------------------------------------------------------------------
# Graph construction
# --------------------------------------------------------------------------

def build_graph() -> tuple[nx.MultiDiGraph, dict]:
    g = nx.MultiDiGraph()
    ast_dir = PROJECT_ROOT / "build" / "ast"
    aggregate = ast_dir / "_aggregate"

    program_files = [
        "01_clean_dm", "02_clean_ae", "03_derive_adsl",
        "04_derive_adae", "05_summary_safety",
    ]
    macro_table = _load(aggregate / "macro_table.json")
    program_dag = _load(aggregate / "program_dag.json")
    docs = _load(PROJECT_ROOT / "build" / "graph" / "doc_entities.json")

    # ---- Dataset + Column nodes from CSVs ---------------------------------
    raw_csv = PROJECT_ROOT / "input_data"
    truth_csv = PROJECT_ROOT / "ground_truth"
    dataset_columns: dict[str, list[str]] = {}

    raw_map = {
        "raw.dm": raw_csv / "dm.csv",
        "raw.ae": raw_csv / "ae.csv",
        "raw.site_lookup": raw_csv / "site_lookup.csv",
    }
    adam_map = {
        "adam.dm_clean": truth_csv / "dm_clean.csv",
        "adam.ae_clean": truth_csv / "ae_clean.csv",
        "adam.adsl": truth_csv / "adsl.csv",
        "adam.adae": truth_csv / "adae.csv",
        "adam.ae_summary": truth_csv / "ae_summary.csv",
        "adam.ae_incidence": truth_csv / "ae_incidence.csv",
    }

    for ds_name, path in {**raw_map, **adam_map}.items():
        producer = program_dag["writers"].get(ds_name) or "(input)"
        cols, info = _scan_csv_columns(path)
        dataset_columns[ds_name] = cols
        g.add_node(ds_name, kind="Dataset",
                    library=ds_name.split(".", 1)[0],
                    name=ds_name.split(".", 1)[1],
                    producer=producer,
                    source_csv=str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"))
        for c in cols:
            cid = f"{ds_name}.{c.lower()}"
            g.add_node(cid, kind="Column", dataset=ds_name, name=c,
                        dtype=info[c]["dtype"], nullable=info[c]["nullable"],
                        samples=info[c]["samples"])

    # ---- Proc / DataStep nodes per program -------------------------------
    program_input_outputs: dict[str, dict] = {}
    for stem in program_files:
        ast = _load(ast_dir / f"{stem}.json")
        in_set: set[str] = set()
        out_set: set[str] = set()
        # First pass: find this program's long-lived (adam.*) outputs
        long_lived_outputs = sorted({
            ds for b in ast["blocks"]
            for ds in b["output_datasets"]
            if not ds.startswith("work.") and "." in ds
        })
        for i, b in enumerate(ast["blocks"]):
            if b["kind"] not in ("data", "proc"):
                continue
            block_id = f"{stem}::b{i}"
            label = (
                f"DATA {b['output_datasets'][0]}" if b["kind"] == "data" and b["output_datasets"]
                else f"PROC {b['proc_name']}"
            )
            g.add_node(block_id, kind="Proc",
                        program=stem, proc_kind=b["kind"],
                        proc_name=b["proc_name"], label=label,
                        line_start=b["line_start"], line_end=b["line_end"])
            for ds in b["input_datasets"]:
                if g.has_node(ds):
                    g.add_edge(block_id, ds, key=f"reads:{block_id}->{ds}",
                                kind="reads")
                    if not ds.startswith("work."):
                        in_set.add(ds)
            for ds in b["output_datasets"]:
                if g.has_node(ds):
                    g.add_edge(block_id, ds, key=f"writes:{block_id}->{ds}",
                                kind="writes")
                    if not ds.startswith("work."):
                        out_set.add(ds)
            # column-level writes for DATA steps. If the immediate output is
            # a work.* transient, propagate the write to the program's
            # long-lived output(s) — every transient eventually flows in.
            if b["kind"] == "data" and b["output_datasets"]:
                out_ds = b["output_datasets"][0]
                target_datasets = [out_ds] if not out_ds.startswith("work.") else long_lived_outputs
                for st in b["statements"]:
                    if st.get("kind") in ("assign", "if_assign", "sum"):
                        col = st.get("col")
                        if not col:
                            continue
                        for td in target_datasets:
                            cid = f"{td}.{col.lower()}"
                            if g.has_node(cid):
                                g.add_edge(block_id, cid,
                                            key=f"writes_col:{block_id}->{cid}:{st.get('line', 0)}",
                                            kind="writes",
                                            line=st.get("line"))
            # column-level writes for PROC SQL `create table X as select ... as col`
            if b["kind"] == "proc" and b["proc_name"] == "sql":
                import re as _re
                for st in b["statements"]:
                    if st.get("kind") != "sql_create_table":
                        continue
                    target = st.get("target")
                    if not target or not g.has_node(target):
                        continue
                    raw = st.get("raw", "")
                    target_datasets = ([target] if not target.startswith("work.")
                                        else long_lived_outputs)
                    for m in _re.finditer(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)",
                                            raw, _re.IGNORECASE):
                        col = m.group(1).lower()
                        for td in target_datasets:
                            cid = f"{td}.{col}"
                            if g.has_node(cid):
                                g.add_edge(block_id, cid,
                                            key=f"writes_col:{block_id}->{cid}:sql",
                                            kind="writes",
                                            line=st.get("line", 0))
        program_input_outputs[stem] = {"inputs": sorted(in_set), "outputs": sorted(out_set)}

    # ---- Macro nodes -----------------------------------------------------
    for m in macro_table["macros"]:
        mid = f"macro::{m['name']}"
        g.add_node(mid, kind="Macro", name=m["name"],
                    params=[p["name"] for p in m["params"]],
                    reads_globals=m["reads_globals"],
                    writes_globals=m["writes_globals"],
                    source_file=m["source_file"], source_line=m["source_line"])

    # macro call edges from per-program ASTs
    for stem in program_files:
        ast = _load(ast_dir / f"{stem}.json")
        for cs in ast.get("macro_call_sites", []):
            mid = f"macro::{cs['macro']}"
            if g.has_node(mid):
                g.add_edge(f"PROGRAM:{stem}", mid,
                            key=f"calls:{stem}->{cs['macro']}:{cs['line']}",
                            kind="calls", line=cs["line"])
        # ensure the program node itself exists
        g.add_node(f"PROGRAM:{stem}", kind="Program", name=stem)

    # ---- depends_on edges (program-level DAG) ----------------------------
    for e in program_dag["edges"]:
        g.add_edge(f"PROGRAM:{e['from']}", f"PROGRAM:{e['to']}",
                    key=f"depends_on:{e['from']}->{e['to']}:{e['via_dataset']}",
                    kind="depends_on", via_dataset=e["via_dataset"])

    # ---- BusinessRule + OpenIssue nodes ----------------------------------
    for i, br in enumerate(docs["business_rules"]):
        nid = f"rule::{i}"
        g.add_node(nid, kind="BusinessRule", text=br["text"],
                    source_file=br["source_file"],
                    source_section=br["source_section"],
                    source_line=br["source_line"])
        # `implements` edges: link rule to datasets it mentions
        for ds_short in br["datasets"]:
            ds_short_l = ds_short.lower()
            # find best dataset match
            for full in dataset_columns:
                if full.endswith(ds_short_l) or full == ds_short_l:
                    g.add_edge(nid, full,
                                key=f"applies_to:{nid}->{full}",
                                kind="applies_to")

    for o in docs["open_issues"]:
        nid = f"issue::{o['id']}"
        g.add_node(nid, kind="OpenIssue", id=o["id"], tickers=o["tickers"],
                    text=o["text"], source_file=o["source_file"],
                    source_section=o["source_section"],
                    source_line=o["source_line"])
        for ds_short in o["datasets"]:
            ds_short_l = ds_short.lower()
            for full in dataset_columns:
                if full.endswith(ds_short_l) or full == ds_short_l:
                    g.add_edge(full, nid, key=f"flagged_by:{full}->{nid}",
                                kind="flagged_by")
        for col in o["columns"]:
            for ds in dataset_columns:
                cid = f"{ds}.{col.lower()}"
                if g.has_node(cid):
                    g.add_edge(cid, nid, key=f"flagged_by:{cid}->{nid}",
                                kind="flagged_by")

    # ---- Constraint nodes (synthesized from filters/keys) ----------------
    constraints = [
        ("USUBJID is unique in DM_CLEAN/ADSL",
         ["adam.dm_clean.usubjid", "adam.adsl.usubjid"], "primary_key"),
        ("AESTDT must not be missing in AE_CLEAN",
         ["adam.ae_clean.aestdt"], "not_null"),
        ("AETERM must not be missing in AE_CLEAN",
         ["adam.ae_clean.aeterm"], "not_null"),
        ("SAFFL is 'Y' or 'N'",
         ["adam.adsl.saffl", "adam.adae.saffl"], "domain"),
        ("ITTFL is 'Y' or 'N'",
         ["adam.adsl.ittfl", "adam.adae.ittfl"], "domain"),
        ("TRTEMFL is 'Y' or 'N'",
         ["adam.adae.trtemfl"], "domain"),
        ("ONTRTFL is 'Y' or 'N'",
         ["adam.adae.ontrtfl"], "domain"),
        ("AESEV_STD ∈ {MILD, MODERATE, SEVERE, blank}",
         ["adam.ae_clean.aesev_std", "adam.adae.aesev_std"], "domain"),
        ("AESEVN ∈ {1, 2, 3, missing}",
         ["adam.ae_clean.aesevn", "adam.adae.aesevn"], "domain"),
    ]
    for i, (text, cols, kind) in enumerate(constraints):
        cid = f"constraint::{i}"
        g.add_node(cid, kind="Constraint", text=text, constraint_kind=kind)
        for c in cols:
            if g.has_node(c):
                g.add_edge(cid, c, key=f"validates:{cid}->{c}",
                            kind="validates")

    # ---- produces / lineage edges between datasets ------------------------
    for stem, io in program_input_outputs.items():
        for in_ds in io["inputs"]:
            for out_ds in io["outputs"]:
                if not in_ds.startswith("work.") and not out_ds.startswith("work."):
                    g.add_edge(in_ds, out_ds,
                                key=f"contributes_to:{in_ds}->{out_ds}:{stem}",
                                kind="contributes_to", via_program=stem)

    # ---- Stats ----------------------------------------------------------
    counts: dict[str, int] = {}
    for _, attr in g.nodes(data=True):
        k = attr.get("kind", "?")
        counts[k] = counts.get(k, 0) + 1
    edge_counts: dict[str, int] = {}
    for _, _, _, attr in g.edges(keys=True, data=True):
        k = attr.get("kind", "?")
        edge_counts[k] = edge_counts.get(k, 0) + 1
    # most-connected nodes
    deg = sorted(g.degree(), key=lambda x: x[1], reverse=True)[:10]
    stats = {
        "node_counts_by_kind": counts,
        "edge_counts_by_kind": edge_counts,
        "total_nodes": g.number_of_nodes(),
        "total_edges": g.number_of_edges(),
        "most_connected": [
            {"id": n, "degree": d, "kind": g.nodes[n].get("kind")}
            for n, d in deg
        ],
    }
    return g, stats


def main() -> None:
    g, stats = build_graph()
    out_dir = PROJECT_ROOT / "build" / "graph"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(g, edges="edges")
    (out_dir / "kg.json").write_text(json.dumps(data, indent=2, default=str),
                                       encoding="utf-8")
    (out_dir / "kg_stats.json").write_text(json.dumps(stats, indent=2),
                                            encoding="utf-8")
    print(f"phase 3 graph written: {stats['total_nodes']} nodes, "
          f"{stats['total_edges']} edges")
    print(f"  by kind: {stats['node_counts_by_kind']}")
    print(f"  edges  : {stats['edge_counts_by_kind']}")


if __name__ == "__main__":
    main()
