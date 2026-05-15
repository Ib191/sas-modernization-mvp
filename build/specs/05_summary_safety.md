# Functional spec — `05_summary_safety`

## Purpose

Produce the safety summary tables. `ae_summary`: event counts and serious-event counts grouped by `ARM × AESEV_STD`, filtered to `TRTEMFL='Y'`. `ae_incidence`: subject-level worst-severity incidence rates per arm against the safety-population denominator (also `TRTEMFL='Y'` only). Outputs: `adam.ae_summary`, `adam.ae_incidence`.

**Run order.** Depends on: adam.adae, adam.adsl.
Produces: adam.ae_incidence, adam.ae_summary.

## Inputs

### `adam.adae`

Producer: `04_derive_adae`. Source CSV: `ground_truth/adae.csv`.

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

## Outputs

### `adam.ae_incidence`

Producer: `05_summary_safety`. Schema file: `build/schemas/adam_ae_incidence.py`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `ARM` | string | False | DRUG_X_HI | DRUG_X_LOW |
| `ARM_DECODE` | string | False | Drug X 100mg | Drug X 50mg |
| `WORST_SEVERITY` | string | False | MODERATE | MILD |
| `WORST_SEVERITY_RANK` | int | False | 2 | 1 |
| `N_SUBJ_WITH_AE` | int | False | 1 | 1 |
| `N_SUBJ_TOTAL` | int | False | 3 | 9 |
| `INCIDENCE_RATE` | float | False | 0.3333 | 0.1111 |

### `adam.ae_summary`

Producer: `05_summary_safety`. Schema file: `build/schemas/adam_ae_summary.py`.

| Column | dtype | nullable | sample |
| ------ | ----- | -------- | ------ |
| `ARM` | string | False | DRUG_X_HI | DRUG_X_LOW |
| `ARM_DECODE` | string | False | Drug X 100mg | Drug X 50mg |
| `SEVERITY` | string | True | MILD | MILD |
| `N_EVENTS` | int | False | 1 | 4 |
| `N_SERIOUS` | int | False | 0 | 0 |

## Transformations

Derived from the program AST (Phase 1) and the data flow graph. Each step describes the operation in plain English; the SAS construct that produced it is annotated for traceability but must not be re-read during Phase 5 codegen.

1. Read `adam.adae` and `adam.adsl` (CSVs).
2. **Denominator** (`work.denom`): from ADSL filter to `SAFFL='Y'`, then group by `(ARM, ARM_DECODE)` and count distinct `USUBJID` → `N_SUBJ`.
3. **Subject-level worst severity** (`work.ae_subj`): from ADAE filter to `TRTEMFL='Y'`, then take the distinct combination of `(ARM, ARM_DECODE, USUBJID, MAX_AESEV, MAX_AESEVN)`.
4. **AE counts** (`work.ae_counts`): group `work.ae_subj` by `(ARM, ARM_DECODE, MAX_AESEV, MAX_AESEVN)` and count rows → `N_SUBJ_WITH_AE`.
5. **`adam.ae_incidence`**: join `work.ae_counts` to `work.denom` on `ARM`, computing `INCIDENCE_RATE = round(N_SUBJ_WITH_AE / N_SUBJ_TOTAL, 4)` (returning null when denominator is null/zero). Sort by `(ARM, MAX_AESEVN)`. Output columns: `ARM, ARM_DECODE, WORST_SEVERITY (=MAX_AESEV), WORST_SEVERITY_RANK (=MAX_AESEVN), N_SUBJ_WITH_AE, N_SUBJ_TOTAL, INCIDENCE_RATE`.
6. **`adam.ae_summary`**: from ADAE filter to `TRTEMFL='Y'`, group by `(ARM, ARM_DECODE, AESEV_STD as SEVERITY)` and compute `N_EVENTS = count(*)`, `N_SERIOUS = sum(1 if AESER='Y' else 0)`. Sort by `(ARM, SEVERITY)` (with blank severity sorting first per ground-truth ordering). Output columns: `ARM, ARM_DECODE, SEVERITY, N_EVENTS, N_SERIOUS`.

## Business rules (excerpt)

Drawn from `sas_codebase/docs/functional_spec.md` and `data_dictionary.md` (parsed in Phase 2). Listed for reference; the Transformations section above is the authoritative spec.


## Ambiguities and resolutions

From `build/reports/ambiguity_log.md`. Items relevant to this program:

- #1 (TRTEMFL semantics inherited from ADAE)

## Acceptance criteria

For each output dataset, the generated CSV under `build/target/output/` must satisfy:

1. **Schema match** — same column names in the same order as `ground_truth/<dataset>.csv`.
2. **Row count match** — same number of rows.
3. **Row-for-row equality** — after sorting both sides by the dataset's stable sort key (defined in the test stub), every cell must equal the ground-truth cell. Floats use `round(x, 4)` before comparison; nulls are treated as equal.

Stable sort keys per output:

- `adam.ae_incidence` — ARM, WORST_SEVERITY_RANK
- `adam.ae_summary` — ARM, SEVERITY (blank-first to match ground truth)
