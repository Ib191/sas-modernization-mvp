/******************************************************************************
* Program     : formats.sas
* Description : Format catalog for clinical study CTX-2024-001
* Owner       : Stats Programming
* Last update : 2024-03-12
*
* Notes:
*   - All study-wide controlled vocabularies live here.
*   - %include this BEFORE any program that applies formats.
*   - Custom formats are stored in WORK; production runs should rebuild
*     into a permanent library (see ticket SP-184, not yet done).
******************************************************************************/

proc format library=work;

  /* Sex (CDISC SDTM controlled terms) */
  value $sexfmt
    'M' = 'Male'
    'F' = 'Female'
    'U' = 'Unknown'
    other = 'Missing';

  /* Severity - the CTCAE-style codes the study CRF actually uses */
  value $sevfmt
    'MILD'     = 'Mild'
    'MODERATE' = 'Moderate'
    'SEVERE'   = 'Severe'
    /* NOTE: vendor B sends 'GRADE 1/2/3' instead - not handled here.
       See data_dictionary.md section 4.2. */
    other      = 'Unknown';

  /* Severity numeric ranking (for max-severity-per-subject derivations) */
  value sevrank
    1 = 'Mild'
    2 = 'Moderate'
    3 = 'Severe';

  /* Age groups - protocol-specified bands */
  value agegrp
    low  - 17  = '< 18'
    18   - 39  = '18-39'
    40   - 64  = '40-64'
    65   - high = '65+';

  /* Treatment arms */
  value $armfmt
    'PLACEBO'    = 'Placebo'
    'DRUG_X_LOW' = 'Drug X 50mg'
    'DRUG_X_HI'  = 'Drug X 100mg';

  /* Yes/No flags */
  value $ynfmt
    'Y' = 'Yes'
    'N' = 'No'
    ' ' = 'Not recorded'
    other = 'Unknown';

run;
