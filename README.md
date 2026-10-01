# rare-earth-intel

A small, auditable pipeline that reads a rare earth company's annual reports, extracts the numbers
into a structured table where every number keeps its meaning, measures its own accuracy against
checked answers, and catches the mistakes that make naive price calculations wrong.

**Status:** v2, October 2026 — one company (MP Materials), three annual reports (FY2023–FY2025 10-Ks),
one label map for all of them. v1 (one filing) shipped 30 Sep 2026.
Started August 2026. Build log: [`notes/devlog.md`](notes/devlog.md).

![The pairing trap](docs/price_trap.png)

## Why this exists

Numbers in company reports are easy to read and easy to misuse. A number only means something
together with its context: which part of the company, which product, which year, which unit, which
scale. Take it out of the PDF without that context and it becomes dangerous.

The chart above shows one example. MP Materials reports a price for its rare earth concentrate per
tonne of rare earth content. Divide *total company* revenue by concentrate volume instead, and the
price comes out 1.0% too high in FY2021, 2.0% in FY2022, 0.4% in FY2023 — then **41% in FY2024 and
435% in FY2025**. For three years the shortcut looks fine. Then the business changes (MP began
refining its own concentrate, then selling magnet materials) and the same calculation becomes
badly wrong, with nothing in the numbers to warn you.

This is obvious to an expert who reads the right page, and invisible to a pipeline, a quick
spreadsheet estimate, or an AI tool that doesn't. The project is about making it impossible for a
machine to make it.

It is one of several traps in these filings:

| Trap | Example |
|---|---|
| Wrong pairing | total revenue ÷ concentrate volume (the chart) |
| Tonnes that aren't physical tonnes | 8,922 t is contained rare earth content, not the weight shipped |
| A basket price that isn't an NdPr price | $4,707/t averages the full mix, about half of it low-value cerium |
| Two scales on one page | "in whole units" and "in thousands" on the same page of the FY2025 10-K |
| Money that isn't revenue | Price Protection Agreement income ($51.0m) is booked outside revenue |
| Modelled volumes | NdPr sales tonnes convert metal to oxide at an assumed ratio (1.20 in FY2024) |
| Same label, different number | "NdPr oxide and metal" is $115.1m in the revenue table but $9.3m in the related-party note |
| Same heading, different scope | "Total revenue" under "Revenue:" is the whole company in the FY2023 10-K, one segment in FY2024 |
| A placeholder read as a number | FY2024 prints `1,294 200 N/A 1,094`; skip the `N/A` and FY2022 gets 1,094 t, which is a change figure |
| Same labels, different periods | each 10-K also has a quarterly KPI table with labels identical to the annual one |
| A stated price that isn't revenue ÷ volume | FY2021 Realized Price ($7,745/t) uses non-GAAP "Total Value Realized"; GAAP revenue ÷ volume is $7,794/t |

## What it does

```
PDF ──► extract_rows.py ──► build_rows.py ──► score.py         (accuracy vs ground truth)
         find tables,         apply label map,  self_checker.py  (checks with no answer key)
         parse lines          28-column rows    plotter.py       (the figure above)
```

1. **Finding the tables** — [`config/mp_tables.csv`](config/mp_tables.csv) lists each table with an
   anchor phrase that appears on exactly one page of every filing. The extractor searches the whole
   PDF; if a phrase matches more than one page it stops instead of guessing. No page numbers in code.
2. **Extraction** — reads each table line by line, tracking the scale header and section heading each
   number sits under, and keeps the exact printed text of every number. Year columns come from the
   filing (the FY2024 10-K shows FY2024, FY2023, FY2022).
3. **Meaning** — one label map for the company ([`config/mp_label_map.csv`](config/mp_label_map.csv))
   records what each line means: scope, segment, material, chain stage, basis, unit. It is keyed on
   table, heading and label, so when MP changes its wording a line is added, not a new map.
