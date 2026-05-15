"""Query CLI for the knowledge graph.

Usage:
  python build/graph/query.py list_datasets
  python build/graph/query.py lineage_for_column <column>
  python build/graph/query.py dependencies_of_program <program>
  python build/graph/query.py issues_for_dataset <dataset>
  python build/graph/query.py macros_with_globals
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parent


def _load_graph() -> nx.MultiDiGraph:
    data = json.loads((HERE / "kg.json").read_text(encoding="utf-8"))
    return nx.node_link_graph(data, edges="edges", directed=True, multigraph=True)


# ---------------------------------------------------------------------------

def list_datasets(g: nx.MultiDiGraph) -> None:
    rows = []
    for n, attr in g.nodes(data=True):
        if attr.get("kind") == "Dataset":
            ncols = sum(
                1 for m, a in g.nodes(data=True)
                if a.get("kind") == "Column" and a.get("dataset") == n
            )
            rows.append((n, attr.get("producer"), ncols))
    rows.sort()
    print(f"{'dataset':<22}  {'producer':<20}  {'cols':>4}")
    print("-" * 52)
    for ds, prod, n in rows:
        print(f"{ds:<22}  {(prod or '-'): <20}  {n:>4}")


def lineage_for_column(g: nx.MultiDiGraph, target_col: str) -> None:
    """Find all column nodes whose name matches `target_col`, then walk
    upstream through Proc → Dataset → Proc edges."""
    target_l = target_col.lower()
    matches = [
        n for n, a in g.nodes(data=True)
        if a.get("kind") == "Column" and a.get("name", "").lower() == target_l
    ]
    if not matches:
        print(f"no column named {target_col!r} found")
        return
    for cid in matches:
        attr = g.nodes[cid]
        ds = attr["dataset"]
        print(f"\n=== column {cid} ===")
        print(f"  dataset : {ds}  dtype: {attr.get('dtype')}  nullable: {attr.get('nullable')}")
        # find Procs that write this column
        writers = [u for u, _, k, a in g.in_edges(cid, keys=True, data=True)
                    if a.get("kind") == "writes"]
        if writers:
            print(f"  written by:")
            for w in writers:
                wattr = g.nodes[w]
                if wattr.get("kind") == "Proc":
                    prog = wattr.get("program")
                    label = wattr.get("label")
                    line_start = wattr.get("line_start")
                    print(f"    - {label}  in {prog}.sas:{line_start}")
        # find Datasets that contribute to ds
        upstream_ds: list[str] = []
        for u, _, _, a in g.in_edges(ds, keys=True, data=True):
            if a.get("kind") == "contributes_to":
                upstream_ds.append(u)
        if upstream_ds:
            print(f"  upstream datasets: {sorted(set(upstream_ds))}")
        # find OpenIssues
        flags = [v for _, v, _, a in g.out_edges(cid, keys=True, data=True)
                  if a.get("kind") == "flagged_by"]
        flags += [v for _, v, _, a in g.out_edges(ds, keys=True, data=True)
                   if a.get("kind") == "flagged_by"]
        if flags:
            print(f"  flagged_by issues:")
            for f in sorted(set(flags)):
                fattr = g.nodes[f]
                print(f"    - {fattr.get('id')}: {fattr.get('text', '')[:80]}")


def dependencies_of_program(g: nx.MultiDiGraph, program: str) -> None:
    pid = f"PROGRAM:{program}"
    if not g.has_node(pid):
        print(f"no program {program!r}")
        return
    print(f"=== {program} ===")
    upstream = [
        v for _, v, _, a in g.out_edges(pid, keys=True, data=True)
        if a.get("kind") == "depends_on"
    ]
    if upstream:
        print("  depends_on:")
        for u in upstream:
            for _, v, k, a in g.out_edges(pid, keys=True, data=True):
                if v == u and a.get("kind") == "depends_on":
                    print(f"    - {u.replace('PROGRAM:', '')} via {a.get('via_dataset')}")
    else:
        print("  depends_on: (none)")
    downstream = [
        u for u, _, _, a in g.in_edges(pid, keys=True, data=True)
        if a.get("kind") == "depends_on"
    ]
    if downstream:
        print("  depended on by:")
        for d in sorted(set(downstream)):
            print(f"    - {d.replace('PROGRAM:', '')}")
    # macros called
    macros = [
        v for _, v, _, a in g.out_edges(pid, keys=True, data=True)
        if a.get("kind") == "calls"
    ]
    if macros:
        print(f"  calls macros: {sorted({m.replace('macro::', '') for m in macros})}")


def issues_for_dataset(g: nx.MultiDiGraph, dataset: str) -> None:
    ds = dataset.lower()
    if not g.has_node(ds):
        # try short form
        for n, a in g.nodes(data=True):
            if a.get("kind") == "Dataset" and a.get("name") == ds:
                ds = n
                break
    if not g.has_node(ds):
        print(f"no dataset {dataset!r}")
        return
    print(f"=== issues for {ds} ===")
    issues = [
        v for _, v, _, a in g.out_edges(ds, keys=True, data=True)
        if a.get("kind") == "flagged_by"
    ]
    for col in [n for n, a in g.nodes(data=True)
                 if a.get("kind") == "Column" and a.get("dataset") == ds]:
        for _, v, _, a in g.out_edges(col, keys=True, data=True):
            if a.get("kind") == "flagged_by":
                issues.append(v)
    for iid in sorted(set(issues)):
        a = g.nodes[iid]
        print(f"  - [{a.get('id')}] §{a.get('source_section')}")
        print(f"      {a.get('text', '')[:150]}")


def macros_with_globals(g: nx.MultiDiGraph) -> None:
    print("macros that read or write global symbols:")
    for n, a in g.nodes(data=True):
        if a.get("kind") != "Macro":
            continue
        rg = a.get("reads_globals") or []
        wg = a.get("writes_globals") or []
        if rg or wg:
            print(f"  {a['name']}({', '.join(a.get('params') or [])})  "
                  f"reads={rg or '-'}  writes={wg or '-'}")


COMMANDS = {
    "list_datasets": list_datasets,
    "lineage_for_column": lineage_for_column,
    "dependencies_of_program": dependencies_of_program,
    "issues_for_dataset": issues_for_dataset,
    "macros_with_globals": macros_with_globals,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    g = _load_graph()
    cmd = sys.argv[1]
    args = sys.argv[2:]
    fn = COMMANDS[cmd]
    if cmd in ("list_datasets", "macros_with_globals"):
        fn(g)
    elif cmd in ("lineage_for_column", "dependencies_of_program",
                 "issues_for_dataset"):
        if not args:
            print(f"usage: {cmd} <name>")
            sys.exit(2)
        fn(g, args[0])


if __name__ == "__main__":
    main()
