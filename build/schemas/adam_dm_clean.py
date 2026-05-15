"""Schema for `adam.dm_clean`. Producer: `01_clean_dm`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'adam.dm_clean'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'USUBJID',
    'AGE',
    'AGE_DERIVED',
    'AGEGRP',
    'SEX',
    'SEX_DECODE',
    'RACE',
    'ARM',
    'ARM_DECODE',
    'RFSTDT',
    'RFENDT',
    'TRTDURD',
    'SITEID',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'USUBJID': 'object',  # string, nullable=False, e.g. CTX-001 | CTX-002 | CTX-003
    'AGE': 'Int64',  # int, nullable=False, e.g. 69 | 59 | 57
    'AGE_DERIVED': 'Int64',  # int, nullable=False, e.g. 69 | 59 | 57
    'AGEGRP': 'object',  # string, nullable=False, e.g. 65+ | 40-64 | 40-64
    'SEX': 'object',  # string, nullable=False, e.g. M | U | U
    'SEX_DECODE': 'object',  # string, nullable=False, e.g. Male | Unknown | Unknown
    'RACE': 'object',  # string, nullable=False, e.g. WHITE | WHITE | WHITE
    'ARM': 'object',  # string, nullable=False, e.g. DRUG_X_HI | PLACEBO | PLACEBO
    'ARM_DECODE': 'object',  # string, nullable=False, e.g. Drug X 100mg | Placebo | Placebo
    'RFSTDT': 'object',  # date, nullable=False, e.g. 2024-01-30 | 2024-01-17 | 2024-02-29
    'RFENDT': 'object',  # date, nullable=False, e.g. 2024-03-12 | 2024-02-15 | 2024-05-08
    'TRTDURD': 'Int64',  # int, nullable=False, e.g. 43 | 30 | 70
    'SITEID': 'object',  # string, nullable=False, e.g. 02 | 01 | 04
}
