"""04_derive_adae — Generated from build/specs/04_derive_adae.md.

Output: adam.adae (build/target/output/adae.{csv,parquet}).
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUTPUT_DIR, STATE_DIR, to_date, write_outputs  # noqa: E402


OUTPUT_COLS = [
    "USUBJID", "AETERM", "AESTDT", "AEENDT", "AEDUR", "AESEV",
    "AESEV_STD", "AESEVN", "AESER", "AESEQ", "MAX_AESEV", "MAX_AESEVN",
    "AGE", "AGEGRP", "SEX", "ARM", "ARM_DECODE", "RFSTDT", "RFENDT",
    "SAFFL", "ITTFL", "TRTEMFL", "ONTRTFL", "ASTDY",
]


def main() -> None:
    # Step 1 — read AE_CLEAN as string. Reading with default dtype inference
    # promotes AESEVN/AEDUR (Int64 with nulls) to float64, which round-trips
    # to '1.0' / '8.0' in CSV instead of '1' / '8'. The downstream ops
    # convert dates inline, so string passthrough preserves formatting.
    ae = pd.read_csv(OUTPUT_DIR / "ae_clean.csv", dtype=str,
                      keep_default_na=False, na_values=[""])

    # Step 2 — read ADSL subset (also as string)
    adsl = pd.read_csv(OUTPUT_DIR / "adsl.csv", dtype=str,
                        keep_default_na=False, na_values=[""])
    adsl_sub = adsl[["USUBJID", "AGE", "AGEGRP", "SEX", "ARM",
                       "ARM_DECODE", "RFSTDT", "RFENDT", "SAFFL", "ITTFL"]]

    # Step 3 — load cohort-level TRT_START_DT from state
    trt_start_dt = pd.to_datetime(
        (STATE_DIR / "trt_start_dt.txt").read_text(encoding="utf-8").strip(),
        format="%Y-%m-%d",
    )

    # Step 4 — inner join on USUBJID
    adae = ae.merge(adsl_sub, on="USUBJID", how="inner")

    # Step 5 — TRTEMFL: cohort-level scalar comparison (ambiguity #1)
    aestdt = to_date(adae["AESTDT"])
    adae["TRTEMFL"] = (
        aestdt.notna() & (aestdt >= trt_start_dt)
    ).map({True: "Y", False: "N"})

    # Step 6 — ONTRTFL: AE start within RFSTDT..RFENDT, all non-null
    rfstdt = to_date(adae["RFSTDT"])
    rfendt = to_date(adae["RFENDT"])
    adae["ONTRTFL"] = (
        aestdt.notna() & rfstdt.notna() & rfendt.notna()
        & (aestdt >= rfstdt) & (aestdt <= rfendt)
    ).map({True: "Y", False: "N"})

    # Step 7 — ASTDY = (AESTDT - RFSTDT).days + 1 when both present.
    # Render as string ('' for null) to match ground-truth CSV formatting.
    diff = (aestdt - rfstdt).dt.days
    adae["ASTDY"] = (diff + 1).apply(
        lambda x: str(int(x)) if pd.notna(x) else ""
    )

    # Step 8 — column order
    out = adae[OUTPUT_COLS].copy()
    out = out.sort_values(by=["USUBJID", "AESEQ"], kind="mergesort").reset_index(drop=True)
    write_outputs(out, "adae")


if __name__ == "__main__":
    main()
