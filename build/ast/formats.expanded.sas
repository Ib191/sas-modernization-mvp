proc format library=work;
value $sexfmt
    'M' = 'Male'
    'F' = 'Female'
    'U' = 'Unknown'
    other = 'Missing';
value $sevfmt
    'MILD'     = 'Mild'
    'MODERATE' = 'Moderate'
    'SEVERE'   = 'Severe'
     
    other      = 'Unknown';
value sevrank
    1 = 'Mild'
    2 = 'Moderate'
    3 = 'Severe';
value agegrp
    low  - 17  = '< 18'
    18   - 39  = '18-39'
    40   - 64  = '40-64'
    65   - high = '65+';
value $armfmt
    'PLACEBO'    = 'Placebo'
    'DRUG_X_LOW' = 'Drug X 50mg'
    'DRUG_X_HI'  = 'Drug X 100mg';
value $ynfmt
    'Y' = 'Yes'
    'N' = 'No'
    ' ' = 'Not recorded'
    other = 'Unknown';
run;