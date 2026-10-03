# Build log

Short dated entries, written at the end of each session.

## 2026-09-21 — Day 1

**Did:** Built the 20-row ground truth for the MP Materials FY2025 10-K. All workbook checks pass,
including the reconciliation: concentrate revenue / REO sales volume = $4,706.57 vs stated $4,707 (0.009%).

**Went wrong:** The first 10-K copy was a browser print-to-PDF with no text layer (221 image pages).
Replaced it with the original Workiva PDF (121 pages, SHA-256 recorded in the sources sheet).
Every pdf_page reference changed; printed page numbers did not.

**Went wrong:** `.gitignore` had `data/`, which ignores the whole folder, so the ground truth could not
be committed and git gave no warning. Changed to `data/*` + `!data/ground-truth/`.

**Found:** Check 3 compared the text "TRUE" (from the dropdown) against a boolean, so it would have
flagged every correct comparative row. Rewrote it with SUMPRODUCT.

**Decision:** The ground truth was drafted with AI assistance. I verify each row against its cited page on Day 2.

**Next:** Verify the 20 rows; first script that opens the PDF and prints a page.

## 2026-09-21 — Day 2 (same day as Day 1)

**Did:** First script (`scripts/page_looker.py`): prints any page of the 10-K by its printed page number.
Confirmed the code sees the same numbers as the ground truth on printed pp.44 and 49.

**Found:** Table lines carry $ change and % change columns after the three years; negatives are in
parentheses; em-dashes mean no value; footnote markers like "(1)" stick to labels. Printed p.49 has two
scale headers ("in whole units", then "in thousands"), and section headings carry meaning, so the parser
must read top to bottom and remember the last scale header and heading it passed.

**Decision:** Skipped manual row-by-row review of the ground truth. Values are machine-checked instead.

## 2026-09-22 — Days 3–7

**Did:** Line parser, page extractor, label map, 28-column row builder, scorer, self-checks, chart.
README rewritten to match what is built.

**Result:** 18 of 20 ground-truth rows found (GT18/19 are on p.29, not parsed). All 13 fields correct on
all 18. 64 of 64 self-checks pass. Revenue / volume matches MP's stated price within 0.01% for all three years.

**Found:** The scorer caught a format bug in the ground-truth CSV: exporting from Excel turned text "TRUE"
into "True", so is_comparative scored 0/18. Fixed the data, not the comparison.
Same label, different number: "NdPr oxide and metal" is $115.1m on p.44 but $9.3m (related-party) on p.105.
PPA income sits under a "Revenue:" heading but is not revenue.
The pairing trap (total revenue / concentrate volume) is 0.4% off in FY2023 and 435% off in FY2025.

**Decision:** Ship first; learn the Python properly before interviews. Code written with AI assistance.

**Next:** Buffer days. Stretch: p.29 parsing, parse_quantity for Chinese units.

## 2026-10-01 — Day 11

**Did:** Parsed printed p.29 (Estimated distribution of TREO content). Text cleaner keeps a
trailing "%" in raw_text, as printed. Extractor takes per-page year columns and starting scale;
p.29 has neither, so it is read with period `not_applicable` and scale 1. Build step leaves
fiscal-year fields blank when the period is not a fiscal year. Label map: four p.29 lines
(Ce, La, NdPr, SEG+). New self-check: element shares sum to 100%.

**Result:** 20 of 20 ground-truth rows found, 13/13 fields correct on all 20. 73 of 73 checks pass.
EX01–EX30 unchanged; p.29 adds EX31–EX34.

**Found:** Adding p.29 with no scale header gave its rows an empty scale_factor, and one empty
value turned the whole column from 1000 into 1000.0. Scoring reads everything as text, so
scale_factor dropped to 0/18 on rows that were never touched. Fixed by giving p.29 a real scale.
Also: the new composition check failed (0 elements, sum 0%) when the label map had not been
saved — it caught a missing-data problem on its first run.

**Decision:** p.29 is read last so existing row_ids stay stable (schema: never renumber).
All four elements mapped, not only the two in the ground truth, so the sum check works.
`La` and `SEG+` added as material values.

**Next:** Update CLAUDE.md handoff. Optional: FY2024 10-K run (self-checks only).

## 2026-10-01 — Day 11 (continued): v2, three filings

