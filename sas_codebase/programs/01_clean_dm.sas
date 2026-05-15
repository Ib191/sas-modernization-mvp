/******************************************************************************
* Program     : 01_clean_dm.sas
* Description : Clean and standardize raw demographics (DM domain).
*               Output: ADAM.DM_CLEAN
* Inputs      : RAW.DM (raw demographics extract)
* Outputs     : ADAM.DM_CLEAN
* Run order   : First (no dependencies on other ADAM datasets)
******************************************************************************/

%include "config/setup.sas";

/* ---- 1. Stage raw read with type conversion ---- */
data work.dm_stage;
  set raw.dm;

  /* Raw extract gives us ISO 8601 char dates; convert to SAS dates */
  rfstdt = %iso_to_sasdate(var=rfstdtc);
  rfendt = %iso_to_sasdate(var=rfendtc);
  brthdt = %iso_to_sasdate(var=brthdtc);

  format rfstdt rfendt brthdt yymmdd10.;

  /* Derived age at study reference start */
  if not missing(brthdt) and not missing(rfstdt) then
    age_derived = %calc_age(birth=brthdt, ref=rfstdt);
  else
    age_derived = .;

  /* Use derived age if raw AGE is missing - keeps audit trail */
  if missing(age) then age = age_derived;

  /* Treatment duration in days, inclusive */
  if not missing(rfstdt) and not missing(rfendt) then
    trtdurd = rfendt - rfstdt + 1;

run;

/* ---- 2. Dedup: keep latest record per subject ----
   Some subjects have screening + post-rerand records from a CRF amendment.
   Sort by USUBJID then by record creation date desc, keep first per group. */
proc sort data=work.dm_stage;
  by usubjid descending recordcreatedt;
run;

data work.dm_dedup;
  set work.dm_stage;
  by usubjid;
  if first.usubjid;  /* first = latest, due to descending sort */
run;

/* ---- 3. Apply formatted derivations and finalize ---- */
data adam.dm_clean;
  set work.dm_dedup;

  length sex_decode arm_decode $40;

  sex_decode = put(sex, $sexfmt.);
  arm_decode = put(arm, $armfmt.);
  agegrp     = put(age, agegrp.);

  label
    usubjid     = 'Unique Subject Identifier'
    age         = 'Age (years)'
    age_derived = 'Age derived from birth date'
    sex         = 'Sex code'
    sex_decode  = 'Sex (decoded)'
    arm         = 'Treatment arm code'
    arm_decode  = 'Treatment arm'
    rfstdt      = 'Reference start date'
    rfendt      = 'Reference end date'
    trtdurd     = 'Treatment duration (days)'
    agegrp      = 'Age group'
  ;

  keep usubjid age age_derived agegrp sex sex_decode race
       arm arm_decode rfstdt rfendt trtdurd siteid;
run;

%put NOTE: 01_clean_dm.sas complete. Output: ADAM.DM_CLEAN;
