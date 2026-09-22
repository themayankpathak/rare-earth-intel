import pandas as pd
import matplotlib
matplotlib.use("Agg")  # draw to a file, not a window (the Codespace has no screen)
import matplotlib.pyplot as plt

EXTRACTED = "data/processed/extracted_v2.csv"
OUTPUT = "docs/price_trap.png"
YEARS = ["FY2023", "FY2024", "FY2025"]

rows = pd.read_csv(EXTRACTED)


def pick(metric, material, period, scope="segment"):
    # Find the one value matching this description.
    match = rows[(rows["metric"] == metric) & (rows["material"] == material)
                 & (rows["period"] == period) & (rows["entity_scope"] == scope)]
    return match["value_base"].iloc[0]


correct = []  # concentrate revenue / concentrate volume: the right pairing
naive = []    # total company revenue / concentrate volume: the trap
for year in YEARS:
    volume = pick("sales_volume", "total_REO", year)
    correct.append(pick("revenue", "total_REO", year) / volume)
    naive.append(pick("revenue", "not_applicable", year, scope="consolidated") / volume)
    print(f"{year}: correct ${correct[-1]:,.0f}/t   naive ${naive[-1]:,.0f}/t   "
          f"overstated {naive[-1] / correct[-1] - 1:+.1%}")

# Draw the two lines.
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(YEARS, naive, marker="o", color="#c0392b",
        label="Wrong: total company revenue / concentrate volume")
ax.plot(YEARS, correct, marker="o", color="#2c3e50",
        label="Right: concentrate revenue / concentrate volume")

# Write each value next to its point.
for year, value in zip(YEARS, naive):
    ax.annotate(f"${value:,.0f}", (year, value), textcoords="offset points",
                xytext=(0, 8), ha="center", color="#c0392b")
for year, value in zip(YEARS, correct):
    ax.annotate(f"${value:,.0f}", (year, value), textcoords="offset points",
                xytext=(0, -16), ha="center", color="#2c3e50")

ax.set_title("MP Materials concentrate price per tonne REO: the pairing trap")
ax.set_ylabel("USD per tonne of contained REO")
ax.set_ylim(0, max(naive) * 1.15)
ax.legend(loc="upper left", fontsize=9)
ax.grid(axis="y", alpha=0.3)
fig.text(0.01, 0.01, "Source: MP Materials FY2025 10-K, printed pp.44, 49. Basket price across the full REO mix, not an NdPr price.",
         fontsize=7, color="gray")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(OUTPUT, dpi=150)
print(f"Chart saved to {OUTPUT}")