"""Schema for `raw.ae`. Producer: `(input)`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'raw.ae'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'USUBJID',
    'AETERM',
    'AESEV',
    'AESER',
    'AESTDTC',
    'AEENDTC',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'USUBJID': 'object',  # string, nullable=False, e.g. CTX-001 | CTX-001 | CTX-003
    'AETERM': 'object',  # string, nullable=False, e.g. FATIGUE | NAUSEA | ARTHRALGIA
    'AESEV': 'object',  # string, nullable=False, e.g. 3 | SEVERE | MILD
    'AESER': 'object',  # string, nullable=False, e.g. N | N | N
    'AESTDTC': 'object',  # date, nullable=True, e.g. 2024-03-03 | 2024-02-18 | 2024-05-07
    'AEENDTC': 'object',  # date, nullable=True, e.g. 2024-02-22 | 2024-04-25 | 2024-02-24
}
