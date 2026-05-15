"""Schema for `raw.site_lookup`. Producer: `(input)`.

Auto-generated from the knowledge graph. Do not edit by hand.
"""
from __future__ import annotations

DATASET = 'raw.site_lookup'

# Column order matches ground_truth/<dataset>.csv header.
COLUMNS: list[str] = [
    'SITE_ID',
    'SITE_NAME',
    'SITE_COUNTRY',
    'SITE_REGION',
]

# pandas dtype map (None ⇒ leave as-is from read_csv)
DTYPES: dict[str, str] = {
    'SITE_ID': 'Int64',  # int, nullable=False, e.g. 1 | 2 | 3
    'SITE_NAME': 'object',  # string, nullable=False, e.g. Boston Medical Ctr | Toronto General | Charite Berlin
    'SITE_COUNTRY': 'object',  # string, nullable=False, e.g. USA | CAN | DEU
    'SITE_REGION': 'object',  # string, nullable=False, e.g. NA | NA | EU
}
