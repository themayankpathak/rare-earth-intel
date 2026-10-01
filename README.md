# rare-earth-intel

A small, auditable pipeline that reads rare earth companies' annual reports, extracts the numbers
into a structured table where every number keeps its meaning, measures its own accuracy against
checked answers, and catches the mistakes that make naive price calculations wrong.

**Status:** v5, October 2026. Two companies, fourteen annual reports:
MP Materials (FY2020–FY2025 10-Ks, covering FY2019–FY2025) and Lynas Rare Earths (FY2019–FY2026
financial reports, covering FY2013–FY2026). One label map per company. v1 (one filing) shipped
30 Sep 2026. Started August 2026. Build log: [`notes/devlog.md`](notes/devlog.md).

![The pairing trap](docs/price_trap.png)

## Why this exists

Numbers in company reports are easy to read and easy to misuse. A number only means something
together with its context: which company, which part of it, which product, which year, which unit,
which scale. Take it out of the PDF without that context and it becomes dangerous.

The chart above shows one example. MP Materials reports a price for its rare earth concentrate per
tonne of rare earth content. Divide *total company* revenue by concentrate volume instead, and the
price comes out 0.5% too high in FY2019, 0.5% in FY2020, 1.0% in FY2021, 2.0% in FY2022, 0.4% in
FY2023, then **41% in FY2024 and 435% in FY2025**. For five years the shortcut looks fine. Then the
business changes (MP began refining its own concentrate, then selling magnet materials) and the same
calculation becomes badly wrong, with nothing in the numbers to warn you.

This is obvious to an expert who reads the right page, and invisible to a pipeline, a quick
spreadsheet estimate, or an AI tool that doesn't. The project is about making it impossible for a
machine to make it.

It is one of many traps in these reports:

| Trap | Example |
|---|---|
| Wrong pairing | MP: total revenue ÷ concentrate volume (the chart) |
| Tonnes that aren't physical tonnes | MP: 8,922 t is contained rare earth content, not the weight shipped |
| A basket price that isn't an NdPr price | MP $4,707/t and Lynas A$80.7/kg average the whole product mix |
| A unit label that is wrong in the source | Lynas five-year table: "Average selling price (per REO tonne) 80.68" is A$ per **kg** (revenue ÷ volume confirms) |
| Cash that isn't revenue | Lynas prints "Cash receipts from customers A$887.3m" right above "Sales revenue A$977.9m" |
| Revenue that isn't this year's sales | Lynas FY25 revenue includes A$13.8m of price adjustments on earlier, provisionally priced sales |
| Money outside revenue | MP: Price Protection Agreement income ($51.0m) is booked outside revenue |
| Two scales on one page | MP: "in whole units" and "in thousands" on the same page of the FY2025 10-K |
| Scale inside the label | Lynas: "(A$m)", "($'000)" and "(t)" in the row labels, not in a header |
| Modelled volumes | MP: NdPr sales tonnes convert metal to oxide at an assumed ratio (1.20 in FY2024) |
| Same label, different number | MP: "NdPr oxide and metal" is $115.1m in the revenue table, $9.3m in the related-party note |
| Same heading, different scope | MP: "Total revenue" under "Revenue:" is the whole company in FY2023, one segment in FY2024 |
| Same label, different meaning over time | MP: "Product sales" is the company total in the FY2020 10-K, one product line after "Other sales" was split out |
| A placeholder read as a number | MP FY2024 prints `1,294 200 N/A 1,094`; skip the `N/A` and FY2022 gets 1,094 t, a change figure |
| Same labels, different periods | MP: each 10-K also has a quarterly KPI table with labels identical to the annual one |
| A stated price that isn't revenue ÷ volume | MP FY2019–FY2021 use non-GAAP "Total Value Realized"; Lynas FY2017, FY2018 and FY2025 don't reconcile (open questions, below) |
| An estimate that was revised | MP: the concentrate's cerium share is 49.1% in the FY2020 10-K, 50.2% from FY2021 |
| Years in a different order | Lynas FY2019 lists `FY16 FY17 FY18 FY19`; later reports newest first; five-year tables oldest first |
| A header that looks like data | Lynas: `30 June 2019 30 June 2020 …` on one line starts with a number, so it parses as a row of values. This one fooled the pipeline (see Results) |

## What it does

```
PDF ──► extract_rows.py ──► build_rows.py ──► score.py         (accuracy vs ground truth)
         find tables,         apply label map,  self_checker.py  (checks with no answer key)
         parse lines          28-column rows    plotter.py       (the figure above)
```

Everything company-specific is configuration, not code:

