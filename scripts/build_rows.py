import sys
import pandas as pd

# Which filing to build, e.g. "FY2024". Default: the FY2025 10-K.
FILING = sys.argv[1] if len(sys.argv) > 1 else "FY2025"
EXTRACTED = f"data/interim/extracted_rows_{FILING}.csv"
LABEL_MAP = "config/mp_label_map.csv"
OUTPUT = f"data/processed/extracted_{FILING}.csv"
KEY = ["table", "group", "label"]  # how an extracted line is matched to its meaning in the label map
COLUMNS = [
    "row_id", "entity", "entity_scope", "segment", "material", "chain_stage",
    "metric", "basis", "period", "period_granularity", "period_end_date",
    "value_reported", "scale_factor", "value_base", "unit", "currency",
    "price_basis", "derivation", "derived_from", "is_comparative", "doc_type",
    "source_document", "pdf_page", "printed_page", "raw_text", "language",
    "confidence", "notes",
]

extracted = pd.read_csv(EXTRACTED)
label_map = pd.read_csv(LABEL_MAP)

# Keep only lines the label map knows, and drop empty values (dash or N/A printed).
rows = extracted.merge(label_map, on=KEY, how="inner")
rows = rows.dropna(subset=["value_reported"])

# Fields that are the same for every row of this filing.
rows["entity"] = "MP Materials"
rows["derivation"] = "as_reported"
rows["derived_from"] = None
rows["doc_type"] = "annual"
rows["source_document"] = f"mp-materials_10k_{FILING}.pdf"
rows["language"] = "en"
rows["notes"] = None

# Fiscal-year fields only make sense when the period is a fiscal year (FY2025, FY2024, ...).
# The composition table has no year: its period is "not_applicable" and these stay blank.
is_year = rows["period"].str.startswith("FY")
rows["period_granularity"] = is_year.map({True: "FY", False: None})
rows["period_end_date"] = (rows["period"].str[2:] + "-12-31").where(is_year)
# A prior-year figure inside this filing is a comparative. A row with no year is not.
rows["is_comparative"] = (is_year & (rows["period"] != FILING)).map({True: "TRUE", False: "FALSE"})

# The number in base units: printed value times its scale ("in thousands" -> x1000).
rows["value_base"] = rows["value_reported"] * rows["scale_factor"]
# row_ids count within one filing: EX01 in FY2024 and EX01 in FY2025 are different rows,
# told apart by source_document.
rows["row_id"] = [f"EX{i:02d}" for i in range(1, len(rows) + 1)]

rows = rows[COLUMNS]
rows.to_csv(OUTPUT, index=False)
print(rows[["row_id", "metric", "material", "period", "value_base", "printed_page"]].to_string(index=False))
print(f"\n{len(rows)} rows saved to {OUTPUT}")