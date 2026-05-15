"""01_clean_dm — Generated from build/specs/01_clean_dm.md.

Output: adam.dm_clean (build/target/output/dm_clean.{csv,parquet}).
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    INPUT_DIR, SEX_DECODE_MAP, ARM_DECODE_MAP, agegrp,
    to_date, fmt_date, write_outputs,
)


OUTPUT_COLS = [
    "USUBJID", "AGE", "AGE_DERIVED", "AGEGRP", "SEX", "SEX_DECODE",
    "RACE", "ARM", "ARM_DECODE", "RFSTDT", "RFENDT", "TRTDURD", "SITEID",
]


def main() -> None:
    # Step 1 — read raw.dm. Keep SITEID as string to preserve leading zeros
    # (spec ambiguity #3 / leading-zero detector in Phase 3).
    dm = pd.read_csv(INPUT_DIR / "dm.csv", dtype={"SITEID": "string"},
                      keep_default_na=False, na_values=[""])

    # Step 2 — convert ISO date strings to dates.
    dm["BRTHDT"] = to_date(dm["BRTHDTC"])
    dm["RFSTDT_d"] = to_date(dm["RFSTDTC"])
    dm["RFENDT_d"] = to_date(dm["RFENDTC"])
    dm["RECORDCREATEDT_d"] = to_date(dm["RECORDCREATEDT"])

    # Step 3 — AGE_DERIVED via integer division by 365 (matches ground truth;
    # see ambiguity #6 — the SAS macro used 365.25 with floor, but ground
    # truth was generated with //365 and R4 takes precedence).
    age_diff = (dm["RFSTDT_d"] - dm["BRTHDT"]).dt.days
    dm["AGE_DERIVED"] = age_diff.apply(
        lambda x: int(x) // 365 if pd.notna(x) else pd.NA
    ).astype("Int64")

    # Step 4 — backfill AGE from AGE_DERIVED where AGE missing. (Synthetic
    # data in the MVP has no missing AGE, but we honour the rule.)
    dm["AGE"] = pd.to_numeric(dm["AGE"], errors="coerce").astype("Int64")
    dm["AGE"] = dm["AGE"].fillna(dm["AGE_DERIVED"])

    # Step 5 — TRTDURD = (RFENDT - RFSTDT).days + 1 when both present.
    trt_diff = (dm["RFENDT_d"] - dm["RFSTDT_d"]).dt.days
    dm["TRTDURD"] = trt_diff.where(trt_diff.notna(),
                                     other=pd.NA).astype("Int64") + 1

    # Step 6 — dedup by USUBJID, keep max RECORDCREATEDT.
    dm = (dm.sort_values(by=["USUBJID", "RECORDCREATEDT_d"],
                          ascending=[True, False], kind="mergesort")
            .drop_duplicates(subset=["USUBJID"], keep="first"))

    # Step 7 — SEX_DECODE
    dm["SEX_DECODE"] = dm["SEX"].map(SEX_DECODE_MAP).fillna("Missing")

    # Step 8 — ARM_DECODE
    dm["ARM_DECODE"] = dm["ARM"].map(ARM_DECODE_MAP).fillna("")

    # Step 9 — AGEGRP from AGE
    dm["AGEGRP"] = dm["AGE"].apply(agegrp)

    # Step 10 — keep + reorder. Format dates back to ISO strings.
    dm["RFSTDT"] = fmt_date(dm["RFSTDT_d"])
    dm["RFENDT"] = fmt_date(dm["RFENDT_d"])

    out = dm[OUTPUT_COLS].copy()
    out = out.sort_values(by="USUBJID", kind="mergesort").reset_index(drop=True)
    write_outputs(out, "dm_clean")


if __name__ == "__main__":
    main()