**Did:** Ran the pipeline on the FY2023 and FY2024 10-Ks as well as FY2025, with no page numbers in
code. Tables are found by anchor phrases listed in `config/mp_tables.csv` (stop if a phrase matches
more than one page); printed page numbers read from the page footer; year columns taken from the
filing. One label map for the company (`config/mp_label_map.csv`), keyed on table, heading and label,
replacing `mp_fy2025_label_map.csv`. Text cleaner treats `N/A` as "no value". New checks: NdPr $/kg
price, rounding-aware price reconciliation, and agreement of every number across filings.
Chart now covers FY2021–FY2025.

**Result:** FY2025: 34 rows, identical to v1 output, 20/20 ground truth. FY2024: 27 rows. FY2023: 23
rows. 209 checks pass, 0 fail, 1 expected exception. All 26 numbers reported in more than one filing
agree. Pairing trap: +1.0%, +2.0%, +0.4%, +41.2%, +434.5% (FY2021–FY2025).

**Found:**
- `N/A` in a value column (FY2024 KPI table). The old parser skipped it and took the next number, so
  FY2022 NdPr production became 1,094 t and the FY2022 NdPr price −$19/kg. Re-introducing the bug on
  purpose showed the checks catch only the −$19 (range); the two volumes are plausible and have no
  second source. Checks catch symptoms, not every error.
- "Total revenue" under "Revenue:" means the whole company in the FY2023 10-K and the Materials
  segment in FY2024. Heading + label is not enough; the table is part of the key.
- The FY2023 10-K has a quarterly KPI table with the same labels as the annual one. Anchors pick the
  annual table ("in whole units or dollars, except percentages"); the quarterly one lacks
  "except percentages".
- FY2021 Realized Price ($7,745/t) is non-GAAP; revenue ÷ volume gives $7,794/t. Recorded as a known
  exception with its page reference (FY2023 10-K, printed p.38) rather than loosening the check.
- Small volumes make exact price checks meaningless: FY2023 NdPr sales of "10" t could be 9.5–10.5 t.
  Price checks now ask whether any unrounded values consistent with the printed ones fit.
- FY2020–FY2022 filings differ in wording, columns and definitions. Also found there: FY2020 revenue
  later split into "Product sales" + "Other sales", and the element distribution revised (Ce 49.1% →
  50.2%). Not built; recorded in README limitations and roadmap.

**Decision:** v2 scope is FY2023–FY2025. FY2020–FY2022 decided later (option C). row_ids count
within each filing; rows are told apart by source_document. The chart takes each year from the
latest filing that reports it, after the cross-filing check confirms they agree.

**Next:** Update CLAUDE.md handoff. Decide on FY2020–FY2022. GitHub About box; resume bullet and
LinkedIn post.
## 2026-10-01 — Day 11 (continued): v4 and v5, second company (Lynas)

**Did:** Company became an input (`extract_rows.py lynas FY2026`); `config/companies.csv` holds each
company's entity, file prefix and year end. Year reader handles `FY26`, oldest-first years,
`30 June 2017 …` dates and any number of columns; the cleaner takes as many values as there are year
columns. Scale and notes can come from the label map (Lynas prints "(A$m)" in labels). Footer page
number read from the last two lines. Price checks work out rounding from how each number is printed;
the cross-check compares every place a number is printed (other reports and other tables), and the
company is part of each number's identity. New status OPEN for real, unexplained differences.
Lynas files renamed `lynas_financial_FY2019`–`FY2026` (all are the full-year Appendix 4E / financial
report; the glossy annual reports FY2019–24 kept as `lynas_annual_*` for reference).

**Result:** MP unchanged (identical output, 20/20). Lynas 44/44/44/44/29/29/32/24 rows (FY2026→FY2019),
covering FY2013–FY2026. 1,004 checks pass, 0 fail, 8 expected, 14 open. 99 numbers printed in more
than one place; all agree except MP's two explained composition revisions.

**Found:**
- The cross-check caught a parser bug: Lynas FY2021–24 five-year headers read `30 June 2019 30 June
  2020 …` on one line; starting with "30", it parsed as numbers, so every five-year value was filed
  under the wrong year. Each value was plausible alone; five copies of the same year disagreed.
- Lynas five-year table labels the price "(per REO tonne)" but the values are A$ per kg. Mapped with
  the true unit and a note; the printed number is untouched; the price check confirms per kg.
