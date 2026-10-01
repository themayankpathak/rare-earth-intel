import re
import sys
import pdfplumber
import pandas as pd
from text_cleaner import parse_line

# Which company and filing to read, e.g. "python scripts/extract_rows.py lynas FY2026".
COMPANY, FILING = sys.argv[1], sys.argv[2]
company = pd.read_csv("config/companies.csv", dtype=str).set_index("company").loc[COMPANY]
PDF_PATH = f"data/raw/{company['file_prefix']}_{FILING}.pdf"
TABLES = f"config/{COMPANY}_tables.csv"  # which tables to read, and the text that identifies each one's page
OUTPUT = f"data/interim/{COMPANY}_extracted_rows_{FILING}.csv"

# Until a table header says otherwise, assume the filing year and the two years before it.
YEAR = int(FILING[2:])
DEFAULT_YEARS = [f"FY{YEAR}", f"FY{YEAR - 1}", f"FY{YEAR - 2}"]


def find_page(texts, anchors):
    # anchors: one or more phrases separated by " | ", tried in order (newer wording first).
    # Return the one page (counting from 1) whose text contains the first phrase that is found.
    # Line breaks are flattened first, so a phrase split over two lines still matches.
    for anchor in anchors.split(" | "):
        pages = [i + 1 for i, text in enumerate(texts) if anchor in " ".join(text.split())]
        if len(pages) > 1:
            sys.exit(f"STOP: '{anchor}' found on several pages {pages} of {FILING}. Make the anchor more specific.")
        if pages:
            return pages[0]
    return None


def printed_page_number(text):
    # The page number printed in the footer: a number at the end or start of the last line,
    # or of the line before it when the very last line is a label ("... Financial Report 11" / "Appendix 4E").
    # "44" (10-K) / "Lynas Rare Earths Limited | 2026 Annual Report 65" / "18 www.LynasRareEarths.com"
    for line in reversed(text.strip().splitlines()[-2:]):
        words = line.split()
        for word in (words[-1:] + words[:1]):
            if word.isdigit():
                return int(word)
    return None


MONTHS = {"January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"}


def years_in_header(line):
    # The year columns of a table, read from a header line, in the order printed:
    #   "2024 2023 2022 2024 vs. 2023"   -> FY2024, FY2023, FY2022   (10-K, newest first)
    #   "FY26 FY25 FY24 FY23 change"      -> FY2026, FY2025, FY2024, FY2023   (Lynas)
    #   "2022 2023 2024 2025 2026"        -> FY2022 ... FY2026   (Lynas five-year table, oldest first)
    #   "30 June 2017 30 June 2018 ..."   -> FY2017, FY2018, ...   (day and month words are skipped)
    # Take the first run of years that step by one in the same direction; stop at anything else.
    years = []
    for token in line.split():
        # Skip day and month words ("30", "June"): a year is four digits or "FY" plus two digits.
        if token in MONTHS or (token.isdigit() and len(token) <= 2):
            continue
        match = re.fullmatch(r"(?:FY)?((?:19|20)\d\d|\d\d)", token)
        year = None
        if match:
            digits = match.group(1)
            year = int(digits) if len(digits) == 4 else (2000 + int(digits) if token.startswith("FY") else None)
        steps_on = year is not None and (len(years) < 2 and (not years or abs(year - years[-1]) == 1)
                                         or len(years) >= 2 and year - years[-1] == years[-1] - years[-2])
        if steps_on:
            years.append(year)
        elif years:
            break
    return [f"FY{y}" for y in years] if len(years) >= 2 else []


def extract_page(text, table, pdf_page, years, scale):
    # Read one page top to bottom and return one row per number.
    # years: the year columns until a header says otherwise ("none" tables keep ["not_applicable"]).
    # scale: starting scale, for pages with no scale line.
    printed_page = printed_page_number(text)
    group = None
    rows = []

    for line in text.splitlines():
        # A scale line ("in thousands", "in whole units") applies to every number below it.
        is_scale_line = "in thousands" in line or "in whole units" in line
        if is_scale_line:
            scale = 1000 if "in thousands" in line else 1

        label, values = parse_line(line, max_values=len(years))
        # A line with no values, or no label, may be a table header naming the year columns (two or more years).
        # "30 June 2019 30 June 2020 ..." has no label: it starts with "30", so it reads as numbers at first.
        if (is_scale_line or not values or not label) and years != ["not_applicable"] and years_in_header(line):
            years = years_in_header(line)
            continue
        if is_scale_line or not label:
            continue
        # A short line with no numbers is a heading: remember it as the group.
        if not values:
            if len(label.split()) < 6 and not label.endswith("."):
                group = label
            continue

        # Pair each value with its year column, left to right.
        for year, (raw, number) in zip(years, values):
            rows.append({
                "table": table,
                "printed_page": printed_page,
                "pdf_page": pdf_page,
                "group": group,
                "label": label,
                "period": year,
                "raw_text": raw,
                "value_reported": number,
                "scale_factor": scale,
            })
    return rows


# Read the text of every page once (slow on long filings: a minute or two).
print(f"Reading {PDF_PATH} ...")
with pdfplumber.open(PDF_PATH) as pdf:
    texts = [page.extract_text() or "" for page in pdf.pages]

# Read the tables in the order they are listed in the tables file (this order sets the row_ids).
tables = pd.read_csv(TABLES, dtype=str).fillna("")
rows = []
for _, t in tables.iterrows():
    pdf_page = find_page(texts, t["anchor"])
    if pdf_page is None:
        print(f"  {t['table']:<13} not in this filing, skipped")
        continue
    # Year columns: read from the table header, or none (the composition table has no year).
    years = DEFAULT_YEARS if t["years"] == "header" else ["not_applicable"]
    scale = int(t["start_scale"]) if t["start_scale"] else None
    found = extract_page(texts[pdf_page - 1], t["table"], pdf_page, years, scale)
    print(f"  {t['table']:<13} pdf p.{pdf_page} (printed p.{printed_page_number(texts[pdf_page - 1])}): {len(found)} values")
    rows += found

table = pd.DataFrame(rows)
table.to_csv(OUTPUT, index=False)
print(f"{len(table)} rows saved to {OUTPUT}")
