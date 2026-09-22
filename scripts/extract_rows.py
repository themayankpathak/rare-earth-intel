import pdfplumber
import pandas as pd
from text_cleaner import parse_line

PDF_PATH = "data/raw/mp-materials_10k_FY2025.pdf"
PAGE_OFFSET = 4
YEARS = ["FY2025", "FY2024", "FY2023"]
OUTPUT = "data/interim/extracted_rows.csv"


def extract_page(pdf, printed_page):
    text = pdf.pages[printed_page + PAGE_OFFSET - 1].extract_text()
    scale = None
    group = None
    rows = []

    for line in text.splitlines():
        if "in thousands" in line:
            scale = 1000
            continue
        if "in whole units" in line:
            scale = 1
            continue

        label, values = parse_line(line)
        if not label:
            continue
        if not values:
            if len(label.split()) < 6 and not label.endswith("."):
                group = label
            continue

        for year, (raw, number) in zip(YEARS, values):
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
    rows = extract_page(pdf, 44) + extract_page(pdf, 49) + extract_page(pdf, 96)

table = pd.DataFrame(rows)
table.to_csv(OUTPUT, index=False)
print(table.to_string())
print(f"\n{len(table)} rows saved to {OUTPUT}")