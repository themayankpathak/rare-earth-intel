import glob
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # draw to a file, not a window (the Codespace has no screen)
import matplotlib.pyplot as plt

FILES = sorted(glob.glob("data/processed/extracted_FY*.csv"))
OUTPUT = "docs/price_trap.png"

# All filings in one table. For a year reported in several filings, keep the latest filing's value
# (self_checker.py confirms the filings agree before we rely on this).
rows = pd.concat(pd.read_csv(path) for path in FILES)
rows = rows.sort_values("source_document").drop_duplicates(
    ["entity_scope", "segment", "material", "metric", "period"], keep="last")


def pick(metric, material, period, scope="segment"):
    # The one value matching this description, or None if no filing reports it.
    match = rows[(rows["metric"] == metric) & (rows["material"] == material)
                 & (rows["period"] == period) & (rows["entity_scope"] == scope)]
    return match["value_base"].iloc[0] if len(match) else None


# Every year that has all three numbers the chart needs.
years, correct, naive = [], [], []
for year in sorted(p for p in rows["period"].unique() if p.startswith("FY")):
    volume = pick("sales_volume", "total_REO", year)
    concentrate = pick("revenue", "total_REO", year)
    total = pick("revenue", "not_applicable", year, scope="consolidated")
    if None in (volume, concentrate, total):
        continue
    years.append(year)
    correct.append(concentrate / volume)  # concentrate revenue / concentrate volume: the right pairing
    naive.append(total / volume)          # total company revenue / concentrate volume: the trap
    print(f"{year}: correct ${correct[-1]:,.0f}/t   naive ${naive[-1]:,.0f}/t   "
          f"overstated {naive[-1] / correct[-1] - 1:+.1%}")

# Draw the two lines.
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(years, naive, marker="o", color="#c0392b",
        label="Wrong: total company revenue / concentrate volume")
ax.plot(years, correct, marker="o", color="#2c3e50",
        label="Right: concentrate revenue / concentrate volume")

# Write each value next to its point.
for year, value in zip(years, naive):
    ax.annotate(f"${value:,.0f}", (year, value), textcoords="offset points",
                xytext=(0, 8), ha="center", color="#c0392b")
for year, value in zip(years, correct):
    ax.annotate(f"${value:,.0f}", (year, value), textcoords="offset points",
                xytext=(0, -16), ha="center", color="#2c3e50")

ax.set_title("MP Materials concentrate price per tonne REO: the pairing trap")
ax.set_ylabel("USD per tonne of contained REO")
ax.set_ylim(0, max(naive) * 1.15)
ax.legend(loc="upper left", fontsize=9)
ax.grid(axis="y", alpha=0.3)
fig.text(0.01, 0.01,
         "Source: MP Materials 10-Ks FY2023-FY2025 (each year from the latest filing that reports it). "
         "Basket price across the full REO mix, not an NdPr price.\n"
         "Right = GAAP revenue / volume. For FY2021 MP's stated Realized Price ($7,745) uses non-GAAP Total Value Realized.",
         fontsize=7, color="gray")
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(OUTPUT, dpi=150)
print(f"Chart saved to {OUTPUT}")