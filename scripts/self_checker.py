import glob
import re
import pdfplumber
import pandas as pd

# Every report the pipeline has built, for every source: data/processed/lynas_extracted_FY2026.csv, usgs_extracted_ED2025.csv.
FILES = sorted(glob.glob("data/processed/*_extracted_*.csv"))
IDENTITY = ["entity", "entity_scope", "segment", "material", "metric", "period"]  # what a number is

# Plausible ranges per (metric, unit), in base units.
# A value outside its range is almost certainly a scale or parsing error.
RANGES = {
    ("sales_volume", "tonnes"): (0, 200_000),
    ("production_volume", "tonnes"): (0, 200_000),
    ("avg_selling_price", "USD_per_tonne"): (1_000, 200_000),
    ("avg_selling_price", "USD_per_kg"): (5, 1_000),
    ("avg_selling_price", "AUD_per_kg"): (5, 1_000),
    ("revenue", "USD"): (100_000, 10_000_000_000),
    ("revenue", "AUD"): (100_000, 10_000_000_000),
    ("cash_receipts", "AUD"): (100_000, 10_000_000_000),
    ("non_revenue_income", "USD"): (0, 10_000_000_000),
    ("intersegment_elimination", "USD"): (-10_000_000_000, 0),
    ("composition_pct", "percent"): (0, 100),  # percentage points (15.7, not 0.157)
    ("market_price", "USD_per_kg"): (0.5, 10_000),
    # A country's or the world's mine production is far larger than one company's.
    ("production_volume", "tonnes", "country"): (0, 1_000_000),
    ("production_volume", "tonnes", "world"): (0, 2_000_000),
}

# Known reasons a check does not pass. Each check still runs and prints its numbers.
#   EXPECTED: explained, with the page where the explanation is printed.
#   OPEN:     a real, unexplained difference, logged so it is not forgotten. Still needs a person.
NON_GAAP_PRICE = ("Realized Price for FY2019-FY2021 uses non-GAAP Total Value Realized, not GAAP revenue "
                  "- FY2021 10-K printed p.34 (definition) and p.45 (reconciliation)")
COMPOSITION_REVISED = ("estimated element distribution revised between the FY2020 10-K (printed p.13) "
                       "and the FY2021 10-K (printed p.26)")
LYNAS_FY25_PRICE = ("FY25 stated A$50.6/kg vs revenue / volume A$50.73/kg, in both the FY2025 and FY2026 reports; "
                    "would need revenue A$1.35m lower than printed. Not explained by the revenue note (FY2025 report "
                    "printed p.78): revenue from contracts A$542.7m gives 49.47, total revenue A$556.5m gives 50.73")
LYNAS_CENT_PRICE = ("five-year table prices (two decimals) are about one cent off revenue / volume in FY2019 "
                    "(18.97 vs 18.98) and FY2022 (60.27 vs 60.28); the one-decimal prices in the sales table "
                    "reconcile. Cause not yet found")
LYNAS_FY17_18_PRICE = ("FY17 and FY18 stated prices are ~2% above revenue / volume (18.0 vs 17.58; 21.6 vs 21.17), "
                       "in the FY2019, FY2020 and FY2021 reports. Lead, unconfirmed: the FY2019 report calls revenue "
                       "'net sales revenue', so the old price may be on gross sales. FY2017-18 reports not collected")
USGS_ND_2021 = ("2021 neodymium oxide price is $49/kg in the 2022 and 2023 editions and $98/kg from the 2024 "
                "edition on; 2020 is unchanged. The price source footnote changed at the same time (Argus Metals "
                "International -> Argus Non-Ferrous Metals), but that alone does not explain one restated year")
