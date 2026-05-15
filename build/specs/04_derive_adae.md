# Functional spec — `04_derive_adae`

## Purpose

Derive the Adverse-Event Analysis Dataset. Inner-join `ae_clean` with subject-level fields from `adsl`. Compute `TRTEMFL` (treatment-emergent flag, using cohort-level `TRT_START_DT` per the resolved ambiguity), `ONTRTFL` (on-treatment window), and `ASTDY` (analysis day relative to RFSTDT). Output: `adam.adae`.

**Run order.** Depends on: adam.adsl, adam.ae_clean.
Produces: adam.adae.

## Inputs

### `adam.adsl`

Producer: `03_derive_adsl`. Source CSV: `ground_truth/adsl.csv`.

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

### `adam.ae_clean`

Producer: `02_clean_ae`. Source CSV: `ground_truth/ae_clean.csv`.

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

## Outputs

### `adam.adae`

Producer: `04_derive_adae`. Schema file: `build/schemas/adam_adae.py`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `USUBJID` | string | False | CTX-001 | CTX-001 |
| `AETERM` | string | False | NAUSEA | FATIGUE |
| `AESTDT` | date | False | 2024-02-18 | 2024-03-03 |
| `AEENDT` | date | True | 2024-02-22 | 2024-04-25 |
| `AEDUR` | int | True | 5 | 10 |
| `AESEV` | string | False | SEVERE | 3 |
| `AESEV_STD` | string | True | SEVERE | SEVERE |
| `AESEVN` | int | True | 3 | 3 |
| `AESER` | string | False | N | N |
| `AESEQ` | int | False | 1 | 2 |
| `MAX_AESEV` | string | False | SEVERE | SEVERE |
| `MAX_AESEVN` | int | False | 3 | 3 |
| `AGE` | int | False | 69 | 69 |
| `AGEGRP` | string | False | 65+ | 65+ |
| `SEX` | string | False | M | M |
| `ARM` | string | False | DRUG_X_HI | DRUG_X_HI |
| `ARM_DECODE` | string | False | Drug X 100mg | Drug X 100mg |
| `RFSTDT` | date | False | 2024-01-30 | 2024-01-30 |
| `RFENDT` | date | False | 2024-03-12 | 2024-03-12 |
| `SAFFL` | string | False | Y | Y |
| `ITTFL` | string | False | Y | Y |
| `TRTEMFL` | string | False | N | N |
| `ONTRTFL` | string | False | Y | Y |
| `ASTDY` | int | False | 20 | 34 |

## Transformations

Derived from the program AST (Phase 1) and the data flow graph. Each step describes the operation in plain English; the SAS construct that produced it is annotated for traceability but must not be re-read during Phase 5 codegen.

1. Read `adam.ae_clean` (CSV).
2. Read `adam.adsl` (CSV); keep only `USUBJID, AGE, AGEGRP, SEX, ARM, ARM_DECODE, RFSTDT, RFENDT, SAFFL, ITTFL`.
3. Read the cohort-level `TRT_START_DT` from `build/target/state/trt_start_dt.txt`.
4. Inner-join on `USUBJID` (keep only AEs whose subject is in ADSL).
5. Compute `TRTEMFL`: `'Y'` if `AESTDT is not null and AESTDT >= TRT_START_DT` else `'N'`. (Cohort-level scalar — see §1.5 #1.)
6. Compute `ONTRTFL`: `'Y'` if `AESTDT, RFSTDT, RFENDT all non-null and RFSTDT <= AESTDT <= RFENDT` else `'N'`.
7. Compute `ASTDY = (AESTDT - RFSTDT).days + 1` when both present.
8. Output column order: `USUBJID, AETERM, AESTDT, AEENDT, AEDUR, AESEV, AESEV_STD, AESEVN, AESER, AESEQ, MAX_AESEV, MAX_AESEVN, AGE, AGEGRP, SEX, ARM, ARM_DECODE, RFSTDT, RFENDT, SAFFL, ITTFL, TRTEMFL, ONTRTFL, ASTDY`.

## Business rules (excerpt)

Drawn from `sas_codebase/docs/functional_spec.md` and `data_dictionary.md` (parsed in Phase 2). Listed for reference; the Transformations section above is the authoritative spec.

- §4.4 ADAE derivations: Inner join `AE_CLEAN` to `ADSL` on `USUBJID`.
- §4.4 ADAE derivations: **Treatment-emergent flag (TRTEMFL)**: `'Y'` if AE start date is on
- §4.4 ADAE derivations: **On-treatment flag (ONTRTFL)**: AE start date within
- §4.4 ADAE derivations: Compute `ASTDY = AESTDT - RFSTDT + 1`.

## Ambiguities and resolutions

From `build/reports/ambiguity_log.md`. Items relevant to this program:

- #1 (TRTEMFL — RESOLVED: cohort-level max(RFSTDT) where SAFFL='Y'; apply uniformly to all subjects)

## Acceptance criteria

For each output dataset, the generated CSV under `build/target/output/` must satisfy:

1. **Schema match** — same column names in the same order as `ground_truth/<dataset>.csv`.
2. **Row count match** — same number of rows.
3. **Row-for-row equality** — after sorting both sides by the dataset's stable sort key (defined in the test stub), every cell must equal the ground-truth cell. Floats use `round(x, 4)` before comparison; nulls are treated as equal.

Stable sort keys per output:

- `adam.adae` — USUBJID, AESEQ
