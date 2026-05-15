"""Phase 1 driver: parse every SAS file in sas_codebase/ and emit the AST,
expanded source, CFG, DFG, plus the program-level DAG and macro table.

Outputs land under build/ast/ and build/ast/_aggregate/.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Allow running as `python build/parser/run.py` from project root
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from parser.sas_parser import (
    MacroTable, parse_program, ast_to_dict,
)
from parser.flow_graphs import (
    build_cfg, build_dfg, program_dependencies,
)


SAS_FILES = [
    "sas_codebase/config/setup.sas",
    "sas_codebase/config/formats.sas",
    "sas_codebase/macros/util_macros.sas",
    "sas_codebase/programs/01_clean_dm.sas",
    "sas_codebase/programs/02_clean_ae.sas",
    "sas_codebase/programs/03_derive_adsl.sas",
    "sas_codebase/programs/04_derive_adae.sas",
    "sas_codebase/programs/05_summary_safety.sas",
]


def main() -> None:
    out_dir = PROJECT_ROOT / "build" / "ast"
    out_dir.mkdir(parents=True, exist_ok=True)
    aggregate_dir = out_dir / "_aggregate"
    aggregate_dir.mkdir(parents=True, exist_ok=True)

    macro_table = MacroTable()

    asts = []
    for rel in SAS_FILES:
        path = PROJECT_ROOT / rel
        # Reset call-site list per program so the per-program AST records
        # only its own call sites; we re-aggregate for the global view.
        macro_table.call_sites = []
        ast = parse_program(path, project_root=PROJECT_ROOT,
                            shared_macro_table=macro_table)
        asts.append(ast)

        stem = ast.program
        (out_dir / f"{stem}.json").write_text(
            json.dumps(ast_to_dict(ast), indent=2), encoding="utf-8"
        )
        (out_dir / f"{stem}.expanded.sas").write_text(
            ast.expanded_source, encoding="utf-8"
        )
        cfg = build_cfg(ast)
        (out_dir / f"{stem}.cfg.json").write_text(
            json.dumps(cfg, indent=2), encoding="utf-8"
        )
        dfg = build_dfg(ast)
        (out_dir / f"{stem}.dfg.json").write_text(
            json.dumps(dfg, indent=2), encoding="utf-8"
        )
        print(f"  parsed {rel} -> {len(ast.blocks)} blocks")

    # Aggregate: macro table + program DAG + counts
    macro_export = {
        "symbols": macro_table.symbols,
        "macros": [
            {
                "name": m.name,
                "params": [{"name": n, "default": d} for n, d in m.params],
                "source_file": m.source_file,
                "source_line": m.source_line,
                "reads_globals": m.reads_globals,
                "writes_globals": m.writes_globals,
            }
            for m in macro_table.macros.values()
        ],
    }
    (aggregate_dir / "macro_table.json").write_text(
        json.dumps(macro_export, indent=2), encoding="utf-8"
    )

    dag = program_dependencies(asts)
    (aggregate_dir / "program_dag.json").write_text(
        json.dumps(dag, indent=2), encoding="utf-8"
    )

    # Counts for SOLUTION.md §1.2
    counts = {
        "programs": [],
        "totals": {
            "data_blocks": 0,
            "proc_blocks": 0,
            "macro_defs": len(macro_table.macros),
            "macro_call_sites": 0,
            "by_proc": {},
        },
    }
    seen_call_sites = []
    for a in asts:
        d_blocks = sum(1 for b in a.blocks if b.kind == "data")
        p_blocks = [b for b in a.blocks if b.kind == "proc"]
        counts["programs"].append({
            "program": a.program,
            "source_file": a.source_file,
            "lines_of_source": len((Path(a.source_file)).read_text(encoding="utf-8").splitlines()),
            "data_blocks": d_blocks,
            "proc_blocks": len(p_blocks),
            "procs_by_kind": _counts(b.proc_name for b in p_blocks),
            "input_datasets": sorted({ds for b in a.blocks for ds in b.input_datasets}),
            "output_datasets": sorted({ds for b in a.blocks for ds in b.output_datasets}),
        })
        counts["totals"]["data_blocks"] += d_blocks
        counts["totals"]["proc_blocks"] += len(p_blocks)
        for b in p_blocks:
            counts["totals"]["by_proc"][b.proc_name] = (
                counts["totals"]["by_proc"].get(b.proc_name, 0) + 1
            )
        seen_call_sites.extend(a.macro_call_sites)
    counts["totals"]["macro_call_sites"] = len(seen_call_sites)
    (aggregate_dir / "counts.json").write_text(
        json.dumps(counts, indent=2), encoding="utf-8"
    )
    print(f"\nphase 1 outputs written under {out_dir}")
    print(f"  totals: {counts['totals']}")


def _counts(items) -> dict:
    out: dict = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


if __name__ == "__main__":
    main()
