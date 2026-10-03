# How precisely a printed number is known, and estimate flags.
import pandas as pd
from self_checker import is_estimate, precision_of, step


def row(raw_text, scale, document, notes=None):
    return pd.Series({"raw_text": raw_text, "scale_factor": scale, "source_document": document, "notes": notes})


def test_precision_by_source():
    assert precision_of("usgs_mcs_ED2025.pdf") == "significant"
    assert precision_of("mp-materials_10k_FY2025.pdf") == "printed"


def test_company_numbers_are_exact_to_the_last_digit():
    assert step(row("556.5", 1_000_000, "lynas_financial_FY2025.pdf")) == 100_000
    assert step(row("$ 41,992", 1000, "mp-materials_10k_FY2025.pdf")) == 1000
    assert step(row("45,000", 1, "mp-materials_10k_FY2025.pdf")) == 1


def test_usgs_trailing_zeros_are_rounding():
    assert step(row("45,000", 1, "usgs_mcs_ED2026.pdf")) == 1000
    assert step(row("42,400", 1, "usgs_mcs_ED2026.pdf")) == 100
    assert step(row("134", 1, "usgs_mcs_ED2026.pdf")) == 1


def test_a_dash_is_exactly_zero():
    assert step(row("—", 1, "usgs_mcs_ED2021.pdf")) == 0


def test_estimate_flag():
    assert is_estimate(row("45,000", 1, "usgs_mcs_ED2025.pdf", "Estimate (marked e by the publisher)"))
    assert not is_estimate(row("45,500", 1, "usgs_mcs_ED2026.pdf", None))
