/******************************************************************************
* Program     : setup.sas
* Description : Environment setup for CTX-2024-001 ADaM pipeline.
*               %include this at the top of every program.
* Owner       : Stats Programming
******************************************************************************/

options
  mprint mlogic symbolgen           /* macro debugging - keep on for audit */
  missing=' '                       /* display missing as blank in output  */
  fmtsearch=(work)                  /* find user-defined formats           */
  nodate nonumber
;

/* Project root - set via -SET PROJ_ROOT at sasautos invocation, or default */
%let PROJ_ROOT = %sysfunc(getoption(SASUSER));

libname raw   "&PROJ_ROOT/input_data";
libname adam  "&PROJ_ROOT/adam";
libname tgt   "&PROJ_ROOT/output";

%include "&PROJ_ROOT/sas_codebase/config/formats.sas";
%include "&PROJ_ROOT/sas_codebase/macros/util_macros.sas";

%put NOTE: Setup complete. PROJ_ROOT=&PROJ_ROOT;
