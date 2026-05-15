"""Schema for `adam.adae`. Producer: `04_derive_adae`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'adam.adae'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'USUBJID',
    'AETERM',
    'AESTDT',
    'AEENDT',
    'AEDUR',
    'AESEV',
    'AESEV_STD',
    'AESEVN',
    'AESER',
    'AESEQ',
    'MAX_AESEV',
    'MAX_AESEVN',
    'AGE',
    'AGEGRP',
    'SEX',
    'ARM',
    'ARM_DECODE',
    'RFSTDT',
    'RFENDT',
    'SAFFL',
    'ITTFL',
    'TRTEMFL',
    'ONTRTFL',
    'ASTDY',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'USUBJID': 'object',  # string, nullable=False, e.g. CTX-001 | CTX-001 | CTX-003
    'AETERM': 'object',  # string, nullable=False, e.g. NAUSEA | FATIGUE | HEADACHE
    'AESTDT': 'object',  # date, nullable=False, e.g. 2024-02-18 | 2024-03-03 | 2024-02-28
    'AEENDT': 'object',  # date, nullable=True, e.g. 2024-02-22 | 2024-04-25 | 2024-02-28
    'AEDUR': 'Int64',  # int, nullable=True, e.g. 5 | 10 | 8
    'AESEV': 'object',  # string, nullable=False, e.g. SEVERE | 3 | MODERATE
    'AESEV_STD': 'object',  # string, nullable=True, e.g. SEVERE | SEVERE | MODERATE
    'AESEVN': 'Int64',  # int, nullable=True, e.g. 3 | 3 | 2
    'AESER': 'object',  # string, nullable=False, e.g. N | N | N
    'AESEQ': 'Int64',  # int, nullable=False, e.g. 1 | 2 | 1
    'MAX_AESEV': 'object',  # string, nullable=False, e.g. SEVERE | SEVERE | MODERATE
    'MAX_AESEVN': 'Int64',  # int, nullable=False, e.g. 3 | 3 | 2
    'AGE': 'Int64',  # int, nullable=False, e.g. 69 | 69 | 57
    'AGEGRP': 'object',  # string, nullable=False, e.g. 65+ | 65+ | 40-64
    'SEX': 'object',  # string, nullable=False, e.g. M | M | U
    'ARM': 'object',  # string, nullable=False, e.g. DRUG_X_HI | DRUG_X_HI | PLACEBO
    'ARM_DECODE': 'object',  # string, nullable=False, e.g. Drug X 100mg | Drug X 100mg | Placebo
    'RFSTDT': 'object',  # date, nullable=False, e.g. 2024-01-30 | 2024-01-30 | 2024-02-29
    'RFENDT': 'object',  # date, nullable=False, e.g. 2024-03-12 | 2024-03-12 | 2024-05-08
    'SAFFL': 'object',  # string, nullable=False, e.g. Y | Y | Y
    'ITTFL': 'object',  # string, nullable=False, e.g. Y | Y | N
    'TRTEMFL': 'object',  # string, nullable=False, e.g. N | N | N
    'ONTRTFL': 'object',  # string, nullable=False, e.g. Y | Y | N
    'ASTDY': 'Int64',  # int, nullable=False, e.g. 20 | 34 | 0
}
