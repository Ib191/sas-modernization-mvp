# CTX-2024-001 ADaM Pipeline — Functional Specification

**Study**: CTX-2024-001, Phase 2 dose-ranging
**Document version**: 1.3 (2024-02-28)
**Owner**: Statistical Programming
**Status**: Approved for execution

---

## 1. Purpose

This document specifies the analysis dataset (ADaM) derivations for the
CTX-2024-001 safety analyses. It is the contract between Stats Programming
and the Reporting team. The CSR shells reference dataset names and column
names defined here.

## 2. Pipeline overview

Five SAS programs produce the ADaM datasets and summary tables:

| # | Program            | Output         | Depends on          |
|---|--------------------|----------------|---------------------|
| 1 | `01_clean_dm.sas`  | `DM_CLEAN`     | RAW.DM              |
| 2 | `02_clean_ae.sas`  | `AE_CLEAN`     | RAW.AE              |
| 3 | `03_derive_adsl.sas` | `ADSL`       | DM_CLEAN, SITE_LOOKUP |
| 4 | `04_derive_adae.sas` | `ADAE`       | AE_CLEAN, ADSL      |
| 5 | `05_summary_safety.sas` | `AE_SUMMARY`, `AE_INCIDENCE` | ADAE, ADSL |

Programs 1 and 2 are independent and can be parallelized. Program 3 must
run before 4. Program 5 runs last.

## 3. Inputs

### 3.1 RAW.DM — Demographics
One row per subject (in principle; see §6.1 on duplicates).

Columns: `USUBJID, AGE, SEX, RACE, ARM, SITEID, BRTHDTC, RFSTDTC, RFENDTC, RECORDCREATEDT`

All `*DTC` columns are ISO 8601 character strings.

### 3.2 RAW.AE — Adverse Events
Multiple rows per subject. Severity (`AESEV`) is captured on the CRF as
free text and must be standardized. See §4.2.

Columns: `USUBJID, AETERM, AESEV, AESER, AESTDTC, AEENDTC`

### 3.3 RAW.SITE_LOOKUP — Site reference
Site descriptors. Joins to DM on site identifier.

Columns: `SITE_ID, SITE_NAME, SITE_COUNTRY, SITE_REGION`

## 4. Derivation rules

### 4.1 Demographics cleaning (`DM_CLEAN`)

- Convert all ISO date strings to SAS dates.
- Where `AGE` is missing, derive from `BRTHDTC` and `RFSTDTC` using
  365.25 days/year and FLOOR.
- Apply formats from `formats.sas` to derive `SEX_DECODE`, `ARM_DECODE`,
  `AGEGRP`.
- Compute `TRTDURD = RFENDT - RFSTDT + 1`.
- **Deduplication**: where multiple records exist for one `USUBJID`,
  keep the most recent (max `RECORDCREATEDT`).

### 4.2 AE cleaning (`AE_CLEAN`)

- Convert dates as above.
- Standardize severity to `MILD` / `MODERATE` / `SEVERE`. Accepted raw
  values: `'MILD'`, `'MODERATE'`, `'MOD'`, `'SEVERE'`, `'SEV'`,
  numeric `1`/`2`/`3`. Records with other severity values
  (e.g. `'GRADE 1'` from vendor B) should be **flagged** for review.
  *(Per data manager email 2024-02-14: "we'll deal with vendor B in v1.4.
  For now just standardize what you can." See SP-184.)*
- Drop records where `AESTDTC` or `AETERM` is missing.
- Assign `AESEQ` within subject, ordered by start date then term.
- Derive `MAX_AESEV` per subject (worst severity observed).

### 4.3 ADSL derivations

- Left join `DM_CLEAN` to `SITE_LOOKUP` on site identifier.
- **Safety population (SAFFL)**: subject has `RFSTDT` populated.
- **ITT population (ITTFL)**: `SAFFL = 'Y'` and `ARM ≠ 'PLACEBO'`.

### 4.4 ADAE derivations

- Inner join `AE_CLEAN` to `ADSL` on `USUBJID`.
- **Treatment-emergent flag (TRTEMFL)**: `'Y'` if AE start date is on
  or after first dose. *(See §6.3 — implementation uses cohort
  randomization date.)*
- **On-treatment flag (ONTRTFL)**: AE start date within
  `[RFSTDT, RFENDT]`.
- Compute `ASTDY = AESTDT - RFSTDT + 1`.

### 4.5 Safety summaries

`AE_SUMMARY`: counts of treatment-emergent AEs by `ARM × SEVERITY`, with
serious-AE counts.

`AE_INCIDENCE`: subject-level worst-case severity, expressed as count and
rate (subjects with ≥1 TE AE at that worst severity, divided by safety
population denominator).

## 5. Formats

Defined in `config/formats.sas`. All programs `%include` this file.

## 6. Known issues / open items

### 6.1 DM duplicates (resolved by dedup logic)
A 2023 CRF amendment caused some subjects to appear twice in the raw
extract. The dedup step in §4.1 handles this.

### 6.2 Vendor B severity codes (deferred)
~5% of AE records arrive with `GRADE 1`/`GRADE 2`/`GRADE 3` style codes.
These are NOT mapped in v1.3. Their `AESEV_STD` will be blank and they
will appear in the "blank severity" row of `AE_SUMMARY`. Tracked as
SP-184. Decision deferred to data review meeting.

### 6.3 "First dose" vs "randomization" date for TRTEMFL
The TRTEMFL definition in §4.4 says "first dose date". The current
implementation uses the cohort-level latest randomization date as a
proxy. The medical monitor accepted this for v1.3 but flagged it for
review in v1.4 (SP-227).

### 6.4 Site lookup join
DM stores `SITEID` as character (`'01'`, `'02'`...). The SITE_LOOKUP
extract delivers `SITE_ID` as numeric (1, 2...). The PROC SQL join
relies on SAS implicit type conversion. Works in SAS, but flagged
during code review as a portability concern.

## 7. Out of scope (v1.3)

- Vital signs, labs, ECG processing
- Concomitant medications
- Death and discontinuation rates
- Subgroup analyses beyond age group and sex
