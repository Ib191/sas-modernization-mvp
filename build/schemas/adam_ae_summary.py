"""Schema for `adam.ae_summary`. Producer: `05_summary_safety`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'adam.ae_summary'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'ARM',
    'ARM_DECODE',
    'SEVERITY',
    'N_EVENTS',
    'N_SERIOUS',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'ARM': 'object',  # string, nullable=False, e.g. DRUG_X_HI | DRUG_X_LOW | DRUG_X_LOW
    'ARM_DECODE': 'object',  # string, nullable=False, e.g. Drug X 100mg | Drug X 50mg | Drug X 50mg
    'SEVERITY': 'object',  # string, nullable=True, e.g. MILD | MILD | MODERATE
    'N_EVENTS': 'Int64',  # int, nullable=False, e.g. 1 | 4 | 2
    'N_SERIOUS': 'Int64',  # int, nullable=False, e.g. 0 | 0 | 1
}
