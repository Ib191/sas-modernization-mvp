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
data work.dm_stage;
set raw.dm;
rfstdt = (input(substr(strip(rfstdtc), 1, 10), ?? yymmdd10.));
rfendt = (input(substr(strip(rfendtc), 1, 10), ?? yymmdd10.));
brthdt = (input(substr(strip(brthdtc), 1, 10), ?? yymmdd10.));
format rfstdt rfendt brthdt yymmdd10.;
if not missing(brthdt) and not missing(rfstdt) then
    age_derived = (floor((rfstdt - brthdt) / 365.25));
else
    age_derived = .;
if missing(age) then age = age_derived;
if not missing(rfstdt) and not missing(rfendt) then
    trtdurd = rfendt - rfstdt + 1;
run;
proc sort data=work.dm_stage;
by usubjid descending recordcreatedt;
run;
data work.dm_dedup;
set work.dm_stage;
by usubjid;
if first.usubjid;
run;
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
    agegrp      = 'Age group';
keep usubjid age age_derived agegrp sex sex_decode race
       arm arm_decode rfstdt rfendt trtdurd siteid;
run;
%put NOTE: 01_clean_dm.sas complete. Output: ADAM.DM_CLEAN;