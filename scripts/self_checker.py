import pdfplumber
import pandas as pd

PDF_PATH = "data/raw/mp-materials_10k_FY2025.pdf"
EXTRACTED = "data/processed/extracted_v2.csv"

# Plausible ranges for each metric: (lowest, highest) in base units.
# A value outside its range is almost certainly a scale or parsing error.
RANGES = {
    "sales_volume": (0, 200_000),              # tonnes
    "production_volume": (0, 200_000),         # tonnes
    "avg_selling_price": (1_000, 200_000),     # USD per tonne
    "revenue": (100_000, 10_000_000_000),      # USD
    "non_revenue_income": (0, 10_000_000_000), # USD
    "intersegment_elimination": (-10_000_000_000, 0),
    "composition_pct": (0, 100),               # percentage points (15.7, not 0.157)
}

rows = pd.read_csv(EXTRACTED)
failures = 0


def report(ok, message):
    # Print one PASS/FAIL line and count the failures.
    global failures
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures += 1


# Check 1: every raw_text really appears on the page it cites.
# Proves no number was invented or taken from the wrong page.
with pdfplumber.open(PDF_PATH) as pdf:
    for _, row in rows.iterrows():
        page_text = " ".join(pdf.pages[row["pdf_page"] - 1].extract_text().split())
        report(row["raw_text"] in page_text,
               f"{row['row_id']} '{row['raw_text']}' found on printed p.{row['printed_page']}")

# Check 2: every value is inside the plausible range for its metric.
# ",.10g" prints 41,992,000 as a whole number but keeps 15.7 as 15.7.
for _, row in rows.iterrows():
    low, high = RANGES[row["metric"]]
    report(low <= row["value_base"] <= high,
           f"{row['row_id']} {row['metric']} = {row['value_base']:,.10g} within range")


def pick(metric, material, period, segment="Materials"):
    # Find the one value matching this description.
    match = rows[(rows["metric"] == metric) & (rows["material"] == material)
                 & (rows["period"] == period) & (rows["segment"] == segment)]
    return match["value_base"].iloc[0]


# Check 3: revenue / volume must equal the price MP states (all three years).
# The division happens here, in code, never by an LLM.
for year in ["FY2025", "FY2024", "FY2023"]:
    revenue = pick("revenue", "total_REO", year)
    volume = pick("sales_volume", "total_REO", year)
    stated = pick("avg_selling_price", "total_REO", year)
    implied = revenue / volume
    gap = abs(implied - stated) / stated
    report(gap < 0.001, f"{year} implied price {implied:,.1f} vs stated {stated:,.0f} (gap {gap:.3%})")

# Check 4: Materials + Magnetics - eliminations must equal consolidated revenue.
materials = pick("revenue", "not_applicable", "FY2025")
magnetics = pick("revenue", "NdPr", "FY2025", segment="Magnetics")
elimination = rows[rows["metric"] == "intersegment_elimination"]["value_base"].iloc[0]
total = rows[(rows["entity_scope"] == "consolidated") & (rows["metric"] == "revenue")
             & (rows["period"] == "FY2025")]["value_base"].iloc[0]
report(materials + magnetics + elimination == total,
       f"FY2025 revenue bridge {materials + magnetics + elimination:,.0f} = {total:,.0f}")

# Check 5: the element shares of the concentrate (printed p.29) must add up to 100%.
# Needs all four elements: a missing or misread one makes the sum wrong.
# The tolerance (0.05) only absorbs rounding in the printed one-decimal figures.
shares = rows[rows["metric"] == "composition_pct"]
total_share = shares["value_base"].sum()
report(len(shares) == 4 and abs(total_share - 100) < 0.05,
       f"p.29 concentrate composition: {len(shares)} elements sum to {total_share:.1f}%")

print(f"\n{failures} failures")