"""Aggregate-equivalence checks (CLAUDE.md §1.7).

These cross-dataset reconciliations cover the kind of internal consistency
that a row-by-row test can pass coincidentally. They confirm that
`AE_SUMMARY` totals reconcile to `ADAE` event counts and that
`AE_INCIDENCE` denominators match `ADSL.SAFFL='Y'` cohorts.
"""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def adsl(target_output_dir):
    return pd.read_csv(target_output_dir / "adsl.csv", dtype=str,
                        keep_default_na=False, na_values=[""])


@pytest.fixture(scope="module")
def adae(target_output_dir):
    return pd.read_csv(target_output_dir / "adae.csv", dtype=str,
                        keep_default_na=False, na_values=[""])


@pytest.fixture(scope="module")
def ae_summary(target_output_dir):
    return pd.read_csv(target_output_dir / "ae_summary.csv", dtype=str,
                        keep_default_na=False, na_values=[""])


@pytest.fixture(scope="module")
def ae_incidence(target_output_dir):
    return pd.read_csv(target_output_dir / "ae_incidence.csv", dtype=str,
                        keep_default_na=False, na_values=[""])


def test_ae_summary_total_matches_adae_treatment_emergent(adae, ae_summary):
    """Sum of N_EVENTS across AE_SUMMARY = count of ADAE rows where TRTEMFL='Y'."""
    te_count = (adae["TRTEMFL"] == "Y").sum()
    summary_total = ae_summary["N_EVENTS"].astype(int).sum()
    assert te_count == summary_total, (
        f"AE_SUMMARY total events {summary_total} != ADAE TRTEMFL='Y' rows {te_count}"
    )


def test_ae_summary_serious_matches_adae_serious_te(adae, ae_summary):
    """Sum of N_SERIOUS = count of ADAE rows where TRTEMFL='Y' and AESER='Y'."""
    expected = ((adae["TRTEMFL"] == "Y") & (adae["AESER"] == "Y")).sum()
    actual = ae_summary["N_SERIOUS"].astype(int).sum()
    assert expected == actual, f"N_SERIOUS total {actual} != ADAE TE+SAE rows {expected}"


def test_ae_incidence_denominators_match_adsl_saffl(adsl, ae_incidence):
    """AE_INCIDENCE.N_SUBJ_TOTAL per ARM must equal ADSL distinct USUBJID
    where SAFFL='Y' for that ARM."""
    saffl = adsl[adsl["SAFFL"] == "Y"]
    expected = saffl.groupby("ARM")["USUBJID"].nunique().to_dict()
    actual = (ae_incidence.drop_duplicates("ARM")
                .set_index("ARM")["N_SUBJ_TOTAL"].astype(int).to_dict())
    assert actual == expected, (
        f"denominator mismatch: gen={actual}, adsl(SAFFL='Y')={expected}"
    )


def test_ae_incidence_numerators_within_denominator(ae_incidence):
    """For each row, N_SUBJ_WITH_AE must be ≤ N_SUBJ_TOTAL."""
    for _, row in ae_incidence.iterrows():
        assert int(row["N_SUBJ_WITH_AE"]) <= int(row["N_SUBJ_TOTAL"]), (
            f"row violates numerator≤denom: {row.to_dict()}"
        )


def test_adae_subjects_subset_of_adsl(adsl, adae):
    """Every USUBJID in ADAE must exist in ADSL (inner-join semantics)."""
    adsl_ids = set(adsl["USUBJID"])
    adae_ids = set(adae["USUBJID"])
    extras = adae_ids - adsl_ids
    assert not extras, f"ADAE has subjects not in ADSL: {extras}"
