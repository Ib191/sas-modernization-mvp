# CTX-2024-001 Data Dictionary

This dictionary documents column-level semantics for the raw inputs and
ADaM outputs. Format: `column — type — description`.

## RAW.DM

- `USUBJID` — char(20) — Unique subject identifier. Format `CTX-NNN`. **Primary key after dedup.**
- `AGE` — num — Age in years at reference start. May be missing; derive from `BRTHDTC` if so.
- `SEX` — char(1) — `M`, `F`, `U`. Decoded via `$sexfmt`.
- `RACE` — char(20) — Free-form, controlled by CRF dropdown.
- `ARM` — char(20) — Treatment arm code: `PLACEBO`, `DRUG_X_LOW`, `DRUG_X_HI`.
- `SITEID` — **char(2)** — Site identifier with leading zeros. *Note:* differs in type from `SITE_LOOKUP.SITE_ID`.
- `BRTHDTC` — char(10) — ISO 8601 date of birth.
- `RFSTDTC` — char(10) — ISO 8601 reference start (first dose).
- `RFENDTC` — char(10) — ISO 8601 reference end (last dose / end of treatment).
- `RECORDCREATEDT` — char(10) — ISO 8601, set by EDC. Used for dedup tiebreak.

## RAW.AE

- `USUBJID` — char(20) — FK to DM.
- `AETERM` — char(60) — Reported term (free text). Not standardized to MedDRA in v1.3.
- `AESEV` — char(20) — Severity, raw. May contain `MILD`/`MODERATE`/`MOD`/`SEVERE`/`SEV`/`1`/`2`/`3`/`GRADE 1`/`GRADE 2`/`GRADE 3`.
- `AESER` — char(1) — `Y`/`N`. Serious AE indicator.
- `AESTDTC` — char(10) — Onset date, ISO 8601. May be missing.
- `AEENDTC` — char(10) — End date, ISO 8601. Often missing for ongoing events.

## RAW.SITE_LOOKUP

- `SITE_ID` — **num** — Site identifier. *Note:* numeric, vs char in DM.
- `SITE_NAME` — char(60)
- `SITE_COUNTRY` — char(3) — ISO 3166-1 alpha-3.
- `SITE_REGION` — char(10) — `NA`, `EU`, `APAC`, `LATAM`.

## ADAM.DM_CLEAN (output)

Adds derived columns: `AGE_DERIVED`, `AGEGRP`, `SEX_DECODE`, `ARM_DECODE`,
`RFSTDT` (numeric date), `RFENDT` (numeric date), `TRTDURD`. Drops
`BRTHDTC`, `RFSTDTC`, `RFENDTC`, `RECORDCREATEDT` from the keep list.

## ADAM.AE_CLEAN (output)

Adds: `AESEQ` (within-subject sequence), `AESTDT`, `AEENDT`, `AEDUR`,
`AESEV_STD`, `AESEVN`, `MAX_AESEV`, `MAX_AESEVN`.

## ADAM.ADSL (output)

DM_CLEAN columns plus site descriptors and population flags:
`SITE_NAME`, `SITE_COUNTRY`, `SITE_REGION`, `SAFFL`, `ITTFL`.

## ADAM.ADAE (output)

AE_CLEAN columns plus subject context: `AGE`, `AGEGRP`, `SEX`, `ARM`,
`ARM_DECODE`, `RFSTDT`, `RFENDT`, `SAFFL`, `ITTFL`, `TRTEMFL`,
`ONTRTFL`, `ASTDY`.

## ADAM.AE_SUMMARY (output)

Grouped counts: `ARM`, `ARM_DECODE`, `SEVERITY`, `N_EVENTS`, `N_SERIOUS`.
Filtered to `TRTEMFL = 'Y'`.

## ADAM.AE_INCIDENCE (output)

Subject-level worst severity rates: `ARM`, `ARM_DECODE`, `WORST_SEVERITY`,
`WORST_SEVERITY_RANK`, `N_SUBJ_WITH_AE`, `N_SUBJ_TOTAL`, `INCIDENCE_RATE`.