| File | Says |
|---|---|
| [`config/companies.csv`](config/companies.csv) | each company's name, file prefix and year end (31 Dec for MP, 30 June for Lynas) |
| `config/<company>_tables.csv` | where to look: each table and one or more anchor phrases that find its page |
| `config/<company>_label_map.csv` | what each line means: scope, segment, material, chain stage, metric, basis, unit, and optionally scale and a note |

1. **Finding the tables.** The extractor searches the whole PDF for each table's anchor phrase,
   trying older wording if the newer is missing. If a phrase matches more than one page it stops
   instead of guessing. No page numbers in code.
2. **Extraction.** Reads each table line by line and keeps the exact printed text of every number.
   Year columns are read from the table's own header (`2025 2024 2023`, `FY26 FY25`, oldest-first
   `2022 … 2026`, `30 June 2017 30 June 2018 …`), so two-, three-, four-, five- and eight-year tables
   all work. Scale comes from the page (`in thousands`) or from the label map (`(A$m)`).
3. **Meaning.** One label map per company, keyed on table, heading and label, matched ignoring
   capital letters. A map line can name a heading or match the label under any heading (`*`); a line
   that names a heading wins. When a company rewords a label, a line is added, not a new map. Guards
   stop the build if one line gets two meanings or a number appears twice in one table.
4. **Traceability.** Every row carries its source report, PDF page, printed page and `raw_text`.
5. **Measured accuracy.** The MP FY2025 output is scored field by field against a 20-row ground truth.
6. **Automatic checks**, with no answer key, on every report:
   raw text found on the cited page; values in a plausible range for their metric and unit;
   revenue ÷ volume agrees with every stated price, allowing for how finely each number is printed;
   segment revenue bridges to the consolidated total; element shares add up to 100%; and
   **every number printed in more than one place (another report, or another table of the same report)
   agrees**.

**Rule:** no language model does arithmetic over retrieved text. Numbers go into the table; the
only division happens in code.

**Rule:** a printed number is never changed. Its meaning goes in the label map (with a note when the
source itself is wrong); a difference that is explained gets its reason and page recorded; a
difference that is not explained stays open.

## Results

| Company | Reports | Rows | Years covered | Ground truth |
|---|---|---|---|---|
| MP Materials | FY2020–FY2025 10-Ks | 135 | FY2019–FY2025 | FY2025: 20 of 20 found, 13 of 13 fields correct on all 20 |
| Lynas Rare Earths | FY2019–FY2026 financial reports | 290 | FY2013–FY2026 | none (checks only) |

| Check | Result |
|---|---|
| All automatic checks | **1,004 pass, 0 fail**, 8 expected (explained), 14 open (unexplained) |
| Numbers printed in more than one place | 99: all agree except 2 explained (MP's revised composition) |
| Revenue bridge (MP FY2025) | 160,369 + 66,861 − 2,789 = 224,441 ($k), exact |
| Concentrate composition (MP) | adds up to 100.0% in all six filings |

Each check prints PASS, FAIL, or the status of a recorded exception:

- **EXPECTED** (explained, with the page where the explanation is printed):
  - MP's Realized Price for FY2019–FY2021 is based on non-GAAP "Total Value Realized" (adjusted for
    tariff rebates), so it does not equal GAAP revenue ÷ volume
    (FY2021 10-K, printed pp.34 and 45).
  - MP's estimated element distribution was revised between the FY2020 10-K (printed p.13) and the
    FY2021 10-K (printed p.26): cerium 49.1% → 50.2%, lanthanum 33.4% → 32.3%.
- **OPEN** (a real difference nobody has explained yet; logged, visible, never counted as a pass):
  - **Lynas FY2025**: stated A$50.6/kg against A$50.73/kg from revenue ÷ volume, in two reports and
    two tables. Already ruled out: the revenue note (FY2025 report, printed p.78). Revenue from
    contracts alone gives 49.47; total revenue gives 50.73.
  - **Lynas FY2017 and FY2018**: stated prices about 2% above revenue ÷ volume (18.0 vs 17.58;
    21.6 vs 21.17), in three reports. A lead, unconfirmed: the FY2019 report calls revenue "net sales
    revenue", so the older price may be on gross sales. The FY2017–FY2018 reports are not collected.
  - **Lynas five-year table, FY2019 and FY2022**: two-decimal prices about one cent off
    (18.97 vs 18.98; 60.27 vs 60.28). The one-decimal prices in the sales table reconcile.

The open count (14) counts check lines, not questions: there are four open questions, each printed in
several tables.

**The cross-check caught a real bug.** In the Lynas FY2021–FY2024 reports the five-year table header
is `30 June 2019 30 June 2020 …` on one line. Because it starts with "30", the parser first read it
as a row of numbers, not a header, and every five-year value was filed under the wrong year (FY2019's
revenue as "FY2023"). Each number was plausible on its own; no range check could see it. But the same
year's revenue is printed in five places across four reports, and the copies disagreed. Fourteen
failures appeared at once; the fix was one line.

