"""02_clean_ae — Generated from build/specs/02_clean_ae.md.

Output: adam.ae_clean (build/target/output/ae_clean.{csv,parquet}).
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import INPUT_DIR, to_date, fmt_date, write_outputs  # noqa: E402


# Spec step 3: severity standardization. GRADE * intentionally unmapped
# per ambiguity #2 (SP-184).
SEV_STD_MAP = {
    "MILD": "MILD", "1": "MILD",
    "MODERATE": "MODERATE", "MOD": "MODERATE", "2": "MODERATE",
    "SEVERE": "SEVERE", "SEV": "SEVERE", "3": "SEVERE",
}
SEVN_MAP = {"MILD": 1, "MODERATE": 2, "SEVERE": 3}

OUTPUT_COLS = [
    "USUBJID", "AESEQ", "AETERM", "AESTDT", "AEENDT", "AEDUR",
    "AESEV", "AESEV_STD", "AESEVN", "AESER", "MAX_AESEV", "MAX_AESEVN",
]


def main() -> None:
    ae = pd.read_csv(INPUT_DIR / "ae.csv",
                      keep_default_na=False, na_values=[""])

    # Step 2 — date conversion
    ae["AESTDT_d"] = to_date(ae["AESTDTC"])
    ae["AEENDT_d"] = to_date(ae["AEENDTC"])

    # Step 3 — AESEV → AESEV_STD via map. Unrecognized → blank "".
    ae["AESEV_STD"] = (
        ae["AESEV"].fillna("").str.strip().str.upper().map(SEV_STD_MAP)
        .fillna("")
    )

    # Step 4 — AESEVN
    ae["AESEVN"] = ae["AESEV_STD"].map(SEVN_MAP).astype("Int64")

    # Step 5 — drop rows with missing AESTDT or AETERM. NB: AETERM is
    # treated as missing if blank (already null because of na_values).
    ae = ae[ae["AESTDT_d"].notna() & ae["AETERM"].fillna("").str.strip().ne("")]

    # Step 6 — AEDUR
    dur = (ae["AEENDT_d"] - ae["AESTDT_d"]).dt.days
    ae["AEDUR"] = (dur + 1).astype("Int64")

    # Step 7 — AESEQ within USUBJID, ordered by AESTDT, AETERM.
    ae = ae.sort_values(by=["USUBJID", "AESTDT_d", "AETERM"],
                          kind="mergesort").reset_index(drop=True)
    ae["AESEQ"] = ae.groupby("USUBJID").cumcount() + 1

    # Step 8 — MAX_AESEV / MAX_AESEVN per USUBJID.
    # Tie-break: take the last row after sorting by (USUBJID, AESEVN) with
    # nulls first. This matches the SAS sort semantics where missing values
    # sort low.
    rank_helper = ae[["USUBJID", "AESEVN", "AESEV_STD"]].copy()
    # NaN AESEVN sorts before integers in mergesort with na_position='first'
    rank_helper = rank_helper.sort_values(
        by=["USUBJID", "AESEVN"], kind="mergesort",
        na_position="first",
    )
    last_per_subj = rank_helper.drop_duplicates(subset=["USUBJID"], keep="last")
    last_per_subj = last_per_subj.rename(
        columns={"AESEVN": "MAX_AESEVN", "AESEV_STD": "MAX_AESEV"}
    )
    ae = ae.merge(last_per_subj, on="USUBJID", how="left")

    # Format dates back to ISO strings
    ae["AESTDT"] = fmt_date(ae["AESTDT_d"])
    ae["AEENDT"] = fmt_date(ae["AEENDT_d"])

    out = ae[OUTPUT_COLS].copy()
    out = out.sort_values(by=["USUBJID", "AESEQ"], kind="mergesort").reset_index(drop=True)
    write_outputs(out, "ae_clean")


if __name__ == "__main__":
    main()
