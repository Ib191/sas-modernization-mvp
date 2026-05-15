"""Schema for `raw.dm`. Producer: `(input)`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'raw.dm'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'USUBJID',
    'AGE',
    'SEX',
    'RACE',
    'ARM',
    'SITEID',
    'BRTHDTC',
    'RFSTDTC',
    'RFENDTC',
    'RECORDCREATEDT',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'USUBJID': 'object',  # string, nullable=False, e.g. CTX-001 | CTX-002 | CTX-003
    'AGE': 'Int64',  # int, nullable=True, e.g. 69 | 59 | 57
    'SEX': 'object',  # string, nullable=False, e.g. M | U | U
    'RACE': 'object',  # string, nullable=False, e.g. WHITE | WHITE | WHITE
    'ARM': 'object',  # string, nullable=False, e.g. DRUG_X_HI | PLACEBO | PLACEBO
    'SITEID': 'object',  # string, nullable=False, e.g. 02 | 01 | 04
    'BRTHDTC': 'object',  # date, nullable=False, e.g. 1954-08-31 | 1964-06-13 | 1966-10-06
    'RFSTDTC': 'object',  # date, nullable=False, e.g. 2024-01-30 | 2024-01-17 | 2024-02-29
    'RFENDTC': 'object',  # date, nullable=False, e.g. 2024-03-12 | 2024-02-15 | 2024-05-08
    'RECORDCREATEDT': 'object',  # date, nullable=False, e.g. 2024-02-04 | 2024-01-18 | 2024-03-01
}