- "Cash receipts from customers" sits next to "Sales revenue": mapped as its own metric.
- Lynas FY25 revenue includes A$13.8m of price adjustments on earlier provisional sales.
- OPEN: FY25 price (50.6 vs 50.73; revenue note checked, does not explain it); FY17/FY18 prices ~2%
  above revenue ÷ volume (lead: "net sales revenue", unconfirmed, older reports not collected);
  one-cent gaps in the two-decimal five-year prices (FY2019, FY2022).

**Decision:** never change a printed number; explained differences are EXPECTED with a page;
unexplained ones stay OPEN. Lynas series = financial reports (unbroken FY2019–FY2026).

**Next:** Neo Performance Materials, then JL Mag English reports, then a Chinese feasibility test.
GitHub About box; resume bullet.

## 2026-10-01 — Day 11 (continued): v6, third company (Neo)

**Did:** Added Neo Performance Materials from its FY2022–FY2025 MD&As (files renamed `neo_mda_FY2022`–
`FY2025`). Five tables per MD&A: selected financial highlights (segment revenue, corporate /
eliminations, consolidated revenue), the reconciliation table (consolidated sales volume) and one
table per segment (Magnequench, C&O, Rare Metals: volume and revenue). Parser changes: anchors can
require two phrases on one page (`10.1 Magnequench && Sales volume (tonnes)`); every run of years in a
header is read, and a `Three Months Ended … Year Ended` line decides which block is the full year;
percentage columns are dropped and the quarter block skipped; the page's header is read before its
rows; a line of `Q4 Q3 Q2 Q1` labels stops annual values until the next header; dot leaders are
dropped from labels; a page number in the middle of a footer is read. New config
`neo_scope_changes.csv` adds notes to affected rows (ZAMR closure FY2024, JAMR/ZAMR sale FY2025,
Quapaw sale FY2025), each with its page. New checks: segment revenues + corporate / eliminations =
consolidated revenue; segment volumes >= consolidated volume.

**Result:** Neo 29 rows per MD&A (116), covering FY2020–FY2025. MP and Lynas output identical to v5 in
all 14 files; MP 20/20. 1,291 checks pass, 0 fail, 8 expected, 14 open (unchanged; all MP and Lynas).
Neo revenue bridge exact in every year; all 35 Neo numbers printed in more than one place agree.
134 multi-place numbers across the three companies.

**Found:**
- Neo's consolidated sales volume adds up tonnes of different products. FY2025: revenue ÷ 13,216 t =
  $36k/t, while segments are about $19k/t (C&O), $34k/t (Magnequench) and $461k/t (Rare Metals). Every
  Neo volume row is marked confidence low with a note: a product mix, not a basis for a price.
- 2024–25 MD&As put the quarter before the full year; 2022–23 put the year first. Reading "first
  numbers = years" would give FY2025 volume 2,988 t (Q4) instead of 13,216 t.
- In the FY2024 reconciliation page the volume row comes out of the PDF before its own header.
- The FY2025 Rare Metals page also holds the start of the quarterly results table (`2025 2024` above
  `Q4 Q3 Q2 Q1 …`): its quarters were read as years. The duplicate guard stopped the build.
- Segment volumes exceed consolidated by 40–226 t a year: segments are reported before intercompany
  eliminations (FY2025 MD&A printed p.20). Checked as an inequality, not an equality.
- FY2023 splits a label over two lines (`Sales volume` / `(tonnes)`): one specific map line.
- Lynas is one company renamed (Lynas Corporation → Lynas Rare Earths, same ACN), handled as one
  identity. The opposite case matters more: same name, different business (Neo's plant sales; MP's
  move into refining and magnets). Neo's pre-2017 history is Molycorp's: a different company.

**Decision:** Neo kept at FY2022–FY2025 MD&As for now; older MD&As (FY2019–21) on the roadmap. Next
source: JL Mag's English Hong Kong reports.

**Next:** Commit v6. Inspect JL Mag. Optional: a Neo chart (revenue per tonne by segment vs the
consolidated "average").

## 2026-10-02 — Day 12: v7, a government source (USGS)