KNOWN_EXCEPTIONS = {
    ("price", "MP Materials", "total_REO", "FY2019"): ("EXPECTED", NON_GAAP_PRICE),
    ("price", "MP Materials", "total_REO", "FY2020"): ("EXPECTED", NON_GAAP_PRICE),
    ("price", "MP Materials", "total_REO", "FY2021"): ("EXPECTED", NON_GAAP_PRICE),
    ("same number", "MP Materials", "composition_pct", "Ce", "not_applicable"): ("EXPECTED", COMPOSITION_REVISED),
    ("same number", "MP Materials", "composition_pct", "La", "not_applicable"): ("EXPECTED", COMPOSITION_REVISED),
    ("same number", "Rare earth market (USGS)", "market_price", "Nd", "FY2021"): ("OPEN", USGS_ND_2021),
    ("price", "Lynas Rare Earths", "total_REO", "FY2025"): ("OPEN", LYNAS_FY25_PRICE),
    ("price", "Lynas Rare Earths", "total_REO", "FY2022"): ("OPEN", LYNAS_CENT_PRICE),
    ("price", "Lynas Rare Earths", "total_REO", "FY2019"): ("OPEN", LYNAS_CENT_PRICE),
    ("price", "Lynas Rare Earths", "total_REO", "FY2017"): ("OPEN", LYNAS_FY17_18_PRICE),
    ("price", "Lynas Rare Earths", "total_REO", "FY2018"): ("OPEN", LYNAS_FY17_18_PRICE),
}

counts = {"PASS": 0, "FAIL": 0, "EXPECTED": 0, "OPEN": 0}


def report(ok, message, exception=None):
    # Print one line per check: PASS, FAIL, or the status of a known exception (EXPECTED / OPEN).
    status = "PASS" if ok else (exception[0] if exception else "FAIL")
    counts[status] += 1
    print(f"{status:<10}{message}" + (f"  [{exception[1]}]" if exception and not ok else ""))


COMPANIES = pd.read_csv("config/companies.csv", dtype=str)


def precision_of(source_document):
    # "printed": a number is exact to its last printed digit (company reports).
    # "significant": trailing zeros are rounding (USGS: "Data are rounded to two significant digits").
    for _, c in COMPANIES.iterrows():
        if source_document.startswith(c["file_prefix"] + "_"):
            return c["precision"]
    return "printed"


def step(row):
    # How finely this number is printed, in base units: "556.5" (A$m) -> 100,000; "41,992" ($k) -> 1,000;
    # in USGS tables "45,000" -> 1,000 and "42,400" -> 100. The true value is within half a step.
    digits = re.sub(r"[^\d.]", "", str(row["raw_text"]))
    if not digits:
        return 0  # a printed dash: exactly zero
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    if precision_of(row["source_document"]) == "significant" and decimals == 0 and digits.strip("0"):
        return 10 ** (len(digits) - len(digits.rstrip("0"))) * row["scale_factor"]
    return 10 ** -decimals * row["scale_factor"]


def is_estimate(row):
    # The publisher marked the value "e" (USGS); a later edition is expected to revise it.
    return "Estimate (marked e" in str(row["notes"])