4. **Traceability** — every row carries its source filing, PDF page, printed page and `raw_text`.
5. **Measured accuracy** — the FY2025 output is scored field by field against a 20-row ground truth.
6. **Automatic checks**, with no answer key, on every filing:
   raw text found on the cited page; values in a plausible range for their metric and unit;
   revenue ÷ volume agrees with the stated price (concentrate $/t and NdPr $/kg), allowing for the
   rounding of each printed number; segment revenue bridges to the consolidated total; element shares
   of the concentrate add up to 100%; and **every number reported in more than one filing is the same
   in each**.

**Rule:** no language model does arithmetic over retrieved text. Numbers go into the table; the
only division happens in code.

## Results

| Filing | Rows extracted | Ground truth |
|---|---|---|
| FY2025 10-K | 34 | 20 of 20 found; 13 of 13 fields correct on all 20 |
| FY2024 10-K | 27 | — (checks only) |
| FY2023 10-K | 23 | — (checks only) |

| Check | Result |
|---|---|
| All automatic checks | 209 pass, 0 fail, 1 expected exception (documented below) |
| Price reconciliation | agrees with the stated price for every year shown in every filing, except FY2021 |
| Revenue bridge (FY2025) | 160,369 + 66,861 − 2,789 = 224,441 ($k), exact |
| Concentrate composition | 50.2 + 32.3 + 15.7 + 1.8 = 100.0% in all three filings |
| Across filings | all 26 numbers reported in more than one filing agree |

**The one expected exception.** For FY2021, revenue ÷ volume is $7,794/t but MP states $7,745/t.
This is not an error: that year's Realized Price is based on a non-GAAP measure adjusted for tariff
rebates (FY2023 10-K, printed p.38). The check still runs and prints both numbers; it reports
EXPECTED with the reason instead of FAIL. Any other mismatch is still a failure.

**How far each year is cross-checked.** Each 10-K repeats the two prior years, so most years are
reported more than once:

| Year | Reported in | Cross-checked |
|---|---|---|
| FY2021 | FY2023 10-K | no — one source |
| FY2022 | FY2023, FY2024 10-Ks | yes |
| FY2023 | FY2023, FY2024, FY2025 10-Ks | yes |
| FY2024 | FY2024, FY2025 10-Ks | yes |
| FY2025 | FY2025 10-K | no — but scored against ground truth |

**Read these honestly.** Values, scales, pages and raw text are extracted independently by code, so
those scores are a real test. The classification fields (basis, chain stage, confidence…) come from
the label map, which was written with the same judgement as the ground truth — for those, the score
shows the map is applied consistently, not that classification was learned.

The checks catch symptoms, not every error. To test them, the `N/A` bug was put back on purpose:
it produces three wrong FY2022 values, and the checks flag one of them (a −$19/kg NdPr price,
out of range). The other two (1,094 t and 1,132 t) are plausible numbers, and no other filing
reports FY2022 NdPr volumes to compare against, so they pass. One red flag would lead a person to
the line and to all three — but that is a limit worth knowing.

## Ground truth

20 rows from the FY2025 10-K, chosen to be hard rather than representative: each one targets a
trap. Stored in [`data/ground-truth/`](data/ground-truth/) as an Excel workbook (with live
consistency checks) and a CSV the code reads.

The rows were drafted with AI assistance. Every value was then machine-checked against the text of
its cited page, and the arithmetic reconciliations pass; they have not all been manually reviewed
row by row. Where the extractor and ground truth disagree, the page decides.

## Run it

```bash
pip install -r requirements.txt

for f in FY2025 FY2024 FY2023; do
  python scripts/extract_rows.py $f    # PDF -> data/interim/extracted_rows_FYyyyy.csv
  python scripts/build_rows.py $f      # + label map -> data/processed/extracted_FYyyyy.csv
done
python scripts/score.py                # FY2025 accuracy vs ground truth
python scripts/self_checker.py         # checks on every filing, and across filings
python scripts/plotter.py              # -> docs/price_trap.png

python scripts/page_looker.py 49       # print any printed page of the FY2025 10-K
```

The extractor reads every page once to find the tables: about half a minute for the FY2025 10-K
and about two minutes each for the FY2023 and FY2024 PDFs (400+ pages, exhibits included).

