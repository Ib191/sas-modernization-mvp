/******************************************************************************
* Program     : 03_derive_adsl.sas
* Description : Derive ADSL (Subject-Level Analysis Dataset).
*               Combines DM_CLEAN with site lookup and protocol milestones.
* Inputs      : ADAM.DM_CLEAN, RAW.SITE_LOOKUP
* Outputs     : ADAM.ADSL
* Run order   : After 01_clean_dm.sas
*
* SIDE EFFECT: This program sets the global macro variable &TRT_START_DT
*              to the most-recent treatment start date in the cohort.
*              Programs 04 and 05 rely on this being set.
******************************************************************************/

%include "config/setup.sas";

/* ---- 1. Pull site descriptors via PROC SQL join ---- */
proc sql;
  create table work.dm_with_site as
  select
    d.*,
    s.site_name,
    s.site_country,
    s.site_region
  from adam.dm_clean as d
  left join raw.site_lookup as s
    on d.siteid = s.site_id   /* join on SITE - see data_dictionary.md 4.5 */
  ;
quit;

/* ---- 2. Apply analysis-population flags ---- */
data work.adsl_pre;
  set work.dm_with_site;

  length saffl ittfl $1;

  /* Safety population: any subject who received >= 1 dose */
  if not missing(rfstdt) then saffl = 'Y'; else saffl = 'N';

  /* ITT population: randomized to a non-placebo arm AND took dose */
  if saffl = 'Y' and arm ne 'PLACEBO' then ittfl = 'Y'; else ittfl = 'N';

run;

/* ---- 3. Capture cohort-level treatment start for downstream use ---- */
proc sql noprint;
  select max(rfstdt) into :TRT_START_DT trimmed
  from work.adsl_pre
  where saffl = 'Y';
quit;

%put NOTE: TRT_START_DT set to &TRT_START_DT (numeric SAS date);

/* ---- 4. Final ADSL ---- */
data adam.adsl;
  set work.adsl_pre;

  label
    saffl       = 'Safety Population Flag'
    ittfl       = 'Intent-to-Treat Population Flag'
    site_name   = 'Site name'
    site_country= 'Country'
    site_region = 'Region'
  ;
run;

%put NOTE: 03_derive_adsl.sas complete. Output: ADAM.ADSL;
