# Phase 4 summary — Specs, schemas, DAG, and tests regenerated

**Inputs (read-only)**

- `build/graph/kg.json` (Phase 3)
- `build/graph/doc_entities.json` (Phase 2)
- `build/ast/<program>.json` and `_aggregate/program_dag.json` (Phase 1, treated
  as derived artifacts — not SAS source per R3)

**Outputs**

- `build/specs/{01_clean_dm,02_clean_ae,03_derive_adsl,04_derive_adae,05_summary_safety}.md`
- `build/schemas/{raw_dm,raw_ae,raw_site_lookup,adam_dm_clean,adam_ae_clean,adam_adsl,adam_adae,adam_ae_summary,adam_ae_incidence}.py`
- `build/dag/pipeline.json`
- `build/tests/test_{raw_dm,...,adam_ae_incidence}.py` + `conftest.py`

**Bug found and fixed during Phase 4**

CSV column-type inference was returning `int` for `SITEID` (which is stored
in input data as `'02'`, `'01'`). Reading that as `Int64` would drop the
leading zero and break the join in 03_derive_adsl. Fixed by adding a
leading-zero detector in `build/graph/build_kg.py::_scan_csv_columns` that
forces such columns to `string`. KG and Phase 4 outputs regenerated.

**Hard-rule note (R1).** From this point on, Phase 5 codegen reads only
`build/specs/` and `build/schemas/`. No SAS file is opened.
