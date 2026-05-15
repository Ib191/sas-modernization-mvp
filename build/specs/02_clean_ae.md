# Functional spec — `02_clean_ae`

## Purpose

Clean raw adverse events. Convert dates, standardize `AESEV` to `MILD`/`MODERATE`/`SEVERE` (leaving unrecognized values blank), drop records lacking `AESTDT` or `AETERM`, assign within-subject `AESEQ`, compute per-subject worst severity (`MAX_AESEV`/`MAX_AESEVN`). Output: `adam.ae_clean`.

**Run order.** Depends on: raw.ae.
Produces: adam.ae_clean.

## Inputs

### `raw.ae`

Producer: `(input)`. Source CSV: `input_data/ae.csv`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `USUBJID` | string | False | CTX-001 | CTX-001 |
| `AETERM` | string | False | FATIGUE | NAUSEA |
| `AESEV` | string | False | 3 | SEVERE |
| `AESER` | string | False | N | N |
| `AESTDTC` | date | True | 2024-03-03 | 2024-02-18 |
| `AEENDTC` | date | True | 2024-02-22 | 2024-04-25 |

## Outputs

### `adam.ae_clean`

Producer: `02_clean_ae`. Schema file: `build/schemas/adam_ae_clean.py`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `USUBJID` | string | False | CTX-001 | CTX-001 |
| `AESEQ` | int | False | 1 | 2 |
| `AETERM` | string | False | NAUSEA | FATIGUE |
| `AESTDT` | date | False | 2024-02-18 | 2024-03-03 |
| `AEENDT` | date | True | 2024-02-22 | 2024-04-25 |
| `AEDUR` | int | True | 5 | 10 |
| `AESEV` | string | False | SEVERE | 3 |
| `AESEV_STD` | string | True | SEVERE | SEVERE |
| `AESEVN` | int | True | 3 | 3 |
| `AESER` | string | False | N | N |
| `MAX_AESEV` | string | False | SEVERE | SEVERE |
| `MAX_AESEVN` | int | False | 3 | 3 |

## Transformations

Derived from the program AST (Phase 1) and the data flow graph. Each step describes the operation in plain English; the SAS construct that produced it is annotated for traceability but must not be re-read during Phase 5 codegen.

1. Read `raw.ae` (CSV).
2. Convert `AESTDTC`, `AEENDTC` from ISO 8601 strings to date values. Missing/invalid → null.
3. Standardize `AESEV` to `AESEV_STD` per the mapping:
   - `MILD`, `1` → `MILD`
   - `MODERATE`, `MOD`, `2` → `MODERATE`
   - `SEVERE`, `SEV`, `3` → `SEVERE`
   - **anything else (incl. `GRADE 1`, `GRADE 2`) → blank ("") — per spec §6.2 / SP-184; do NOT remap GRADE codes.**
4. Compute `AESEVN` from `AESEV_STD` (`MILD`=1, `MODERATE`=2, `SEVERE`=3, blank/other → null).
5. Drop rows where `AESTDT` is null OR `AETERM` is null/blank.
6. Compute `AEDUR = (AEENDT - AESTDT).days + 1` when both present.
7. Sort by `(USUBJID, AESTDT, AETERM)` and assign `AESEQ` starting at 1 within each `USUBJID`.
8. For each `USUBJID`, compute the maximum `AESEVN` (treating null as < 1). The corresponding `AESEV_STD` becomes `MAX_AESEV`; the value becomes `MAX_AESEVN`. Tie-break: take the last row after sorting by `(USUBJID, AESEVN)` with nulls first.
9. Output column order: `USUBJID, AESEQ, AETERM, AESTDT, AEENDT, AEDUR, AESEV, AESEV_STD, AESEVN, AESER, MAX_AESEV, MAX_AESEVN`.

## Business rules (excerpt)

Drawn from `sas_codebase/docs/functional_spec.md` and `data_dictionary.md` (parsed in Phase 2). Listed for reference; the Transformations section above is the authoritative spec.

- §4.2 AE cleaning (`AE_CLEAN`): Convert dates as above.
- §4.2 AE cleaning (`AE_CLEAN`): Standardize severity to `MILD` / `MODERATE` / `SEVERE`. Accepted raw
- §4.2 AE cleaning (`AE_CLEAN`): Drop records where `AESTDTC` or `AETERM` is missing.
- §4.2 AE cleaning (`AE_CLEAN`): Assign `AESEQ` within subject, ordered by start date then term.
- §4.2 AE cleaning (`AE_CLEAN`): Derive `MAX_AESEV` per subject (worst severity observed).
- §4.4 ADAE derivations: Inner join `AE_CLEAN` to `ADSL` on `USUBJID`.
- §4.4 ADAE derivations: **Treatment-emergent flag (TRTEMFL)**: `'Y'` if AE start date is on
- §4.4 ADAE derivations: **On-treatment flag (ONTRTFL)**: AE start date within
- §4.4 ADAE derivations: Compute `ASTDY = AESTDT - RFSTDT + 1`.

## Ambiguities and resolutions

From `build/reports/ambiguity_log.md`. Items relevant to this program:

- #2 (SP-184 vendor B severity codes — leave AESEV_STD blank for unrecognized values)

## Acceptance criteria

For each output dataset, the generated CSV under `build/target/output/` must satisfy:

1. **Schema match** — same column names in the same order as `ground_truth/<dataset>.csv`.
2. **Row count match** — same number of rows.
3. **Row-for-row equality** — after sorting both sides by the dataset's stable sort key (defined in the test stub), every cell must equal the ground-truth cell. Floats use `round(x, 4)` before comparison; nulls are treated as equal.

Stable sort keys per output:

- `adam.ae_clean` — USUBJID, AESEQ
