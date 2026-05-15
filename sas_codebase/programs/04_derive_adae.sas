/******************************************************************************
* Program     : 04_derive_adae.sas
* Description : Derive ADAE (Adverse Event analysis dataset).
*               Merges AE_CLEAN with ADSL, derives treatment-emergent flag,
*               serious-AE indicators, and on-treatment status.
* Inputs      : ADAM.AE_CLEAN, ADAM.ADSL
* Outputs     : ADAM.ADAE
* Run order   : After 02_clean_ae.sas AND 03_derive_adsl.sas
*
* DEPENDS ON  : Global macro &TRT_START_DT (set in 03_derive_adsl.sas).
******************************************************************************/

%include "config/setup.sas";

/* Sanity check that ADSL has run */
%if not %symexist(TRT_START_DT) %then %do;
  %put WARNING: TRT_START_DT not set. Run 03_derive_adsl.sas first.;
%end;

/* ---- 1. Merge AE with subject-level info ---- */
proc sort data=adam.ae_clean out=work.ae_sorted;
  by usubjid;
run;

proc sort data=adam.adsl(keep=usubjid age agegrp sex arm arm_decode rfstdt rfendt saffl ittfl)
          out=work.adsl_sub;
  by usubjid;
run;

data work.adae_pre;
  merge work.ae_sorted(in=a)
        work.adsl_sub(in=b);
  by usubjid;
  if a and b;  /* keep AEs only for subjects in ADSL */

  /* Treatment-emergent flag - relies on macro + global */
  length trtemfl $1;
  if %is_treatment_emergent(ae_start=aestdt) then trtemfl = 'Y';
  else trtemfl = 'N';

  /* On-treatment window: AE start within rfstdt..rfendt */
  length ontrtfl $1;
  if not missing(aestdt) and not missing(rfstdt) and not missing(rfendt)
     and rfstdt <= aestdt <= rfendt then ontrtfl = 'Y';
  else ontrtfl = 'N';

  /* Days from treatment start to AE onset */
  if not missing(aestdt) and not missing(rfstdt) then
    astdy = aestdt - rfstdt + 1;
run;

/* ---- 2. Final ADAE ---- */
data adam.adae;
  set work.adae_pre;

  label
    trtemfl = 'Treatment Emergent Flag'
    ontrtfl = 'On-Treatment Flag'
    astdy   = 'Analysis Start Day relative to ref start'
  ;
run;

%put NOTE: 04_derive_adae.sas complete. Output: ADAM.ADAE;
