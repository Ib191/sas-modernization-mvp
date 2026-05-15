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