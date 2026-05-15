# Functional spec — `01_clean_dm`

## Purpose

Clean and standardize raw demographics. Convert ISO 8601 character dates to date values, derive `AGE_DERIVED` and `AGEGRP`, decode `SEX` and `ARM`, compute `TRTDURD`, and deduplicate by USUBJID keeping the most-recently-created record. Output: `adam.dm_clean`.

**Run order.** Depends on: raw.dm.
Produces: adam.dm_clean.

## Inputs

### `raw.dm`

Producer: `(input)`. Source CSV: `input_data/dm.csv`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `USUBJID` | string | False | CTX-001 | CTX-002 |
| `AGE` | int | True | 69 | 59 |
| `SEX` | string | False | M | U |
| `RACE` | string | False | WHITE | WHITE |
| `ARM` | string | False | DRUG_X_HI | PLACEBO |
| `SITEID` | string | False | 02 | 01 |
| `BRTHDTC` | date | False | 1954-08-31 | 1964-06-13 |
| `RFSTDTC` | date | False | 2024-01-30 | 2024-01-17 |
| `RFENDTC` | date | False | 2024-03-12 | 2024-02-15 |
| `RECORDCREATEDT` | date | False | 2024-02-04 | 2024-01-18 |

## Outputs

### `adam.dm_clean`

Producer: `01_clean_dm`. Schema file: `build/schemas/adam_dm_clean.py`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `USUBJID` | string | False | CTX-001 | CTX-002 |
| `AGE` | int | False | 69 | 59 |
| `AGE_DERIVED` | int | False | 69 | 59 |
| `AGEGRP` | string | False | 65+ | 40-64 |
| `SEX` | string | False | M | U |
| `SEX_DECODE` | string | False | Male | Unknown |
| `RACE` | string | False | WHITE | WHITE |
| `ARM` | string | False | DRUG_X_HI | PLACEBO |
| `ARM_DECODE` | string | False | Drug X 100mg | Placebo |
| `RFSTDT` | date | False | 2024-01-30 | 2024-01-17 |
| `RFENDT` | date | False | 2024-03-12 | 2024-02-15 |
| `TRTDURD` | int | False | 43 | 30 |
| `SITEID` | string | False | 02 | 01 |

## Transformations

Derived from the program AST (Phase 1) and the data flow graph. Each step describes the operation in plain English; the SAS construct that produced it is annotated for traceability but must not be re-read during Phase 5 codegen.

1. Read `raw.dm` (CSV).
2. Convert `BRTHDTC`, `RFSTDTC`, `RFENDTC` from ISO 8601 strings to date values. Missing/invalid → null.
3. Compute `AGE_DERIVED = (RFSTDT - BRTHDT).days // 365` (integer division by 365) when both `BRTHDT` and `RFSTDT` are present, else null. **Note (ambiguity #6):** the SAS macro uses 365.25 with floor; ground truth was generated with 365. Spec follows ground truth per R4.
4. Backfill `AGE` from `AGE_DERIVED` where `AGE` is null.
5. Compute `TRTDURD = (RFENDT - RFSTDT).days + 1` when both ends are present, else null.
6. Deduplicate by `USUBJID` keeping the row with the maximum `RECORDCREATEDT`.
7. Decode `SEX_DECODE` from `SEX` via the `$sexfmt` map (`M`→Male, `F`→Female, `U`→Unknown, other→Missing).
8. Decode `ARM_DECODE` from `ARM` via the `$armfmt` map (`PLACEBO`→Placebo, `DRUG_X_LOW`→Drug X 50mg, `DRUG_X_HI`→Drug X 100mg).
9. Compute `AGEGRP` from `AGE` via the `agegrp` numeric ranges (`<18`, `18-39`, `40-64`, `65+`).
10. Keep columns: `USUBJID, AGE, AGE_DERIVED, AGEGRP, SEX, SEX_DECODE, RACE, ARM, ARM_DECODE, RFSTDT, RFENDT, TRTDURD, SITEID`.

Output `RFSTDT` and `RFENDT` are written as ISO date strings (YYYY-MM-DD) to match `ground_truth/dm_clean.csv`. Cell `SITEID` is written as a zero-padded 2-character string (e.g. `'02'`).

## Business rules (excerpt)

Drawn from `sas_codebase/docs/functional_spec.md` and `data_dictionary.md` (parsed in Phase 2). Listed for reference; the Transformations section above is the authoritative spec.

- §4.1 Demographics cleaning (`DM_CLEAN`): Convert all ISO date strings to SAS dates.
- §4.1 Demographics cleaning (`DM_CLEAN`): Where `AGE` is missing, derive from `BRTHDTC` and `RFSTDTC` using
- §4.1 Demographics cleaning (`DM_CLEAN`): Apply formats from `formats.sas` to derive `SEX_DECODE`, `ARM_DECODE`,
- §4.1 Demographics cleaning (`DM_CLEAN`): Compute `TRTDURD = RFENDT - RFSTDT + 1`.
- §4.1 Demographics cleaning (`DM_CLEAN`): **Deduplication**: where multiple records exist for one `USUBJID`,

## Ambiguities and resolutions

From `build/reports/ambiguity_log.md`. Items relevant to this program:

- #5 (PROJ_ROOT cosmetic)
- #4 (DM dedup)

## Acceptance criteria

For each output dataset, the generated CSV under `build/target/output/` must satisfy:

1. **Schema match** — same column names in the same order as `ground_truth/<dataset>.csv`.
2. **Row count match** — same number of rows.
3. **Row-for-row equality** — after sorting both sides by the dataset's stable sort key (defined in the test stub), every cell must equal the ground-truth cell. Floats use `round(x, 4)` before comparison; nulls are treated as equal.

Stable sort keys per output:

- `adam.dm_clean` — USUBJID
