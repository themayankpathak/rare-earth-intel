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
    # anchors: one or more alternatives separated by " | ", tried in order (newer wording first).
    # An alternative can require several phrases on the same page, joined by " && "
    # ("10.1 Magnequench && Sales volume (tonnes)": the segment page, not the table of contents).
    # Return the one page (counting from 1) that matches the first alternative found.
    # Line breaks are flattened first, so a phrase split over two lines still matches.
    for anchor in anchors.split(" | "):
        phrases = anchor.split(" && ")
        pages = [i + 1 for i, text in enumerate(texts)
                 if all(phrase in " ".join(text.split()) for phrase in phrases)]
        if len(pages) > 1:
            sys.exit(f"STOP: '{anchor}' found on several pages {pages} of {FILING}. Make the anchor more specific.")
        if pages:
            return pages[0]
    return None


def printed_page_number(text):
    # The page number printed in the footer: a number at the end or start of the last line,
    # or of the line before it when the very last line is a label ("... Financial Report 11" / "Appendix 4E").
    # "44" (10-K) / "Lynas Rare Earths Limited | 2026 Annual Report 65" / "18 www.LynasRareEarths.com"
    last_lines = list(reversed(text.strip().splitlines()[-2:]))
    for line in last_lines:
        words = line.split()
        for word in (words[-1:] + words[:1]):
            if word.isdigit():
                return int(word)
    # Number in the middle of the footer: "Neo Performance Materials Inc. 18 2025 Management's ..."
    # (one to three digits, so a year like 2025 is never taken for a page number).
    for word in last_lines[0].split():
        if word.isdigit() and len(word) <= 3:
            return int(word)
    return None


MONTHS = {"January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"}


def year_runs(line):
    # Every run of year columns in a header line, in the order printed. A run is two or more years
    # stepping by one in the same direction:
    #   "2024 2023 2022 2024 vs. 2023"        -> [FY2024, FY2023, FY2022]   (10-K, newest first)
    #   "FY26 FY25 FY24 FY23 change"           -> [FY2026 ... FY2023]   (Lynas)
    #   "2022 2023 2024 2025 2026"             -> [FY2022 ... FY2026]   (Lynas five-year table, oldest first)
    #   "30 June 2017 30 June 2018 ..."        -> [FY2017, FY2018, ...]   (day and month words are skipped)
    #   "2025 2024 2023 2025 2024 2023"        -> [FY2025, FY2024, FY2023], [FY2025, FY2024, FY2023]
    #   "2025 2024 % 2025 2024 %"              -> [FY2025, FY2024], [FY2025, FY2024]   (Neo: quarter, year)
    runs, run = [], []
    for token in line.split():
        # Skip day and month words ("30", "June"): a year is four digits or "FY" plus two digits.
        if token in MONTHS or (token.isdigit() and len(token) <= 2):
            continue
        match = re.fullmatch(r"(?:FY)?((?:19|20)\d\d|\d\d)", token)
        year = None
        if match:
            digits = match.group(1)
            year = int(digits) if len(digits) == 4 else (2000 + int(digits) if token.startswith("FY") else None)
        steps_on = year is not None and run and (len(run) < 2 and abs(year - run[-1]) == 1
                                                 or len(run) >= 2 and year - run[-1] == run[-1] - run[-2])
        if steps_on:
            run.append(year)
            continue
        if len(run) >= 2:
            runs.append(run)
        run = [year] if year is not None else []
    if len(run) >= 2:
        runs.append(run)
    return [[f"FY{y}" for y in r] for r in runs]


def years_in_header(line):
    # The first run of year columns in a header line, or [] if there is none.
    runs = year_runs(line)
    return runs[0] if runs else []


def quarter_first(line):
    # True if this header puts a "Three Months Ended" block before the "Year Ended" block (Neo 2024-25);
    # False if the year comes first (Neo 2022-23) or the line names no quarter block at all.
    year_at = max(line.find("Year Ended"), line.find("Year ended"))
    quarter_at = line.find("Three Months")
    return quarter_at != -1 and year_at != -1 and quarter_at < year_at


def column_layout(line, quarter_block_first):
    # From a header line, which year columns hold full-year figures, and how many values come before them.
    # Returns (years, skip) or None if the line is not a header.
    runs = year_runs(line)
    if not runs:
        return None
    if quarter_block_first and len(runs) >= 2:
        return runs[1], len(runs[0])   # quarter block first: the full year is the second block
    return runs[0], 0


def is_header(line, label, values):
    # A line with no values, or no label, may be a table header naming the year columns.
    # "30 June 2019 30 June 2020 ..." has no label: it starts with "30", so it reads as numbers at first.
    scale_line = "in thousands" in line or "in whole units" in line
    return (scale_line or not values or not label) and bool(year_runs(line))


def extract_page(text, table, pdf_page, years, scale):
    # Read one page top to bottom and return one row per number.
    # years: the year columns until a header says otherwise ("none" tables keep ["not_applicable"]).
    # scale: starting scale, for pages with no scale line.
    printed_page = printed_page_number(text)
    group = None
    rows = []
    skip = 0                     # values to pass over before the full-year columns (Neo: the quarter block)
    has_years = years != ["not_applicable"]
    lines = text.splitlines()

    # Look at the page's first table header before reading any rows: the text of a page does not always
    # come out in reading order, and a header can follow its own rows (Neo FY2024 reconciliation table).
    order = False
    if has_years:
        for line in lines:
            order = quarter_first(line) or order
            label, values = parse_line(line, max_values=100)
            if is_header(line, label, values):
                years, skip = column_layout(line, order)
                break
    order = False

    for line in lines:
        # A scale line ("in thousands", "in whole units") applies to every number below it.
        is_scale_line = "in thousands" in line or "in whole units" in line
        if is_scale_line:
            scale = 1000 if "in thousands" in line else 1
        # "Three Months Ended ... Year Ended" says which block of columns comes first.
        if "Three Months" in line and ("Year Ended" in line or "Year ended" in line):
            order = quarter_first(line)

        label, values = parse_line(line, max_values=100)
        if has_years and is_header(line, label, values):
            years, skip = column_layout(line, order)
            continue
        # A line of quarter labels ("amounts) Q4 Q3 Q2 Q1 Q4 Q3 Q2 Q1") means the columns below are quarters,
        # even if the line above said "2025 2024": take no full-year values until the next real header.
        words = line.split()
        quarters = [w for w in words if re.fullmatch(r"Q[1-4]", w)]
        if has_years and len(quarters) >= 2 and len(quarters) * 2 >= len(words):
            years = []
            continue
        if is_scale_line or not label:
            continue
        # A short line with no numbers is a heading: remember it as the group.
        if not values:
            if len(label.split()) < 6 and not label.endswith("."):
                group = label
            continue

        # Keep the full-year values: drop percentages (change columns), pass over the quarter block,
        # then pair each value with its year column, left to right.
        if has_years:
            values = [v for v in values if not v[0].endswith("%")]
        values = values[skip:skip + len(years)]
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
