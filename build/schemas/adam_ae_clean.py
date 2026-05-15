"""Schema for `adam.ae_clean`. Producer: `02_clean_ae`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'adam.ae_clean'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'USUBJID',
    'AESEQ',
    'AETERM',
    'AESTDT',
    'AEENDT',
    'AEDUR',
    'AESEV',
    'AESEV_STD',
    'AESEVN',
    'AESER',
    'MAX_AESEV',
    'MAX_AESEVN',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'USUBJID': 'object',  # string, nullable=False, e.g. CTX-001 | CTX-001 | CTX-003
    'AESEQ': 'Int64',  # int, nullable=False, e.g. 1 | 2 | 1
    'AETERM': 'object',  # string, nullable=False, e.g. NAUSEA | FATIGUE | HEADACHE
    'AESTDT': 'object',  # date, nullable=False, e.g. 2024-02-18 | 2024-03-03 | 2024-02-28
    'AEENDT': 'object',  # date, nullable=True, e.g. 2024-02-22 | 2024-04-25 | 2024-02-28
    'AEDUR': 'Int64',  # int, nullable=True, e.g. 5 | 10 | 8
    'AESEV': 'object',  # string, nullable=False, e.g. SEVERE | 3 | MODERATE
    'AESEV_STD': 'object',  # string, nullable=True, e.g. SEVERE | SEVERE | MODERATE
    'AESEVN': 'Int64',  # int, nullable=True, e.g. 3 | 3 | 2
    'AESER': 'object',  # string, nullable=False, e.g. N | N | N
    'MAX_AESEV': 'object',  # string, nullable=False, e.g. SEVERE | SEVERE | MODERATE
    'MAX_AESEVN': 'Int64',  # int, nullable=False, e.g. 3 | 3 | 2
}
