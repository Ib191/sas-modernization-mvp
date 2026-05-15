"""Shared utilities for the modernized pipeline. Generated from build/specs/.

R1 reminder: this module and the per-program modules MUST NOT read SAS
source. All semantics come from build/specs/<program>.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "input_data"
OUTPUT_DIR = PROJECT_ROOT / "build" / "target" / "output"
STATE_DIR = PROJECT_ROOT / "build" / "target" / "state"


SEX_DECODE_MAP = {"M": "Male", "F": "Female", "U": "Unknown"}
ARM_DECODE_MAP = {
    "PLACEBO": "Placebo",
    "DRUG_X_LOW": "Drug X 50mg",
    "DRUG_X_HI": "Drug X 100mg",
}


def to_date(s: pd.Series) -> pd.Series:
    """ISO 8601 string column → pandas datetime (NaT on failure)."""
    return pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")


def fmt_date(s: pd.Series) -> pd.Series:
    """datetime → ISO 8601 string ('' on NaT)."""
    return s.dt.strftime("%Y-%m-%d").fillna("")


def agegrp(age: int | None) -> str:
    """Protocol age bands per spec 01_clean_dm.md step 9."""
    if age is None or pd.isna(age):
        return ""
    a = int(age)
    if a < 18:
        return "< 18"
    if a <= 39:
        return "18-39"
    if a <= 64:
        return "40-64"
    return "65+"


def write_outputs(df: pd.DataFrame, name: str) -> None:
    """Write CSV (validated against ground truth) and Parquet alongside,
    per the user's choice. Empty floats are rendered as blank in CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / f"{name}.csv"
    pq_path = OUTPUT_DIR / f"{name}.parquet"
    df.to_csv(csv_path, index=False, lineterminator="\n")
    df.to_parquet(pq_path, index=False)
    print(f"  wrote {csv_path.name} ({len(df)} rows) + {pq_path.name}")
