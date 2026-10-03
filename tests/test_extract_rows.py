# Finding tables, reading year columns and page numbers, and reading small pages built from real report lines.
import pytest
from extract_rows import (column_layout, extract_page, find_page, printed_page_number, quarter_first, year_runs)

NO_ESTIMATES = {"years": set(), "lines": {}, "marked": set()}


# --- year columns -------------------------------------------------------------------------------------
def test_years_newest_first_10k():
    assert year_runs("(in thousands, except percentages) 2024 2023 2022 2024 vs. 2023") == [["FY2024", "FY2023", "FY2022"]]


def test_years_fy_labels_lynas():
    assert year_runs("Sales by tonnage and value FY26 FY25 FY24 FY23 change") == [["FY2026", "FY2025", "FY2024", "FY2023"]]


def test_years_oldest_first():
    assert year_runs("2022 2023 2024 2025 2026") == [["FY2022", "FY2023", "FY2024", "FY2025", "FY2026"]]


def test_years_written_as_dates():
    # Lynas: this header starts with "30", so it first looked like a row of numbers
    assert year_runs("30 June 2019 30 June 2020 30 June 2021") == [["FY2019", "FY2020", "FY2021"]]


def test_two_blocks_quarter_and_year_neo():
    assert year_runs("2025 2024 % 2025 2024 %") == [["FY2025", "FY2024"], ["FY2025", "FY2024"]]


def test_change_columns_are_not_years():
    assert year_runs("2025 vs. 2024 vs. 2025 vs. 2024 vs.") == []


def test_which_block_comes_first():
    assert quarter_first("($000s, except volume) Three Months Ended Year ended") is True
    assert quarter_first("Year Ended Three Months Ended") is False


def test_quarter_first_takes_the_second_block():
    assert column_layout("2025 2024 % 2025 2024 %", True) == (["FY2025", "FY2024"], 2)
    assert column_layout("2022 2021 Change % 2022 2021 Change %", False) == (["FY2022", "FY2021"], 0)


# --- printed page numbers -----------------------------------------------------------------------------
@pytest.mark.parametrize("text, page", [
    ("body\n44", 44),                                                         # 10-K
    ("body\nLynas Rare Earths Limited | 2026 Annual Report 65", 65),        # Lynas, number at the end
    ("body\n18 www.LynasRareEarths.com", 18),                                # Lynas, number at the start
    ("body\nConsolidated Financial Report incorporating 11\nAppendix 4E", 11),  # number on the line above
    ("body\nNeo Performance Materials Inc. 18 2025 Management's Discussion", 18),  # number mid-footer
    ("133\nbody\nU.S. Geological Survey, Mineral Commodity Summaries, February 2026", 133),  # USGS header
    ("14 5\nbody\nU.S. Geological Survey, Mineral Commodity Summaries, January", 145),  # spaced digits
    ("RARE EARTHS\nbody\nU.S. Geological Survey, Mineral Commodity Summaries, February 2026", None),  # a year is not a page
])
def test_printed_page_number(text, page):
    assert printed_page_number(text) == page


# --- finding a table's page ---------------------------------------------------------------------------
PAGES = ["Contents 10.1 Magnequench", "10.1 Magnequench Sales volume (tonnes) 6,063", "Revenue consists of"]


def test_anchor_found():
    assert find_page(PAGES, "Revenue consists") == 3


def test_anchor_alternatives_tried_in_order():
    assert find_page(PAGES, "Not printed anywhere | Revenue consists") == 3


def test_anchor_needs_both_phrases():
    # skips the contents page, which names the segment but has no table
    assert find_page(PAGES, "10.1 Magnequench && Sales volume (tonnes)") == 2


def test_anchor_on_two_pages_stops_the_run():
    with pytest.raises(SystemExit):
        find_page(PAGES, "10.1 Magnequench")


def test_anchor_missing():
    assert find_page(PAGES, "Not printed anywhere") is None


# --- reading a page -----------------------------------------------------------------------------------
def values_by_year(rows):
    return {r["period"]: r["value_reported"] for r in rows}


def test_full_year_block_after_quarter_block_neo_2025():
    page = "\n".join(["($000s, except volume) Three Months Ended Year ended",
                      "2025 2024 % 2025 2024 %",
                      "Sales volume (tonnes) 2,988 3,157 (5.4%) 13,216 12,413 6.5%",
                      "22"])
    rows = extract_page(page, "consolidated", 24, ["FY2025", "FY2024", "FY2023"], 1, NO_ESTIMATES)
    assert values_by_year(rows) == {"FY2025": 13216.0, "FY2024": 12413.0}   # not the Q4 figures


def test_header_after_its_rows_neo_2024():
    page = "\n".join(["Sales volume (tonnes) . . . 3,157 3,144 0.4% 12,413 12,970 (4.3%)",
                      "($000s, except volume) Three Months Ended Year Ended",
                      "2024 2023 % 2024 2023 %",
                      "18"])
    rows = extract_page(page, "consolidated", 18, ["FY2024", "FY2023", "FY2022"], 1, NO_ESTIMATES)
    assert values_by_year(rows) == {"FY2024": 12413.0, "FY2023": 12970.0}


def test_quarterly_table_gives_no_years_neo_2025():
    page = "\n".join(["($000s, except for per share 2025 2024",
                      "amounts) Q4 Q3 Q2 Q1 Q4 Q3 Q2 Q1",
                      "Revenue $ 120,270 $ 122,213 $ 114,700 $ 121,610 $ 134,903 $ 111,281 $ 107,549 $ 122,095",
                      "22"])
    assert extract_page(page, "rare_metals", 24, ["FY2025", "FY2024", "FY2023"], 1000, NO_ESTIMATES) == []


def test_scale_line_applies_to_rows_below():
    page = "\n".join(["(in thousands, except percentages) 2025 2024 2023",
                      "Total revenue $ 224,441 $ 203,855 $ 253,445",
                      "44"])
    rows = extract_page(page, "revenue", 48, ["FY2025", "FY2024", "FY2023"], None, NO_ESTIMATES)
    assert {r["scale_factor"] for r in rows} == {1000}
    assert rows[0]["printed_page"] == 44 and rows[0]["raw_text"] == "$ 224,441"


def test_estimate_marks_are_carried():
    page = "\n".join(["2023 2024", "Australia 16,000 13,000 5,700,000", "145"])
    estimates = {"years": {"FY2024"}, "lines": {}, "marked": set()}
    rows = extract_page(page, "world", 2, ["FY2025", "FY2024", "FY2023"], None, estimates)
    assert {r["period"]: r["estimate"] for r in rows} == {"FY2023": False, "FY2024": True}
