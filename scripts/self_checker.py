import glob
import pdfplumber
import pandas as pd

# Every filing the pipeline has built, e.g. data/processed/extracted_FY2024.csv.
FILES = sorted(glob.glob("data/processed/extracted_FY*.csv"))
IDENTITY = ["entity_scope", "segment", "material", "metric", "period"]  # what a number is, independent of filing

# Plausible ranges per (metric, unit), in base units.
# A value outside its range is almost certainly a scale or parsing error.
RANGES = {
    ("sales_volume", "tonnes"): (0, 200_000),
    ("production_volume", "tonnes"): (0, 200_000),
    ("avg_selling_price", "USD_per_tonne"): (1_000, 200_000),
    ("avg_selling_price", "USD_per_kg"): (5, 1_000),
    ("revenue", "USD"): (100_000, 10_000_000_000),
    ("non_revenue_income", "USD"): (0, 10_000_000_000),
    ("intersegment_elimination", "USD"): (-10_000_000_000, 0),
    ("composition_pct", "percent"): (0, 100),  # percentage points (15.7, not 0.157)
}

# Known, documented reasons a check should not pass. Each needs a page reference.
# The check still runs and prints its numbers, but reports EXPECTED instead of FAIL.
KNOWN_EXCEPTIONS = {
    ("concentrate price", "FY2021"):
        "FY2021 Realized Price uses non-GAAP Total Value Realized (adjusted for tariff rebates), "
        "not GAAP revenue - FY2023 10-K printed p.38",
}

failures = 0
expected = 0


def report(ok, message, exception=None):
    # Print one line per check: PASS, FAIL, or EXPECTED (a documented exception).
    global failures, expected
    if ok:
        print("PASS      " + message)
    elif exception:
        print("EXPECTED  " + message + "  [" + exception + "]")
        expected += 1
    else:
        print("FAIL      " + message)
        failures += 1


def value(rows, metric, material, period, segment="Materials"):
    # The one value matching this description, or None if this filing does not report it.
    match = rows[(rows["metric"] == metric) & (rows["material"] == material)
                 & (rows["period"] == period) & (rows["segment"] == segment)]
    return match["value_base"].iloc[0] if len(match) else None


def price_consistent(revenue, volume, stated, revenue_step, volume_step, price_step, per):
    # Printed numbers are rounded (revenue to $1,000, volume to 1 tonne, price to $1).
    # The check passes if some unrounded values, each within half a step of what is printed,
    # make revenue / volume equal the stated price. per = 1 for USD/tonne, 1000 for USD/kg.
    lowest = (revenue - revenue_step / 2) / ((volume + volume_step / 2) * per)
    highest = (revenue + revenue_step / 2) / ((volume - volume_step / 2) * per)
    return stated - price_step / 2 <= highest and stated + price_step / 2 >= lowest


everything = []
for path in FILES:
    rows = pd.read_csv(path)
    filing = rows["source_document"].iloc[0]
    print(f"\n===== {filing} ({len(rows)} rows)")

    # Check 1: every raw_text really appears on the page it cites.
    # Each cited page is read once and kept, because reading pages is the slow part.
    page_texts = {}
    with pdfplumber.open("data/raw/" + filing) as pdf:
        for _, row in rows.iterrows():
            page = row["pdf_page"]
            if page not in page_texts:
                page_texts[page] = " ".join(pdf.pages[page - 1].extract_text().split())
            report(row["raw_text"] in page_texts[page],
                   f"{row['row_id']} '{row['raw_text']}' found on printed p.{row['printed_page']}")

    # Check 2: every value is inside the plausible range for its metric and unit.
    for _, row in rows.iterrows():
        low, high = RANGES[(row["metric"], row["unit"])]
        report(low <= row["value_base"] <= high,
               f"{row['row_id']} {row['metric']} = {row['value_base']:,.10g} {row['unit']} within range")

    # Check 3: revenue / volume must agree with the price MP states, for every year shown.
    # The division happens here, in code, never by an LLM.
    for period in sorted(rows["period"].unique()):
        revenue = value(rows, "revenue", "total_REO", period)
        volume = value(rows, "sales_volume", "total_REO", period)
        stated = value(rows, "avg_selling_price", "total_REO", period)
        if None not in (revenue, volume, stated):
            ok = price_consistent(revenue, volume, stated, 1000, 1, 1, per=1)
            report(ok, f"{period} concentrate price: revenue / volume = {revenue / volume:,.1f} vs stated {stated:,.0f} $/t",
                   KNOWN_EXCEPTIONS.get(("concentrate price", period)))
        revenue = value(rows, "revenue", "NdPr", period)
        volume = value(rows, "sales_volume", "NdPr", period)
        stated = value(rows, "avg_selling_price", "NdPr", period)
        if None not in (revenue, volume, stated):
            ok = price_consistent(revenue, volume, stated, 1000, 1, 1, per=1000)
            report(ok, f"{period} NdPr price: revenue / volume = {revenue / volume / 1000:,.2f} vs stated {stated:,.0f} $/kg",
                   KNOWN_EXCEPTIONS.get(("NdPr price", period)))

    # Check 4: Materials + Magnetics + eliminations = consolidated revenue (only where all parts are reported).
    for period in sorted(rows["period"].unique()):
        materials = value(rows, "revenue", "not_applicable", period)
        magnetics = value(rows, "revenue", "NdPr", period, segment="Magnetics")
        elimination = rows[(rows["metric"] == "intersegment_elimination") & (rows["period"] == period)]["value_base"]
        total = rows[(rows["entity_scope"] == "consolidated") & (rows["metric"] == "revenue")
                     & (rows["period"] == period)]["value_base"]
        if None not in (materials, magnetics) and len(elimination) and len(total):
            bridge = materials + magnetics + elimination.iloc[0]
            report(bridge == total.iloc[0], f"{period} revenue bridge {bridge:,.0f} = {total.iloc[0]:,.0f}")

    # Check 5: the element shares of the concentrate must add up to 100%.
    # The tolerance (0.05) only absorbs rounding in the printed one-decimal figures.
    shares = rows[rows["metric"] == "composition_pct"]
    if len(shares):
        total_share = shares["value_base"].sum()
        report(len(shares) == 4 and abs(total_share - 100) < 0.05,
               f"concentrate composition: {len(shares)} elements sum to {total_share:.1f}%")

    everything.append(rows)

# Check 6: a number reported in more than one filing must be the same in each.
# FY2023 revenue appears in the FY2023, FY2024 and FY2025 10-Ks. A difference means a restatement
# or a parsing error - either way, a person should look.
print("\n===== Across filings")
combined = pd.concat(everything)
single_source = 0
for identity, group in combined.groupby(IDENTITY, dropna=False):
    if len(group) < 2:
        single_source += 1
        continue
    scope, segment, material, metric, period = identity
    name = f"{period} {scope if pd.isna(segment) else segment} {material} {metric}"
    # Each value with the filing it came from, e.g. "252,468,000 (FY2024)".
    values = ", ".join(f"{v:,.10g} ({doc[-10:-4]})" for v, doc in zip(group["value_base"], group["source_document"]))
    report(group["value_base"].nunique() == 1, f"{name}: {values}")
print(f"({single_source} numbers appear in only one filing, so they cannot be cross-checked)")

print(f"\n{failures} failures, {expected} expected exceptions")