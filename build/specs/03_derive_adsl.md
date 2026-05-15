# Functional spec — `03_derive_adsl`

## Purpose

Derive the Subject-Level Analysis Dataset. Left-join `dm_clean` with `site_lookup` on `SITEID`/`SITE_ID` (with explicit type coercion — see §Ambiguities). Apply Safety (`SAFFL`) and ITT (`ITTFL`) population flags. Capture the cohort-level maximum `RFSTDT` over `SAFFL='Y'` subjects as the runtime symbol `TRT_START_DT` for downstream use. Output: `adam.adsl`.

**Run order.** Depends on: adam.dm_clean, raw.site_lookup.
Produces: adam.adsl.

## Inputs

### `adam.dm_clean`

Producer: `01_clean_dm`. Source CSV: `ground_truth/dm_clean.csv`.

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

### `raw.site_lookup`

Producer: `(input)`. Source CSV: `input_data/site_lookup.csv`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `SITE_ID` | int | False | 1 | 2 |
| `SITE_NAME` | string | False | Boston Medical Ctr | Toronto General |
| `SITE_COUNTRY` | string | False | USA | CAN |
| `SITE_REGION` | string | False | NA | NA |

## Outputs

### `adam.adsl`

Producer: `03_derive_adsl`. Schema file: `build/schemas/adam_adsl.py`.

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
| `SITE_NAME` | string | False | Toronto General | Boston Medical Ctr |
| `SITE_COUNTRY` | string | False | CAN | USA |
| `SITE_REGION` | string | False | NA | NA |
| `SAFFL` | string | False | Y | Y |
| `ITTFL` | string | False | Y | N |

## Transformations

Derived from the program AST (Phase 1) and the data flow graph. Each step describes the operation in plain English; the SAS construct that produced it is annotated for traceability but must not be re-read during Phase 5 codegen.

1. Read `adam.dm_clean` (CSV).
2. Read `raw.site_lookup` (CSV) with `SITE_ID` as int.
3. **Coerce** `site_lookup.SITE_ID` from int to zero-padded 2-character string (`f"{int(x):02d}"`) — this resolves the char-vs-num implicit cast that the SAS PROC SQL relied on (§1.5 #3).
4. Left-join: `dm_clean LEFT JOIN site_lookup ON dm_clean.SITEID = site_lookup.SITE_ID_padded`. Bring in `SITE_NAME, SITE_COUNTRY, SITE_REGION`.
5. Apply Safety population flag: `SAFFL = 'Y' if RFSTDT is not null else 'N'`.
6. Apply ITT population flag: `ITTFL = 'Y' if SAFFL='Y' and ARM != 'PLACEBO' else 'N'`.
7. Compute `TRT_START_DT` as the maximum `RFSTDT` over rows with `SAFFL='Y'`. **This is a single scalar applied uniformly to every subject downstream.** (§1.5 #1, resolved 2026-05-07.)
8. Persist `TRT_START_DT` to a small file at `build/target/state/trt_start_dt.txt` so program 04 can read it without re-reading ADSL.
9. Output column order: `USUBJID, AGE, AGE_DERIVED, AGEGRP, SEX, SEX_DECODE, RACE, ARM, ARM_DECODE, RFSTDT, RFENDT, TRTDURD, SITEID, SITE_NAME, SITE_COUNTRY, SITE_REGION, SAFFL, ITTFL`.

## Business rules (excerpt)

Drawn from `sas_codebase/docs/functional_spec.md` and `data_dictionary.md` (parsed in Phase 2). Listed for reference; the Transformations section above is the authoritative spec.

- §4.3 ADSL derivations: Left join `DM_CLEAN` to `SITE_LOOKUP` on site identifier.
- §4.3 ADSL derivations: **Safety population (SAFFL)**: subject has `RFSTDT` populated.
- §4.3 ADSL derivations: **ITT population (ITTFL)**: `SAFFL = 'Y'` and `ARM ≠ 'PLACEBO'`.

## Ambiguities and resolutions

From `build/reports/ambiguity_log.md`. Items relevant to this program:

- #3 (SITE_ID type coercion: cast SITE_LOOKUP.SITE_ID to zero-padded 2-char string before join)

## Acceptance criteria

For each output dataset, the generated CSV under `build/target/output/` must satisfy:

1. **Schema match** — same column names in the same order as `ground_truth/<dataset>.csv`.
2. **Row count match** — same number of rows.
3. **Row-for-row equality** — after sorting both sides by the dataset's stable sort key (defined in the test stub), every cell must equal the ground-truth cell. Floats use `round(x, 4)` before comparison; nulls are treated as equal.

Stable sort keys per output:

- `adam.adsl` — USUBJID
