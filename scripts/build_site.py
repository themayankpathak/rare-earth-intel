# Build the data the website reads (docs/data/), from the pipeline's output.
# Run after build_rows.py and self_checker.py. The website itself is docs/index.html (GitHub Pages).
#   docs/data/numbers.json          every number, with its document, page and printed text
#   docs/data/site.json             headline counts, MP vs USGS, Neo by segment, open questions
#   docs/data/rare_earth_intel.csv  every number, for download
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
    print(f"{len(rows)} numbers from {site['documents']} documents and {len(checks)} checks -> {OUT}/")


if __name__ == "__main__":
    main()
