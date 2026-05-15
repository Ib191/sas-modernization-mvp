# Ambiguity Log

Static-analysis ambiguities detected during Phases 1–3. Entries follow the
schema mirrored in `SOLUTION.md` §1.5; this file carries the full assumption
write-ups for High-severity items.

## Summary

| # | Severity | Status                | Title                                                  |
|---|----------|-----------------------|--------------------------------------------------------|
| 1 | High     | **Resolved 2026-05-07** | `&TRT_START_DT` cross-program coupling for TRTEMFL  |
| 2 | Medium   | Logged                | SP-184 vendor B severity codes (GRADE 1/2/3)          |
| 3 | Medium   | Logged                | SITE_ID type mismatch (char vs num) in DM ↔ SITE_LOOKUP |
| 4 | Low      | Logged                | DM duplicates from CRF amendment                      |
| 5 | Low      | Logged                | `&PROJ_ROOT = %sysfunc(getoption(SASUSER))`           |

**Resolution of #1 (2026-05-07).** User confirmed Option B (cohort-level
`max(RFSTDT)` over `SAFFL='Y'`) — match the running SAS implementation and
ground truth. SP-227 remains as a v1.4 follow-up to revisit per-subject
first-dose semantics.

## High-severity assumptions (full write-ups)

### #1 — `&TRT_START_DT` cross-program coupling

**Locations.**
- Definition site: `sas_codebase/programs/03_derive_adsl.sas:46`
  ```sas
  proc sql noprint;
    select max(rfstdt) into :TRT_START_DT trimmed
    from work.adsl_pre
    where saffl = 'Y';
  quit;
  ```
- Reading macro: `sas_codebase/macros/util_macros.sas:46-48`
  ```sas
  %macro is_treatment_emergent(ae_start=);
    (not missing(&ae_start) and &ae_start >= &TRT_START_DT)
  %mend is_treatment_emergent;
  ```
- Call site: `sas_codebase/programs/04_derive_adae.sas:38`
  ```sas
  if %is_treatment_emergent(ae_start=aestdt) then trtemfl = 'Y';
  ```

**Why it is ambiguous.**
The functional specification (§4.4) defines TRTEMFL semantically as
"AE start date is on or after **first dose**". In a real SDTM/ADaM context
"first dose" is a **per-subject** value (the subject's own RFSTDT). The
implementation, however, computes a single **cohort-level** scalar
(the maximum RFSTDT across the safety population) and applies it
identically to every subject. The functional spec acknowledges this in §6.3
("medical monitor accepted this for v1.3 but flagged it for review in v1.4
— SP-227").

Static analysis cannot, on its own, decide which of these two definitions
the modernized pipeline should honour:

| Option | Behaviour                                                                                  | Match with ground truth |
| ------ | ------------------------------------------------------------------------------------------ | ----------------------- |
| A      | Per-subject "first dose" — TRTEMFL = (AESTDT ≥ subject's own RFSTDT)                       | Likely **mismatch**     |
| B      | Cohort-level latest randomization — TRTEMFL = (AESTDT ≥ max(RFSTDT) over SAFFL='Y' cohort) | Matches existing SAS    |

**Pre-flagged assumption.** Adopt Option B (cohort-level
`max(RFSTDT)` over `SAFFL='Y'`). This is the assumption that reproduces
ground truth row-for-row and matches the running SAS implementation.

**Counterfactual.** If Option A is what the user actually wants, the
modernized output will diverge from ground truth on TRTEMFL for every
subject whose RFSTDT differs from the cohort max. Downstream impacts:
ADAE.TRTEMFL, AE_SUMMARY (filters TRTEMFL='Y'), AE_INCIDENCE (filters
TRTEMFL='Y'). Validation would fail row-for-row on those three datasets.

**User decision required before Phase 5.** Confirm Option B, or override
to Option A (in which case the spec text and Phase 5 codegen change, and
the validation step measures the divergence vs ground truth instead of
row-for-row equality).

## Medium / Low — auto-logged write-ups

### #2 — SP-184 vendor B severity codes

`02_clean_ae.sas:24-26` standardizes only `MILD/1`, `MODERATE/MOD/2`,
`SEVERE/SEV/3`. Input data contains `GRADE 1` and `GRADE 2` values
(detected via `csv.DictReader` scan of `input_data/ae.csv`). The else
branch leaves `AESEV_STD` blank, producing the blank-severity rows
observable in `ground_truth/ae_summary.csv`:

```
DRUG_X_LOW,Drug X 50mg,,4,0
PLACEBO,Placebo,,2,0
```

Phase 5 codegen replicates the deferred behaviour exactly — no `GRADE *`
mapping. Tracker SP-184 captures the v1.4 follow-up.

### #3 — SITE_ID type mismatch

`03_derive_adsl.sas:25-27` performs a left join between
`adam.dm_clean.siteid` (char) and `raw.site_lookup.site_id` (num). SAS does
this with implicit type promotion and case-insensitive matching. Python's
join semantics (pandas merge / duckdb SQL) require explicit alignment.
Phase 5 codegen will:

1. Read `site_lookup.csv` with `SITE_ID` as int.
2. Coerce to `f"{int(site_id):02d}"` (zero-padded 2-character string).
3. Join on the resulting char column.

Output `SITEID` retains the leading-zero `'02'` form expected by
ground truth.

### #4 — DM duplicate handling

§6.1 of `functional_spec.md` notes that a 2023 CRF amendment caused some
subjects to appear twice in the DM raw extract; the dedup logic in
`01_clean_dm.sas:41-49` (`sort by usubjid desc recordcreatedt; first.usubjid`)
is the resolution. The synthetic input `dm.csv` happens to be already
unique on USUBJID (22 rows, 22 distinct subjects, but ground truth shows
20 — so 2 are dropped, presumably duplicates), so the dedup rule is
load-bearing for matching ground truth row counts.

### #5 — `&PROJ_ROOT`

`setup.sas:16` defines `%let PROJ_ROOT = %sysfunc(getoption(SASUSER));`.
The macro evaluator in Phase 1 leaves `%sysfunc(...)` literal. The variable
only feeds `libname` paths and `%include` resolution; the parser resolves
`%include` against the project root via a candidate-path search, and
`libname` is irrelevant once the pipeline moves to Python. No further
action.
