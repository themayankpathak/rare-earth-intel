import pdfplumber
import pandas as pd
from text_cleaner import parse_line

PDF_PATH = "data/raw/mp-materials_10k_FY2025.pdf"
PAGE_OFFSET = 4  # in this file, pdf page = printed page + 4
YEARS = ["FY2025", "FY2024", "FY2023"]  # the usual three year columns, left to right
OUTPUT = "data/interim/extracted_rows.csv"


def extract_page(pdf, printed_page, years=YEARS, scale=None):
    # Read one printed page top to bottom and return one row per number.
    # years: what each value column on this page means, left to right.
    # scale: starting scale, for pages with no "in thousands" / "in whole units" line.
    text = pdf.pages[printed_page + PAGE_OFFSET - 1].extract_text()
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
                "printed_page": printed_page,
                "pdf_page": printed_page + PAGE_OFFSET,
                "group": group,
                "label": label,
                "period": year,
                "raw_text": raw,
                "value_reported": number,
                "scale_factor": scale,
            })
    return rows


with pdfplumber.open(PDF_PATH) as pdf:
    # Printed pp.44 revenue by product, 49 KPIs, 96 Note 16: three year columns, scale headers on the page.
    rows = extract_page(pdf, 44) + extract_page(pdf, 49) + extract_page(pdf, 96)
    # Printed p.29: TREO distribution. One percentage per element, no year columns, no scale header.
    # Percentages are stored as points (15.7), so the scale is 1.
    # Read last, so the rows above keep their row_ids (EX01-EX30) and p.29 adds EX31-EX34.
    rows += extract_page(pdf, 29, years=["not_applicable"], scale=1)

table = pd.DataFrame(rows)
table.to_csv(OUTPUT, index=False)
print(table.to_string())
print(f"\n{len(table)} rows saved to {OUTPUT}")