**Source documents** (not committed). Save each as `data/raw/mp-materials_10k_FYyyyy.pdf` and verify
with `sha256sum`. Page references assume these exact files; other copies of the same filing can
paginate differently.

| File | Filing (EDGAR accession) | Pages | SHA-256 |
|---|---|---|---|
| `mp-materials_10k_FY2025.pdf` | [0001801368-26-000008](https://www.sec.gov/Archives/edgar/data/1801368/000180136826000008/mp-20251231.htm) | 121 | `c28ed1338d6ff136b8de06ad6ef768613dec44968cb88e4e00db9779b0f104a1` |
| `mp-materials_10k_FY2024.pdf` | [0001801368-25-000009](https://www.sec.gov/Archives/edgar/data/1801368/000180136825000009/mp-20241231.htm) | 444 | `b24f88946900d3153dfe45f9ee6d6c9c964f012f38119d567fe4aa32e5f38445` |
| `mp-materials_10k_FY2023.pdf` | [0001801368-24-000014](https://www.sec.gov/Archives/edgar/data/1801368/000180136824000014/mp-20231231.htm) | 404 | `193ee7039bd9bfe6a7468de0b60ea4e9108971bd56f00917ef1a3c403ae11bb0` |

A browser "Print to PDF" copy has no text layer and different page numbers — this project started
with one.

## Known limitations

- One company, three filings (FY2023–FY2025), four tables per filing.
- **FY2020–FY2022 10-Ks are not handled yet.** They use different wording ("Product sales",
  lowercase KPI labels), FY2020 has two year columns instead of three, and the realized price before
  FY2022 is non-GAAP. Two meaning changes already found there: FY2020 revenue was later split between
  "Product sales" and a new "Other sales" line ($134.3m became $133.7m + $0.6m), and the estimated
  element distribution of the concentrate was revised (cerium 49.1% in the FY2020 10-K, 50.2% from
  FY2021).
- The composition table is treated as having no period. That holds for FY2021–FY2025, where the
  estimate is unchanged, but not across the FY2020 revision above.
- FY2021 and FY2025 figures come from one filing each and cannot be cross-checked.
- "In thousands, except per share data" is applied to per-share rows too (not mapped, so no effect).
- A heading carries over until the next heading, so a line can inherit the wrong section name. The
  label map keys on table and label as well, so this does not affect results — but a section name is
  a hint, not a meaning.

## Roadmap

- **Older MP filings (FY2020–FY2022)** — a few synonym lines in the map, year columns per filing,
  backup anchors, and recorded exceptions for the non-GAAP price and the revenue reclassification.
  Adds FY2019–FY2020 and a third source for FY2021.
- **Structured data where it exists** — GAAP figures such as total revenue are published by the SEC
  in machine-readable form (XBRL) and could be used to check the parsed values. Operating figures
  (volumes, realized prices) generally are not, which is why the documents are parsed.
- **More companies** (Lynas, Neo Performance Materials, others) — one label map and one table list
  per company; unmapped labels get flagged automatically.
- **AI-drafted label maps** — a language model proposes map entries for a new company, a person
  reviews them. Classification, not arithmetic.
- **Chinese sources** — the schema already carries `language` and `scale_factor` (for 万 and 亿);
  next is a `parse_quantity(text, lang)` with tests.
- **Question answering with citations** — answer numeric questions from the table, cite the page,
  refuse when the data isn't there.

## Repository layout

```
config/            table list (where to look) and label map (what it means), per company
data/ground-truth/ 20 checked rows: workbook + CSV (tracked)
data/raw/          source PDFs (ignored; see "Run it")
data/interim/      parser output per filing (ignored, regenerated)
data/processed/    28-column rows per filing (ignored, regenerated)
docs/              the chart
notes/             design notes (PROJECT.md), sources, build log
scripts/           the pipeline
```

## About

Built by Mayank Pathak, who works in the NdFeB magnet supply chain. The domain rules, trap
selection and design are his; the Python was written with AI assistance.