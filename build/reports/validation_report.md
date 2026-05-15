# Validation report — CTX-2024-001 modernization MVP

**Date.** 2026-05-08
**Pipeline.** `python build/dag/run.py` (5 programs, topological order)
**Test suite.** `python -m pytest build/tests/` — **23 passed, 0 failed** in 0.64s.

## 1. Per-dataset row-for-row equality

The pytest stubs at `build/tests/test_adam_*.py` apply, for each output dataset:

1. **Schema match** — column order in the generated CSV equals
   `ground_truth/<dataset>.csv`.
2. **Row count match** — same number of rows.
3. **Row-for-row equality** — after stable sort by the dataset's natural
   key (defined per spec §Acceptance criteria), every cell equals the
   ground-truth cell. Float `INCIDENCE_RATE` is normalized via
   `round(x, 4)` before comparison; nulls compare equal.

| Dataset             | Rows | Cols | Schema | Row count | Row-for-row equality |
| ------------------- | ---: | ---: | :----: | :-------: | :------------------: |
| `adam.dm_clean`     |   20 |   13 |   ✓    |     ✓     |          ✓           |
| `adam.ae_clean`     |   58 |   12 |   ✓    |     ✓     |          ✓           |
| `adam.adsl`         |   20 |   18 |   ✓    |     ✓     |          ✓           |
| `adam.adae`         |   58 |   24 |   ✓    |     ✓     |          ✓           |
| `adam.ae_summary`   |    9 |    5 |   ✓    |     ✓     |          ✓           |
| `adam.ae_incidence` |    7 |    7 |   ✓    |     ✓     |          ✓           |

## 2. Aggregate equivalence checks

`build/tests/test_aggregates.py`:

| Check                                                                         | Result |
| ----------------------------------------------------------------------------- | :----: |
| `sum(AE_SUMMARY.N_EVENTS) == count(ADAE where TRTEMFL='Y')`                  |   ✓    |
| `sum(AE_SUMMARY.N_SERIOUS) == count(ADAE where TRTEMFL='Y' and AESER='Y')`   |   ✓    |
| `AE_INCIDENCE.N_SUBJ_TOTAL[arm] == count(distinct USUBJID in ADSL where SAFFL='Y' and ARM=arm)` | ✓ |
| `N_SUBJ_WITH_AE ≤ N_SUBJ_TOTAL` per row of AE_INCIDENCE                       |   ✓    |
| `set(USUBJID in ADAE) ⊆ set(USUBJID in ADSL)`                                |   ✓    |

## 3. Ambiguity register summary

| # | Severity | Status              | Outcome at validation                                       |
| - | -------- | ------------------- | ----------------------------------------------------------- |
| 1 | High     | Resolved 2026-05-07 | TRTEMFL = (AESTDT ≥ cohort `max(RFSTDT)` over SAFFL='Y') — matches ground truth row-for-row |
| 2 | Medium   | Logged              | `GRADE 1`/`GRADE 2` AESEV → blank AESEV_STD — produces the 2 blank-severity rows in `ae_summary.csv` exactly |
| 3 | Medium   | Logged              | SITE_LOOKUP.SITE_ID coerced to `f"{int:02d}"` — preserves `SITEID='02'` in ADSL rows |
| 4 | Low      | Logged              | DM dedup by max RECORDCREATEDT — synthetic data has no actual duplicates but rule preserved |
| 5 | Low      | Logged              | `&PROJ_ROOT = %sysfunc(getoption(SASUSER))` — purely cosmetic |
| 6 | Medium   | Logged 2026-05-08   | AGE_DERIVED uses `//365` not `floor(/365.25)` — discovered via Phase 5 test failure, fixed in spec |

No ambiguities remain unresolved.

## 4. Phase-5 fixes during validation

Two issues surfaced during `pytest build/tests/`. Both followed the
"fix the spec, regenerate, re-test" loop mandated by R1.

| # | Symptom                                                       | Root cause                                                                              | Fix                                                                       |
| - | ------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 1 | `dm_clean` AGE_DERIVED off-by-one for CTX-008, CTX-020         | Spec said `floor((RFSTDT - BRTHDT).days / 365.25)`; ground truth uses `//365`           | Updated spec `01_clean_dm.md` step 3 + ambiguity #6; rewrote codegen      |
| 2 | `ae_summary` N_SERIOUS rendering as `'0.0'`/`'1.0'` in CSV     | duckdb's `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` returns DECIMAL → pandas float64 → CSV  | Cast SUM and COUNT to `::INTEGER` in the SQL                              |
| 3 | `adae` AESEVN/AEDUR rendering as `'1.0'`/`'8.0'` in CSV        | Pandas reading ae_clean.csv with default dtypes promoted nullable Int64 to float64      | Read upstream CSVs with `dtype=str` in 04_derive_adae; render ASTDY as string |

After these fixes the pipeline produces all 6 outputs correctly on a single
end-to-end run (`python build/dag/run.py`).

## 5. End-to-end success criteria (from plan §Verification plan)

| Criterion                                                                       | Status |
| ------------------------------------------------------------------------------- | ------ |
| `build/SOLUTION.md` contains all nine §1.x sections including 3 Mermaid graphs   | ✓      |
| Row count, schema, and full row-equality green for every output dataset          | ✓ (6/6) |
| Aggregate reconciliation: AE_SUMMARY ↔ ADAE, AE_INCIDENCE ↔ ADSL                 | ✓      |
| `build/graph/query.py lineage_for_column …` answers for ≥5 critical columns      | ✓ (TRTEMFL, MAX_AESEV, ITTFL, TRTDURD, INCIDENCE_RATE) |
| `build/reports/ambiguity_log.md` has TRT_START_DT High-severity entry            | ✓      |
| User can read SOLUTION.md end-to-end without opening SAS or generated code       | _to be self-assessed_ |
