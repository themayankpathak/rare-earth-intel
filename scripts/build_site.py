# Build the data the website reads (docs/data/), from the pipeline's output.
# Run after build_rows.py and self_checker.py. The website itself is docs/index.html (GitHub Pages).
#   docs/data/numbers.json          every number, with its document, page and printed text
#   docs/data/site.json             headline counts, MP vs USGS, Neo by segment, open questions
#   docs/data/rare_earth_intel.csv  every number, for download
#   docs/data/caveats.json          each explained or open check, tied to the numbers it concerns (who, what,
#                                   material, year), so the question box can mention it
#   docs/data/vocabulary.json       what can be asked about: every who, what, material, part and year that
#                                   exists in the data (the question box may only choose from this list)
import glob
import json
import os

import pandas as pd

OUT = "docs/data"
CHECKS = "data/interim/checks.csv"
FIELDS = ["entity", "period", "metric", "material", "segment", "value_base", "unit",
          "source_document", "printed_page", "raw_text", "confidence", "notes"]


def latest(frame):
    # For each year, the value from the most recent document that reports it.
    return frame.sort_values("source_document", kind="stable").drop_duplicates("period", keep="last")


def mp_against_usgs(rows, checks):
    # MP's own production next to USGS's US figure, year by year, with the checker's verdict.
    production = rows[(rows["metric"] == "production_volume") & (rows["material"] == "total_REO")
                      & (rows["chain_stage"] == "concentrate")]
    mp = latest(production[production["entity"] == "MP Materials"]).set_index("period")
    usgs = latest(production[(production["entity"] == "United States")
                             & production["source_document"].str.startswith("usgs_")]).set_index("period")
    verdicts = checks[checks["section"] == "Company against government (USGS)"]
    table = []
    for period in sorted(set(mp.index) & set(usgs.index), reverse=True):
        verdict = verdicts[verdicts["check"].str.startswith(period + " ")]["status"]
        table.append({"year": period[2:], "mp": mp.loc[period, "value_base"],
                      "mp_document": mp.loc[period, "source_document"],
                      "usgs": usgs.loc[period, "value_base"], "usgs_document": usgs.loc[period, "source_document"],
                      "status": verdict.iloc[0] if len(verdict) else "not checked"})
    return table


def neo_by_segment(rows, period="FY2025"):
    # Neo's revenue per tonne for each segment and for the whole company: why mixed tonnes give no price.
    neo = rows[(rows["entity"] == "Neo Performance Materials") & (rows["period"] == period)]
    neo = neo.drop_duplicates(["entity_scope", "segment", "metric"])
    table = []
    for segment, part in neo.groupby(neo["segment"].fillna("Whole company")):
        values = part.set_index("metric")["value_base"]
        if {"revenue", "sales_volume"} <= set(values.index):
            table.append({"part": segment, "revenue": values["revenue"], "tonnes": values["sales_volume"],
                          "per_tonne": values["revenue"] / values["sales_volume"]})   # division in code
    return sorted(table, key=lambda r: r["per_tonne"])


# What each metric means, in words a question would use (for the question box's language model).
METRIC_WORDS = {
    "production_volume": "tonnes produced (mine production for countries; output for companies)",
    "sales_volume": "tonnes sold",
    "revenue": "revenue / sales in money",
    "avg_selling_price": "the company's stated average selling (realized) price",
    "market_price": "USGS average market price of an oxide, US dollars per kg",
    "cash_receipts": "cash received from customers (not revenue)",
    "composition_pct": "share of each element in the concentrate, percent",
    "intersegment_elimination": "eliminations between segments",
    "non_revenue_income": "income booked outside revenue (MP's price protection agreement)",
}


def vocabulary(rows):
    # For each who and what: the materials, parts (segments) and years that exist, so a question can only
    # be turned into a lookup of something that is really in the data.
    entries = []
    for (entity, metric), part in rows.groupby(["entity", "metric"]):
        entries.append({"entity": entity, "metric": metric, "metric_means": METRIC_WORDS.get(metric, metric),
                        "materials": sorted(part["material"].dropna().unique().tolist()),
                        "segments": sorted(part["segment"].dropna().unique().tolist()),
                        "years": sorted(part["period"].dropna().unique().tolist())})
    return entries


def caveats(checks, rows):
    # Each EXPECTED or OPEN check, tied to the numbers it concerns, for the question box's answers.
    # "Same number" checks name who, year, material and what; price checks name year and material, and the
    # document's source tells who. Checks that passed are not caveats.
    entities = sorted(rows["entity"].unique(), key=len, reverse=True)
    sources = pd.read_csv("config/companies.csv", dtype=str)
    found = []
    for _, c in checks[checks["status"].isin(["EXPECTED", "OPEN"])].iterrows():
        words = c["check"].split(":")[0].split()
        if c["section"] == "Same number, every place it is printed":
            entity = next((e for e in entities if c["check"].startswith(e + " ")), None)
            if entity:
                rest = c["check"][len(entity) + 1:].split(":")[0].split()
                found.append({"entity": entity, "year": rest[0], "material": rest[-2], "metric": rest[-1],
                              "status": c["status"], "reason": c["reason"]})
        elif len(words) >= 3 and words[2] == "price":
            source = next((s for _, s in sources.iterrows() if c["section"].startswith(s["file_prefix"] + "_")), None)
            if source is not None:
                found.append({"entity": source["entity"], "year": words[0], "material": words[1],
                              "metric": "avg_selling_price", "status": c["status"], "reason": c["reason"]})
    return pd.DataFrame(found).drop_duplicates().to_dict(orient="records")


def explanations(checks, status):
    # Each recorded reason once, with how many check lines it covers.
    picked = checks[checks["status"] == status]
    counted = picked.groupby("reason").size().sort_values(ascending=False)
    return [{"reason": reason, "lines": int(n)} for reason, n in counted.items()]


def main():
    files = sorted(glob.glob("data/processed/*_extracted_*.csv"))
    rows = pd.concat(pd.read_csv(f) for f in files)
    checks = pd.read_csv(CHECKS).fillna("")
    os.makedirs(OUT, exist_ok=True)

    rows.to_csv(f"{OUT}/rare_earth_intel.csv", index=False)
    numbers = rows[FIELDS].astype(object).where(rows[FIELDS].notna(), None)
    with open(f"{OUT}/numbers.json", "w") as f:
        json.dump(numbers.to_dict(orient="records"), f, separators=(",", ":"))

    counts = checks["status"].value_counts()
    site = {
        "numbers": len(rows), "documents": int(rows["source_document"].nunique()),
        "checks": {s: int(counts.get(s, 0)) for s in ["PASS", "FAIL", "EXPECTED", "OPEN"]},
        "mp_vs_usgs": mp_against_usgs(rows, checks),
        "neo_fy2025": neo_by_segment(rows),
        "open": explanations(checks, "OPEN"),
        "expected": explanations(checks, "EXPECTED"),
    }
    with open(f"{OUT}/site.json", "w") as f:
        json.dump(site, f, indent=1)
    with open(f"{OUT}/vocabulary.json", "w") as f:
        json.dump(vocabulary(rows), f, indent=1)
    with open(f"{OUT}/caveats.json", "w") as f:
        json.dump(caveats(checks, rows), f, indent=1)
    print(f"{len(rows)} numbers from {site['documents']} documents and {len(checks)} checks -> {OUT}/")


if __name__ == "__main__":
    main()
