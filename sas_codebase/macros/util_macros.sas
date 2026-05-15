/******************************************************************************
* Program     : util_macros.sas
* Description : Common utility macros for the CTX-2024-001 ADaM pipeline
* Owner       : Stats Programming (originally J. Park, 2022; maintained team)
*
* Conventions:
*   - All macros assume formats.sas has been %included
*   - Date macros expect ISO 8601 strings (YYYY-MM-DD); see iso_to_sasdate
*   - Several macros depend on global symbols set by 03_derive_adsl.sas;
*     these are noted inline.
******************************************************************************/


/*---------------------------------------------------------------------------*
 * iso_to_sasdate: convert an ISO 8601 char date to a SAS date number.
 *   var = name of the character variable holding 'YYYY-MM-DD' text.
 *   Returns: numeric SAS date, or . if the input is missing/invalid.
 *---------------------------------------------------------------------------*/
%macro iso_to_sasdate(var=);
  input(substr(strip(&var), 1, 10), ?? yymmdd10.)
%mend iso_to_sasdate;


/*---------------------------------------------------------------------------*
 * calc_age: integer age in years between two SAS dates.
 *   birth = SAS date of birth
 *   ref   = SAS reference date
 *   Uses 365.25 day-year (matches legacy Stata code we replaced).
 *---------------------------------------------------------------------------*/
%macro calc_age(birth=, ref=);
  floor((&ref - &birth) / 365.25)
%mend calc_age;


/*---------------------------------------------------------------------------*
 * is_treatment_emergent: 1 if AE onset is on or after first treatment.
 *   ae_start = SAS date of AE onset
 *
 *   IMPORTANT: this macro reads the global symbol &TRT_START_DT, which
 *   is set per-subject inside 03_derive_adsl.sas. Calling this macro
 *   outside an ADSL-aware data step will return wrong results silently.
 *
 *   Historical note: the original spec said "first dose date" but the
 *   implementation uses randomization date. See SP-227 (open).
 *---------------------------------------------------------------------------*/
%macro is_treatment_emergent(ae_start=);
  (not missing(&ae_start) and &ae_start >= &TRT_START_DT)
%mend is_treatment_emergent;


/*---------------------------------------------------------------------------*
 * sev_to_rank: map severity text to numeric rank.
 *   sev = char severity code from raw data
 *   Returns: 1=Mild, 2=Moderate, 3=Severe, . otherwise.
 *---------------------------------------------------------------------------*/
%macro sev_to_rank(sev=);
  (case
     when upcase(strip(&sev)) = 'MILD'     then 1
     when upcase(strip(&sev)) = 'MODERATE' then 2
     when upcase(strip(&sev)) = 'SEVERE'   then 3
     else .
   end)
%mend sev_to_rank;


/*---------------------------------------------------------------------------*
 * safe_div: division that returns missing on zero/missing denominator.
 *---------------------------------------------------------------------------*/
%macro safe_div(num=, den=);
  (case when missing(&den) or &den = 0 then . else &num / &den end)
%mend safe_div;
