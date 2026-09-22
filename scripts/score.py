import pandas as pd

GROUND_TRUTH = "data/ground-truth/ground_truth.csv"
EXTRACTED = "data/processed/extracted_v2.csv"
KEY = ["entity_scope", "segment", "material", "metric", "period"]
FIELDS = [
    "value_base", "scale_factor", "raw_text", "printed_page", "pdf_page",
    "chain_stage", "basis", "unit", "currency", "price_basis",
    "confidence", "is_comparative", "period_end_date",
]

truth = pd.read_csv(GROUND_TRUTH, dtype=str).fillna("")
found = pd.read_csv(EXTRACTED, dtype=str).fillna("")

pairs = truth.merge(found, on=KEY, how="left", suffixes=("_gt", "_ex"), indicator=True)
matched = pairs[pairs["_merge"] == "both"]
missing = pairs[pairs["_merge"] == "left_only"]

print(f"Ground truth rows: {len(truth)}")
print(f"Found by extractor: {len(matched)} of {len(truth)}")
for _, row in missing.iterrows():
    print(f"  MISSING {row['row_id_gt']}: {row['metric']} {row['material']} {row['period']}")

print("\nField accuracy on found rows:")
for field in FIELDS:
    same = matched[f"{field}_gt"] == matched[f"{field}_ex"]
    print(f"  {field:<16} {same.sum():>2} / {len(matched)}")
    for _, row in matched[~same].iterrows():
        print(f"      {row['row_id_gt']}: truth={row[field + '_gt']!r}  extracted={row[field + '_ex']!r}")