/* %include setup.sas expanded */
options
  mprint mlogic symbolgen            
  missing=' '                        
  fmtsearch=(work)                   
  nodate nonumber;
%let PROJ_ROOT = %sysfunc(getoption(SASUSER));
libname raw   "%sysfunc(getoption(SASUSER))/input_data";
libname adam  "%sysfunc(getoption(SASUSER))/adam";
libname tgt   "%sysfunc(getoption(SASUSER))/output";
%put NOTE: Setup complete. PROJ_ROOT=&PROJ_ROOT;
%if not %symexist(TRT_START_DT) %then %do;
%put WARNING: TRT_START_DT not set. Run 03_derive_adsl.sas first.;
%end;
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
if a and b;
length trtemfl $1;
if ((not missing(aestdt) and aestdt >= &TRT_START_DT)) then trtemfl = 'Y';
else trtemfl = 'N';
length ontrtfl $1;
if not missing(aestdt) and not missing(rfstdt) and not missing(rfendt)
     and rfstdt <= aestdt <= rfendt then ontrtfl = 'Y';
else ontrtfl = 'N';
if not missing(aestdt) and not missing(rfstdt) then
    astdy = aestdt - rfstdt + 1;
run;
data adam.adae;
set work.adae_pre;
label
    trtemfl = 'Treatment Emergent Flag'
    ontrtfl = 'On-Treatment Flag'
    astdy   = 'Analysis Start Day relative to ref start';
run;
%put NOTE: 04_derive_adae.sas complete. Output: ADAM.ADAE;