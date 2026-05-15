/******************************************************************************
* Program     : 02_clean_ae.sas
* Description : Clean raw adverse events. Standardize severity, drop
*               obviously invalid records, derive sequence numbers.
* Inputs      : RAW.AE
* Outputs     : ADAM.AE_CLEAN
* Run order   : Independent of 01 (can run in parallel)
******************************************************************************/

%include "config/setup.sas";

/* ---- 1. Stage with date conversion and severity standardization ---- */
data work.ae_stage;
  set raw.ae;

  aestdt = %iso_to_sasdate(var=aestdtc);
  aeendt = %iso_to_sasdate(var=aeendtc);

  format aestdt aeendt yymmdd10.;

  length aesev_std $10;

  /* Severity standardization - the CRF accepts free-text in some cases */
  if upcase(strip(aesev)) in ('MILD','1') then aesev_std = 'MILD';
  else if upcase(strip(aesev)) in ('MODERATE','MOD','2') then aesev_std = 'MODERATE';
  else if upcase(strip(aesev)) in ('SEVERE','SEV','3') then aesev_std = 'SEVERE';
  /* else: leave aesev_std blank - downstream code treats blank as missing */

  aesevn = %sev_to_rank(sev=aesev_std);

  /* Filter: must have at least a start date and a term */
  if missing(aestdt) then delete;
  if missing(aeterm) then delete;

  /* Derive duration in days; missing if end date missing */
  if not missing(aeendt) then aedur = aeendt - aestdt + 1;

run;

/* ---- 2. Sort and derive AESEQ within subject ---- */
proc sort data=work.ae_stage;
  by usubjid aestdt aeterm;
run;

data work.ae_seq;
  set work.ae_stage;
  by usubjid aestdt aeterm;

  retain aeseq;
  if first.usubjid then aeseq = 0;
  aeseq + 1;
run;

/* ---- 3. Derive maximum severity per subject (used by ADAE) ----
   BY USUBJID, want LAST. record after sorting by severity rank. */
proc sort data=work.ae_seq out=work.ae_for_max;
  by usubjid aesevn;
run;

data work.ae_max_sev;
  set work.ae_for_max;
  by usubjid aesevn;
  if last.usubjid;
  rename aesevn = max_aesevn aesev_std = max_aesev;
  keep usubjid aesevn aesev_std;
run;

/* ---- 4. Merge max severity back onto cleaned AE ---- */
proc sort data=work.ae_seq;
  by usubjid;
run;

data adam.ae_clean;
  merge work.ae_seq(in=a)
        work.ae_max_sev(in=b);
  by usubjid;
  if a;

  label
    usubjid    = 'Unique Subject Identifier'
    aeseq      = 'AE sequence number'
    aeterm     = 'AE reported term'
    aestdt     = 'AE start date'
    aeendt     = 'AE end date'
    aedur      = 'AE duration (days)'
    aesev      = 'AE severity (raw)'
    aesev_std  = 'AE severity (standardized)'
    aesevn     = 'AE severity (rank 1-3)'
    aeser      = 'Serious AE flag'
    max_aesev  = 'Subject max severity (text)'
    max_aesevn = 'Subject max severity (rank)'
  ;
run;

%put NOTE: 02_clean_ae.sas complete. Output: ADAM.AE_CLEAN;
