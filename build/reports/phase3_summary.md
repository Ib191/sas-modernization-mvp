# Phase 3 summary — Knowledge graph built

**Outputs**

- `build/graph/kg.json`        — node-link serialisation, 173 nodes, 93 edges
- `build/graph/kg_stats.json`  — counts + most-connected nodes
- `build/graph/query.py`       — CLI: `list_datasets`, `lineage_for_column`,
                                  `dependencies_of_program`, `issues_for_dataset`,
                                  `macros_with_globals`

**Verification**

- All 5 critical columns from CLAUDE.md §1.3.3 (TRTEMFL, MAX_AESEV, ITTFL,
  TRTDURD, INCIDENCE_RATE) return non-trivial lineage from
  `query.py lineage_for_column …`.
- `query.py macros_with_globals` correctly surfaces only
  `is_treatment_emergent` with `reads=['TRT_START_DT']`.
- `query.py dependencies_of_program 04_derive_adae` shows both upstream
  programs (02, 03), the downstream program (05), and the macro call.

**SOLUTION.md sections updated**

- §1.3.2 — Dataset-level lineage (Mermaid)
- §1.3.3 — Column-level lineage for the 5 critical columns (table + Mermaid)
- §1.4 — KG schema + counts + top-10 most connected