def value(rows, metric, material, period, segment="Materials"):
    # The one value matching this description, or None if this filing does not report it.
    match = rows[(rows["metric"] == metric) & (rows["material"] == material)
                 & (rows["period"] == period) & (rows["segment"] == segment)]
    return match["value_base"].iloc[0] if len(match) else None


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
        low, high = RANGES.get((row["metric"], row["unit"], row["entity_scope"]), RANGES.get((row["metric"], row["unit"])))
        report(low <= row["value_base"] <= high,
               f"{row['row_id']} {row['metric']} = {row['value_base']:,.10g} {row['unit']} within range")

    # Check 3: revenue / volume must agree with every stated price, allowing for rounding:
    # the check passes if some unrounded values, each within half a printed step, fit exactly.
    # Revenue and volume are taken from the price's own page where possible, else anywhere in the filing.
    # The division happens here, in code, never by an LLM.
    for _, price in rows[rows["metric"] == "avg_selling_price"].iterrows():
        same = rows[(rows["entity_scope"] == price["entity_scope"]) & (rows["material"] == price["material"])
                    & (rows["period"] == price["period"])
                    & ((rows["segment"] == price["segment"]) | (rows["segment"].isna() & pd.isna(price["segment"])))]
        picked = []
        for metric in ["revenue", "sales_volume"]:
            found = same[same["metric"] == metric]
            on_page = found[found["pdf_page"] == price["pdf_page"]]
            picked.append(on_page.iloc[0] if len(on_page) else (found.iloc[0] if len(found) else None))
        revenue, volume = picked
        if revenue is None or volume is None:
            continue
        per = 1000 if price["unit"].endswith("_per_kg") else 1  # tonnes -> kg for a per-kg price
        lowest = (revenue["value_base"] - step(revenue) / 2) / ((volume["value_base"] + step(volume) / 2) * per)
        highest = (revenue["value_base"] + step(revenue) / 2) / ((volume["value_base"] - step(volume) / 2) * per)
        ok = price["value_base"] - step(price) / 2 <= highest and price["value_base"] + step(price) / 2 >= lowest
        implied = revenue["value_base"] / (volume["value_base"] * per)
        report(ok, f"{price['period']} {price['material']} price (printed p.{price['printed_page']}): revenue / volume = "
                   f"{implied:,.2f} vs stated {price['value_base']:,.10g} {price['unit']}",
               KNOWN_EXCEPTIONS.get(("price", price["entity"], price["material"], price["period"])))

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

    # Check 4b: segment revenues + corporate / eliminations = consolidated revenue, where a report gives
    # at least two segment totals (Neo). Each segment is counted once even if two tables print it.
    for period in sorted(rows["period"].unique()):
        in_year = rows[rows["period"] == period]
        segments = in_year[(in_year["entity_scope"] == "segment") & (in_year["metric"] == "revenue")
                           & (in_year["material"] == "not_applicable")].drop_duplicates("segment")
        elimination = in_year[in_year["metric"] == "intersegment_elimination"]["value_base"]
        total = in_year[(in_year["entity_scope"] == "consolidated") & (in_year["metric"] == "revenue")]["value_base"]
        if len(segments) >= 2 and len(elimination) and len(total):
            bridge = segments["value_base"].sum() + elimination.iloc[0]
            report(bridge == total.iloc[0], f"{period} segment revenue bridge: {len(segments)} segments "
                   f"{segments['value_base'].sum():,.0f} + eliminations {elimination.iloc[0]:,.0f} = {total.iloc[0]:,.0f}")

    # Check 4c: segment sales volumes add up to at least the consolidated volume. Not equal: Neo reports its
    # segments before intercompany eliminations (C&O sells to Magnequench), so tonnes sold inside the group
    # are in the segments but not in the consolidated figure (Neo FY2025 MD&A printed p.20).
    for period in sorted(rows["period"].unique()):
        in_year = rows[rows["period"] == period]
        volumes = in_year[(in_year["entity_scope"] == "segment") & (in_year["metric"] == "sales_volume")
                          & (in_year["material"] == "not_applicable")].drop_duplicates("segment")
        total = in_year[(in_year["entity_scope"] == "consolidated") & (in_year["metric"] == "sales_volume")]["value_base"]
        if len(volumes) >= 2 and len(total):
            segment_sum = volumes["value_base"].sum()
            report(segment_sum >= total.iloc[0], f"{period} segment volumes {segment_sum:,.0f} t >= consolidated "
                   f"{total.iloc[0]:,.0f} t (difference {segment_sum - total.iloc[0]:,.0f} t, consistent with segments "
                   f"reported before intercompany eliminations)")

    # Check 5: the element shares of the concentrate must add up to 100%.
    # At least four elements (FY2020 lists Nd and Pr separately, so five); a missing one breaks the sum.
    # The tolerance (0.05) only absorbs rounding in the printed one-decimal figures.
    shares = rows[rows["metric"] == "composition_pct"]
    if len(shares):
        total_share = shares["value_base"].sum()
        report(len(shares) >= 4 and abs(total_share - 100) < 0.05,
               f"concentrate composition: {len(shares)} elements sum to {total_share:.1f}%")

    everything.append(rows)

