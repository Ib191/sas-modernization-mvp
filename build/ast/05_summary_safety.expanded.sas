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
create table work.denom as
  select arm, arm_decode, count(distinct usubjid) as n_subj
  from adam.adsl
  where saffl = 'Y'
  group by arm, arm_decode;
quit;
proc sql;
create table work.ae_subj as
  select distinct
    arm, arm_decode, usubjid, max_aesev, max_aesevn
  from adam.adae
  where trtemfl = 'Y';
quit;
proc sort data=work.ae_subj;
by arm max_aesevn;
run;
proc summary data=work.ae_subj nway;
class arm arm_decode max_aesev max_aesevn;
output out=work.ae_counts(drop=_type_ _freq_ rename=(_freq_=n_subj_with_ae))
         n=n_subj_with_ae;
run;
proc sql;
create table adam.ae_incidence as
  select
    c.arm,
    c.arm_decode,
    c.max_aesev as worst_severity,
    c.max_aesevn as worst_severity_rank,
    c.n_subj_with_ae,
    d.n_subj as n_subj_total,
    ((case when missing(d.n_subj) or d.n_subj = 0 then . else c.n_subj_with_ae / d.n_subj end)) as incidence_rate
  from work.ae_counts as c
  left join work.denom as d
    on c.arm = d.arm
  order by c.arm, c.max_aesevn;
quit;
proc sql;
create table adam.ae_summary as
  select
    arm,
    arm_decode,
    aesev_std as severity,
    count(*) as n_events,
    sum(case when aeser='Y' then 1 else 0 end) as n_serious
  from adam.adae
  where trtemfl = 'Y'
  group by arm, arm_decode, aesev_std
  order by arm, aesev_std;
quit;
%put NOTE: 05_summary_safety.sas complete.;
%put NOTE: Outputs: ADAM.AE_SUMMARY (event counts), ADAM.AE_INCIDENCE (subject incidence);