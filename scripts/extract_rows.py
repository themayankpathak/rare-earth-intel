import sys
import pdfplumber
import pandas as pd
from text_cleaner import parse_line

# Which filing to read, e.g. "FY2024". Default: the FY2025 10-K.
FILING = sys.argv[1] if len(sys.argv) > 1 else "FY2025"
PDF_PATH = f"data/raw/mp-materials_10k_{FILING}.pdf"
TABLES = "config/mp_tables.csv"  # which tables to read, and the text that identifies each one's page
OUTPUT = f"data/interim/extracted_rows_{FILING}.csv"

# A 10-K shows the filing year and the two years before it: FY2024 -> FY2024, FY2023, FY2022.
YEAR = int(FILING[2:])
YEARS = [f"FY{YEAR}", f"FY{YEAR - 1}", f"FY{YEAR - 2}"]


def find_page(texts, anchor):
    # Return the one page (counting from 1) whose text contains the anchor phrase.
    # Line breaks are flattened first, so a phrase split over two lines still matches.
    pages = [i + 1 for i, text in enumerate(texts) if anchor in " ".join(text.split())]
    if len(pages) > 1:
        sys.exit(f"STOP: '{anchor}' found on several pages {pages} of {FILING}. Make the anchor more specific.")
    return pages[0] if pages else None


def printed_page_number(text):
    # The page number printed at the bottom of the page is the last line of its text.
    last_line = text.strip().splitlines()[-1].strip()
    return int(last_line) if last_line.isdigit() else None


def extract_page(text, table, pdf_page, years, scale):
    # Read one page top to bottom and return one row per number.
    # years: what each value column means, left to right. scale: starting scale, for pages with no scale line.
    printed_page = printed_page_number(text)
    group = None
    rows = []

    for line in text.splitlines():
        # A scale header applies to every number below it, until the next scale header.
        if "in thousands" in line:
            scale = 1000
            continue
        if "in whole units" in line:
            scale = 1
            continue

        label, values = parse_line(line)
        if not label:
            continue
        # A short line with no numbers is a heading: remember it as the group.
        if not values:
            if len(label.split()) < 6 and not label.endswith("."):
                group = label
            continue

        # Pair each value with its column; zip stops at the shorter list.
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

# Read the tables in the order they are listed in mp_tables.csv (this order sets the row_ids).
tables = pd.read_csv(TABLES, dtype=str).fillna("")
rows = []
for _, t in tables.iterrows():
    pdf_page = find_page(texts, t["anchor"])
    if pdf_page is None:
        print(f"  {t['table']:<13} not in this filing, skipped")
        continue
    # Year columns: three years, or none (the composition table has no year).
    years = YEARS if t["year_columns"] == "3" else ["not_applicable"]
    scale = int(t["start_scale"]) if t["start_scale"] else None
    found = extract_page(texts[pdf_page - 1], t["table"], pdf_page, years, scale)
    print(f"  {t['table']:<13} pdf p.{pdf_page} (printed p.{printed_page_number(texts[pdf_page - 1])}): {len(found)} values")
    rows += found

table = pd.DataFrame(rows)
table.to_csv(OUTPUT, index=False)
print(f"{len(table)} rows saved to {OUTPUT}")