# Check 6: a number printed in more than one place - another filing, or another table of the same
# report - must agree, allowing for how finely each copy is printed (A$977.9m and A$977,945k agree).
# A difference means a restatement, a revised estimate or a parsing error: a person should look.
print("\n===== Same number, every place it is printed")
combined = pd.concat(everything)
single_source = 0
for identity, group in combined.groupby(IDENTITY, dropna=False):
    if len(group) < 2:
        single_source += 1
        continue
    entity, scope, segment, material, metric, period = identity
    name = f"{entity} {period} {scope if pd.isna(segment) else segment} {material} {metric}"
    lows = [v - step(r) / 2 for v, (_, r) in zip(group["value_base"], group.iterrows())]
    highs = [v + step(r) / 2 for v, (_, r) in zip(group["value_base"], group.iterrows())]
    # Each value with where it came from, e.g. "252,468,000 (FY2024 p.43)".
    values = ", ".join(f"{v:,.10g} ({doc[-10:-4]} " + (f"p.{p:.0f})" if pd.notna(p) else "no page number)")
                       for v, doc, p in zip(group["value_base"], group["source_document"], group["printed_page"]))
    agree = max(lows) <= min(highs)
    exception = KNOWN_EXCEPTIONS.get(("same number", entity, metric, material, period))
    if not agree and not exception:
        # An estimate revised by a later edition is expected, as long as the figures that are not
        # estimates agree with each other.
        final = [(lo, hi) for lo, hi, (_, r) in zip(lows, highs, group.iterrows()) if not is_estimate(r)]
        if len(final) < len(group) and (len(final) <= 1 or max(lo for lo, _ in final) <= min(hi for _, hi in final)):
            exception = ("EXPECTED", "an earlier edition's estimate (e) was revised in a later edition")
    report(agree, f"{name}: {values}", exception)
print(f"({single_source} numbers appear in only one place, so they cannot be cross-checked)")

# Check 7: a company's own production against the government's figure for its country, where the company is the
# country's main producer and both count the same thing (config/companies.csv, column usgs_country: MP and the
# United States, both in tonnes of REO in concentrate, calendar years). Each side uses its latest report;
# the company figure must fall within the USGS figure's rounding.
print("\n===== Company against government (USGS)")
production = combined[(combined["metric"] == "production_volume") & (combined["material"] == "total_REO")
                      & (combined["chain_stage"] == "concentrate")].sort_values("source_document")
for _, c in COMPANIES.dropna(subset=["usgs_country"]).iterrows():
    own = production[production["entity"] == c["entity"]].drop_duplicates("period", keep="last")
    usgs = production[(production["entity"] == c["usgs_country"])
                      & production["source_document"].str.startswith("usgs_")].drop_duplicates("period", keep="last")
    for _, gov in usgs.iterrows():
        mine = own[own["period"] == gov["period"]]
        if not len(mine):
            continue
        company_value = mine["value_base"].iloc[0]
        within = abs(company_value - gov["value_base"]) <= step(gov) / 2
        report(within, f"{gov['period']} {c['entity']} {company_value:,.0f} t ({mine['source_document'].iloc[0][-10:-4]}) "
                       f"vs USGS {c['usgs_country']} {gov['value_base']:,.0f} t ({gov['source_document'][-10:-4]} edition, "
                       f"rounded to {step(gov):,.0f} t)")

print(f"\n{counts['FAIL']} failures, {counts['EXPECTED']} expected (explained), {counts['OPEN']} open (unexplained)")
