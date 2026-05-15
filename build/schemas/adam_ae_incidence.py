"""Schema for `adam.ae_incidence`. Producer: `05_summary_safety`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'adam.ae_incidence'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'ARM',
    'ARM_DECODE',
    'WORST_SEVERITY',
    'WORST_SEVERITY_RANK',
    'N_SUBJ_WITH_AE',
    'N_SUBJ_TOTAL',
    'INCIDENCE_RATE',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'ARM': 'object',  # string, nullable=False, e.g. DRUG_X_HI | DRUG_X_LOW | DRUG_X_LOW
    'ARM_DECODE': 'object',  # string, nullable=False, e.g. Drug X 100mg | Drug X 50mg | Drug X 50mg
    'WORST_SEVERITY': 'object',  # string, nullable=False, e.g. MODERATE | MILD | MODERATE
    'WORST_SEVERITY_RANK': 'Int64',  # int, nullable=False, e.g. 2 | 1 | 2
    'N_SUBJ_WITH_AE': 'Int64',  # int, nullable=False, e.g. 1 | 1 | 2
    'N_SUBJ_TOTAL': 'Int64',  # int, nullable=False, e.g. 3 | 9 | 9
    'INCIDENCE_RATE': 'float64',  # float, nullable=False, e.g. 0.3333 | 0.1111 | 0.2222
}
