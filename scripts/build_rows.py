import pandas as pd

EXTRACTED = "data/interim/extracted_rows.csv"
LABEL_MAP = "config/mp_fy2025_label_map.csv"
OUTPUT = "data/processed/extracted_v2.csv"
KEY = ["printed_page", "group", "label"]
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

rows = extracted.merge(label_map, on=KEY, how="inner")
rows = rows.dropna(subset=["value_reported"])

rows["entity"] = "MP Materials"
rows["period_granularity"] = "FY"
rows["period_end_date"] = rows["period"].str[2:] + "-12-31"
rows["value_base"] = rows["value_reported"] * rows["scale_factor"]
rows["derivation"] = "as_reported"
rows["derived_from"] = None
rows["is_comparative"] = (rows["period"] != "FY2025").map({True: "TRUE", False: "FALSE"})
rows["doc_type"] = "annual"
rows["source_document"] = "mp-materials_10k_FY2025.pdf"
rows["language"] = "en"
rows["notes"] = None
rows["row_id"] = [f"EX{i:02d}" for i in range(1, len(rows) + 1)]

rows = rows[COLUMNS]
rows.to_csv(OUTPUT, index=False)
print(rows[["row_id", "metric", "material", "period", "value_base", "printed_page"]].to_string(index=False))
print(f"\n{len(rows)} rows saved to {OUTPUT}")