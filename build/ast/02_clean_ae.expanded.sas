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
data work.ae_stage;
set raw.ae;
aestdt = (input(substr(strip(aestdtc), 1, 10), ?? yymmdd10.));
aeendt = (input(substr(strip(aeendtc), 1, 10), ?? yymmdd10.));
format aestdt aeendt yymmdd10.;
length aesev_std $10;
if upcase(strip(aesev)) in ('MILD','1') then aesev_std = 'MILD';
else if upcase(strip(aesev)) in ('MODERATE','MOD','2') then aesev_std = 'MODERATE';
else if upcase(strip(aesev)) in ('SEVERE','SEV','3') then aesev_std = 'SEVERE';
aesevn = ((case
     when upcase(strip(aesev_std)) = 'MILD'     then 1
     when upcase(strip(aesev_std)) = 'MODERATE' then 2
     when upcase(strip(aesev_std)) = 'SEVERE'   then 3
     else .
   end));
if missing(aestdt) then delete;
if missing(aeterm) then delete;
if not missing(aeendt) then aedur = aeendt - aestdt + 1;
run;
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
    max_aesevn = 'Subject max severity (rank)';
run;
%put NOTE: 02_clean_ae.sas complete. Output: ADAM.AE_CLEAN;