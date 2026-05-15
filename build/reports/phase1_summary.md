# Phase 1 summary — SAS parsed into AST + CFG + DFG

**Outputs**

- `build/ast/<program>.json` — structural AST (8 programs)
- `build/ast/<program>.cfg.json` — control flow graph
- `build/ast/<program>.dfg.json` — data flow graph
- `build/ast/<program>.expanded.sas` — post-macro-expansion source
- `build/ast/_aggregate/macro_table.json` — 5 macros, with reads/writes-globals
- `build/ast/_aggregate/program_dag.json` — 5 cross-program edges
- `build/ast/_aggregate/counts.json` — totals fed into SOLUTION.md §1.2

**Counts confirmed**

- 8 SAS files, 533 lines, 11 DATA steps, 15 PROC blocks (format ×1, sort ×7,
  sql ×6, summary ×1), 5 macro defs, 9 macro call sites.
- 5 inter-program dataset dependencies, matching `functional_spec.md` §2.
- 1 cross-program global-macro coupling (`&TRT_START_DT`), exposed only by
  the macro-table scan.

**Ambiguities/coverage notes detected during Phase 1**

- The hand-rolled parser does not evaluate `%sysfunc(getoption(SASUSER))` in
  `setup.sas` line 16; the symbol `&PROJ_ROOT` is left as a literal and only
  affects `libname`/`%include` paths, both of which are resolved against
  the project root by the parser driver. Logged in coverage.
- `%mend` statements without a preceding `;` (the canonical SAS form) require
  a pre-processing fix-up; documented in the parser source.