**Did:** Added the USGS Mineral Commodity Summaries rare earths chapter, editions 2019–2026 (files
`usgs_mcs_ED2019`–`ED2026`). Two tables per edition: US salient statistics (production, prices of Nd,
NdPr, Dy and Tb oxides) and world mine production by country. `config/companies.csv` gained per-source
reading rules: doc_type, superscripts (drop for USGS), dash_means (zero for USGS), precision
(significant for USGS), usgs_country (MP → United States). Extractor: characters smaller than three
quarters of the page's main text size are removed before reading (footnote numbers, "e" marks); the
"e" marks become estimate flags per value, per year column, or for a whole block when on a heading.
Placeholders NA, W, XX, E keep their column. Page numbers: one to three digits only; also read from a
page's first line. Build: map lines can name the entity (each country); estimates get a note and low
confidence; "comparative" now means earlier than the latest year in the document; duplicate guard
includes the entity. Checks: ranges by scope (country, world); USGS rounding by significant digits;
an estimate revised by a later edition is EXPECTED if the non-estimates agree; new check: MP's own
production against USGS's US figure.

**Result:** USGS 336 rows from 8 editions, 2014–2025, 13 entities. Companies unchanged (all 18 outputs
identical to v6); MP 20/20. 2,041 checks pass, 0 fail, 46 expected (38 of them USGS estimate revisions),
15 open. MP vs USGS: 7 of 7 years agree within USGS rounding (2019–2025). 877 rows in total; 244
numbers printed in more than one place.

**Found:**
- The downloaded "2021" chapter was byte-for-byte the 2020 edition (same SHA-256); the real 2021
  edition was downloaded and added.
- Footnote numbers glued to values: "China 11105,000" (footnote 11 + 105,000); Australia's reserves
  read as 135,700,000 are 5,700,000 + footnote 13. They are printed smaller, so they can be removed by size.
- USGS revises: Australia 2024 13,000 t → 29,000 t (2026 edition, "revised based on Government
  reports"); China 2023 240,000 → 255,000; US 2021 43,000 → 42,000 → 42,400.
- Nd oxide 2021 price restated from $49 to $98/kg in the 2024 edition while 2020 stayed; the price
  source footnote changed at the same time. Logged OPEN.
- USGS's US production includes more than Mountain Pass (southeastern US monazite; Utah compounds in
  2026), yet MP agrees within rounding every year. My earlier claim that the US figure "is essentially
  MP's" was corrected from the documents.
- In USGS tables "—" means zero, the 2021–2023 chapter files have no printed page numbers, and the
  2025 file spaces its page number as "14 5".
- Lynas is not compared with Australia: June fiscal years and finished-product REO vs calendar-year
  mine output.

**Decision:** Government statistics are a source like a company, with their own reading rules in
config. Estimate revisions are expected; revisions of reported figures are not.

**Next:** Unit tests and a GitHub check (CI). Then the web app (explorer, then questions with citations).

## 2026-10-03 — Day 13: v8, unit tests and a GitHub check

**Did:** Gave `extract_rows.py` and `self_checker.py` a `main()`, run only from the terminal, so tests
can load the functions without anything running (`find_page` takes the document name for its STOP
message). 54 pytest tests in `tests/`: text_cleaner (dollars, negatives, dashes, N/A, %, footnotes, dot
leaders, USGS codes, years not values); extract_rows (year runs incl. FY labels, oldest-first, dates,
quarter/year blocks; page numbers in every footer style seen; anchors with | and &&, STOP on two pages;
small sample pages: Neo quarter-first, header after rows, quarterly table, scale line, estimate flags);
self_checker (printed vs significant precision, dash = zero, estimate flag); config (known reading rules,
every map table exists, no line with two meanings, every metric has a range). GitHub Actions workflow
`.github/workflows/tests.yml` runs `pytest` on every push; badge in README. pytest added to requirements.

**Result:** 54 passed in 0.4 s. Refactor checked: all 26 outputs identical to v7; checker output identical
line for line (2,041 pass, 0 fail, 46 expected, 15 open).

**Found:** Mutation tests — re-introducing three real past bugs (N/A not a placeholder; day/month words not
skipped in dates; a duplicated map line) each fails exactly one named test.

**Decision:** Tests use real report lines as text, not PDFs, so CI needs nothing that is not in the repo.

**Next:** Web app: data explorer first, then questions answered with citations.

## 2026-10-03 — Day 13 (continued): v9, the website

