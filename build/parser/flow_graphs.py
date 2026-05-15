"""Derive Control Flow Graph (CFG) and Data Flow Graph (DFG) from a ProgramAST.

CFG: nodes = blocks (data/proc/macro_def/misc), edges = sequential succession
plus conditional branches (we mark `if ... then delete;` as a branch).

DFG: nodes = datasets and (dataset, column) pairs; edges = `reads`, `writes`,
`derives_from`. Cross-program edges are surfaced via the union of inputs
and outputs declared across all programs (computed at the package level).
"""
from __future__ import annotations

import re
from typing import Iterable

from .sas_parser import ProgramAST, Block

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"


def build_cfg(ast: ProgramAST) -> dict:
    nodes = []
    edges = []
    for i, b in enumerate(ast.blocks):
        node_id = f"b{i}"
        label = (
            f"DATA {b.output_datasets[0]}" if b.kind == "data" and b.output_datasets
            else f"PROC {b.proc_name}" if b.kind == "proc"
            else b.kind
        )
        nodes.append({
            "id": node_id, "kind": b.kind, "label": label,
            "line_start": b.line_start, "line_end": b.line_end,
            "inputs": b.input_datasets, "outputs": b.output_datasets,
        })
        if i > 0:
            edges.append({"from": f"b{i-1}", "to": node_id, "kind": "sequential"})
    # mark blocks that contain `if ... then delete` as having a conditional branch
    for i, b in enumerate(ast.blocks):
        for st in b.statements:
            if st.get("kind") == "if_delete":
                edges.append({"from": f"b{i}", "to": f"b{i}_filter", "kind": "branch_filter"})
                nodes.append({"id": f"b{i}_filter", "kind": "filter",
                                "label": "delete row", "line_start": st.get("line", 0),
                                "line_end": st.get("line", 0),
                                "inputs": [], "outputs": []})
    return {"program": ast.program, "nodes": nodes, "edges": edges}


def _column_writes_in_data_block(b: Block) -> list[str]:
    """Heuristic: every `assign` and `if_assign` LHS is a written column."""
    cols: list[str] = []
    for st in b.statements:
        if st.get("kind") in ("assign", "if_assign", "sum"):
            c = st.get("col")
            if c:
                cols.append(c)
        if st.get("kind") == "rename":
            # Extract `OLD=NEW` pairs from raw rename statement
            for m in re.finditer(rf"({_IDENT})\s*=\s*({_IDENT})", st.get("raw", "")):
                cols.append(m.group(2).lower())
    return list(dict.fromkeys(cols))


def _column_reads_in_data_block(b: Block) -> list[str]:
    """Heuristic: scan RHS of assignments and `if` conditions for identifiers
    that look like column references. We're permissive — false positives are
    fine because column-level lineage is informational, not authoritative."""
    cols: set[str] = set()
    keywords = {
        "if", "then", "else", "and", "or", "not", "missing", "input",
        "substr", "strip", "upcase", "lowcase", "put", "floor", "ceil",
        "round", "max", "min", "sum", "first", "last", "by", "set", "merge",
        "case", "when", "in", "is", "null", "format", "informat", "length",
        "label", "keep", "drop", "retain", "delete", "rename", "yymmdd10",
        "data", "run", "proc", "do", "end",
    }
    for st in b.statements:
        text = ""
        if st.get("kind") == "assign":
            text = st.get("expr", "")
        elif st.get("kind") == "if_assign":
            text = (st.get("expr", "") + " " + (st.get("else_expr") or "")
                    + " " + st.get("raw", ""))
        elif st.get("kind") == "raw":
            text = st.get("raw", "")
        for m in re.finditer(rf"\b({_IDENT})\b", text):
            tok = m.group(1).lower()
            if tok in keywords:
                continue
            if tok.isdigit():
                continue
            cols.add(tok)
    return sorted(cols)


def build_dfg(ast: ProgramAST) -> dict:
    """Per-program DFG. Cross-program lineage is built later at package level."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_dataset(name: str) -> None:
        if name not in nodes:
            nodes[name] = {"id": name, "kind": "Dataset"}

    def add_column(dataset: str, col: str) -> None:
        nid = f"{dataset}.{col}"
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": "Column", "dataset": dataset, "name": col}

    for b in ast.blocks:
        for ds in b.input_datasets:
            add_dataset(ds)
        for ds in b.output_datasets:
            add_dataset(ds)

        if b.kind == "data" and b.output_datasets:
            out_ds = b.output_datasets[0]
            writes = _column_writes_in_data_block(b)
            reads = _column_reads_in_data_block(b)

            # writes: out_ds.col <- assign expr
            for c in writes:
                add_column(out_ds, c)
                edges.append({
                    "from": f"PROGRAM:{ast.program}",
                    "to": f"{out_ds}.{c}",
                    "kind": "writes",
                })
            # set/merge propagates input columns to output columns (we infer
            # this transitively in the package-level pass)
            for in_ds in b.input_datasets:
                edges.append({
                    "from": f"PROGRAM:{ast.program}",
                    "to": in_ds,
                    "kind": "reads_dataset",
                })
                edges.append({
                    "from": in_ds, "to": out_ds, "kind": "produces",
                })
            for c in reads:
                # skip identifiers that don't look like columns (libref patterns etc)
                if "." in c:
                    continue

        if b.kind == "proc":
            for in_ds in b.input_datasets:
                edges.append({
                    "from": f"PROGRAM:{ast.program}",
                    "to": in_ds, "kind": "reads_dataset",
                })
            for out_ds in b.output_datasets:
                edges.append({
                    "from": f"PROGRAM:{ast.program}",
                    "to": out_ds, "kind": "writes_dataset",
                })
                for in_ds in b.input_datasets:
                    edges.append({"from": in_ds, "to": out_ds, "kind": "produces"})

    return {"program": ast.program, "nodes": list(nodes.values()), "edges": edges}


def program_dependencies(asts: Iterable[ProgramAST]) -> dict:
    """Cross-program DAG: program A depends_on program B if A reads a dataset
    that B writes. Library-qualified datasets only (e.g. `adam.dm_clean`).
    Excludes `work.*` (transient)."""
    asts = list(asts)
    writers: dict[str, str] = {}      # dataset -> producing program
    reads: dict[str, set[str]] = {}    # program -> {dataset}

    for a in asts:
        reads.setdefault(a.program, set())
        for b in a.blocks:
            for ds in b.output_datasets:
                if ds.startswith("work.") or ds.startswith("_"):
                    continue
                if "." not in ds:
                    continue
                # later writes win; in this codebase every dataset is written by exactly one program
                writers[ds] = a.program
        for b in a.blocks:
            for ds in b.input_datasets:
                if ds.startswith("work.") or ds.startswith("_"):
                    continue
                if "." not in ds:
                    continue
                reads[a.program].add(ds)

    edges: list[dict] = []
    for prog, ds_set in reads.items():
        for ds in ds_set:
            producer = writers.get(ds)
            if producer and producer != prog:
                edges.append({
                    "from": prog, "to": producer,
                    "kind": "depends_on", "via_dataset": ds,
                })
    edges.sort(key=lambda e: (e["from"], e["to"], e["via_dataset"]))
    return {
        "programs": [a.program for a in asts],
        "writers": writers,
        "edges": edges,
    }
