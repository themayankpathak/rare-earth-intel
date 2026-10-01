import sys
import pandas as pd

# Which company and filing to build, e.g. "python scripts/build_rows.py lynas FY2026".
COMPANY, FILING = sys.argv[1], sys.argv[2]
company = pd.read_csv("config/companies.csv", dtype=str).set_index("company").loc[COMPANY]
EXTRACTED = f"data/interim/{COMPANY}_extracted_rows_{FILING}.csv"
LABEL_MAP = f"config/{COMPANY}_label_map.csv"
OUTPUT = f"data/processed/{COMPANY}_extracted_{FILING}.csv"
IDENTITY = ["entity_scope", "segment", "material", "metric", "period"]  # what a number is
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
# Optional map columns: "scale" (for labels that carry their own unit, like "(A$m)") and "notes".
for optional in ["scale", "notes"]:
    if optional not in label_map.columns:
        label_map[optional] = None

# Labels are matched ignoring capital letters: "REO sales volume (MTs)" (FY2021) = "REO Sales Volume (MTs)".
extracted["line"] = extracted.index          # remember each line's position, to keep the page order
extracted["label_key"] = extracted["label"].str.lower()
extracted["group"] = extracted["group"].fillna("")
label_map["label_key"] = label_map["label"].str.lower()
label_map = label_map.drop(columns="label")

# Two kinds of map line:
#   specific: matches one table, one heading and one label.
#   general (group "*"): matches the label under any heading of that table.
# A specific line wins: "Product sales" under the "Revenue:" heading is one product line (FY2021-22);
# "Product sales" anywhere else is the company total (FY2020, before the line was split).
specific = extracted.merge(label_map[label_map["group"] != "*"], on=["table", "group", "label_key"])
general = extracted.merge(label_map[label_map["group"] == "*"].drop(columns="group"), on=["table", "label_key"])
general = general[~general["line"].isin(specific["line"])]
rows = pd.concat([specific, general]).sort_values("line")

# Guard: one extracted line must get exactly one meaning.
if rows["line"].duplicated().any():
    sys.exit("STOP: a line matched more than one map entry. Check the label map.")

# Drop empty values (dash or N/A printed).
rows = rows.dropna(subset=["value_reported"])

# Fields that are the same for every row of this filing.
rows["entity"] = company["entity"]
rows["derivation"] = "as_reported"
rows["derived_from"] = None
rows["doc_type"] = "annual"
rows["source_document"] = f"{company['file_prefix']}_{FILING}.pdf"
rows["language"] = "en"

# Scale: the label map wins where the label carries its own unit ("Sales revenue (A$m)" -> x1,000,000);
# otherwise the page's scale line ("in thousands" -> x1,000).
rows["scale_factor"] = rows["scale"].fillna(rows["scale_factor"])

# Fiscal-year fields only make sense when the period is a fiscal year (FY2025, FY2024, ...).
# The year ends on the company's year-end date: 31 December for MP, 30 June for Lynas.
is_year = rows["period"].str.startswith("FY")
rows["period_granularity"] = is_year.map({True: "FY", False: None})
rows["period_end_date"] = (rows["period"].str[2:] + "-" + company["year_end"]).where(is_year)
# A prior-year figure inside this filing is a comparative. A row with no year is not.
rows["is_comparative"] = (is_year & (rows["period"] != FILING)).map({True: "TRUE", False: "FALSE"})

# The number in base units: printed value times its scale.
rows["value_base"] = rows["value_reported"] * rows["scale_factor"]

# Guard: within one table, each kind of number (identity) must appear only once.
# (The same number in two tables of one report is allowed: the checks compare them.)
if rows.duplicated(["table"] + IDENTITY).any():
    print(rows[rows.duplicated(["table"] + IDENTITY, keep=False)][["table"] + IDENTITY + ["raw_text"]].to_string())
    sys.exit("STOP: the same number identity appears twice in one table (see above).")

# row_ids count within one filing: EX01 in FY2024 and EX01 in FY2025 are different rows,
# told apart by source_document.
rows["row_id"] = [f"EX{i:02d}" for i in range(1, len(rows) + 1)]

rows = rows[COLUMNS]
rows.to_csv(OUTPUT, index=False)
print(rows[["row_id", "metric", "material", "period", "value_base", "printed_page"]].to_string(index=False))
print(f"\n{len(rows)} rows saved to {OUTPUT}")