**Did:** Owner chose to keep shipping and apply now (learning alongside; mock interview before the first
real interview), and chose a designed website over a Streamlit data tool (the Streamlit version was built
and parked). One page, `docs/index.html`, served by GitHub Pages from `docs/`: the hero is a real USGS line
as a computer reads it (`Australia 1216,000 1213,000 135,700,000`), whose glued footnote digits shrink back
into superscripts on load, with what it actually says underneath; then the traps (MP pairing-trap chart,
Neo revenue per tonne by segment, glued footnotes, revised estimates), MP against USGS, how it works, the
open questions, and every number browsable (search, filters, 25 rows then "show 100 more") and
downloadable. Colours from the salts of neodymium (lilac), praseodymium (green) and erbium (rose); Public
Sans for text, IBM Plex Mono only for lines quoted as printed. New `scripts/build_site.py` writes
`docs/data/` (numbers.json, site.json, rare_earth_intel.csv); the checker saves every check to
`data/interim/checks.csv`. `tests/test_site.py`: the data files agree with each other, no check failed,
every open/expected item has a reason, the page links its data and chart. MP-vs-USGS check lines now come
out in a fixed order (a sort without a tie order made them vary between runs).

**Result:** 58 tests pass. Checked in a headless browser at desktop and phone widths: no script errors,
all tables filled, search works, the hero line fits a phone screen, page length 9,000 px.

**Found:** A sort that does not keep ties in order made the report's line order change between runs.
Reviewing screenshots caught three design problems before release: footnotes that left gaps when they
lifted, a chart too narrow to read, and a 29,000 px page from showing 200 rows.

**Next:** Turn on GitHub Pages (Settings → Pages → main, /docs). Add the site to the CV.

## 2026-10-03 — Day 13 (continued): v10, the question box

**Did:** Added "Ask a question" to the website. A language model only turns a question into a lookup (who,
what, material, part, year); `worker/worker.js` (Cloudflare Worker, Workers AI free tier, no API key, no
card) accepts it only if every value exists in `docs/data/vocabulary.json` (new, written by build_site.py
from the data) and refuses everything else. The page finds the figures itself and shows each with its
document, page and printed text, the other places it is printed, and what was looked up. No arithmetic
anywhere. 20 test questions with known answers (5 must be refused: forecast, advice, a company, a metric
and a year not in the data) and `scripts/evaluate_chatbot.py`, which scores the deployed Worker and saves
the result for the website. `tests/test_chatbot.py`: the test set points only at things that exist; the
vocabulary matches the published numbers.

**Result:** 61 tests pass. Worker's checking logic tested with Node: an invented company, a metric, year or
element not in the data, and a reply that is a number instead of a lookup are all refused. Page tested in
a headless browser against a stand-in Worker: answers, refusal and outage message all render; no errors.
The real model's accuracy is measured after deployment.

**Decision:** Free Cloudflare Workers AI over Anthropic (cost), Gemini (unpublished free limits, would still
need a Worker for the key) and Chinese first-party APIs (perception in a China-sensitive industry; Chinese
open models can still run on Cloudflare). The model choice is a measurement: change one line, re-run the
20 questions.

**Next:** Owner creates the Cloudflare Worker, adds the AI binding, sets ASK_URL, runs the evaluation, pushes.

## 2026-10-03 — Day 13 (continued): v10 live, then v11, written answers

**Did:** v10 went live: lookup accuracy 19/20 on the test questions, 5/5 refusals (one false refusal:
Magnequench 2024 sales). Two go-live bugs: the Worker answered the browser's CORS preflight with a 204 that
had a body (invalid, so every browser question failed; the evaluation script and the stand-in browser test
never send a preflight), and a fix bundle's index.html overwrote the Worker address. Both fixed; a test now
checks the preflight reply. Owner found the answers underwhelming (a template, no context), so v11 adds
written answers: the page gathers facts by code (figures with document and page, trend over nearby years,
revisions between documents with estimate flags, explained or open checks from the new
docs/data/caveats.json), the model writes 2-4 sentences from those facts only, and a number guard in the
Worker rejects the text if any number in it is not in the facts. Cited figures show at once; the text
appears above them when verified; "How this answer was made" explains the three steps.

**Result:** 67 tests pass (6 new Worker tests via Node: guard accepts faithful text, rejects a calculated
percentage, an invented figure and a wrong figure; invented company refused; preflight 204 without a body).
Browser test with a stand-in Worker and the real guard: verified answer renders; an invented 37% is withheld.

**Found:** The guard caught a wrong number in my own stand-in text (2023 neodymium price typed as 74 from
memory; the data says 78). Limit stated honestly: the guard proves every number is from the data, not that
each is attached to the right year, so the cited figures stay under the text.

**Next:** Owner pastes the new worker.js into Cloudflare and deploys; check real write-ups on the live site.
