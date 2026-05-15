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
proc sql;
create table work.dm_with_site as
  select
    d.*,
    s.site_name,
    s.site_country,
    s.site_region
  from adam.dm_clean as d
  left join raw.site_lookup as s
    on d.siteid = s.site_id;
quit;
data work.adsl_pre;
set work.dm_with_site;
length saffl ittfl $1;
if not missing(rfstdt) then saffl = 'Y';
else saffl = 'N';
if saffl = 'Y' and arm ne 'PLACEBO' then ittfl = 'Y';
else ittfl = 'N';
run;
proc sql noprint;
select max(rfstdt) into :TRT_START_DT trimmed
  from work.adsl_pre
  where saffl = 'Y';
quit;
%put NOTE: TRT_START_DT set to &TRT_START_DT (numeric SAS date);
data adam.adsl;
set work.adsl_pre;
label
    saffl       = 'Safety Population Flag'
    ittfl       = 'Intent-to-Treat Population Flag'
    site_name   = 'Site name'
    site_country= 'Country'
    site_region = 'Region';
run;
%put NOTE: 03_derive_adsl.sas complete. Output: ADAM.ADSL;