**How far each year is cross-checked:**

| | Reported in |
|---|---|
| MP FY2019 | 2 filings (concentrate revenue: 1) |
| MP FY2020–FY2023 | 3 filings each |
| MP FY2024 | 2 filings |
| MP FY2025 | 1 filing, but scored against ground truth |
| Lynas FY2013–FY2015 | 1 report (revenue only, from the FY2020 report's eight-year table) |
| Lynas FY2016 | 2 reports |
| Lynas FY2017 / FY2018 | 3 / 4 reports |
| Lynas FY2019–FY2022 | 5 reports each |
| Lynas FY2023 / FY2024 / FY2025 | 4 / 3 / 2 reports |
| Lynas FY2026 | 1 report |

**Read these honestly.** Values, scales, pages and raw text are extracted independently by code, so
those scores are a real test. The classification fields (basis, chain stage, confidence…) come from
the label map, written with the same judgement as the ground truth; for those, the score shows the
map is applied consistently, not that classification was learned. Lynas has no ground truth; it is
guarded by the checks alone.

The checks catch symptoms, not every error. To test them, an earlier `N/A` bug was put back on
purpose: it produces three wrong MP FY2022 values, and the checks flag one of them (a −$19/kg price,
out of range). The other two (1,094 t and 1,132 t) are plausible and have no second source, so they
pass. One red flag would lead a person to the line and to all three, but that is a limit worth
knowing.

## Ground truth

20 rows from the MP FY2025 10-K, chosen to be hard rather than representative: each one targets a
trap. Stored in [`data/ground-truth/`](data/ground-truth/) as an Excel workbook (with live
consistency checks) and a CSV the code reads.

The rows were drafted with AI assistance. Every value was then machine-checked against the text of
its cited page, and the arithmetic reconciliations pass; they have not all been manually reviewed
row by row. Where the extractor and ground truth disagree, the page decides.

## Run it

```bash
pip install -r requirements.txt

for f in FY2025 FY2024 FY2023 FY2022 FY2021 FY2020; do
  python scripts/extract_rows.py mp $f       # PDF -> data/interim/mp_extracted_rows_FYyyyy.csv
  python scripts/build_rows.py mp $f         # + label map -> data/processed/mp_extracted_FYyyyy.csv
done
for f in FY2026 FY2025 FY2024 FY2023 FY2022 FY2021 FY2020 FY2019; do
  python scripts/extract_rows.py lynas $f
  python scripts/build_rows.py lynas $f
done
python scripts/score.py                      # MP FY2025 accuracy vs ground truth
python scripts/self_checker.py               # checks on every report, and across reports
python scripts/plotter.py                    # -> docs/price_trap.png
```

The extractor reads every page once to find the tables: under a minute for most reports, about two
minutes each for MP's FY2021, FY2023 and FY2024 PDFs (400+ pages, exhibits included).

**Source documents** (not committed). Save each under `data/raw/` with the name shown and verify with
`sha256sum`. Page references assume these exact files; other copies can paginate differently.

| File | Source | Pages | SHA-256 |
|---|---|---|---|
| `mp-materials_10k_FY2025.pdf` | [0001801368-26-000008](https://www.sec.gov/Archives/edgar/data/1801368/000180136826000008/mp-20251231.htm) | 121 | `c28ed1338d6ff136b8de06ad6ef768613dec44968cb88e4e00db9779b0f104a1` |
| `mp-materials_10k_FY2024.pdf` | [0001801368-25-000009](https://www.sec.gov/Archives/edgar/data/1801368/000180136825000009/mp-20241231.htm) | 444 | `b24f88946900d3153dfe45f9ee6d6c9c964f012f38119d567fe4aa32e5f38445` |
| `mp-materials_10k_FY2023.pdf` | [0001801368-24-000014](https://www.sec.gov/Archives/edgar/data/1801368/000180136824000014/mp-20231231.htm) | 404 | `193ee7039bd9bfe6a7468de0b60ea4e9108971bd56f00917ef1a3c403ae11bb0` |
| `mp-materials_10k_FY2022.pdf` | [0001801368-23-000009](https://www.sec.gov/Archives/edgar/data/1801368/000180136823000009/0001801368-23-000009-index.htm) | 110 | `bfbe5cf67dcbb44e2071f5a799f1e92a98d489763b75e7795ca2d207cc127913` |
| `mp-materials_10k_FY2021.pdf` | [0001801368-22-000010](https://www.sec.gov/Archives/edgar/data/1801368/000180136822000010/0001801368-22-000010-index.htm) | 414 | `938c8cd9471078f4b9e4bfba9e225b3e1aa8bbd46576a333b426d3acda5aa14f` |
| `mp-materials_10k_FY2020.pdf` | [0001801368-21-000011](https://www.sec.gov/Archives/edgar/data/1801368/000180136821000011/0001801368-21-000011-index.html) | 124 | `858be5b31ff450772f073f542d195cfd9dcd62f81d92c4c1f259a1ce254e928e` |
| `lynas_financial_FY2026.pdf` | Lynas Appendix 4E / annual report, year to 30 June 2026 | 141 | `82f9b0ffff029d0581231badaeb5dad662036b4d3987b35fbc965b0e1646303c` |
| `lynas_financial_FY2025.pdf` | same, year to 30 June 2025 | 125 | `15fd5fce3a649ef94fb903d5fb1757639bb36bacf44d92abb0e21d94925c86eb` |
| `lynas_financial_FY2024.pdf` | Consolidated Financial Report, year to 30 June 2024 | 109 | `59f179e3e8864f4c83231ff41a18b4ec3931694ff586b36e27e7a1a1a4462974` |
| `lynas_financial_FY2023.pdf` | same, year to 30 June 2023 | 104 | `490458642fc54e98065b7b2578e68dc1c7430b71b2e301ae95c9367b88fc3fb5` |
| `lynas_financial_FY2022.pdf` | same, incorporating Appendix 4E, year to 30 June 2022 | 102 | `642fed8b4d3b25abf8d07fcf326d06bdb67a9cf2da7b4552c6f2a5d1225b88eb` |
| `lynas_financial_FY2021.pdf` | Appendix 4E, year to 30 June 2021 | 83 | `c7466d4ce5d073e481d738647a4d6e67104d72061e1119791e207c9bba9d2f51` |
| `lynas_financial_FY2020.pdf` | Appendix 4E, year to 30 June 2020 (Lynas Corporation Ltd) | 75 | `6e948130e4f52730b2f28cdf30bf0e219d93d327948104cd4b2b1c48866a9ada` |
| `lynas_financial_FY2019.pdf` | Appendix 4E, year to 30 June 2019 (Lynas Corporation Ltd) | 71 | `f1a46d82d75de601c49cfbc95dbdd3363791777793a4863d4932cde900114616` |

Lynas Corporation Ltd became Lynas Rare Earths Ltd between the FY2020 and FY2021 reports (same ACN 009 066 648). The glossy
Lynas annual reports for FY2019–FY2024 contain the same financial report and are kept only for
reference. A browser "Print to PDF" copy has no text layer and different page numbers; this project
started with one.

## Known limitations

- Two companies, US and Australian reporting habits. The parser still assumes English labels,
  parentheses for negatives, and that a table's years appear on a header line.
- The chart covers MP only.
- MP's composition table is treated as having no period; the FY2020 → FY2021 revision is recorded as
  an exception rather than modelled as a dated estimate.
- Some years come from one report only and cannot be cross-checked (see the table above).
- "In thousands, except per share data" is applied to per-share rows too (not mapped, so no effect).
- A heading carries over until the next heading, so a line can inherit the wrong section name. Map
  lines that need a heading name it explicitly; the rest match under any heading.

## Roadmap

- **More English-language companies**: Neo Performance Materials next, then JL Mag's English Hong
  Kong reports (an English route into a Chinese company).
- **Close the open questions**: the Lynas FY2025 and FY2017–FY2018 price gaps (quarterly reports,
  older annual reports).
- **Chinese sources**: the schema already carries `language` and `scale_factor` (for 万 and 亿);
  next is a feasibility test on one report and a `parse_quantity(text, lang)` with tests.
- **Cross-source reconciliation**: company figures against USGS, IEA and trade data.
- **Structured data where it exists**: GAAP figures are published by the SEC in machine-readable
  form (XBRL) and could check the parsed values. Operating figures (volumes, realized prices)
  generally are not, which is why the documents are parsed.
- **AI-drafted label maps**: a language model proposes map entries for a new company, a person
  reviews them. Classification, not arithmetic.
- **Question answering with citations**: answer numeric questions from the table, cite the page,
  refuse when the data isn't there.

## Repository layout

```
config/            companies list; per company: table list (where to look), label map (what it means)
data/ground-truth/ 20 checked rows: workbook + CSV (tracked)
data/raw/          source PDFs (ignored; see "Run it")
data/interim/      parser output per report (ignored, regenerated)
data/processed/    28-column rows per report (ignored, regenerated)
docs/              the chart
notes/             design notes (PROJECT.md), sources, build log
scripts/           the pipeline
```

## About

Built by Mayank Pathak, who works in the NdFeB magnet supply chain. The domain rules, trap
selection and design are his; the Python was written with AI assistance.
