"""03_derive_adsl — Generated from build/specs/03_derive_adsl.md.

Output: adam.adsl (build/target/output/adsl.{csv,parquet}).
Side-effect: writes cohort-level TRT_START_DT to build/target/state/.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    INPUT_DIR, OUTPUT_DIR, STATE_DIR, to_date, write_outputs,
)


OUTPUT_COLS = [
    "USUBJID", "AGE", "AGE_DERIVED", "AGEGRP", "SEX", "SEX_DECODE",
    "RACE", "ARM", "ARM_DECODE", "RFSTDT", "RFENDT", "TRTDURD", "SITEID",
    "SITE_NAME", "SITE_COUNTRY", "SITE_REGION", "SAFFL", "ITTFL",
]


def main() -> None:
    # Step 1 — read upstream dm_clean. Keep SITEID as string.
    dm = pd.read_csv(OUTPUT_DIR / "dm_clean.csv",
                      dtype={"SITEID": "string"},
                      keep_default_na=False, na_values=[""])

    # Step 2-3 — read site_lookup with SITE_ID int, then coerce to
    # zero-padded 2-char string (resolves ambiguity #3).
    sites = pd.read_csv(INPUT_DIR / "site_lookup.csv",
                          keep_default_na=False, na_values=[""])
    sites["SITE_ID_padded"] = sites["SITE_ID"].apply(lambda x: f"{int(x):02d}")

    # Step 4 — left join on SITEID = SITE_ID_padded
    adsl = dm.merge(
        sites[["SITE_ID_padded", "SITE_NAME", "SITE_COUNTRY", "SITE_REGION"]],
        left_on="SITEID", right_on="SITE_ID_padded", how="left",
    ).drop(columns=["SITE_ID_padded"])

    # Step 5 — SAFFL = 'Y' if RFSTDT not null else 'N'
    adsl["SAFFL"] = adsl["RFSTDT"].fillna("").ne("").map({True: "Y", False: "N"})

    # Step 6 — ITTFL = 'Y' if SAFFL='Y' and ARM != 'PLACEBO' else 'N'
    adsl["ITTFL"] = (
        (adsl["SAFFL"].eq("Y")) & (adsl["ARM"].ne("PLACEBO"))
    ).map({True: "Y", False: "N"})

    # Step 7-8 — TRT_START_DT = max RFSTDT over SAFFL='Y'. Persist for
    # downstream programs (cohort-level scalar — ambiguity #1 resolved).
    saffl_y = adsl[adsl["SAFFL"].eq("Y")]
    rf_dates = to_date(saffl_y["RFSTDT"])
    trt_start_dt = rf_dates.max()
    if pd.isna(trt_start_dt):
        raise RuntimeError("no SAFFL='Y' subjects; cannot derive TRT_START_DT")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "trt_start_dt.txt").write_text(
        trt_start_dt.strftime("%Y-%m-%d") + "\n", encoding="utf-8"
    )

    # Step 9 — column order
    out = adsl[OUTPUT_COLS].copy()
    out = out.sort_values(by="USUBJID", kind="mergesort").reset_index(drop=True)
    write_outputs(out, "adsl")
    print(f"  TRT_START_DT = {trt_start_dt.strftime('%Y-%m-%d')} "
          f"(cohort-level, SAFFL='Y' only)")


if __name__ == "__main__":
    main()
