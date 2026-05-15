# Phase 5 summary — Target code generated and validated

**Inputs (read-only)**

- `build/specs/<program>.md` (5 files, Phase 4 output)
- `build/schemas/<lib>_<dataset>.py` (9 schema modules, Phase 4 output)
- `input_data/*.csv` (raw CSV inputs)

**No SAS file was opened during Phase 5** (R1 honoured).

**Outputs**

- `build/target/{common,01_clean_dm,02_clean_ae,03_derive_adsl,04_derive_adae,05_summary_safety}.py`
- `build/target/output/{dm_clean,ae_clean,adsl,adae,ae_summary,ae_incidence}.csv` (validated row-for-row vs ground truth)
- `build/target/output/{...}.parquet` (alongside CSV per the user's choice)
- `build/target/state/trt_start_dt.txt` (cohort-level scalar shared 03→04)

**Phase-5 spec corrections (R1 loop)**

| Discovered via                | Spec change                                                               |
| ----------------------------- | ------------------------------------------------------------------------- |
| `test_adam_dm_clean::test_row_for_row_equality` | `01_clean_dm.md` step 3 — AGE_DERIVED uses `//365`, not `floor(/365.25)`. Also added ambiguity #6. |

**Phase-5 codegen-only corrections** (no spec change needed)

| Symptom                                                | Fix                                                  |
| ------------------------------------------------------ | ---------------------------------------------------- |
| `ae_summary.csv` rendered N_SERIOUS as `'0.0'`         | Cast `SUM(CASE…)::INTEGER` in 05_summary_safety.py   |
| `adae.csv` rendered AESEVN/AEDUR as `'1.0'`/`'8.0'`    | Read upstream CSVs with `dtype=str` in 04_derive_adae.py |

**Tests**

- `pytest build/tests/`: 23 passed, 0 failed (18 row-equality + 5 aggregate).
- Pipeline runner: `python build/dag/run.py` succeeds end-to-end.
