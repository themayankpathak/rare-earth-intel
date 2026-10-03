# Reading one line of a report into its label and values. Every example is a real line from a report.
from text_cleaner import parse_line, to_number


def test_dollars_and_negatives_mp_10k():
    label, values = parse_line("Rare earth concentrate $ 41,992 $ 144,363 $ 252,468 $ (102,371) $ (108,105) (71) % (43) %")
    assert label == "Rare earth concentrate"
    assert values == [("$ 41,992", 41992.0), ("$ 144,363", 144363.0), ("$ 252,468", 252468.0)]


def test_parentheses_are_negative():
    assert to_number("(2,789)") == -2789.0


def test_footnote_stripped_and_dash_is_empty():
    label, values = parse_line("Intersegment eliminations(1) (2,789) — — (2,789) — N/M N/M")
    assert label == "Intersegment eliminations"
    assert values == [("(2,789)", -2789.0), ("—", None), ("—", None)]


def test_na_keeps_its_column():
    # MP FY2024: skipping N/A would put a change figure (1,094) under FY2022
    label, values = parse_line("NdPr Production Volume (MTs) 1,294 200 N/A 1,094 N/A 547 % N/A")
    assert values == [("1,294", 1294.0), ("200", 200.0), ("N/A", None)]


def test_percent_kept_in_printed_text():
    assert parse_line("Neodymium-Praseodymium 15.7 %") == ("Neodymium-Praseodymium", [("15.7 %", 15.7)])


def test_footnote_on_label_with_percent():
    assert parse_line("SEG+(1) 1.8 %") == ("SEG+", [("1.8 %", 1.8)])


def test_four_year_columns_lynas():
    label, values = parse_line("Sales revenue (A$m) 977.9 556.5 463.3 739.3 75.7%", max_values=4)
    assert label == "Sales revenue (A$m)"
    assert [v for _, v in values] == [977.9, 556.5, 463.3, 739.3]


def test_dot_leaders_not_in_label_neo():
    label, values = parse_line("Sales volume (tonnes) . . . . . 13,118 15,103 (1,985) (13.1%) 3,193", max_values=2)
    assert label == "Sales volume (tonnes)"
    assert [v for _, v in values] == [13118.0, 15103.0]


def test_usgs_codes_keep_their_column():
    # "Burma NA 5,000 NA": without NA as a placeholder, 5,000 would land in the first year
    label, values = parse_line("Burma NA 5,000 NA", max_values=3)
    assert label == "Burma"
    assert [v for _, v in values] == [None, 5000.0, None]


def test_a_year_is_not_a_value():
    label, values = parse_line("(in thousands, except percentages) 2025 2024 2023 2024 2023")
    assert values == []
