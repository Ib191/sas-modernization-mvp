"""05_summary_safety — Generated from build/specs/05_summary_safety.md.

Outputs:
  - adam.ae_summary   (build/target/output/ae_summary.{csv,parquet})
  - adam.ae_incidence (build/target/output/ae_incidence.{csv,parquet})
"""
from __future__ import annotations

from pathlib import Path
import sys

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUTPUT_DIR, write_outputs  # noqa: E402


INCIDENCE_COLS = [
    "ARM", "ARM_DECODE", "WORST_SEVERITY", "WORST_SEVERITY_RANK",
    "N_SUBJ_WITH_AE", "N_SUBJ_TOTAL", "INCIDENCE_RATE",
]
SUMMARY_COLS = ["ARM", "ARM_DECODE", "SEVERITY", "N_EVENTS", "N_SERIOUS"]


def main() -> None:
    adsl = pd.read_csv(OUTPUT_DIR / "adsl.csv",
                        keep_default_na=False, na_values=[""])
    adae = pd.read_csv(OUTPUT_DIR / "adae.csv",
                        keep_default_na=False, na_values=[""])

    con = duckdb.connect()
    con.register("adsl", adsl)
    con.register("adae", adae)

    # Step 2 — denominators per (ARM, ARM_DECODE) on SAFFL='Y'
    denom = con.execute("""
        SELECT ARM, ARM_DECODE, COUNT(DISTINCT USUBJID) AS N_SUBJ
        FROM adsl
        WHERE SAFFL = 'Y'
        GROUP BY ARM, ARM_DECODE
    """).df()
    con.register("denom", denom)

    # Step 3-4 — subject-level worst severity, then count subjects per
    # (ARM, MAX_AESEV, MAX_AESEVN). TRTEMFL='Y' filter applied.
    ae_counts = con.execute("""
        WITH ae_subj AS (
            SELECT DISTINCT
                ARM, ARM_DECODE, USUBJID, MAX_AESEV, MAX_AESEVN
            FROM adae
            WHERE TRTEMFL = 'Y'
        )
        SELECT
            ARM, ARM_DECODE, MAX_AESEV, MAX_AESEVN,
            COUNT(*) AS N_SUBJ_WITH_AE
        FROM ae_subj
        GROUP BY ARM, ARM_DECODE, MAX_AESEV, MAX_AESEVN
    """).df()
    con.register("ae_counts", ae_counts)

    # Step 5 — ae_incidence
    incidence = con.execute("""
        SELECT
            c.ARM,
            c.ARM_DECODE,
            c.MAX_AESEV   AS WORST_SEVERITY,
            c.MAX_AESEVN  AS WORST_SEVERITY_RANK,
            c.N_SUBJ_WITH_AE,
            d.N_SUBJ      AS N_SUBJ_TOTAL,
            CASE WHEN d.N_SUBJ IS NULL OR d.N_SUBJ = 0 THEN NULL
                 ELSE ROUND(c.N_SUBJ_WITH_AE * 1.0 / d.N_SUBJ, 4)
            END           AS INCIDENCE_RATE
        FROM ae_counts AS c
        LEFT JOIN denom AS d ON c.ARM = d.ARM
        ORDER BY c.ARM, c.MAX_AESEVN
    """).df()
    incidence = incidence[INCIDENCE_COLS]
    write_outputs(incidence, "ae_incidence")

    # Step 6 — ae_summary: counts of TE AEs by ARM × AESEV_STD.
    # Cast SUM(CASE...) to INTEGER explicitly: duckdb's SUM returns
    # DECIMAL(38, ...) which round-trips to float64 in pandas and writes
    # '0.0' instead of '0' to CSV.
    summary = con.execute("""
        SELECT
            ARM,
            ARM_DECODE,
            AESEV_STD AS SEVERITY,
            COUNT(*)::INTEGER AS N_EVENTS,
            SUM(CASE WHEN AESER = 'Y' THEN 1 ELSE 0 END)::INTEGER AS N_SERIOUS
        FROM adae
        WHERE TRTEMFL = 'Y'
        GROUP BY ARM, ARM_DECODE, AESEV_STD
        ORDER BY ARM, AESEV_STD NULLS FIRST
    """).df()
    summary = summary[SUMMARY_COLS]
    write_outputs(summary, "ae_summary")


if __name__ == "__main__":
    main()
